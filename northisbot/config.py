import logging
from logging.config import dictConfig

logger = logging.getLogger(__name__)

_info_config = {"handlers": ["console"], "level": logging.INFO, "propagate": False}
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
            "": {"handlers": ["console"], "level": logging.DEBUG, "propagate": True},

            'aiohttp.access': _info_config,
            'aiohttp.client': _info_config,
            'aiohttp.internal': _info_config,
            'aiohttp.server': _info_config,
            'aiohttp.web': _info_config,
            'aiohttp.websocket': _info_config,
            "__main__": {
                "handlers": ["console"],
                "level": logging.INFO,
                "propagate": False,
            },
            "discord": {
                "handlers": ["console"],
                "level": logging.INFO,
                "propagate": False,
            },
            "northisbot": {
                "handlers": ["console"],
                "level": logging.DEBUG,
                "propagate": False,
            },
            "northisbot.config": {
                "handlers": ["console"],
                "level": logging.INFO,
                "propagate": False,
            },
        },
        "remove_existing_loggers": True,
    }

    dictConfig(logging_config)
