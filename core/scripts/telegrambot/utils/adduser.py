import qrcode
import io
import json
from telebot import types
from utils.command import *
from utils.common import create_main_markup
from utils.api_client import APIClient


def create_cancel_markup(back_step=None):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    if back_step:
        markup.row(types.KeyboardButton("⬅️ Back"))
    markup.row(types.KeyboardButton("❌ Cancel"))
    return markup

@bot.message_handler(func=lambda message: is_admin(message.from_user.id) and message.text == 'Add User')
def add_user(message):
    msg = bot.reply_to(message, "Enter username:", reply_markup=create_cancel_markup())
    bot.register_next_step_handler(msg, process_add_user_step1)

def process_add_user_step1(message):
    if message.text == "❌ Cancel":
        bot.reply_to(message, "Process canceled.", reply_markup=create_main_markup())
        return

    username = message.text.strip()
    if username == "":
        bot.reply_to(message, "Username cannot be empty. Please enter a valid username.", reply_markup=create_cancel_markup())
        bot.register_next_step_handler(message, process_add_user_step1)
        return

    try:
        # Initialize API client
        api_client = APIClient()
        
        # Get list of users from API
        users = api_client.get_users()
        existing_users = {user.get('username', '').lower() for user in users}

        if username.lower() in existing_users:
            bot.reply_to(message, f"Username '{username}' already exists. Please choose a different username:", reply_markup=create_cancel_markup())
            bot.register_next_step_handler(message, process_add_user_step1)
            return
    except Exception as e:
        if "No such file or directory" in str(e) or "404" in str(e):
            bot.reply_to(message, "User list not available. Adding the first user.", reply_markup=create_cancel_markup())
        else:
            bot.reply_to(message, f"Error retrieving user list: {str(e)}. Please try again later.")
            bot.send_message(message.chat.id, "Returning to main menu...", reply_markup=create_main_markup())
            return

    msg = bot.reply_to(message, "Enter traffic limit (GB):", reply_markup=create_cancel_markup(back_step=process_add_user_step1))
    bot.register_next_step_handler(msg, process_add_user_step2, username)

def process_add_user_step2(message, username):
    if message.text == "❌ Cancel":
        bot.reply_to(message, "Process canceled.", reply_markup=create_main_markup())
        return
    if message.text == "⬅️ Back":
        msg = bot.reply_to(message, "Enter username:", reply_markup=create_cancel_markup())
        bot.register_next_step_handler(msg, process_add_user_step1)
        return

    try:
        traffic_limit = int(message.text.strip())
        msg = bot.reply_to(message, "Enter expiration days:", reply_markup=create_cancel_markup(back_step=process_add_user_step2))
        bot.register_next_step_handler(msg, process_add_user_step3, username, traffic_limit)
    except ValueError:
        bot.reply_to(message, "Invalid traffic limit. Please enter a number:", reply_markup=create_cancel_markup(back_step=process_add_user_step1))
        bot.register_next_step_handler(message, process_add_user_step2, username)

def process_add_user_step3(message, username, traffic_limit):
    if message.text == "❌ Cancel":
        bot.reply_to(message, "Process canceled.", reply_markup=create_main_markup())
        return
    if message.text == "⬅️ Back":
        msg = bot.reply_to(message, "Enter traffic limit (GB):", reply_markup=create_cancel_markup(back_step=process_add_user_step1))
        bot.register_next_step_handler(msg, process_add_user_step2, username)
        return

    try:
        expiration_days = int(message.text.strip())
        lower_username = username.lower()
        
        try:
            # Initialize API client
            api_client = APIClient()
            
            # Add user via API
            result = api_client.add_user(
                username=lower_username,
                traffic_limit=traffic_limit,
                expiration_days=expiration_days
            )
            
            # Display success message
            success_message = f"✅ User {lower_username} added successfully\n"
            success_message += f"Traffic limit: {traffic_limit} GB\n"
            success_message += f"Expiration days: {expiration_days}\n"
            
            bot.send_chat_action(message.chat.id, 'typing')
            
            # Use CLI for QR code generation as it might not be in the API yet
            qr_command = f"python3 {CLI_PATH} show-user-uri -u {lower_username} -ip 4"
            qr_result = run_cli_command(qr_command).replace("IPv4:\n", "").strip()

            if not qr_result:
                bot.reply_to(message, success_message + "\nFailed to generate QR code.", reply_markup=create_main_markup())
                return

            qr_v4 = qrcode.make(qr_result)
            bio_v4 = io.BytesIO()
            qr_v4.save(bio_v4, 'PNG')
            bio_v4.seek(0)
            caption = f"{success_message}\n\n`{qr_result}`"
            bot.send_photo(message.chat.id, photo=bio_v4, caption=caption, parse_mode="Markdown", reply_markup=create_main_markup())
            
        except Exception as e:
            bot.reply_to(message, f"❌ Error adding user: {str(e)}", reply_markup=create_main_markup())
            
    except ValueError:
        bot.reply_to(message, "Invalid expiration days. Please enter a number:", reply_markup=create_cancel_markup(back_step=process_add_user_step2))
        bot.register_next_step_handler(message, process_add_user_step3, username, traffic_limit)
