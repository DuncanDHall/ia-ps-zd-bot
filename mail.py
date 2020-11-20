from os import environ as env
import imapclient
import smtplib
from email.mime.text import MIMEText

from config import *
from custom_logging import logger


DEFAULT_IMAP_CONFIG = {
    'host': IMAP_SERVER,
    'port': IMAP_PORT,
    'user': env['MAILBOT_ADDRESS'],
    'pass': env['MAILBOT_PASSWORD'],
}

DEFAULT_SMTP_CONFIG = {
    'host': SMTP_SERVER,
    'port': SMTP_PORT,
    'user': env['MAILBOT_ADDRESS'],
    'pass': env['MAILBOT_PASSWORD'],
}


def get_raw_mail(unseen=False, read_only=False, config=DEFAULT_IMAP_CONFIG):
    host = config['host']
    port = config['port']
    user = config['user']
    password = config['pass']
    logger.info('getting {}mail from {}'.format('' if unseen else 'new ', user))
    try:
        logger.debug('establishing connection to {}:{}'.format(host, port))
        server = imapclient.IMAPClient(host=host, port=port)
        logger.debug('logging in as ' + user)
        server.login(user, password)
        logger.debug('selecting INBOX')
        server.select_folder('INBOX', readonly=read_only)
        logger.debug('polling for mail')
        msg_ids = server.search('UNSEEN' if unseen else 'ALL')
        logger.info("{} {}emails found: {}".format(len(msg_ids), '' if unseen else 'new ', msg_ids))
        logger.debug('fetching msg data')
        msg_data = server.fetch(msg_ids, ['BODY[TEXT]', 'ENVELOPE'])
        return msg_data
    except Exception as e:
        logger.critical(e)
        raise e


def send_mail(sender, receiver, subject, body, cc=None, config=DEFAULT_SMTP_CONFIG):
    host = config['host']
    port = config['port']
    user = config['user']
    password = config['pass']
    logger.info('sending email from {} to {} over {}:{}'.format(sender, receiver, host, port))
    logger.debug('composing message headers')
    msg = MIMEText(body)
    msg['From'] = sender
    msg['To'] = receiver
    if isinstance(cc, list):
        msg['Cc'] = ', '.join(cc)
    msg['Subject'] = subject

    try:
        logger.debug('establishing connection to {}:{}'.format(host, port))
        server = smtplib.SMTP_SSL(host=host, port=port)
        logger.debug('logging in as ' + user)
        server.login(user, password)
        logger.debug('sending')
        server.sendmail(config['user'], receiver, msg.as_string())
    except Exception as e:
        logger.critical(e)
        raise e


