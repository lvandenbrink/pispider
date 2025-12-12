import os, logging
from logging.handlers import RotatingFileHandler

###############################################
# Logging
###############################################
log_dir = os.getenv('LOG_DIR', '/var/log')
log_handler = RotatingFileHandler(f'{log_dir}/site.log',
                                  mode='a',
                                  maxBytes=5*1024*1024,
                                  backupCount=2,
                                  encoding=None,
                                  delay=0)
log_formatter = logging.Formatter('%(asctime)s %(levelname)s %(funcName)s(%(lineno)d) %(message)s')
log_handler.setFormatter(log_formatter)
log_handler.setLevel(logging.INFO)

log = logging.getLogger('root')
log.setLevel(logging.DEBUG)
log.addHandler(log_handler)
log.addHandler(logging.StreamHandler())
