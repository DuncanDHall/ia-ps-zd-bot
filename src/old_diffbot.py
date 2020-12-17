import datetime
import pickle
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

from zdbotutils import diff, mail
from zdbotutils.custom_logging import logger, logging
from config import *
from zdbotutils.mail import chunked


def epoch_time(d):
    return int((d - datetime.datetime(1970, 1, 1)).total_seconds())


def run():

    #######################################################
    # get updates in Zendesk (including suspended)
    # TODO this vvv
    since = None
    if since:
        start_time = since
    else:
        start_time = epoch_time(datetime.datetime.now()) - 60 * 60 * 2  # 2 hours ago
        start_time = 1607984459

    url_template = 'https://archivesupport.zendesk.com/api/v2/incremental/ticket_events.json?start_time={}&include=comment_events'
    session = requests.session()
    logger.info('getting incremental ticket updates from Zendesk since {}'.format(start_time))
    response = session.get(
        url_template.format(start_time),
        auth=HTTPBasicAuth(env['ZENDESK_AGENT_ACCOUNT'] + "/token", env['ZENDESK_API_KEY'])
    )
    assert(response.status_code == 200), "{}: {}".format(response.status_code, response.content)

    zendesk_comments = []  # [(timestamp, comment, ticket_id)...]
    for event in response.json()['ticket_events']:
        contents_found = 0  # TODO ditch this variable
        for child in event['child_events']:
            if child['event_type'].lower() == 'comment':
                contents_found += 1
                if contents_found > 1:
                    logger.error('found {} content children in single event'.format(contents_found))
                zendesk_comments.append((event['timestamp'], child['body'], event['ticket_id']))


    pickle.dump(zendesk_comments, open('zendesk_comments.pickle', 'wb'))


    ######################################################
    # get emails from support addresses
    logger.info('getting archive support emails')
    server = imaplib.IMAP4_SSL(host=IMAP_SERVER, port=IMAP_PORT)
    server.login(env['DIFFBOT_ADDRESS'], env['DIFFBOT_PASSWORD'])
    server.select(FROM_ARCHIVE_ACCOUNTS_FOLDER)
    # TODO status, response = server.search(None, 'ALL')
    # status, response = server.search(None, 'SINCE', '14-Dec-2020')
    status, response = server.search(None, 'ALL')
    if status != 'OK':
        print('crap')
        exit(1)
    # response of the form: [b'1 2 3 4']
    if response[0] == b'':
        # TODO handle no emails to match against
        logger.error('no support emails to match against')
    msg_ids = response[0].decode().split(' ')
    logger.info('found {} support emails'.format(len(msg_ids)))
    responses = []
    for msg_ids_chunk in chunked(msg_ids, 1000):
        logger.debug('getting a message chunk')
        status, response = server.fetch(','.join(msg_ids_chunk), '(BODY[])')
        if status != 'OK':
            print('crap')
            exit(1)
        responses.extend(response)
    server.logout()
    pickle.dump(responses, open('responses.pickle', 'wb'))


    responses = pickle.load(open('responses.pickle', 'rb'))

    # these configurations match what we get from zendesk
    html2text.config.IGNORE_TABLES = True
    html2text.config.IGNORE_IMAGES = False
    h = html2text.HTML2Text()
    h.ignore_links = True

    # collect decorated messages [(timestamp, comment, id)...]
    support_msgs = []

    # patterns and formats
    # id_pattern = re.compile(b"(\d+) \(BODY\[\] \{\d+\}")
    id_pattern = re.compile(b"(\d+).+")
    time_str_format = '%a,  %d %b %Y %H:%M:%S %z (%Z)'

    logger.info('parsing archive support email data')
    for li in responses:

        # weird case – something isn't implemented properly in the libraries
        if li == b')':
            continue

        id_bytes, msg_bytes = li
        msg = BytesParser(policy=policy.default).parsebytes(msg_bytes)

        # get id
        msg_id = int(re.match(id_pattern, id_bytes.strip()).group(1))
        logger.debug(id_bytes)
        logger.debug(msg_id)

        # get time stamp
        time_str = msg['Received'].split(';')[-1].strip()
        time_stamp = epoch_time(parser.parse(time_str))

        # get message body
        raw = msg.get_body(preferencelist=('plain',))
        if raw is None:
            raw = msg.get_body(preferencelist=('html',))
            if raw is None:
                logger.error('Found message with no plain or html body')
                continue
        body = h.handle(raw.get_content())

        support_msgs.append((time_stamp, body, msg_id))


    print(len(support_msgs))


    pickle.dump(support_msgs, open('support_msgs.pickle', 'wb'))



    #######################################################
    zendesk_comments = pickle.load(open("zendesk_comments.pickle", "rb"))
    support_msgs = pickle.load(open("support_msgs.pickle", "rb"))
    print(len(support_msgs))
    # match
    logger.info('comment matching... (this could take a while)')
    results = diff.match_msgs(zendesk_comments, support_msgs)
    pickle.dump(results, open('results.pickle', 'wb'))


    results = pickle.load(open('results.pickle', 'rb'))
    zd_matched, zd_unmatched, archive_matched, archive_unmatched = results
    with open('inspect.txt', 'w') as f:
        f.write('\nZD MATCHED\n')
        f.write(str(zd_matched))
        f.write('\nZD UNMATCHED\n')
        f.write(str(zd_unmatched))
        f.write('\nARCHIVE MATCHED\n')
        f.write(str(archive_matched))
        f.write('\nARCHIVE UNMATCHED\n')
        f.write(str(archive_unmatched))
    print("zd_matched: {}".format(len(zd_matched)))
    print("zd_unmatched: {}".format(len(zd_unmatched)))
    print("archive_matched: {}".format(len(archive_matched)))
    print("archive_unmatched: {}".format(len(archive_unmatched)))

    # #######################################################
    # # move matched emails
    # server = imaplib.IMAP4_SSL(host=IMAP_SERVER, port=IMAP_PORT)
    # server.login(env['DIFFBOT_ADDRESS'], env['DIFFBOT_PASSWORD'])
    # server.select(FROM_ARCHIVE_ACCOUNTS_FOLDER)
    # archive_matched_ids = [str(msg_id) for _, _, msg_id in archive_matched]
    # logger.info('moving {} matched emails'.format(len(archive_matched_ids)))
    # for msg_ids_chunk in chunked(archive_matched_ids, 1000):
    #     ids = ','.join(msg_ids_chunk[:10])
    #     logger.debug(ids)
    #     server.copy(ids, MATCHED_ARCHIVE_FOLDER)

