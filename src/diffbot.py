import datetime
import pickle
import time

from zdbotutils import diff, mail
from zdbotutils.custom_logging import logger, logging

from config import *


def run():
    # Get New Messages
    folders = [FROM_ZENDESK_FOLDER, FROM_ARCHIVE_ACCOUNTS_FOLDER]
    logger.info('getting mail from folders {}'.format(folders))
    data = mail.get_msgs(folders)
    pickle.dump(data, open('maildata.pickle', 'wb'))

    # Get Raw Messages from Zendesk
    data = pickle.load(open('maildata.pickle', 'rb'))
    zendesk_msgs = data[FROM_ZENDESK_FOLDER]
    # import random
    # zendesk_msgs = {k: v for k, v in zendesk_msgs.items() if random.random() < 0.002}
    logger.info('fetching raw emails for {} zd emails'.format(len(zendesk_msgs)))
    diff.hotswap_zd_msgs(zendesk_msgs)
    pickle.dump(zendesk_msgs, open('raw_zd.pickle', 'wb'))

    # Compare
    data = pickle.load(open('maildata.pickle', 'rb'))
    support_msgs = data[FROM_ARCHIVE_ACCOUNTS_FOLDER]
    zendesk_msgs = pickle.load(open('raw_zd.pickle', 'rb'))
    logger.info('beginning matching process with {} zd and {} support msgs'.format(
        len(zendesk_msgs), len(support_msgs)
    ))
    zendesk_matched, zendesk_unmatched, support_matched, support_unmatched = diff.match_msgs(
        zendesk_msgs, support_msgs)
    pickle.dump((zendesk_matched, zendesk_unmatched, support_matched, support_unmatched), open('matches.pickle', 'wb'))
    logger.info('match results: {}/{} Zendesk and {}/{} Support emails'.format(
        len(zendesk_matched), len(zendesk_msgs), len(support_matched), len(support_msgs)
    ))

    # Move Matches
    zendesk_matched, zendesk_unmatched, support_matched, support_unmatched = pickle.load(open('matches.pickle', 'rb'))
    logger.info('moving {} zd and {} support messages to matched folders'.format(
        len(zendesk_matched), len(support_matched)
    ))
    mail.change_folder(zendesk_matched.keys(), FROM_ZENDESK_FOLDER, MATCHED_ZENDESK_FOLDER)
    mail.change_folder(support_matched.keys(), FROM_ARCHIVE_ACCOUNTS_FOLDER, MATCHED_ARCHIVE_FOLDER)

    # Move Old Unmatched
    cutoff = datetime.datetime.now() - datetime.timedelta(minutes=MINUTES_GRACE_PERIOD)
    old_zendesk_msg_ids = diff.get_old_ids(zendesk_unmatched, cutoff)
    old_support_msg_ids = diff.get_old_ids(support_unmatched, cutoff)
    logger.info('removing {} zd and {} support unmatched messages from before {} ({} minutes old)'.format(
        len(old_zendesk_msg_ids), len(old_support_msg_ids), cutoff, MINUTES_GRACE_PERIOD
    ))
    mail.change_folder(old_zendesk_msg_ids, FROM_ZENDESK_FOLDER, UNMATCHED_ZENDESK_FOLDER)
    mail.change_folder(old_support_msg_ids, FROM_ARCHIVE_ACCOUNTS_FOLDER, UNMATCHED_ARCHIVE_FOLDER)


if __name__ == '__main__':
    for name in logging.root.manager.loggerDict:
        logging.getLogger(name).setLevel(logging.WARNING)

    while True:
        logger.info('STARTING CYCLE')
        run()
        logger.info('ENDING CYCLE, will resume in {} seconds...'.format(DIFFBOT_LOOP_WAIT_PERIOD))
        time.sleep(DIFFBOT_LOOP_WAIT_PERIOD)
