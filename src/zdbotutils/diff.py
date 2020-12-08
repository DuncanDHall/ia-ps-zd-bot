import datetime
import difflib
import io
import re
import multiprocessing
import time
import threading
import concurrent.futures

import diff_match_patch as dmp_module

from zdbotutils import apiservice
from zdbotutils.custom_logging import logger

from config import *


def match_msgs(zd_msgs, archive_msgs):
    return diff_pools(
        zd_msgs,
        archive_msgs,
        # sort_key=lambda kv_pair: kv_pair[1][b'ENVELOPE'].date,
        sort_key=lambda kv_pair: kv_pair[1][b'INTERNALDATE'],
        within_error=email_datetime_match,
        is_match=zd_archive_email_match
    )


def diff_pools(dict1, dict2, sort_key, within_error, is_match):
    """
    :param dict1: first pool of items
    :param dict2: second pool of items
    :param sort_key: function for sorting items
    :param within_error: func whether items are within error margin w/respect to sort attr.
    :param is_match: func whether items are match
    :return: four tuple: matched/unmatched from dict1/dict2
    """

    # decorate and sort
    aa = sorted(dict1.items(), key=sort_key)
    bb = sorted(dict2.items(), key=sort_key)

    j0 = 0  # the 'lower bound' index in bb for matching

    a_matched = {}
    a_unmatched = {}
    b_matched = {}
    b_unmatched = {}

    for i, kv_pair in enumerate(aa):
        logger.info('Searching for match for item {}/{}'.format(i, len(aa)))
        ka, a = kv_pair

        # move the lower bound up
        while j0 < len(bb):
            # once we are within error, stop increasing
            if within_error(a, bb[j0][1]):
                break
            # if we get beyond our aa item, stop increasing
            if sort_key(kv_pair) < sort_key(bb[j0]):
                break
            # any unmatched bb items at j0 at this point are unmatched
            if not bb[j0][0] in b_matched:
                b_unmatched[bb[j0][0]] = bb[j0][1]
            j0 += 1

        j = j0
        while True:
            # don't run off the end of bb
            if j == len(bb):
                a_unmatched[ka] = a
                break
            # skip bb items already matched
            elif bb[j][0] in b_matched:
                pass
            # if bb item is beyond error, then no match for aa item
            elif not within_error(a, bb[j][1]):
                a_unmatched[ka] = a
                break
            # we got a match
            elif is_match(a, bb[j][1]):
                a_matched[ka] = a
                b_matched[bb[j][0]] = bb[j][1]
                break
            # try the next item in bb
            j += 1

    return a_matched, a_unmatched, b_matched, b_unmatched


def email_datetime_match(msg1, msg2, margin=datetime.timedelta(minutes=MINUTES_TIME_MATCH_ERROR)):
    d1 = msg1[b'INTERNALDATE']
    d2 = msg2[b'INTERNALDATE']
    verdict = d1 - d2 < margin and d2 - d1 < margin
    logger.debug('comparing {} and {}, {}within {} margin'.format(
        d1, d2, '' if verdict else 'not ', margin
    ))
    return verdict


def zd_archive_email_match(zd_msg, archive_msg):
    is_match = text_match(zd_msg, archive_msg)
    return is_match


def text_match(zd_msg, archive_msg, threshold=0.90):
    zd_subject = zd_msg[b'ENVELOPE'].subject
    if zd_subject is None:
        logger.warning('found message from zendesk with no subject')
    zd_subject = '' if zd_subject is None else zd_subject.decode()
    archive_subject = archive_msg[b'ENVELOPE'].subject
    if archive_subject is None:
        logger.warning('found message from archive with no subject')
    archive_subject = '' if archive_subject is None else archive_subject.decode()
    try:
        zd_text = zd_msg[b'BODY[TEXT]'].decode()
        archive_text = archive_msg[b'BODY[TEXT]'].decode()
    except:
        logger.error('found msg with no body. subject: "{}" or "{}"'.format(zd_subject, archive_subject))
        return False

    # Cut the shit
    if zd_text == archive_text:
        logger.info('COMPLETE MATCH')
        return True

    # Preliminary check
    matcher = difflib.SequenceMatcher(isjunk=lambda c: c in ' \n\r\t')
    matcher.set_seqs(zd_text, archive_text)
    qr = matcher.quick_ratio()
    if qr < threshold:
        logger.debug('quick ratio: {} – "{}" and "{}" don\'t match'.format(
            qr, zd_subject, archive_subject
        ))
        return False

    # Full check
    dmp = dmp_module.diff_match_patch()
    dmp.Diff_Timeout = 0.2
    diff = dmp.diff_main(zd_text, archive_text)
    d = dmp.diff_levenshtein(diff)
    ratio = 1 - d / max(len(zd_text), len(archive_text))
    verdict = ratio > threshold
    if verdict:
        logger.info('full ratio: {} – "{}" and "{}" FULL MATCH'.format(
            round(ratio, 4), zd_subject, archive_subject
        ))
    else:
        logger.debug('full ratio: {} – "{}" and "{}" no match'.format(
            round(ratio, 4), zd_subject, archive_subject
        ))
    return verdict


def hotswap_zd_msgs(zendesk_msgs):
    started_at = time.monotonic()

    pattern = re.compile(b'.*ZD(\d+):.*')
    msg_ids = list(zendesk_msgs.keys())
    ticket_ids = []
    for msg_id in msg_ids:
        try:
            bin_subject = zendesk_msgs[msg_id][b'ENVELOPE'].subject
            subject_match = pattern.match(bin_subject)
            if subject_match is None:
                raise Exception('invalid subject line "{}"'.format(bin_subject.decode()))
            ticket_ids.append(int(subject_match.group(1).decode()))
        except Exception as e:
            ticket_ids.append(None)
            logger.error('bad subject line {}'.format(e))

    first_audit_ids = apiservice.concurrent_get_first_comments(ticket_ids)
    raw_emails = apiservice.concurrent_get_raw_emails(ticket_ids, first_audit_ids)

    for msg_id, raw in zip(msg_ids, raw_emails):
        zendesk_msgs[msg_id][b'BODY[TEXT]'] = raw if raw is not None else b''

    logger.debug('completed hotswap in {} seconds'.format(round(time.monotonic() - started_at, 2)))


def get_old_ids(msgs, cutoff):
    old = []
    for msg_id, msg in msgs.items():
        date = msg[b'ENVELOPE'].date
        if date is None:
            date = msg[b'INTERNALDATE']
        if date is None:
            logger.error('message found with not internal date')
        if date < cutoff:
            old.append(msg_id)
    return old