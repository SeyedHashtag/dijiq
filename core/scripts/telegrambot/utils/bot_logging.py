import functools
import logging
import os
import time
from logging.handlers import RotatingFileHandler


DEFAULT_LOG_FILE = "/etc/dijiq/core/scripts/telegrambot/logs/bot.log"
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_SLOW_HANDLER_MS = 1000
MAX_LOG_VALUE_LENGTH = 160
LOG_FORMAT = "%(asctime)s %(levelname)s [%(threadName)s] %(name)s: %(message)s"


def _coerce_log_level(value):
    level_name = str(value or DEFAULT_LOG_LEVEL).strip().upper()
    return getattr(logging, level_name, logging.INFO)


def _int_env(name, default, minimum=1):
    try:
        value = int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default
    return value if value >= minimum else default


def get_bot_log_file():
    return os.getenv("DIJIQ_BOT_LOG_FILE", DEFAULT_LOG_FILE)


def get_slow_handler_ms():
    if os.getenv("DIJQ_SLOW_HANDLER_MS") is not None:
        return _int_env("DIJQ_SLOW_HANDLER_MS", DEFAULT_SLOW_HANDLER_MS)
    return _int_env("DIJIQ_SLOW_HANDLER_MS", DEFAULT_SLOW_HANDLER_MS)


def configure_logging(log_file=None):
    log_file = log_file or get_bot_log_file()
    log_level = _coerce_log_level(os.getenv("DIJIQ_BOT_LOG_LEVEL", DEFAULT_LOG_LEVEL))
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    absolute_log_file = os.path.abspath(log_file)
    for handler in root_logger.handlers:
        if (
            isinstance(handler, RotatingFileHandler)
            and getattr(handler, "baseFilename", None) == absolute_log_file
        ):
            handler.setLevel(log_level)
            return absolute_log_file

    file_handler = RotatingFileHandler(
        absolute_log_file,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    root_logger.addHandler(file_handler)
    logging.getLogger("dijiq.bot").info("Bot logging initialized log_file=%s", absolute_log_file)
    return absolute_log_file


def get_telegram_worker_count(default=8):
    return _int_env("TELEGRAM_BOT_WORKERS", default)


def _truncate(value):
    if value is None:
        return ""
    text = " ".join(str(value).split())
    if len(text) <= MAX_LOG_VALUE_LENGTH:
        return text
    return text[: MAX_LOG_VALUE_LENGTH - 3] + "..."


def _safe_attr(obj, name, default=None):
    return getattr(obj, name, default) if obj is not None else default


def _describe_event(kind, event):
    from_user = _safe_attr(event, "from_user")
    message = _safe_attr(event, "message") if kind == "callback" else event
    chat = _safe_attr(message, "chat")

    if kind == "callback":
        value_name = "data"
        value = _safe_attr(event, "data")
    else:
        value_name = "text"
        value = _safe_attr(event, "text")
        if value is None:
            value = f"<{_safe_attr(event, 'content_type', 'unknown')}>"

    return {
        "user_id": _safe_attr(from_user, "id", "unknown"),
        "chat_id": _safe_attr(chat, "id", "unknown"),
        "value_name": value_name,
        "value": _truncate(value),
    }


def _wrap_handler(func, kind):
    logger = logging.getLogger("dijiq.bot.handlers")
    slow_handler_ms = get_slow_handler_ms()

    @functools.wraps(func)
    def wrapped(event, *args, **kwargs):
        started_at = time.monotonic()
        details = _describe_event(kind, event)
        logger.info(
            "handler_start kind=%s handler=%s user_id=%s chat_id=%s %s=%r",
            kind,
            func.__name__,
            details["user_id"],
            details["chat_id"],
            details["value_name"],
            details["value"],
        )
        try:
            result = func(event, *args, **kwargs)
        except Exception:
            elapsed_ms = int((time.monotonic() - started_at) * 1000)
            logger.exception(
                "handler_error kind=%s handler=%s user_id=%s chat_id=%s elapsed_ms=%s %s=%r",
                kind,
                func.__name__,
                details["user_id"],
                details["chat_id"],
                elapsed_ms,
                details["value_name"],
                details["value"],
            )
            raise

        elapsed_ms = int((time.monotonic() - started_at) * 1000)
        log_method = logger.warning if elapsed_ms >= slow_handler_ms else logger.info
        log_method(
            "handler_end kind=%s handler=%s user_id=%s chat_id=%s elapsed_ms=%s %s=%r",
            kind,
            func.__name__,
            details["user_id"],
            details["chat_id"],
            elapsed_ms,
            details["value_name"],
            details["value"],
        )
        return result

    return wrapped


def instrument_bot(bot):
    if getattr(bot, "_dijiq_logging_instrumented", False):
        return bot

    original_message_handler = bot.message_handler
    original_callback_query_handler = bot.callback_query_handler

    def message_handler(*handler_args, **handler_kwargs):
        decorator = original_message_handler(*handler_args, **handler_kwargs)

        def register(func):
            return decorator(_wrap_handler(func, "message"))

        return register

    def callback_query_handler(*handler_args, **handler_kwargs):
        decorator = original_callback_query_handler(*handler_args, **handler_kwargs)

        def register(func):
            return decorator(_wrap_handler(func, "callback"))

        return register

    bot.message_handler = message_handler
    bot.callback_query_handler = callback_query_handler
    bot._dijiq_logging_instrumented = True
    return bot
