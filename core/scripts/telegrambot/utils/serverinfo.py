from dotenv import load_dotenv
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from telebot import types
from utils.command import *
from utils.telegram_safe import safe_answer_callback_query, safe_edit_message_text, safe_reply_to


SERVER_INFO_DEFAULT_SECTION = "overview"
SERVER_INFO_SECTIONS = (
    ("overview", "📌 Overview"),
    ("business", "💰 Business"),
    ("customers", "📈 Customers"),
    ("tech", "🖥️ Tech"),
    ("traffic", "🚦 Traffic"),
    ("alerts", "⚠️ Alerts"),
)
SERVER_INFO_CACHE_LOCK = threading.RLock()
SERVER_INFO_REFRESH_LOCK = threading.Lock()
SERVER_INFO_JOB_LOCK = threading.Lock()
SERVER_INFO_MIN_REFRESH_SECONDS = 60
SERVER_INFO_SNAPSHOT_CACHE = {"snapshot": None, "cached_at": 0.0}
SERVER_INFO_RENDER_INFLIGHT = set()


def _int_env(name, default, minimum=1):
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default
    return value if value >= minimum else default


SERVER_INFO_JOB_EXECUTOR = ThreadPoolExecutor(
    max_workers=_int_env("DIJIQ_SERVER_INFO_WORKERS", 1),
    thread_name_prefix="dijiq-server-info",
)


def _load_cli_api_module():
    core_path = os.path.dirname(CLI_PATH)
    if core_path and core_path not in sys.path:
        sys.path.append(core_path)
    import cli_api
    return cli_api


def _normalize_server_info_section(section):
    valid_sections = {key for key, _label in SERVER_INFO_SECTIONS}
    section = str(section or SERVER_INFO_DEFAULT_SECTION).lower()
    return section if section in valid_sections else SERVER_INFO_DEFAULT_SECTION


def _build_server_info_markup(section=SERVER_INFO_DEFAULT_SECTION):
    section = _normalize_server_info_section(section)
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = []
    for key, label in SERVER_INFO_SECTIONS:
        display = f"• {label}" if key == section else label
        buttons.append(types.InlineKeyboardButton(display, callback_data=f"server_info:view:{key}"))
    markup.add(*buttons)
    markup.add(types.InlineKeyboardButton("🔄 Refresh", callback_data=f"server_info:refresh:{section}"))
    return markup


def _get_server_info_snapshot(force_refresh=False):
    now = time.monotonic()
    with SERVER_INFO_CACHE_LOCK:
        snapshot = SERVER_INFO_SNAPSHOT_CACHE.get("snapshot")
        cached_at = SERVER_INFO_SNAPSHOT_CACHE.get("cached_at", 0.0)
        recently_built = now - cached_at < SERVER_INFO_MIN_REFRESH_SECONDS
        if snapshot is not None and (not force_refresh or recently_built):
            return snapshot

    has_snapshot = snapshot is not None
    refresh_acquired = SERVER_INFO_REFRESH_LOCK.acquire(blocking=not has_snapshot)
    if not refresh_acquired:
        return snapshot

    try:
        now = time.monotonic()
        with SERVER_INFO_CACHE_LOCK:
            snapshot = SERVER_INFO_SNAPSHOT_CACHE.get("snapshot")
            cached_at = SERVER_INFO_SNAPSHOT_CACHE.get("cached_at", 0.0)
            recently_built = now - cached_at < SERVER_INFO_MIN_REFRESH_SECONDS
            if snapshot is not None and (not force_refresh or recently_built):
                return snapshot

        cli_api = _load_cli_api_module()
        snapshot = cli_api.build_server_info_snapshot()
        with SERVER_INFO_CACHE_LOCK:
            SERVER_INFO_SNAPSHOT_CACHE["snapshot"] = snapshot
            SERVER_INFO_SNAPSHOT_CACHE["cached_at"] = time.monotonic()
        return snapshot
    finally:
        SERVER_INFO_REFRESH_LOCK.release()


def _build_server_info_text(section=SERVER_INFO_DEFAULT_SECTION, force_refresh=False):
    section = _normalize_server_info_section(section)
    try:
        cli_api = _load_cli_api_module()
        snapshot = _get_server_info_snapshot(force_refresh=force_refresh)
        return cli_api.format_server_info_section(snapshot, section)
    except Exception as e:
        return f"Error generating server info: {e}"


