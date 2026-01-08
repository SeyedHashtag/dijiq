import qrcode
import io
import json
import os
import requests
from telebot import types
from utils.command import *
from utils.common import create_main_markup
from dotenv import load_dotenv


class APIClient:
    def __init__(self):
        load_dotenv()
        
        self.base_url = os.getenv('URL')
        self.token = os.getenv('TOKEN')
        
        if not self.base_url or not self.token:
            print("Warning: API URL or TOKEN not found in environment variables.")
            return
            
        if self.base_url and not self.base_url.endswith('/'):
            self.base_url += '/'
            
        self.users_endpoint = f"{self.base_url}api/v1/users/"
        
        self.headers = {
            'accept': 'application/json',
            'Authorization': self.token
        }
    
    def get_users(self):
        try:
            response = requests.get(self.users_endpoint, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching users: {e}")
            return None

    def get_user(self, username):
        try:
            user_endpoint = f"{self.users_endpoint}{username}"
            response = requests.get(user_endpoint, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching user {username}: {e}")
            return None
    
    def add_user(self, username, traffic_limit, expiration_days, unlimited=False):
        data = {
            "username": username,
            "traffic_limit": traffic_limit,
            "expiration_days": expiration_days,
            "unlimited": unlimited
        }
        
        post_headers = self.headers.copy()
        post_headers['Content-Type'] = 'application/json'
        
        try:
            response = requests.post(
                self.users_endpoint, 
                headers=post_headers, 
                json=data
            )
            response.raise_for_status()
            
            try:
                return response.json()
            except json.JSONDecodeError:
                return response.text
                
        except requests.exceptions.RequestException as e:
            print(f"Error adding user: {e}")
            return None
    
    def get_user_uri(self, username):
        try:
            user_uri_endpoint = f"{self.base_url}api/v1/users/{username}/uri"
            response = requests.get(user_uri_endpoint, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error getting user URI: {e}")
            return None


def create_cancel_markup(back_step=None):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    if back_step:
        markup.row(types.KeyboardButton("⬅️ Back"))
    markup.row(types.KeyboardButton("❌ Cancel"))
    return markup

@bot.message_handler(func=lambda message: is_admin(message.from_user.id) and message.text == '➕ Add User')
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

    api_client = APIClient()
    users = api_client.get_users()

    if users is None:
        bot.reply_to(message, "Error connecting to API. Please check API configuration and try again.", reply_markup=create_main_markup())
        return

    try:
        existing_usernames = [user['username'].lower() for user in users] if users else []

        if username.lower() in existing_usernames:
            bot.reply_to(message, f"Username '{username}' already exists. Please choose a different username:", reply_markup=create_cancel_markup())
            bot.register_next_step_handler(message, process_add_user_step1)
            return
    except (KeyError, TypeError):
        bot.reply_to(message, "Error processing user data. Adding new user.", reply_markup=create_cancel_markup())

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
        
        markup = types.InlineKeyboardMarkup()
        markup.row(types.InlineKeyboardButton("✅ Yes", callback_data=f"unlimited_user_choice:yes:{username}:{traffic_limit}:{expiration_days}"),
                   types.InlineKeyboardButton("❌ No", callback_data=f"unlimited_user_choice:no:{username}:{traffic_limit}:{expiration_days}"))
        bot.reply_to(message, "Should this user have unlimited access?", reply_markup=markup)

    except ValueError:
        bot.reply_to(message, "Invalid expiration days. Please enter a number:", reply_markup=create_cancel_markup(back_step=process_add_user_step2))
        bot.register_next_step_handler(message, process_add_user_step3, username, traffic_limit)

@bot.callback_query_handler(func=lambda call: call.data.startswith("unlimited_user_choice:"))
def process_add_user_step4(call):
    try:
        bot.answer_callback_query(call.id)
        _, choice, username, traffic_limit, expiration_days = call.data.split(':')
        traffic_limit, expiration_days = int(traffic_limit), int(expiration_days)
        
        unlimited = choice == 'yes'
        
        api_client = APIClient()
        
        bot.send_chat_action(call.message.chat.id, 'typing')
        result = api_client.add_user(username, traffic_limit, expiration_days, unlimited)

        if not result:
            bot.edit_message_text(
                "Failed to add user. Please check API connection and try again.",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=create_main_markup()
            )
            return

        # Get user URI from API
        user_uri_data = api_client.get_user_uri(username)
        if not user_uri_data or 'normal_sub' not in user_uri_data:
            bot.edit_message_text(
                f"User '{username}' created successfully, but failed to get subscription URI. Check API configuration.",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=create_main_markup()
            )
            return

        sub_url = user_uri_data['normal_sub']

        # Generate QR code for subscription URL
        qr_code = qrcode.make(sub_url)
        bio = io.BytesIO()
        qr_code.save(bio, 'PNG')
        bio.seek(0)
        
        # Create success message
        unlimited_text = "Yes" if unlimited else "No"
        success_message = f"User '{username}' added successfully!\n"
        success_message += f"Traffic limit: {traffic_limit} GB\n"
        success_message += f"Expiration days: {expiration_days}\n"
        success_message += f"Unlimited Access: {unlimited_text}\n\n"
        success_message += f"Subscription URL: {sub_url}"
        
        bot.send_photo(call.message.chat.id, photo=bio, caption=success_message, parse_mode="Markdown", reply_markup=create_main_markup())

    except Exception as e:
        bot.edit_message_text(
            f"? Error adding user: {str(e)}",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=create_main_markup()
        )
