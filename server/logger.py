import asyncio
import contextvars
import logging
import logging.config
import traceback
from copy import deepcopy
from typing import Any, cast

import msgspec
from settings import DEV

log = logging.getLogger(__name__)
_STRUCTURED_LOG_JSON_ENCODER = msgspec.json.Encoder()


class PychessLogRecord(logging.LogRecord):
    name_lineno: str
    gameId: str
    username: str
    json: str


############################################################################################
###################################### NOTE!!! #############################################
## Editing this config will not have effect until the config in mongo is updated          ##
## This is only used on init, before the config from mongo is fetched                     ##
## and as template if no config in mongo exists - then this will be inserted on startup   ##
############################################################################################
DEFAULT_LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "addPychessContextFilter": {"()": "logger.AddPychessContextFilter"},
        # "addJsonStructuredLogRecordInContextFilter": { "()": "logger.AddJsonStructuredLogRecordInContextFilter" },
    },
    "formatters": {
        "standard": {
            "format": "%(asctime)s.%(msecs)03d %(levelname_brackets)-7s %(gameId)-8s %(username)-12s %(name_lineno)-31s %(message)s"
        },
        "json": {
            "format": "%(json)s",
        },
    },
    "handlers": {
        "default": {
            "level": "DEBUG",
            "formatter": "standard",
            # "formatter": "json",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",  # Default is stderr
            "filters": [
                "addPychessContextFilter",
                # "addJsonStructuredLogRecordInContextFilter",
            ],
        },
    },
    "loggers": {
        # root logger
        "": {"handlers": ["default"], "level": "DEBUG", "propagate": False},
        # frameworks:
        "asyncio": {"handlers": ["default"], "level": "WARNING", "propagate": False},
        "pymongo": {"handlers": ["default"], "level": "INFO", "propagate": False},
        # pychess modules:
        "wsr": {"handlers": ["default"], "level": "DEBUG", "propagate": False},
        "wsl": {"handlers": ["default"], "level": "DEBUG", "propagate": False},
        "websocket_utils": {
            "handlers": ["default"],
            "level": "DEBUG",
            "propagate": False,
        },
        "views.tournaments": {
            "handlers": ["default"],
            "level": "DEBUG",
            "propagate": False,
        },
        "views.invite": {"handlers": ["default"], "level": "DEBUG", "propagate": False},
        "views": {"handlers": ["default"], "level": "DEBUG", "propagate": False},
        "utils": {"handlers": ["default"], "level": "DEBUG", "propagate": False},
        "users": {"handlers": ["default"], "level": "DEBUG", "propagate": False},
        "user": {"handlers": ["default"], "level": "DEBUG", "propagate": False},
        "twitch": {"handlers": ["default"], "level": "DEBUG", "propagate": False},
        "tournament.tournament": {
            "handlers": ["default"],
            "level": "DEBUG",
            "propagate": False,
        },
        "tournament.tournaments": {
            "handlers": ["default"],
            "level": "DEBUG",
            "propagate": False,
        },
        "tournament.scheduler": {
            "handlers": ["default"],
            "level": "DEBUG",
            "propagate": False,
        },
        "tournament.auto_play_tournament": {
            "handlers": ["default"],
            "level": "DEBUG",
            "propagate": False,
        },
        "tournament.arena": {
            "handlers": ["default"],
            "level": "DEBUG",
            "propagate": False,
        },
        "tournament.arena_new": {
            "handlers": ["default"],
            "level": "DEBUG",
            "propagate": False,
        },
        "server": {"handlers": ["default"], "level": "DEBUG", "propagate": False},
        "seek": {"handlers": ["default"], "level": "DEBUG", "propagate": False},
        "pychess_global_app_state": {
            "handlers": ["default"],
            "level": "DEBUG",
            "propagate": False,
        },
        "login": {"handlers": ["default"], "level": "DEBUG", "propagate": False},
        "logger": {"handlers": ["default"], "level": "DEBUG", "propagate": False},
        "lichess_team_msg": {
            "handlers": ["default"],
            "level": "DEBUG",
            "propagate": False,
        },
        "generate_crosstable": {
            "handlers": ["default"],
            "level": "DEBUG",
            "propagate": False,
        },
        "game_api": {"handlers": ["default"], "level": "DEBUG", "propagate": False},
        "game": {"handlers": ["default"], "level": "DEBUG", "propagate": False},
        "fishnet": {"handlers": ["default"], "level": "DEBUG", "propagate": False},
        "fairy.fairy_board": {
            "handlers": ["default"],
            "level": "DEBUG",
            "propagate": False,
        },
        "clock": {"handlers": ["default"], "level": "DEBUG", "propagate": False},
        "bugchess.pgn": {"handlers": ["default"], "level": "DEBUG", "propagate": False},
        "bugchess.gaviota": {
            "handlers": ["default"],
            "level": "DEBUG",
            "propagate": False,
        },
        "bugchess.engine": {
            "handlers": ["default"],
            "level": "DEBUG",
            "propagate": False,
        },
        "bug.wsr_bug": {"handlers": ["default"], "level": "DEBUG", "propagate": False},
        "bug.utils_bug": {
            "handlers": ["default"],
            "level": "DEBUG",
            "propagate": False,
        },
        "bug.import_bugh_game": {
            "handlers": ["default"],
            "level": "DEBUG",
            "propagate": False,
        },
        "bug.game_bug": {"handlers": ["default"], "level": "DEBUG", "propagate": False},
        "broadcast": {"handlers": ["default"], "level": "DEBUG", "propagate": False},
        "bot_api": {"handlers": ["default"], "level": "DEBUG", "propagate": False},
        "ai": {"handlers": ["default"], "level": "DEBUG", "propagate": False},
        "admin": {"handlers": ["default"], "level": "DEBUG", "propagate": False},
        "export2pgn": {"handlers": ["default"], "level": "DEBUG", "propagate": False},
        "puzzle": {"handlers": ["default"], "level": "DEBUG", "propagate": False},
        # if __name__ == '__main__'
        "__main__": {"handlers": ["default"], "level": "DEBUG", "propagate": False},
    },
}

