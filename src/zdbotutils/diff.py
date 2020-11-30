import difflib
import datetime
import io

from tqdm import tqdm

from zdbotutils.custom_logging import logger


def unmatched_msgs(msgs1, msgs2):
    return diff_pools(
        msgs1,
        msgs2,
        sort_key=lambda msg: msg[b'INTERNALDATE'],
        within_error=email_datetime_match,
        is_match=zd_archive_email_match
    )


def diff_pools(aa, bb, sort_key, within_error, is_match):
    """
    :param aa: first pool of items
    :param bb: second pool of items
    :param sort: function for sorting items
    :param within_error: func whether items are within error margin w/respect to sort attr.
    :param is_match: func whether items are match
    :return:
    """
    aa = sorted(aa, key=sort_key)
    bb = sorted(bb, key=sort_key)
    i = 0
    i0 = 0
    j = 0
    j0 = 0
    b_matched = [False] * len(bb)
    a_unmatched = []

    # ################
    # import pudb
    # pudb.set_trace()
    # ################

    for i, a in tqdm(enumerate(aa), desc="Matching messages..."):
        logger.debug('on zd email {}/{}: {}'.format(i, len(bb), a[b'ENVELOPE'].subject))
        while not within_error(a, bb[j0]):
            if sort_key(a) < sort_key(bb[j0]):
                break
            j0 += 1

        j = j0
        while True:
            if j == len(bb):
                a_unmatched.append(a)
                break
            elif b_matched[j]:
                pass
            elif not within_error(a, bb[j]):
                a_unmatched.append(a)
                break
            elif is_match(a, bb[j]):
                b_matched[j] = True
                break
            j += 1

    b_unmatched = [b for x, b in enumerate(bb) if not b_matched[x]]
    return a_unmatched, b_unmatched


def email_datetime_match(msg1, msg2, margin=datetime.timedelta(minutes=1)):
    d1 = msg1[b'INTERNALDATE']
    d2 = msg2[b'INTERNALDATE']
    # logger.debug('time diff: {} | {} & {}'.format(d1 - d2, d2 - d1, margin))
    # logger.debug('time diff: {} | {}'.format(d1 - d2 < margin, d2 - d1 < margin))
    # logger.debug(msg1[b'ENVELOPE'].subject.decode())
    # logger.debug(msg2[b'ENVELOPE'].subject.decode())
    return d1 - d2 < margin and d2 - d1 < margin


def zd_archive_email_match(zd_msg, archive_msg):
    if not from_match(zd_msg, archive_msg):
        return False
    is_match = text_match(zd_msg, archive_msg)
    return is_match


def text_match(zd_msg, archive_msg, threshold=0.97):

    zd_body_buf = io.BytesIO(zd_msg[b'BODY[TEXT]'])
    while zd_body_buf.readline().strip() != b'': pass  # one blank line after headers
    while zd_body_buf.readline().strip() != b'': pass  # one blank line after ZD annotation
    zd_msg_body = zd_body_buf.read()

    archive_body_buf = io.BytesIO(archive_msg[b'BODY[TEXT]'])
    while archive_body_buf.readline().strip() != b'': pass  # one blank line after headers
    archive_msg_body = archive_body_buf.read()

    matcher = difflib.SequenceMatcher(isjunk=lambda c: c in b' \n\r\t', autojunk=False)
    matcher.set_seqs(zd_msg_body, archive_msg_body)

    ################
    import pudb
    pudb.set_trace()
    ################
    logger.debug("""MATCH?: 
        {}
        ********
        {}
        """.format(zd_msg_body, archive_msg_body))

    # TODO
    d1 = zd_msg[b'INTERNALDATE']
    d2 = archive_msg[b'INTERNALDATE']
    time_diff = d1 - d2

    if matcher.real_quick_ratio() < threshold:
        logger.debug('real quick: {}, time_diff: {}, {}'.format(matcher.real_quick_ratio(), time_diff, archive_msg[b'ENVELOPE'].subject))
        return False
    if matcher.quick_ratio() < threshold:
        logger.debug('quick: {}'.format(matcher.quick_ratio()))
        return False
    if matcher.ratio() > threshold:
        logger.debug("""MATCH FOUND {}: 
        {}
        ********
        {}
        """.format(matcher.ratio(), zd_msg_body, archive_msg_body))
        return True


def from_match(zd_msg, archive_msg):
    return True

    # archive_msg_from_address = archive_msg[b'ENVELOPE'].from_[0]
    # archive_from = '{}@{}'.format(
    #     archive_msg_from_address.mailbox, archive_msg_from_address.host
    # ).lower()
    #
    # return zd_from == archive_from
