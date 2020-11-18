MAILBOX_FOLDER = 'INBOX'

IMAP_SERVER = "imap.gmail.com"
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = "587"
SMTP_MODE = "tls"

ZD_ADDRESS = "support@archivesupport.zendesk.com"

SUBJECT_PATTERN = "ZDC{}: {}"
DELIMITER = "==============================="
INTERNAL_MESSAGE = """


{0}
This is an automatically forwarded email from the Patron Support team's via Zendesk. Your \
assistance with this ticket is greatly appreciated.

Text sent in a reply above this note will appear in our ticket logs as an internal note. \
If you feel it is appropriate, please Reply-All to share your response with the original \
requester. Also, please don't edit the subject line. We need it to associate your reply \
with the correct ticket.
{0}

""".format(DELIMITER)
