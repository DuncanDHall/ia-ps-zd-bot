import requests
from requests.auth import HTTPBasicAuth
import re
from os import environ as env
import time

import quopri
import html2text

from config import *
from zdbotutils.custom_logging import logger
from zdbotutils import mail


class TicketUpdateException(Exception):
    pass


def run():
    # connection = setup_connection()
    # msg_ids = get_new_msg_ids(connection)
    # msgs_data = get_data_for_msgs(connection, msg_ids)
    # pickle.dump(msgs_data, open('message-data.pickle', 'wb'))

    msgs_data = mail.get_raw_mail()

    for msg_id in msgs_data.keys():
        logger.info("parsing message")
        ticket, body, sender, reply_all = parse_msg_data(msgs_data[msg_id])
        if ticket is None:
            logger.info("sending rejection message")
            send_rejection(sender[1])
            continue
        logger.info("updating ticket")
        try:
            update_ticket(ticket, body, sender, reply_all)
        except TicketUpdateException as e:
            logger.error(e)
            continue
        logger.info("ticket updated – ID: {}, Body: {}, Sender: {}, Public: {}".format(
            ticket, body.partition('\n')[0][:100], sender, reply_all))


# MARK: Handling messages

def parse_msg_data(msg_data):

    # get ticket id
    subject_pattern = re.compile(SUBJECT_PATTERN.format(
        '(?P<id>\d+)',  # ticket number
        '.*'           # original subject line
    ))
    subject = msg_data[b'ENVELOPE'].subject.decode()
    match = subject_pattern.search(subject)
    if match is None:
        logger.error('Received mail with invalid subject line: "{}"'.format(subject))
        ticket = None
    else:
        ticket = match.group('id')

    # get body
    response_body = get_plain_response_body(msg_data[b'BODY[TEXT]'])

    # get sender
    envelope = msg_data[b'ENVELOPE']
    if len(envelope.from_) == 1:
        address = envelope.from_[0]
    elif len(envelope.reply_to) == 1:
        address = envelope.reply_to[0]
    else:
        address = envelope.sender[0]
    # ("John Smith", "jsmith@example.com")
    sender = (address.name.decode(), "{}@{}".format(address.mailbox.decode(), address.host.decode()))

    # get public flag
    reply_all = False
    if envelope.cc is not None:
        if env['MAILBOT_CC_ADDRESS'] in ["{}@{}".format(cc.mailbox.decode(), cc.host.decode()) for cc in envelope.cc]:
            reply_all = True

    return ticket, response_body, sender, reply_all


def send_rejection(receiver):
    subject = "You have reached an automated mailbox"
    body = """Hi,

    You've reached the automated mailbox, used by the Internet Archive's Patron Services team. \
    
    You are receiving this because you sent an email with incorrectly formatted subject line to \
    this address. If you are replying to an automated email from this address, please leave the \
    subject line intact.

    Thanks!
    """
    mail.send_mail(
        sender='{} <{}>'.format(MAILBOT_NAME, env['MAILBOT_ADDRESS']),
        receiver=receiver,
        subject=subject,
        body=body,
    )


def get_plain_response_body(raw_body):
    plain = None
    html = None
    for content_type, part_body in part_gen(raw_body, content_types=['text/html', 'text/plain']):
        if content_type == 'text/html' and html is None:
            html = part_body
        if content_type == 'text/plain' and plain is None:
            plain = part_body
            break
    if plain is None:
        if html is None:
            logger.error("could not find plain or html text section: {}".format(raw_body))
            exit(1)
        plain = html2text.HTML2Text().handle(html)

    prelim_lines = plain.split(DELIMITER)[0].split('\n')
    if prelim_lines[-1].find(MAILBOT_NAME) != -1:
        body = '\n'.join(prelim_lines[:-1])
    else:
        body = '\n'.join(prelim_lines)

    return body.strip()


def part_gen(raw_body, content_types=None):
    content_types = [t.lower() for t in content_types]
    email_part_pattern = re.compile(b'(?:--.+?\n(?:Content-Transfer-Encoding:(?P<encoding>.*?);?\n|Content-Type:(?P<type>.*?);?\n|.+?\n)+)\n(?P<part_body>(?:.*\n)+?)(?=--)')

    matches_count = 0
    for match in email_part_pattern.finditer(raw_body):
        matches_count += 1

        # check that it's a desired content types
        content_type = match.group('type').strip().lower()
        if content_types is not None:
            if content_type not in content_types:
                continue

        part_body = match.group('part_body')

        # check for quoted-printable encoding
        encoding = match.group('encoding').strip().lower()
        if encoding == 'quoted-printable':
            part_body = quopri.decodestring(part_body).decode()

        yield content_type, part_body

    if matches_count == 0:
        yield 'text/html', quopri.decodestring(raw_body).decode()


# MARK: Update the ticket

payload_template_dict = {
    "ticket": {
        "comment": {
            "body": "{body}",
            "public": False,
            "via": {
                "channel": "mailbot"
            }
        },
        "status": "open",
        "additional_tags": ["_automated_update_"]
    }
}
# payload_template_dict = {
#     "ticket": {
#         "comment": {
#             "body": "{body}",
#             "public": False,
#             "via": {
#                 "channel": "mailbot"
#             }
#         },
#         "status": "open"
#     }
# }

comment_template = """{body}
– {signed}
"""


def update_ticket(ticket_id, body, sender, public=True):
    signed = sender[0] if public else "{} <{}>".format(*sender)
    comment = comment_template.format(body=body, signed=signed)
    payload = payload_template_dict
    payload['ticket']['comment']['body'] = comment
    payload['ticket']['comment']['public'] = public
    response = post_ticket_update(ticket_id, payload)
    if response.status_code != 200:
        logger.info('ZD API: ' + response.content)
        raise TicketUpdateException()


def post_ticket_update(ticket_id, payload):
    url_template = 'https://{subdomain}.zendesk.com/api/v2/tickets/update_many.json?ids={id}'
    response = requests.put(
        url_template.format(subdomain='archivesupport', id=ticket_id),
        auth=HTTPBasicAuth(
            env['ZENDESK_AGENT_ACCOUNT'] + "/token",
            env['ZENDESK_API_KEY']),
        json=payload
    )
    return response


if __name__ == '__main__':
    while True:
        run()
        time.sleep(60)
