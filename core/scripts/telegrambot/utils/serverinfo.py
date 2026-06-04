from dotenv import load_dotenv
from telebot import types
from utils.command import *


def _build_server_info_markup():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔄 Refresh", callback_data="server_info:refresh"))
    return markup


def _build_server_info_text():
    command = f"python3 {CLI_PATH} server-info"
    return run_cli_command(command)


@bot.message_handler(func=lambda message: is_admin(message.from_user.id) and message.text == '📊 Server Info')
def server_info(message):
    bot.send_chat_action(message.chat.id, 'typing')
    bot.reply_to(message, _build_server_info_text(), reply_markup=_build_server_info_markup(), parse_mode='Markdown')


@bot.callback_query_handler(func=lambda call: call.data == "server_info:refresh")
def handle_server_info_refresh(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "Unauthorized.")
        return

    bot.answer_callback_query(call.id, "Refreshed.")
    bot.edit_message_text(
        _build_server_info_text(),
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=_build_server_info_markup(),
        parse_mode='Markdown',
    )
