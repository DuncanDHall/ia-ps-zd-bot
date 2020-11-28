import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
syslog = logging.StreamHandler()
formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')
syslog.setFormatter(formatter)
syslog.setLevel(logging.DEBUG)
logger.addHandler(syslog)
