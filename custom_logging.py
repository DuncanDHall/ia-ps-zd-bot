import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
syslog = logging.StreamHandler()
formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')
syslog.setFormatter(formatter)
syslog.setLevel(logging.INFO)
logger.addHandler(syslog)