############################################################################################
# additional logger context
log_context_data = contextvars.ContextVar("log_context_data", default={})


def set_log_context(varname, value):
    # ContextVar values must be replaced, not mutated: multiple aiohttp tasks
    # otherwise share the same dictionary and log each other's users/game IDs.
    context_dict = log_context_data.get().copy()
    context_dict[varname] = value
    log_context_data.set(context_dict)


set_log_context("username", "system")
set_log_context("gameId", "init")


class AddPychessContextFilter(logging.Filter):
    """
    This is a filter which injects contextual information from `contextvars.ContextVar` (log_context_data) into the log.
    """

    def __init__(self):
        super().__init__()

    def filter(self, record: logging.LogRecord):
        context_dict = log_context_data.get()

        # shorten WARNING to WARN:
        if record.levelname == "WARNING":
            record.levelname = "WARN"
        # I want to pad level together with brackets in the log formatter:
        record.levelname_brackets = f"[{record.levelname}]"
        # I want to pad name+lineno together in the log formatter:
        record.name_lineno = record.name + ":" + str(record.lineno)
        # pychess context specific values:
        record.username = context_dict.get("username", "none-user")
        record.gameId = context_dict.get("gameId", "none-game")

        return True


# ~additional logger context
############################################################################################


class AddJsonStructuredLogRecordInContextFilter(logging.Filter):
    """
    This is a filter which constructs a json from the log record and adds it in the context in case we want structured
    logging.

    Usage:
     "filters": {
        "addPychessContextFilter": {"()": "logger.AddPychessContextFilter"},
        "addJsonStructuredLogRecordInContextFilter": { "()": "logger.AddJsonStructuredLogRecordInContextFilter" },
    },
    "formatters": {
        ...
        "json": { "format": "%(json)s" },
    },
    "handlers": {
        "default": {
            ...
            "formatter": "json",
            "filters": [
                "addPychessContextFilter",
                "addJsonStructuredLogRecordInContextFilter",
            ],
        },
    },

    Make sure the order of filters is this, so the json filter has the new context values when constructing the json
    """

    def __init__(self):
        super().__init__()

    def filter(self, record: logging.LogRecord):
        pychess_record = cast(PychessLogRecord, record)
        try:
            pychess_record.json = _STRUCTURED_LOG_JSON_ENCODER.encode(
                {
                    "level": record.levelname,
                    "message": record.getMessage(),
                    "name_lineno": pychess_record.name_lineno,
                    "stack_info": record.stack_info,
                    "gameId": pychess_record.gameId,
                    "username": pychess_record.username,
                    "exc_info": "".join(
                        traceback.format_exception(
                            record.exc_info[0], record.exc_info[1], record.exc_info[2]
                        )
                    )
                    if record.exc_info is not None
                    else None,
                }
            ).decode("utf-8")
        except Exception as e:
            print(e)
            pychess_record.json = (
                "error constructing json structured log record. See stdout for traceback."
            )
        return True


