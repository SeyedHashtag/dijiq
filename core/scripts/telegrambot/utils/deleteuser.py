from dotenv import load_dotenv
from telebot import types
from utils.command import *
from utils.common import *
from utils.api_client import APIClient


@bot.callback_query_handler(func=lambda call: call.data == "cancel_delete")
def handle_cancel_delete(call):
    bot.edit_message_text("Operation canceled.", chat_id=call.message.chat.id, message_id=call.message.message_id)
    create_main_markup(call.message)

@bot.message_handler(func=lambda message: is_admin(message.from_user.id) and message.text == 'Delete User')
def delete_user(message):
    markup = types.InlineKeyboardMarkup()
    cancel_button = types.InlineKeyboardButton("❌ Cancel", callback_data="cancel_delete")
    markup.add(cancel_button)
    
    msg = bot.reply_to(message, "Enter username:", reply_markup=markup)
    bot.register_next_step_handler(msg, process_delete_user)

def process_delete_user(message):
    username = message.text.strip().lower()
    
    try:
        # Initialize API client
        api_client = APIClient()
        
        # Call API to remove user
        # Since we don't have a remove_user method in the API client yet, we'll add it
        response = api_remove_user(username)
        
        if response:
            bot.reply_to(message, f"✅ User {username} has been deleted successfully.", reply_markup=create_main_markup())
        else:
            bot.reply_to(message, f"❌ Failed to delete user {username}.", reply_markup=create_main_markup())
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}", reply_markup=create_main_markup())

def api_remove_user(username):
    """Temporary function to remove user via CLI until API endpoint is fully implemented"""
    command = f"python3 {CLI_PATH} remove-user -u {username}"
    result = run_cli_command(command)
    
    if "successfully" in result.lower():
        return True
    return False