MAILBOX_FOLDER = 'INBOX'

IMAP_SERVER = "mail.archive.org"
IMAP_PORT = "993"
IMAP_MODE = "ssl"
SMTP_SERVER = "mail.archive.org"
SMTP_PORT = "465"
SMTP_MODE = "ssl"

MAILBOT_NAME = "Support Team (automated)"
MAILBOT_CC_NAME = "Original Sender (automated)"

# Authentication in .env
# MAILBOT_ADDRESS
# MAILBOT_PASSWORD
# MAILBOT_CC_ADDRESS
# MAILBOT_AGENT_ACCOUNT
# ZENDESK_API_KEY
# ZENDESK_TRIGGER_USERNAME
# ZENDESK_TRIGGER_PASSWORD


SUBJECT_PATTERN = "ZDC{}: {}"
DELIMITER = "===================="
_MESSAGE = """This is an automatically forwarded email from the Internet Archive Patron Support
team. Your assistance with this ticket is greatly appreciated. Text sent in a reply above this \
note will appear in our ticket logs as an internal note. \
If you feel it is appropriate, please Reply-All to share your response with the original \
requester. Also, please don't edit the subject line. We need it to associate your reply \
with the correct request."""

INTERNAL_MESSAGE_PLAIN = """

{0}{0}
{1}
{0}{0}

""".format(DELIMITER, _MESSAGE)

INTERNAL_MESSAGE_HTML = """
<br>
<p>{0}{0}</p>
<p>{1}</p>
<p>{0}{0}</p>
<br>
""".format(DELIMITER, _MESSAGE)
