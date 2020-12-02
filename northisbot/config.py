import logging
from logging.config import dictConfig

logger = logging.getLogger(__name__)


def configure_logging():
    logging_config = {
        "version": 1,
        "formatters": {
            "f": {"format": "%(asctime)s %(levelname)-8s %(name)-20s -- %(message)s"}
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "f",
                "level": logging.DEBUG,
            }
        },
        "loggers": {
            "": {"handlers": ["console"], "level": logging.DEBUG, "propagate": False},
            "discord": {
                "handlers": ["console"],
                "level": logging.INFO,
                "propagate": False,
            },
            "tourguide": {
                "handlers": ["console"],
                "level": logging.DEBUG,
                "propagate": False,
            },
            "tourguide.config": {
                "handlers": ["console"],
                "level": logging.INFO,
                "propagate": False,
            },
        },
        "remove_existing_loggers": True,
    }

    dictConfig(logging_config)