#     #######################################################
#     # log old unmatched ticket comments
#     cutoff = time.time() - MINUTES_GRACE_PERIOD * 60
#     old_zd_unmatched = {(t, c, ticket_id) for t, c, ticket_id in zd_unmatched if t < cutoff}
#     logger.info('logging {} old unmatched zendesk comments'.format(len(old_zd_unmatched)))
#     with open('zd_unmatched_log.txt', 'w') as f:
#         for t, c, t_id in old_zd_unmatched:
#             f.write("""
# Ticket #{}
# Time: {}
# Comment:
#     {}
#             """.format(t_id, str(datetime.datetime.fromtimestamp(t)), c))
#
#     #######################################################
#     # store non-old unmatched ticket comments
#     non_old_zd_unmatched = zd_unmatched.difference(old_zd_unmatched)
#     logger.info('saving {} unmatched zendesk comments for later'.format(len(non_old_zd_unmatched)))
#     pickle.dump(non_old_zd_unmatched, open('zd_unmatched_temp.pickle', 'wb'))
#
    #######################################################
    # move old emails to unmatched
    # cutoff = time.time() - MINUTES_GRACE_PERIOD * 60
    # old_archive_unmatched_ids = [msg_id for t, _, msg_id in archive_matched if t < cutoff]
    # logger.info('moving {} old unmatched archive emails'.format(len(old_archive_unmatched_ids)))
    # for msg_ids_chunk in chunked(old_archive_unmatched_ids, 1000):
    #     server.copy(msg_ids_chunk, UNMATCHED_ARCHIVE_FOLDER)

    # server.logout()

    # # Get New Messages
    # folders = [FROM_ZENDESK_FOLDER, FROM_ARCHIVE_ACCOUNTS_FOLDER]
    # logger.info('getting mail from folders {}'.format(folders))
    # data = mail.get_msgs(folders)
    # pickle.dump(data, open('maildata.pickle', 'wb'))
    #
    # # Get Raw Messages from Zendesk
    # data = pickle.load(open('maildata.pickle', 'rb'))
    # zendesk_msgs = data[FROM_ZENDESK_FOLDER]
    # # import random
    # # zendesk_msgs = {k: v for k, v in zendesk_msgs.items() if random.random() < 0.002}
    # logger.info('fetching raw emails for {} zd emails'.format(len(zendesk_msgs)))
    # diff.hotswap_zd_msgs(zendesk_msgs)
    # pickle.dump(zendesk_msgs, open('raw_zd.pickle', 'wb'))
    #
    # # Compare
    # data = pickle.load(open('maildata.pickle', 'rb'))
    # support_msgs = data[FROM_ARCHIVE_ACCOUNTS_FOLDER]
    # zendesk_msgs = pickle.load(open('raw_zd.pickle', 'rb'))
    # logger.info('beginning matching process with {} zd and {} support msgs'.format(
    #     len(zendesk_msgs), len(support_msgs)
    # ))
    # zendesk_matched, zendesk_unmatched, support_matched, support_unmatched = diff.og_match_msgs(
    #     zendesk_msgs, support_msgs)
    # pickle.dump((zendesk_matched, zendesk_unmatched, support_matched, support_unmatched), open('matches.pickle', 'wb'))
    # logger.info('match results: {}/{} Zendesk and {}/{} Support emails'.format(
    #     len(zendesk_matched), len(zendesk_msgs), len(support_matched), len(support_msgs)
    # ))
    #
    # # Move Matches
    # zendesk_matched, zendesk_unmatched, support_matched, support_unmatched = pickle.load(open('matches.pickle', 'rb'))
    # logger.info('moving {} zd and {} support messages to matched folders'.format(
    #     len(zendesk_matched), len(support_matched)
    # ))
    # mail.change_folder(zendesk_matched.keys(), FROM_ZENDESK_FOLDER, MATCHED_ZENDESK_FOLDER)
    # mail.change_folder(support_matched.keys(), FROM_ARCHIVE_ACCOUNTS_FOLDER, MATCHED_ARCHIVE_FOLDER)
    #
    # # Move Old Unmatched
    # cutoff = datetime.datetime.now() - datetime.timedelta(minutes=MINUTES_GRACE_PERIOD)
    # old_zendesk_msg_ids = diff.get_old_ids(zendesk_unmatched, cutoff)
    # old_support_msg_ids = diff.get_old_ids(support_unmatched, cutoff)
    # logger.info('removing {} zd and {} support unmatched messages from before {} ({} minutes old)'.format(
    #     len(old_zendesk_msg_ids), len(old_support_msg_ids), cutoff, MINUTES_GRACE_PERIOD
    # ))
    # mail.change_folder(old_zendesk_msg_ids, FROM_ZENDESK_FOLDER, UNMATCHED_ZENDESK_FOLDER)
    # mail.change_folder(old_support_msg_ids, FROM_ARCHIVE_ACCOUNTS_FOLDER, UNMATCHED_ARCHIVE_FOLDER)


if __name__ == '__main__':
    for name in logging.root.manager.loggerDict:
        logging.getLogger(name).setLevel(logging.WARNING)

    while True:
        logger.info('STARTING CYCLE')
        run()
        break
        logger.info('ENDING CYCLE, will resume in {} seconds...'.format(DIFFBOT_LOOP_WAIT_PERIOD))
        time.sleep(DIFFBOT_LOOP_WAIT_PERIOD)
