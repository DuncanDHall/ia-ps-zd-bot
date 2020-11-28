import pickle

from zdbotutils import diff, mail
from zdbotutils.custom_logging import logger

from config import FROM_ZENDESK_FOLDER, FROM_ARCHIVE_ACCOUNTS_FOLDER, \
    UNMATCHED_ZENDESK_FOLDER, UNMATCHED_ARCHIVE_FOLDER


def run():
    # mail.change_folder([4, 5], folders[1], folders[2])
    data = mail.get_msgs([FROM_ZENDESK_FOLDER, FROM_ARCHIVE_ACCOUNTS_FOLDER])
    pickle.dump(data, open('maildata.pickle', 'wb'))
    # data = pickle.load(open('maildata.pickle', 'rb'))
    # zendesk_msgs = data[FROM_ZENDESK_FOLDER].values()
    # support_msgs = data[FROM_ARCHIVE_ACCOUNTS_FOLDER].values()
    # logger.debug('beginning matching process with {} zd and {} support msgs'.format(len(zendesk_msgs), len(support_msgs)))
    # zendesk_unmatched, support_unmatched = diff.unmatched_msgs(zendesk_msgs, support_msgs)
    # print("Unmatched from Zendesk: {}".format(len(zendesk_unmatched)))
    # print("Unmatched from Support: {}".format(len(support_unmatched)))
    #
    # pickle.dump((zendesk_unmatched, support_unmatched), open('temp.pickle', 'wb'))

    # mail.change_folder(zendesk_unmatched, FROM_ZENDESK_FOLDER, UNMATCHED_ZENDESK_FOLDER)
    # mail.change_folder(support_unmatched, FROM_ARCHIVE_ACCOUNTS_FOLDER, UNMATCHED_ARCHIVE_FOLDER)


if __name__ == '__main__':
    run()