def _has_server_info_snapshot():
    with SERVER_INFO_CACHE_LOCK:
        return SERVER_INFO_SNAPSHOT_CACHE.get("snapshot") is not None


def _server_info_placeholder(force_refresh=False):
    if force_refresh:
        return "Refreshing server info..."
    return "Generating server info..."


def _submit_server_info_render(chat_id, message_id, section, force_refresh=False):
    key = (chat_id, message_id, section, bool(force_refresh))
    with SERVER_INFO_JOB_LOCK:
        if key in SERVER_INFO_RENDER_INFLIGHT:
            return False
        SERVER_INFO_RENDER_INFLIGHT.add(key)

    def run():
        try:
            if force_refresh or not _has_server_info_snapshot():
                safe_edit_message_text(
                    bot,
                    _server_info_placeholder(force_refresh=force_refresh),
                    chat_id=chat_id,
                    message_id=message_id,
                    reply_markup=_build_server_info_markup(section),
                    parse_mode='Markdown',
                )
            safe_edit_message_text(
                bot,
                _build_server_info_text(section, force_refresh=force_refresh),
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=_build_server_info_markup(section),
                parse_mode='Markdown',
            )
        finally:
            with SERVER_INFO_JOB_LOCK:
                SERVER_INFO_RENDER_INFLIGHT.discard(key)

    try:
        SERVER_INFO_JOB_EXECUTOR.submit(run)
    except Exception:
        with SERVER_INFO_JOB_LOCK:
            SERVER_INFO_RENDER_INFLIGHT.discard(key)
        raise
    return True


def _submit_server_info_reply(message, section):
    key = ("reply", getattr(getattr(message, "chat", None), "id", None), getattr(message, "message_id", id(message)), section)
    with SERVER_INFO_JOB_LOCK:
        if key in SERVER_INFO_RENDER_INFLIGHT:
            return False
        SERVER_INFO_RENDER_INFLIGHT.add(key)

    def run():
        try:
            if _has_server_info_snapshot():
                safe_reply_to(
                    bot,
                    message,
                    _build_server_info_text(section),
                    reply_markup=_build_server_info_markup(section),
                    parse_mode='Markdown',
                )
                return

            reply = safe_reply_to(
                bot,
                message,
                _server_info_placeholder(),
                reply_markup=_build_server_info_markup(section),
                parse_mode='Markdown',
            )
            text = _build_server_info_text(section)
            if reply is not None:
                safe_edit_message_text(
                    bot,
                    text,
                    chat_id=reply.chat.id,
                    message_id=reply.message_id,
                    reply_markup=_build_server_info_markup(section),
                    parse_mode='Markdown',
                )
            else:
                safe_reply_to(
                    bot,
                    message,
                    text,
                    reply_markup=_build_server_info_markup(section),
                    parse_mode='Markdown',
                )
        finally:
            with SERVER_INFO_JOB_LOCK:
                SERVER_INFO_RENDER_INFLIGHT.discard(key)

    try:
        SERVER_INFO_JOB_EXECUTOR.submit(run)
    except Exception:
        with SERVER_INFO_JOB_LOCK:
            SERVER_INFO_RENDER_INFLIGHT.discard(key)
        raise
    return True


@bot.message_handler(func=lambda message: is_admin(message.from_user.id) and message.text == '📊 Server Info')
def server_info(message):
    section = SERVER_INFO_DEFAULT_SECTION
    _submit_server_info_reply(message, section)


@bot.callback_query_handler(func=lambda call: call.data.startswith("server_info:"))
def handle_server_info_callback(call):
    if not is_admin(call.from_user.id):
        safe_answer_callback_query(bot, call.id, "Unauthorized.")
        return

    parts = call.data.split(":")
    action = parts[1] if len(parts) > 1 else "view"
    section = _normalize_server_info_section(parts[2] if len(parts) > 2 else SERVER_INFO_DEFAULT_SECTION)
    force_refresh = action == "refresh"
    answer = "Refreshed." if force_refresh else "Opened."

    safe_answer_callback_query(bot, call.id, answer)
    _submit_server_info_render(call.message.chat.id, call.message.message_id, section, force_refresh=force_refresh)


def handle_server_info_refresh(call):
    handle_server_info_callback(call)
