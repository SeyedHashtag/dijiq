#show and edituser file

import qrcode
import io
import json
import os
import requests
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
    
    def get_user(self, username):
        """Get user details using API endpoint"""
        try:
            user_endpoint = f"{self.users_endpoint}{username}"
            response = requests.get(user_endpoint, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error getting user details: {e}")
            if e.response and e.response.status_code == 404:
                return {"error": f"User '{username}' not found."}
            return {"error": f"Failed to get user details: {str(e)}"}
    
    def update_user(self, username, data):
        """Update user using API endpoint with PATCH"""
        try:
            user_endpoint = f"{self.users_endpoint}{username}"
            
            headers = self.headers.copy()
            headers['Content-Type'] = 'application/json'
            
            response = requests.patch(user_endpoint, headers=headers, json=data)
            response.raise_for_status()
            
            try:
                return response.json()
            except json.JSONDecodeError:
                return {"message": "User updated successfully."}
                
        except requests.exceptions.RequestException as e:
            print(f"Error updating user: {e}")
            if e.response and e.response.status_code == 404:
                return {"error": f"User '{username}' not found."}
            return {"error": f"Failed to update user: {str(e)}"}
    
    def reset_user(self, username):
        """Reset user traffic data"""
        return self.update_user(username, {
            "renew_creation_date": True,
            "blocked": False
        })
    
    def get_user_uri(self, username):
        try:
            user_uri_endpoint = f"{self.base_url}api/v1/users/{username}/uri"
            response = requests.get(user_uri_endpoint, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error getting user URI: {e}")
            return None


@bot.callback_query_handler(func=lambda call: call.data == "cancel_show_user")
def handle_cancel_show_user(call):
    bot.edit_message_text("Operation canceled.", chat_id=call.message.chat.id, message_id=call.message.message_id)
    create_main_markup(call.message)

@bot.message_handler(func=lambda message: is_admin(message.from_user.id) and message.text == '👤 Show User')
def show_user(message):
    markup = types.InlineKeyboardMarkup()
    cancel_button = types.InlineKeyboardButton("❌ Cancel", callback_data="cancel_show_user")
    markup.add(cancel_button)
    
    msg = bot.reply_to(message, "Enter username:", reply_markup=markup)
    bot.register_next_step_handler(msg, process_show_user)

def process_show_user(message):
    username = message.text.strip().lower()
    bot.send_chat_action(message.chat.id, 'typing')
    
    # Use API client to get user details directly
    api_client = APIClient()
    
    # Just attempt to get the user directly
    user_details = api_client.get_user(username)
    
    if "error" in user_details:
        bot.reply_to(message, user_details["error"])
        return
    
    # Use the provided username directly
    actual_username = username
    
    try:
        upload_bytes = user_details.get('upload_bytes')
        download_bytes = user_details.get('download_bytes')
        status = user_details.get('status', 'Unknown')

        if upload_bytes is None or download_bytes is None:
            traffic_message = "**Traffic Data:**\nUser not active or no traffic data available."
        else:
            upload_gb = upload_bytes / (1024 ** 3)  # Convert bytes to GB
            download_gb = download_bytes / (1024 ** 3)  # Convert bytes to GB
            totalusage = upload_gb + download_gb
            
            traffic_message = (
                f"🔼 Upload: {upload_gb:.2f} GB\n"
                f"🔽 Download: {download_gb:.2f} GB\n"
                f"📊 Total Usage: {totalusage:.2f} GB\n"
                f"🌐 Status: {status}"
            )
    except Exception as e:
        bot.reply_to(message, f"Failed to process user data: {str(e)}")
        return

    formatted_details = (
        f"\n🆔 Name: {actual_username}\n"
        f"📊 Traffic Limit: {user_details['max_download_bytes'] / (1024 ** 3):.2f} GB\n"
        f"📅 Days: {user_details['expiration_days']}\n"
        f"⏳ Creation: {user_details['account_creation_date']}\n"
        f"💡 Blocked: {user_details['blocked']}\n\n"
        f"{traffic_message}"
    )
    
    # Get user URI from the API client
    user_uri_data = api_client.get_user_uri(actual_username)
    
    if not user_uri_data or 'normal_sub' not in user_uri_data:
        bot.reply_to(message, f"Error: Could not retrieve subscription URL for user '{actual_username}'. Check API configuration.")
        return
    
    sub_url = user_uri_data['normal_sub']
    
    # Create QR code for subscription URL
    qr_code = qrcode.make(sub_url)
    bio = io.BytesIO()
    qr_code.save(bio, 'PNG')
    bio.seek(0)

    markup = types.InlineKeyboardMarkup(row_width=3)
    markup.add(types.InlineKeyboardButton("Reset User", callback_data=f"reset_user:{actual_username}"))
    markup.add(types.InlineKeyboardButton("Edit Username", callback_data=f"edit_username:{actual_username}"),
               types.InlineKeyboardButton("Edit Traffic Limit", callback_data=f"edit_traffic:{actual_username}"))
    markup.add(types.InlineKeyboardButton("Edit Expiration Days", callback_data=f"edit_expiration:{actual_username}"),
               types.InlineKeyboardButton("Renew Password", callback_data=f"renew_password:{actual_username}"))
    markup.add(types.InlineKeyboardButton("Renew Creation Date", callback_data=f"renew_creation:{actual_username}"),
               types.InlineKeyboardButton("Block User", callback_data=f"block_user:{actual_username}"))

    caption = f"{formatted_details}\n\nSubscription URL: `{sub_url}`"
    
    bot.send_photo(
        message.chat.id,
        bio,
        caption=caption,
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_') or call.data.startswith('renew_') or call.data.startswith('block_') or call.data.startswith('reset_'))
def handle_edit_callback(call):
    action, username = call.data.split(':')
    api_client = APIClient()
    
    if action == 'edit_username':
        msg = bot.send_message(call.message.chat.id, f"Enter new username for {username}:")
        bot.register_next_step_handler(msg, process_edit_username, username)
    elif action == 'edit_traffic':
        msg = bot.send_message(call.message.chat.id, f"Enter new traffic limit (GB) for {username}:")
        bot.register_next_step_handler(msg, process_edit_traffic, username)
    elif action == 'edit_expiration':
        msg = bot.send_message(call.message.chat.id, f"Enter new expiration days for {username}:")
        bot.register_next_step_handler(msg, process_edit_expiration, username)
    elif action == 'renew_password':
        # Use API to renew password
        result = api_client.update_user(username, {"renew_password": True})
        if "error" in result:
            bot.send_message(call.message.chat.id, result["error"])
        else:
            bot.send_message(call.message.chat.id, f"Password for user '{username}' renewed successfully.")
    elif action == 'renew_creation':
        # Use API to renew creation date
        result = api_client.update_user(username, {"renew_creation_date": True})
        if "error" in result:
            bot.send_message(call.message.chat.id, result["error"])
        else:
            bot.send_message(call.message.chat.id, f"Creation date for user '{username}' renewed successfully.")
    elif action == 'block_user':
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("True", callback_data=f"confirm_block:{username}:true"),
                   types.InlineKeyboardButton("False", callback_data=f"confirm_block:{username}:false"))
        bot.send_message(call.message.chat.id, f"Set block status for {username}:", reply_markup=markup)
    elif action == 'reset_user':
        # Use API to reset user
        result = api_client.reset_user(username)
        if "error" in result:
            bot.send_message(call.message.chat.id, result["error"])
        else:
            bot.send_message(call.message.chat.id, f"User '{username}' reset successfully.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('confirm_block:'))
def handle_block_confirmation(call):
    _, username, block_status = call.data.split(':')
    api_client = APIClient()
    
    # Use API to set block status
    is_blocked = block_status == 'true'
    result = api_client.update_user(username, {"blocked": is_blocked})
    
    if "error" in result:
        bot.send_message(call.message.chat.id, result["error"])
    else:
        status = "blocked" if is_blocked else "unblocked"
        bot.send_message(call.message.chat.id, f"User '{username}' {status} successfully.")

def process_edit_username(message, username):
    new_username = message.text.strip()
    
    # Validate the new username is not empty
    if not new_username:
        bot.reply_to(message, "Username cannot be empty.")
        return
    
    api_client = APIClient()
    result = api_client.update_user(username, {"new_username": new_username})
    
    if "error" in result:
        bot.reply_to(message, result["error"])
    else:
        bot.reply_to(message, f"Username updated from '{username}' to '{new_username}' successfully.")

def process_edit_traffic(message, username):
    try:
        new_traffic_limit = int(message.text.strip())
        api_client = APIClient()
        result = api_client.update_user(username, {"new_traffic_limit": new_traffic_limit})
        
        if "error" in result:
            bot.reply_to(message, result["error"])
        else:
            bot.reply_to(message, f"Traffic limit for user '{username}' updated to {new_traffic_limit} GB successfully.")
    except ValueError:
        bot.reply_to(message, "Invalid traffic limit. Please enter a number.")

def process_edit_expiration(message, username):
    try:
        new_expiration_days = int(message.text.strip())
        api_client = APIClient()
        result = api_client.update_user(username, {"new_expiration_days": new_expiration_days})
        
        if "error" in result:
            bot.reply_to(message, result["error"])
        else:
            bot.reply_to(message, f"Expiration days for user '{username}' updated to {new_expiration_days} days successfully.")
    except ValueError:
        bot.reply_to(message, "Invalid expiration days. Please enter a number.")
