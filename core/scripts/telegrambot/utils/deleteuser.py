from telebot import types
from utils.command import bot, is_admin
from utils.common import create_main_markup
from utils.api_client import APIClient


@bot.callback_query_handler(func=lambda call: call.data == "cancel_delete")
def handle_cancel_delete(call):
    bot.edit_message_text("Operation canceled.", chat_id=call.message.chat.id, message_id=call.message.message_id)
    create_main_markup(call.message)

@bot.message_handler(func=lambda message: is_admin(message.from_user.id) and message.text == '❌ Delete User')
def delete_user(message):
    markup = types.InlineKeyboardMarkup()
    cancel_button = types.InlineKeyboardButton("❌ Cancel", callback_data="cancel_delete")
    markup.add(cancel_button)
    
    msg = bot.reply_to(message, "Enter username:", reply_markup=markup)
    bot.register_next_step_handler(msg, process_delete_user)

def process_delete_user(message):
    username = message.text.strip().lower()
    
    if not username:
        bot.reply_to(message, "Username cannot be empty. Operation canceled.", reply_markup=create_main_markup(is_admin=True))
        return
    
    # Use API client to delete the user
    api_client = APIClient()
    
    # Just attempt to delete the user directly
    bot.send_chat_action(message.chat.id, 'typing')
    result = api_client.delete_user(username)

    if result is None:
        bot.reply_to(message, f"Error: Failed to delete user '{username}'. They may not exist.", reply_markup=create_main_markup(is_admin=True))
    else:
        bot.reply_to(message, f"User '{username}' removed successfully.", reply_markup=create_main_markup(is_admin=True))
