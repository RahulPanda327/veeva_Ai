import os
import sys
import json
import logging
import threading
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class JsonFormatter(logging.Formatter):
    def format(self, record):
        if isinstance(record.msg, dict):
            message = record.msg
        else:
            message = {"message": record.msg}

        log_record = {
            "time": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "name": record.name,
            "pid": os.getpid(),
            "thread": threading.current_thread().name,
            "message": message
        }

        if record.exc_info:
            log_record['exception'] = self.formatException(record.exc_info)

        if hasattr(record, 'status_code'):
            log_record['status_code'] = (
                record.status_code if record.status_code else None
            )

        return json.dumps(log_record)


logger_initialized = {}


def setup_logging(logger_name):
    global logger_initialized

    if logger_name in logger_initialized:
        return logging.getLogger(logger_name)

    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(JsonFormatter())
        logger.addHandler(stream_handler)

    logger_initialized[logger_name] = True
    return logger