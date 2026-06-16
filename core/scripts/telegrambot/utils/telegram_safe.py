import logging
import os
from functools import wraps


DEFAULT_TELEGRAM_TIMEOUT_SECONDS = 5
DEFAULT_CALLBACK_TIMEOUT_SECONDS = 3
EXPECTED_TELEGRAM_ERROR_MARKERS = (
    "query is too old",
    "response timeout expired",
    "query id is invalid",
    "message is not modified",
    "message to edit not found",
    "message to delete not found",
)


def _int_env(name, default, minimum=1):
    try:
        value = int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default
    return value if value >= minimum else default


def get_telegram_timeout_seconds():
    return _int_env("DIJIQ_TELEGRAM_TIMEOUT_SECONDS", DEFAULT_TELEGRAM_TIMEOUT_SECONDS)


def get_callback_timeout_seconds():
    return _int_env("DIJIQ_CALLBACK_TIMEOUT_SECONDS", DEFAULT_CALLBACK_TIMEOUT_SECONDS)


def is_expected_telegram_error(error):
    text = str(error).lower()
    return any(marker in text for marker in EXPECTED_TELEGRAM_ERROR_MARKERS)


def _call_with_timeout(func, timeout_seconds, *args, ignore_expected=True, **kwargs):
    if timeout_seconds is not None:
        kwargs.setdefault("timeout", timeout_seconds)
    try:
        return func(*args, **kwargs)
    except TypeError as error:
        if "unexpected keyword argument 'timeout'" not in str(error):
            raise
        kwargs.pop("timeout", None)
        try:
            return func(*args, **kwargs)
        except Exception as retry_error:
            if ignore_expected and is_expected_telegram_error(retry_error):
                logging.getLogger("dijiq.bot.telegram").info("Ignored Telegram API error: %s", retry_error)
                return None
            raise
    except Exception as error:
        if ignore_expected and is_expected_telegram_error(error):
            logging.getLogger("dijiq.bot.telegram").info("Ignored Telegram API error: %s", error)
            return None
        raise


def safe_answer_callback_query(bot, callback_query_id, *args, **kwargs):
    return _call_with_timeout(
        bot.answer_callback_query,
        get_callback_timeout_seconds(),
        callback_query_id,
        *args,
        **kwargs,
    )


def safe_edit_message_text(bot, *args, **kwargs):
    return _call_with_timeout(bot.edit_message_text, get_telegram_timeout_seconds(), *args, **kwargs)


def safe_delete_message(bot, *args, **kwargs):
    return _call_with_timeout(bot.delete_message, get_telegram_timeout_seconds(), *args, **kwargs)


def safe_send_message(bot, *args, **kwargs):
    return _call_with_timeout(bot.send_message, get_telegram_timeout_seconds(), *args, **kwargs)


def safe_send_photo(bot, *args, **kwargs):
    return _call_with_timeout(bot.send_photo, get_telegram_timeout_seconds(), *args, **kwargs)


def safe_reply_to(bot, *args, **kwargs):
    return _call_with_timeout(bot.reply_to, get_telegram_timeout_seconds(), *args, **kwargs)


def safe_send_chat_action(bot, *args, **kwargs):
    return _call_with_timeout(bot.send_chat_action, get_telegram_timeout_seconds(), *args, **kwargs)


def install_safe_telegram_methods(bot):
    if getattr(bot, "_dijiq_safe_telegram_installed", False):
        return bot

    methods = {
        "answer_callback_query": get_callback_timeout_seconds,
        "edit_message_text": get_telegram_timeout_seconds,
        "edit_message_caption": get_telegram_timeout_seconds,
        "edit_message_reply_markup": get_telegram_timeout_seconds,
        "delete_message": get_telegram_timeout_seconds,
        "send_message": get_telegram_timeout_seconds,
        "send_photo": get_telegram_timeout_seconds,
        "reply_to": get_telegram_timeout_seconds,
        "send_chat_action": get_telegram_timeout_seconds,
    }

    for method_name, timeout_getter in methods.items():
        original = getattr(bot, method_name, None)
        if original is None:
            continue

        @wraps(original)
        def wrapped(*args, __original=original, __timeout_getter=timeout_getter, **kwargs):
            return _call_with_timeout(__original, __timeout_getter(), *args, **kwargs)

        setattr(bot, f"_dijiq_original_{method_name}", original)
        setattr(bot, method_name, wrapped)

    setattr(bot, "_dijiq_safe_telegram_installed", True)
    return bot