# logging before initializing the Web App's event loop will use this,
# after that it will be re-initialized again with what is in the mongo db if any
def init_default_logger():
    logging.config.dictConfig(_apply_dev_logging_overrides(DEFAULT_LOGGING_CONFIG))
    log.info("Logging initialized with default config")


def _apply_dev_logging_overrides(logging_config: dict[str, Any]) -> dict[str, Any]:
    """Force verbose logging on DEV without requiring Mongo config edits."""

    if not DEV:
        return logging_config

    config = deepcopy(logging_config)
    handlers = config.setdefault("handlers", {})
    default_handler = handlers.setdefault("default", {})
    default_handler["level"] = "DEBUG"

    loggers = config.setdefault("loggers", {})
    root_logger = loggers.setdefault("", {})
    root_logger["level"] = "DEBUG"
    root_logger.setdefault("handlers", ["default"])
    root_logger.setdefault("propagate", False)

    push_logger = loggers.setdefault("push_notifications", {})
    push_logger["level"] = "DEBUG"
    push_logger.setdefault("handlers", ["default"])
    push_logger.setdefault("propagate", False)

    pymongo_logger = loggers.setdefault("pymongo", {})
    pymongo_logger["level"] = "ERROR"
    pymongo_logger.setdefault("handlers", ["default"])
    pymongo_logger.setdefault("propagate", False)

    return config


# periodic refresh of logging config from mongo:
async def start_config_refresh_timer(db: Any) -> asyncio.Task[None] | None:
    async def periodic_refresh():
        last_logging_config = None
        while True:
            logging_config = await db.config.find_one({"name": "logging.config"})
            if logging_config is None:
                log.warning("Missing logging config in db. Inserting default")
                await db.config.insert_one(
                    {"name": "logging.config", "value": DEFAULT_LOGGING_CONFIG}
                )
                logging.config.dictConfig(_apply_dev_logging_overrides(DEFAULT_LOGGING_CONFIG))
                last_logging_config = DEFAULT_LOGGING_CONFIG
            elif last_logging_config != logging_config["value"]:
                log.info("New logging config detected in db")
                last_logging_config = logging_config["value"]
                logging.config.dictConfig(_apply_dev_logging_overrides(logging_config["value"]))
            await asyncio.sleep(60)

    if db:
        return asyncio.create_task(periodic_refresh(), name="logging-config-refresh")
    else:
        logging.config.dictConfig(_apply_dev_logging_overrides(DEFAULT_LOGGING_CONFIG))
        return None
