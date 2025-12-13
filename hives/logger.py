import os
import logging
from logging.handlers import RotatingFileHandler

# initalize loggings
log_dir = os.getenv('LOG_DIR', '/var/log')
log_handler = RotatingFileHandler(os.path.join(log_dir, 'hives.log'),
                                  mode='a',
                                  maxBytes=5*1024*1024,
                                  backupCount=2,
                                  encoding=None,
                                  delay=0)
log_formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
log_handler.setFormatter(log_formatter)
log_handler.setLevel(logging.INFO)

log = logging.getLogger('root')
log.setLevel(logging.INFO)
log.addHandler(log_handler)
log.addHandler(logging.StreamHandler())
