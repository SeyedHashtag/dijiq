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
        self.sub_url = os.getenv('SUB_URL')
        
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
    
    def add_user(self, username, traffic_limit, expiration_days):
        data = {
            "username": username,
            "traffic_limit": traffic_limit,
            "expiration_days": expiration_days
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
    
    def get_subscription_url(self, username):
        if not self.sub_url:
            return None
        
        # Remove trailing slash if present
        sub_url = self.sub_url.rstrip('/')
        return f"{sub_url}/{username}#Hysteria2"


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
        api_client = APIClient()
        
        bot.send_chat_action(message.chat.id, 'typing')
        result = api_client.add_user(username, traffic_limit, expiration_days)

        if not result:
            bot.reply_to(message, "Failed to add user. Please check API connection and try again.", reply_markup=create_main_markup())
            return

        # Generate subscription URL
        sub_url = api_client.get_subscription_url(username)
        
        if not sub_url:
            bot.reply_to(message, f"User '{username}' created successfully, but failed to generate subscription URL. Check SUB_URL configuration.", reply_markup=create_main_markup())
            return

        # Generate QR code for subscription URL
        qr_code = qrcode.make(sub_url)
        bio = io.BytesIO()
        qr_code.save(bio, 'PNG')
        bio.seek(0)
        
        # Create success message
        success_message = f"User '{username}' added successfully!\n"
        success_message += f"Traffic limit: {traffic_limit} GB\n"
        success_message += f"Expiration days: {expiration_days}\n\n"
        success_message += f"Subscription URL: `{sub_url}`"
        
        bot.send_photo(message.chat.id, photo=bio, caption=success_message, parse_mode="Markdown", reply_markup=create_main_markup())

    except ValueError:
        bot.reply_to(message, "Invalid expiration days. Please enter a number:", reply_markup=create_cancel_markup(back_step=process_add_user_step2))
        bot.register_next_step_handler(message, process_add_user_step3, username, traffic_limit)
