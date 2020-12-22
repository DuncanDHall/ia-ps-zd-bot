"""

When sorting through the UNMATCHED_ARCHIVE folder, I use the following color markings:

Red - could not be found manually within Zendesk
Purple - found in suspended
Yellow - could not be found manually within Zendesk, but I think it's spam
Green - found manually in Zendesk, saving for fine-tuning of the matching algorithm
Uncolored - visually confirmed as spam

"""


import pickle
import time
import datetime
from dateutil import parser
import requests
from requests.auth import HTTPBasicAuth
from os import environ as env
import imaplib
from email.parser import BytesParser
from email import policy
import re

import html2text

from shared import diff
from shared.custom_logging import logger
from shared.config import *
from shared.mail import chunked


def get_zd_updates(start_time):
    url_template = 'https://archivesupport.zendesk.com/api/v2/incremental/ticket_events.json?start_time={}&include=comment_events'
    next_page = url_template.format(start_time)
    session = requests.session()

    ticket_events = []
    while True:
        logger.info('getting incremental ticket updates from Zendesk since {}'.format(start_time))
        response = session.get(
            next_page,
            auth=HTTPBasicAuth(env['ZENDESK_AGENT_ACCOUNT'] + "/token", env['ZENDESK_API_KEY'])
        )
        assert (response.status_code == 200), "{}: {}".format(response.status_code, response.content)
        data = response.json()
        ticket_events.extend(data['ticket_events'])

        if data['end_of_stream']:
            break
        next_page = data['next_page']
        start_time = data['end_time']

    logger.info('found {} zendesk updates'.format(len(ticket_events)))

    end_time = data['end_time']
    if end_time is None:
        end_time = start_time

    return end_time, ticket_events


def process_events(ticket_events):
    zendesk_comments = []  # [(timestamp, comment, ticket_id)...]

    for event in ticket_events:
        contents_found = 0  # TODO ditch this variable

        for child in event['child_events']:
            if child['event_type'].lower() == 'comment':
                contents_found += 1
                if contents_found > 1:
                    logger.error('found {} comment children in single event'.format(contents_found))
                zendesk_comments.append((event['timestamp'], child['body'], event['ticket_id']))

    logger.info('found {} zendesk comments'.format(len(zendesk_comments)))

    return zendesk_comments


def get_support_emails():
    logger.info('getting archive support emails')
    imap4 = imaplib.IMAP4_SSL(host=IMAP_SERVER, port=IMAP_PORT)
    imap4.login(env['DIFFBOT_ADDRESS'], env['DIFFBOT_PASSWORD'])
    imap4.select(FROM_ARCHIVE_ACCOUNTS_FOLDER)

    status, response = imap4.uid('search', None, 'ALL')
    if status != 'OK':
        logger.error('unable to search email server')
        exit(1)
    # response of the form: [b'1 2 3 4']
    if response[0] == b'':
        logger.info('no support emails to match against')
        return []

    msg_ids = response[0].decode().split(' ')
    logger.info('found {} support emails'.format(len(msg_ids)))
    responses = []
    for msg_ids_chunk in chunked(msg_ids, 1000):
        logger.debug('getting a message chunk')
        status, response = imap4.uid('fetch', ','.join(msg_ids_chunk), '(BODY[])')
        if status != 'OK':
            logger.error('unable to fetch from email server')
            exit(1)
        responses.extend(response)
    imap4.close()
    imap4.logout()

    return responses


def parse_emails_response(support_emails_response):
    # these configurations match what we get from zendesk
    html2text.config.IGNORE_TABLES = True
    html2text.config.IGNORE_IMAGES = False
    h = html2text.HTML2Text()
    h.body_width = 0
    h.ignore_links = True

    # patterns and formats
    id_pattern = re.compile(b".*UID (\d+) .*")
    time_str_format = '%a,  %d %b %Y %H:%M:%S %z (%Z)'

    # collect decorated messages [(timestamp, comment, id)...]
    support_decorated_comments = []
    logger.info('parsing archive support email data')
    for li in support_emails_response:

        # weird case – something isn't implemented properly in the libraries
        if li == b')':
            continue

        id_bytes, msg_bytes = li
        msg = BytesParser(policy=policy.default).parsebytes(msg_bytes)

        # get id
        msg_id = int(re.match(id_pattern, id_bytes.strip()).group(1))

        # get time stamp
        time_str = msg['Received'].split(';')[-1].strip()
        time_stamp = parser.parse(time_str).timestamp()

        # get message body
        raw = msg.get_body(preferencelist=('plain',))
        if raw is not None:
            try:
                body = raw.get_content()
            except LookupError as e:
                logger.error(e)
                continue
        else:
            raw = msg.get_body(preferencelist=('html',))
            if raw is None:
                logger.error('Found message with no plain or html body')
                continue
            try:
                html_content = raw.get_content()
            except LookupError as e:
                logger.error(e)
                continue
            body = h.handle(html_content)

        support_decorated_comments.append((time_stamp, body, msg_id))

    return support_decorated_comments


