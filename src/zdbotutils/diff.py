import difflib
import datetime

from tqdm import tqdm


def unmatched_msgs(msgs1, msgs2):
    return diff_pools(
        msgs1,
        msgs2,
        sort_key=lambda msg: msg[b'INTERNALDATE'],
        within_error=email_datetime_match,
        is_match=email_match
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
    ################
    import pudb
    # pudb.set_trace()
    ################
    aa = sorted(aa, key=sort_key)
    bb = sorted(bb, key=sort_key)
    i = 0
    i0 = 0
    j = 0
    j0 = 0
    b_matched = [False] * len(bb)
    a_unmatched = []

    for i, a in tqdm(enumerate(aa), desc="Matching messages..."):
        while not within_error(a, bb[j0]):
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


def email_datetime_match(msg1, msg2, margin=datetime.timedelta(days=1)):
    d1 = msg1[b'INTERNALDATE']
    d2 = msg2[b'INTERNALDATE']
    return d1 - d2 < margin and d2 - d1 < margin


def email_match(msg1, msg2):
    if not from_match(msg1, msg2):
        return False
    return text_match(msg1, msg2)


def text_match(msg1, msg2, threshold=0.97):
    matcher = difflib.SequenceMatcher(isjunk=lambda c: c in ' \n\r\t', autojunk=False)
    matcher.set_seqs(msg1[b'BODY[TEXT]'], msg2[b'BODY[TEXT]'])

    if matcher.real_quick_ratio() < threshold:
        return False
    if matcher.quick_ratio() < threshold:
        return False
    return matcher.ratio() > threshold


def from_match(msg1, msg2):
    from_1 = msg1[b'ENVELOPE'].from_[0]
    from_2 = msg2[b'ENVELOPE'].from_[0]
    return from_1.mailbox == from_2.mailbox and from_1.host == from_2.host
