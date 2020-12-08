import requests
import re
from requests.auth import HTTPBasicAuth
from os import environ as env
import time
from threading import Lock
import io

from requests_futures.sessions import FuturesSession

from zdbotutils.custom_logging import logger
from zdbotutils.mail import chunked
from config import *


def concurrent_get_first_comments(ticket_ids):
    session = FuturesSession()

    url_template = 'https://archivesupport.zendesk.com/api/v2/tickets/{}/audits.json'
    audit_ids = []

    for ticket_ids_chunk in chunked(ticket_ids, 1000):
        audit_futures = []
        for i, ticket_id in enumerate(ticket_ids_chunk):
            if ticket_id is None:
                audit_futures.append(None)
                continue
            logger.debug('getting audit future for ticket {}/{}'.format(i, len(ticket_ids_chunk)))
            audit_futures.append(session.get(
                url_template.format(ticket_id),
                auth=HTTPBasicAuth(env['ZENDESK_AGENT_ACCOUNT'] + "/token", env['ZENDESK_API_KEY'])
            ))
            time.sleep(60 / ZENDESK_API_RATE_LIMIT)

        for i, af in enumerate(audit_futures):
            if af is None:
                audit_ids.append(None)
                continue
            result = af.result()
            if result.status_code != 200:
                logger.error('ticket #{} bad status code {}: {}'.format(ticket_ids_chunk[1], result.status_code, result.content))
                audit_ids.append(None)
                continue
            try:
                audit_ids.append(result.json()['audits'][0]['id'])
            except Exception as e:
                logger.error('while parsing result for #{} {}'.format(ticket_ids_chunk[i], e))
                audit_ids.append(None)

    return audit_ids


def get_logged_in_sesh():
    sesh = requests.Session()

    # get a fresh authenticity token
    response = sesh.get('https://archivesupport.zendesk.com/auth/v2/login/signin')
    auth_token_pattern = re.compile(b'<input[^<^>]*?name="authenticity_token"[^<^>]*?value="(.*?)".*?/>')
    m = auth_token_pattern.search(response.content)
    auth_token = m.group(1).decode()

    login_form_data = {
        'utf8': '✓',
        'authenticity_token': auth_token,
        'return_to_on_failure': '/auth/v2/login/signin',
        'return_to': 'https://help.archive.org/auth/v2/login/signed_in',
        'brand_id': '360000261412',
        'form_origin': 'no_return',
        'user[email]': env['ZENDESK_AGENT_ACCOUNT'],
        'user[password]': env['ZENDESK_AGENT_PASSWORD']
    }
    sesh.post('https://archivesupport.zendesk.com/access/login', data=login_form_data)
    return sesh


def get_logged_in_future_sesh():
    sesh = FuturesSession()

    # get a fresh authenticity token
    response = sesh.get('https://archivesupport.zendesk.com/auth/v2/login/signin').result()
    auth_token_pattern = re.compile(b'<input[^<^>]*?name="authenticity_token"[^<^>]*?value="(.*?)".*?/>')
    m = auth_token_pattern.search(response.content)
    auth_token = m.group(1).decode()

    login_form_data = {
        'utf8': '✓',
        'authenticity_token': auth_token,
        'return_to_on_failure': '/auth/v2/login/signin',
        'return_to': 'https://help.archive.org/auth/v2/login/signed_in',
        'brand_id': '360000261412',
        'form_origin': 'no_return',
        'user[email]': env['ZENDESK_AGENT_ACCOUNT'],
        'user[password]': env['ZENDESK_AGENT_PASSWORD']
    }
    sesh.post('https://archivesupport.zendesk.com/access/login', data=login_form_data).result()
    return sesh


def concurrent_get_raw_emails(ticket_ids, first_audit_ids):
    assert(len(ticket_ids) == len(first_audit_ids)), 'unmatched ticket and first audit ids'
    url_template = 'https://archivesupport.zendesk.com/audits/{}/email.eml?ticket_id={}'
    session = get_logged_in_future_sesh()

    raw_email_futures = []
    for i, t_id, fa_id in zip(range(len(ticket_ids)), ticket_ids, first_audit_ids):
        logger.debug('getting raw email future for ticket #{} {}/{}'.format(ticket_ids[i], i, len(ticket_ids)))
        if t_id is None or fa_id is None:
            raw_email_futures.append(None)
            continue
        raw_email_futures.append(session.get(
            url_template.format(fa_id, t_id)
        ))
        time.sleep(60 / ZENDESK_API_RATE_LIMIT)

    raw_emails = []
    for i, raw_email_future in enumerate(raw_email_futures):
        if raw_email_future is None:
            raw_emails.append(None)
            continue
        result = raw_email_future.result()
        if result.status_code != 200:
            logger.error('bad status code {}: {}'.format(result.status_code, result.content))
            raw_emails.append(None)
            continue

        try:
            zd_body_buf = io.StringIO(result.content.decode())
            while zd_body_buf.readline().strip() != '':
                pass
            raw_emails.append(''.join(zd_body_buf.readlines()).encode())
        except Exception as e:
            logger.error('{}#{} problem while stripping headers: {}'.format(
                first_audit_ids[i], ticket_ids[i], e
            ))
            raw_emails.append(None)

    return raw_emails