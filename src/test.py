import random

from zdbotutils import diff


def second_match(a, b):
    return abs(a - b) < 30

def is_match(a, b):
    return a == b

a = [(random.randint(100, 200), random.randint(0, 4), 'part of A') for _ in range(100)]
b = [(random.randint(100, 200), random.randint(0, 4), 'part of b') for _ in range(100)]

import pudb
pudb.set_trace()

res = diff.matching(
    a, b,
    lambda x: x[0],
    second_match,
    is_match
)

a_m, a_un, b_m, b_un = res

print('matched {}/{} for `a`'.format(len(a_m), len(a)))
print('matched {}/{} for `b`'.format(len(b_m), len(b)))
print('if these numbers don\'t match, why?')
