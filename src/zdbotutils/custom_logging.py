import logging


logger = logging.getLogger()
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(filename)s:%(lineno)d > %(message)s')
logger.setLevel(logging.DEBUG)

sys_log = logging.StreamHandler()
sys_log.setFormatter(formatter)
sys_log.setLevel(logging.INFO)
logger.addHandler(sys_log)

debug_log = logging.FileHandler('debug.log')
debug_log.setFormatter(formatter)
debug_log.setLevel(logging.DEBUG)
logger.addHandler(debug_log)

info_log = logging.FileHandler('info.log')
info_log.setFormatter(formatter)
info_log.setLevel(logging.INFO)
logger.addHandler(info_log)
