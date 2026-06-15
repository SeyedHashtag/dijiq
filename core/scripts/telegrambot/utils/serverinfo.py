from dotenv import load_dotenv
from telebot import types
from utils.command import *


SERVER_INFO_DEFAULT_SECTION = "overview"
SERVER_INFO_SECTIONS = (
    ("overview", "📌 Overview"),
    ("business", "💰 Business"),
    ("customers", "📈 Customers"),
    ("tech", "🖥️ Tech"),
    ("traffic", "🚦 Traffic"),
    ("alerts", "⚠️ Alerts"),
)


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


def _build_server_info_text(section=SERVER_INFO_DEFAULT_SECTION):
    section = _normalize_server_info_section(section)
    command = f"python3 {CLI_PATH} server-info --section {section}"
    return run_cli_command(command)


@bot.message_handler(func=lambda message: is_admin(message.from_user.id) and message.text == '📊 Server Info')
def server_info(message):
    bot.send_chat_action(message.chat.id, 'typing')
    section = SERVER_INFO_DEFAULT_SECTION
    bot.reply_to(message, _build_server_info_text(section), reply_markup=_build_server_info_markup(section), parse_mode='Markdown')


@bot.callback_query_handler(func=lambda call: call.data.startswith("server_info:"))
def handle_server_info_callback(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "Unauthorized.")
        return

    parts = call.data.split(":")
    action = parts[1] if len(parts) > 1 else "view"
    section = _normalize_server_info_section(parts[2] if len(parts) > 2 else SERVER_INFO_DEFAULT_SECTION)
    answer = "Refreshed." if action == "refresh" else "Opened."

    bot.answer_callback_query(call.id, answer)
    bot.edit_message_text(
        _build_server_info_text(section),
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=_build_server_info_markup(section),
        parse_mode='Markdown',
    )


def handle_server_info_refresh(call):
    handle_server_info_callback(call)
