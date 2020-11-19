import requests
from requests.auth import HTTPBasicAuth
import re
import imaplib
import os
import time

from imapclient import IMAPClient
import quopri
import html2text

from config import *
from main import send_message, build_message


class TicketUpdateException(Exception):
    pass


def run():
    # connection = setup_connection()
    # msg_ids = get_new_msg_ids(connection)
    # msgs_data = get_data_for_msgs(connection, msg_ids)
    # pickle.dump(msgs_data, open('message-data.pickle', 'wb'))

    print("setting up the email client")
    client = setup_client()
    print("searching for new mail...")
    msg_ids = client.search('UNSEEN')
    print("\t{} new emails found: {}".format(len(msg_ids), msg_ids))
    print("getting full email data")
    msgs_data = client.fetch(msg_ids, ['BODY[TEXT]', 'ENVELOPE'])

    for msg_id in msg_ids:
        print("parsing message")
        ticket, body, sender, reply_all = parse_msg_data(msgs_data[msg_id])
        if ticket is None:
            print("sending rejection message")
            send_rejection(sender)
            continue
        print("updating ticket")
        try:
            update_ticket(ticket, body, sender, reply_all)
        except TicketUpdateException as e:
            print(e)
            continue
        print("ticket updated:")
        print("\tID: {}".format(ticket))
        print("\tBody: {}".format(body.partition('\n')[0][:100]))
        print("\tSender: {}".format(sender))
        print("\tPublic/Reply-all: {}".format(reply_all))


def setup_client():
    client = IMAPClient(IMAP_SERVER)
    client.login(os.environ['MAILBOT_ADDRESS'], os.environ['MAILBOT_PASSWORD'])
    client.select_folder('INBOX', readonly=False)
    return client

# MARK: Getting new messages


def setup_connection():
    connection = imaplib.IMAP4_SSL(IMAP_SERVER)
    try:
        rv, data = connection.login(os.environ['MAILBOT_ADDRESS'], os.environ['MAILBOT_PASSWORD'])
    except imaplib.IMAP4.error as e:
        print("Error: Login failed ", e)
        exit(1)
    connection.select('INBOX', readonly=True)
    return connection


def check_ok(rv, data):
    if rv != 'OK':
        print("Bad: ", rv, data)
        exit(1)


def get_new_msg_ids(connection):
    rv, data = connection.search(None, 'UNSEEN')
    check_ok(rv, data)
    return data[0].decode().split(' ')


def get_data_for_msgs(connection, msg_ids):
    # TODO implement whitelist
    rv, data = connection.fetch(','.join(msg_ids), '(UID BODY[TEXT])')
    check_ok(rv, data)
    return [d for d in data if d != b')']


# MARK: Handling messages


def parse_msg_data(msg_data):

    # get ticket id
    subject_pattern = re.compile(SUBJECT_PATTERN.format(
        '(?P<id>\d+)',  # ticket number
        '.*'           # original subject line
    ))
    subject = msg_data[b'ENVELOPE'].subject.decode()
    try:
        ticket = subject_pattern.search(subject).group('id')
    except:
        raise Exception('Malformed subject line "{}"'.format(subject))

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
        if os.environ['MAILBOT_CC_ADDRESS'] in ["{}@{}".format(cc.mailbox.decode(), cc.host.decode()) for cc in envelope.cc]:
            reply_all = True

    return ticket, response_body, sender, reply_all


def send_rejection(receiver):
    subject = "You have reached an automated mailbox"
    body = """Hi,

    You've reached the automated mailbox, used by the Internet Archive's Patron Services team. \
    If you were trying to reach an actual person, best to look elsewhere.

    Bye!
    """
    msg = build_message(receiver, subject, body, None)
    send_message(msg)


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
            print("Could not find plain or html text section.")
            exit(1)
        plain = html2text.HTML2Text().handle(html)

    return plain.split(DELIMITER)[0]


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
        "status": "open"
    }
}

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
        print(response.content)
        raise TicketUpdateException()


def post_ticket_update(ticket_id, payload):
    url_template = 'https://{subdomain}.zendesk.com/api/v2/tickets/{id}.json'
    response = requests.put(
        url_template.format(subdomain='archivesupport', id=ticket_id),
        auth=HTTPBasicAuth(
            os.environ['MAILBOT_AGENT_ACCOUNT'] + "/token",
            os.environ['ZENDESK_API_KEY']),
        json=payload
    )
    return response


if __name__ == '__main__':
    while True:
        run()
        time.sleep(10*60)
