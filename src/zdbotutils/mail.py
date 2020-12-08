from os import environ as env
import imapclient
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from config import IMAP_SERVER, IMAP_PORT, SMTP_SERVER, SMTP_PORT
from zdbotutils.custom_logging import logger


def get_default_imap_config():
    return {
        'host': IMAP_SERVER,
        'port': IMAP_PORT,
        'user': env['MAILBOT_ADDRESS'],
        'pass': env['MAILBOT_PASSWORD'],
        'folder': 'INBOX'
    }


def get_default_smtp_config():
    return {
        'host': SMTP_SERVER,
        'port': SMTP_PORT,
        'user': env['MAILBOT_ADDRESS'],
        'pass': env['MAILBOT_PASSWORD'],
    }


def chunked(chunkee, size):
    chunkee = list(chunkee)
    for i in range(int(len(chunkee) / size) + 1):
        chunk = chunkee[(i * size):((i + 1) * size)]
        if chunk:
            yield chunk


def get_raw_mail(unseen=True, read_only=False, config=get_default_imap_config()):
    host = config['host']
    port = config['port']
    user = config['user']
    password = config['pass']
    folder = config['folder']
    logger.info('getting {}mail from {}'.format('' if unseen else 'new ', user))
    try:
        logger.debug('establishing connection to {}:{}'.format(host, port))
        server = imapclient.IMAPClient(host=host, port=port)
        logger.debug('logging in as ' + user)
        server.login(user, password)
        logger.debug('selecting {}'.format(folder))
        server.select_folder(folder)

        logger.debug('polling for mail')
        msg_ids = server.search('UNSEEN' if unseen else 'ALL')
        logger.debug("{} {}emails found".format(len(msg_ids), '' if unseen else 'new '))

        logger.debug('fetching msg data')
        msg_data = {}
        for msg_ids_chunk in chunked(msg_ids, 1000):
            msg_data.update(server.fetch(msg_ids_chunk, ['BODY[TEXT]', 'ENVELOPE']))

        server.logout()
        return msg_data
    except Exception as e:
        logger.critical(e)
        raise e


def get_msgs(folders):
    try:
        logger.debug('establishing connection to {}:{}'.format(IMAP_SERVER, IMAP_PORT))
        server = imapclient.IMAPClient(host=IMAP_SERVER, port=IMAP_PORT)
        logger.debug('logging in as ' + env['DIFFBOT_ADDRESS'])
        server.login(env['DIFFBOT_ADDRESS'], env['DIFFBOT_PASSWORD'])

        data = {}
        for folder in folders:
            logger.debug('selecting {}'.format(folder))
            server.select_folder(folder)
            logger.debug('polling for mail')
            msg_ids = server.search('ALL')
            logger.info("{} emails found".format(len(msg_ids)))

            logger.debug('fetching msg data')
            msg_data = {}
            for msg_ids_chunk in chunked(msg_ids, 1000):
                logger.info('getting msg data for ids [{}... {}]'.format(msg_ids_chunk[0], msg_ids_chunk[-1]))
                msg_data.update(server.fetch(msg_ids_chunk, ['BODY[TEXT]', 'ENVELOPE', 'INTERNALDATE']))

            data[folder] = msg_data

        server.logout()
        return data
    except Exception as e:
        logger.critical(e)
        raise e


def change_folder(msg_ids, current_folder, new_folder):
    if not msg_ids:
        return
    logger.debug('establishing connection to {}:{}'.format(IMAP_SERVER, IMAP_PORT))
    server = imapclient.IMAPClient(host=IMAP_SERVER, port=IMAP_PORT)
    logger.debug('logging in as ' + env['DIFFBOT_ADDRESS'])
    server.login(env['DIFFBOT_ADDRESS'], env['DIFFBOT_PASSWORD'])
    server.select_folder(current_folder)
    logger.debug('moving {} messages from {} to {}'.format(len(msg_ids), current_folder, new_folder))

    for msg_ids_chunk in chunked(msg_ids, 1000):
        server.copy(msg_ids_chunk, new_folder)
        server.delete_messages(msg_ids_chunk)
        server.expunge(msg_ids_chunk)
    server.logout()


def send_mail(sender, receiver, subject, body, html_body=None, cc=None, config=get_default_smtp_config()):
    host = config['host']
    port = config['port']
    user = config['user']
    password = config['pass']
    logger.info('sending email from {} to {} over {}:{}'.format(sender, receiver, host, port))
    logger.debug('composing message headers')

    msg = MIMEMultipart('alternative')
    msg['From'] = sender
    msg['To'] = receiver
    if isinstance(cc, list):
        msg['Cc'] = ', '.join(cc)
    msg['Subject'] = subject

    if html_body is not None:
        html_part = MIMEText(html_body, 'html')
        msg.attach(html_part)

    text_part = MIMEText(body, 'plain')
    msg.attach(text_part)

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

