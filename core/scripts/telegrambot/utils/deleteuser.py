import requests
import json
import os
from dotenv import load_dotenv
from telebot import types
from utils.command import bot, is_admin
from utils.common import create_main_markup

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
    
    def delete_user(self, username):
        try:
            user_endpoint = f"{self.users_endpoint}{username}"
            response = requests.delete(user_endpoint, headers=self.headers)
            response.raise_for_status()
            
            try:
                return response.json()
            except json.JSONDecodeError:
                return "User deleted successfully."
                
        except requests.exceptions.RequestException as e:
            print(f"Error deleting user: {e}")
            if e.response and e.response.status_code == 404:
                return f"Error: User '{username}' not found."
            return f"Error: Failed to delete user. {str(e)}"


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
    
    # Check if there was an error message returned
    if isinstance(result, str) and result.startswith("Error:"):
        bot.reply_to(message, result, reply_markup=create_main_markup(is_admin=True))
    else:
        bot.reply_to(message, f"User '{username}' removed successfully.", reply_markup=create_main_markup(is_admin=True))