def cleanup(zd_matched, zd_unmatched, archive_matched, archive_unmatched, zd_still_fresh_filename, start_time):
    imap4 = imaplib.IMAP4_SSL(host=IMAP_SERVER, port=IMAP_PORT)
    imap4.login(env['DIFFBOT_ADDRESS'], env['DIFFBOT_PASSWORD'])
    imap4.select(FROM_ARCHIVE_ACCOUNTS_FOLDER)

    # move matched emails
    archive_matched_ids = [str(msg_id) for _, _, msg_id in archive_matched]
    logger.info('moving {} matched emails'.format(len(archive_matched_ids)))
    for msg_ids_chunk in chunked(archive_matched_ids, 1000):
        uids = ','.join(msg_ids_chunk)
        result, err = imap4.uid('COPY', uids, MATCHED_ARCHIVE_FOLDER)
        if result != 'OK':
            logger.error('unable to copy items')
        result, delete = imap4.uid('STORE', uids, '+FLAGS', '(\Deleted)')
        if result != 'OK':
            logger.error('unable to delete original versions')

    # deal with unmatched updates from Zendesk
    cutoff = datetime.datetime.now().timestamp() - MINUTES_GRACE_PERIOD * 60
    still_fresh = []
    old = []
    for triple in zd_unmatched:
        if triple[0] > cutoff:
            still_fresh.append(triple)
        else:
            old.append(triple)
    # save still fresh for later
    logger.info('saving {} zd ticket messages for the next round'.format(len(still_fresh)))
    pickle.dump((start_time, still_fresh), open(zd_still_fresh_filename, 'wb'))
    # log old unmatched ticket comments
    logger.info('logging {} old zd ticket messages that went unmatched'.format(len(old)))
    with open('zd_unmatched.log', 'a') as f:
        for t, c, t_id in old:
            f.write("""
Ticket #{}
Time: {}
Comment:
{}
""".format(t_id, str(datetime.datetime.fromtimestamp(t)), c))

    # move old emails to unmatched
    cutoff = datetime.datetime.now().timestamp() - MINUTES_GRACE_PERIOD * 60
    old_archive_unmatched_ids = [str(msg_id) for t, _, msg_id in archive_unmatched if t < cutoff]
    logger.info('moving {} old unmatched archive emails'.format(len(old_archive_unmatched_ids)))
    for msg_ids_chunk in chunked(old_archive_unmatched_ids, 1000):
        uids = ','.join(msg_ids_chunk)
        result, err = imap4.uid('COPY', uids, UNMATCHED_ARCHIVE_FOLDER)
        if result != 'OK':
            logger.error('unable to copy items')
        result, delete = imap4.uid('STORE', uids, '+FLAGS', '(\Deleted)')
        if result != 'OK':
            logger.error('unable to delete original versions')

    # we're done here
    imap4.expunge()
    imap4.close()
    imap4.logout()


def get_still_fresh_zd_triples(zd_still_fresh_filename):
    try:
        return pickle.load(open(zd_still_fresh_filename, 'rb'))
    except FileNotFoundError:
        return int(datetime.datetime.now().timestamp()), []


def run():

    USE_TZ = True  # makes datetime.now() not naive
    zd_still_fresh_filename = 'zd_still_fresh.pickle'
    start_time, still_fresh_zd_triples = get_still_fresh_zd_triples(zd_still_fresh_filename)

    while True:
        logger.info('START CYCLE')
        end_time, ticket_events = get_zd_updates(start_time)
        start_time = end_time
        zd_decorated_comments = process_events(ticket_events)
        zd_decorated_comments += still_fresh_zd_triples

        support_emails_response = get_support_emails()
        support_decorated_comments = parse_emails_response(support_emails_response)

        results = diff.match_msgs(zd_decorated_comments, support_decorated_comments)

        logger.info("zd_matched: {}/{}".format(len(results[0]), len(zd_decorated_comments)))
        logger.info("archive_matched: {}/{}".format(len(results[2]), len(support_decorated_comments)))

        cleanup(*results, zd_still_fresh_filename, start_time)

        logger.info('END CYCLE - sleeping for {} seconds'.format(DIFFBOT_LOOP_WAIT_PERIOD))
        time.sleep(DIFFBOT_LOOP_WAIT_PERIOD)


if __name__ == '__main__':
    run()
