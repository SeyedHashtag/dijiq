#show and edituser file

import qrcode
import io
import json
import os
import requests
from dotenv import load_dotenv
from telebot import types
from utils.command import bot, is_admin, CLI_PATH, run_cli_command
from utils.common import create_main_markup


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
    
    def get_subscription_url(self, username):
        if not self.sub_url:
            return None
        
        # Remove trailing slash if present
        sub_url = self.sub_url.rstrip('/')
        return f"{sub_url}/{username}#Hysteria2"


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
    
    # Still need to use CLI for getting URI because API endpoint for URI might not exist
    combined_command = f"python3 {CLI_PATH} show-user-uri -u {actual_username} -ip 4 -s -n"
    combined_result = run_cli_command(combined_command)

    if "Error" in combined_result or "Invalid" in combined_result:
        bot.reply_to(message, combined_result)
        return

    result_lines = combined_result.strip().split('\n')
    
    uri_v4 = ""
    singbox_sublink = ""
    normal_sub_sublink = ""

    for line in result_lines:
        line = line.strip()
        if line.startswith("hy2://"):
            uri_v4 = line
        elif line.startswith("Singbox Sublink:"):
            singbox_sublink = result_lines[result_lines.index(line) + 1].strip()
        elif line.startswith("Normal-SUB Sublink:"):
            normal_sub_sublink = result_lines[result_lines.index(line) + 1].strip()

    if not uri_v4:
        bot.reply_to(message, "No valid URI found.")
        return
    
    # Get subscription URL from the API client
    sub_url = api_client.get_subscription_url(actual_username)
    if sub_url:
        singbox_sublink = sub_url

    qr_v4 = qrcode.make(uri_v4)
    bio_v4 = io.BytesIO()
    qr_v4.save(bio_v4, 'PNG')
    bio_v4.seek(0)

    markup = types.InlineKeyboardMarkup(row_width=3)
    markup.add(types.InlineKeyboardButton("Reset User", callback_data=f"reset_user:{actual_username}"),
               types.InlineKeyboardButton("IPv6-URI", callback_data=f"ipv6_uri:{actual_username}"))
    markup.add(types.InlineKeyboardButton("Edit Username", callback_data=f"edit_username:{actual_username}"),
               types.InlineKeyboardButton("Edit Traffic Limit", callback_data=f"edit_traffic:{actual_username}"))
    markup.add(types.InlineKeyboardButton("Edit Expiration Days", callback_data=f"edit_expiration:{actual_username}"),
               types.InlineKeyboardButton("Renew Password", callback_data=f"renew_password:{actual_username}"))
    markup.add(types.InlineKeyboardButton("Renew Creation Date", callback_data=f"renew_creation:{actual_username}"),
               types.InlineKeyboardButton("Block User", callback_data=f"block_user:{actual_username}"))

    caption = f"{formatted_details}\n\n**IPv4 URI:**\n\n`{uri_v4}`"
    if singbox_sublink:
        caption += f"\n\n**SingBox SUB:**\n{singbox_sublink}"
    if normal_sub_sublink:
        caption += f"\n\n**Normal SUB:**\n{normal_sub_sublink}"

    bot.send_photo(
        message.chat.id,
        bio_v4,
        caption=caption,
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_') or call.data.startswith('renew_') or call.data.startswith('block_') or call.data.startswith('reset_') or call.data.startswith('ipv6_'))
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
    elif action == 'ipv6_uri':
        # Still need to use CLI for getting URI because API endpoint might not exist
        command = f"python3 {CLI_PATH} show-user-uri -u {username} -ip 6"
        result = run_cli_command(command)
        if "Error" in result or "Invalid" in result:
            bot.send_message(call.message.chat.id, result)
            return
        
        uri_v6 = result.split('\n')[-1].strip()
        qr_v6 = qrcode.make(uri_v6)
        bio_v6 = io.BytesIO()
        qr_v6.save(bio_v6, 'PNG')
        bio_v6.seek(0)
        
        bot.send_photo(
            call.message.chat.id,
            bio_v6,
            caption=f"**IPv6 URI for {username}:**\n\n`{uri_v6}`",
            parse_mode="Markdown"
        )

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
