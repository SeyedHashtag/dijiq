import qrcode
import io
import json
import os
import requests
from dotenv import load_dotenv
from telebot import types
from utils.command import bot
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
    
    def get_subscription_url(self, username):
        if not self.sub_url:
            return None
        
        # Remove trailing slash if present
        sub_url = self.sub_url.rstrip('/')
        return f"{sub_url}/{username}#Hysteria2"


@bot.message_handler(func=lambda message: message.text == '📱 My Configs')
def my_configs(message):
    user_id = message.from_user.id
    
    # Use API client to get all users
    api_client = APIClient()
    all_users = api_client.get_users()
    
    if all_users is None:
        bot.reply_to(message, "❌ Error retrieving configurations. Please try again later or contact support.")
        return
    
    # Find configs belonging to this user
    user_configs = []
    user_id_prefix = str(user_id) + "t"  # Format: {telegram_id}t{timestamp}
    
    try:
        # In this structure, the username is the key and user details is the value
        for username, details in all_users.items():
            if username.lower().startswith(user_id_prefix.lower()):
                user_configs.append({
                    'username': username,
                    'details': details
                })
    except Exception as e:
        bot.reply_to(message, f"❌ Error processing configuration data: {str(e)}")
        return
    
    # Check if user has any configs
    if not user_configs:
        bot.reply_to(message, "You don't have any active configurations. Use the 'Purchase Plan' or 'Test Config' options to get started.")
        return
    
    # Sort configs by creation date (newest first) if available
    try:
        user_configs.sort(key=lambda x: x['details'].get('account_creation_date', ''), reverse=True)
    except:
        pass  # If sorting fails, continue with unsorted list
    
    # Create message showing all configs with navigation buttons
    if len(user_configs) == 1:
        # Only one config, show it directly
        send_config_details(message.chat.id, user_configs[0]['username'], user_configs[0]['details'])
    else:
        # Multiple configs, create navigation
        create_config_navigation(message.chat.id, user_configs)


def create_config_navigation(chat_id, configs):
    message = "📱 Your VPN Configurations:\n\n"
    
    for i, config in enumerate(configs):
        username = config['username']
        details = config['details']
        
        # Extract status information
        is_blocked = details.get('blocked', False)
        max_gb = details.get('max_download_bytes', 0) / (1024 ** 3)
        status_emoji = "🔴" if is_blocked else "🟢"
        
        message += f"{i+1}. {status_emoji} {username} ({max_gb:.1f} GB)\n"
    
    message += "\nSelect a configuration to view details:"
    
    # Create inline buttons for each config
    markup = types.InlineKeyboardMarkup(row_width=3)
    buttons = []
    
    for i, config in enumerate(configs):
        buttons.append(types.InlineKeyboardButton(
            str(i+1), 
            callback_data=f"view_config:{config['username']}"
        ))
    
    markup.add(*buttons)
    
    bot.send_message(
        chat_id,
        message,
        reply_markup=markup
    )


def send_config_details(chat_id, username, user_details):
    api_client = APIClient()
    
    # Check if user details are already provided
    if not isinstance(user_details, dict) or "error" in user_details:
        # If not, fetch user details
        user_details = api_client.get_user(username)
        if "error" in user_details:
            bot.send_message(chat_id, f"❌ Error: {user_details['error']}")
            return
    
    try:
        # Format traffic information
        upload_bytes = user_details.get('upload_bytes', 0)
        download_bytes = user_details.get('download_bytes', 0)
        max_bytes = user_details.get('max_download_bytes', 0)
        status = user_details.get('status', 'Unknown')
        is_blocked = user_details.get('blocked', False)
        
        upload_gb = upload_bytes / (1024 ** 3)
        download_gb = download_bytes / (1024 ** 3)
        total_used_gb = upload_gb + download_gb
        max_gb = max_bytes / (1024 ** 3)
        remaining_gb = max(0, max_gb - total_used_gb)
        
        traffic_message = (
            f"🔼 Upload: {upload_gb:.2f} GB\n"
            f"🔽 Download: {download_gb:.2f} GB\n"
            f"📊 Total Usage: {total_used_gb:.2f} GB\n"
            f"⬇️ Remaining: {remaining_gb:.2f} GB\n"
            f"🌐 Status: {status}"
        )

        formatted_details = (
            f"\n🆔 Name: {username}\n"
            f"📊 Traffic Limit: {max_gb:.2f} GB\n"
            f"📅 Days: {user_details.get('expiration_days', 'Unknown')}\n"
            f"⏳ Creation: {user_details.get('account_creation_date', 'Unknown')}\n"
            f"💡 Blocked: {is_blocked}\n\n"
            f"{traffic_message}"
        )
        
        # Get subscription URL
        sub_url = api_client.get_subscription_url(username)
        
        if is_blocked:
            # If the config is blocked, show a message
            bot.send_message(
                chat_id,
                f"❌ This configuration is expired/blocked:\n{formatted_details}\n\nPlease purchase a new plan to continue.",
                parse_mode="Markdown"
            )
            return
        
        if not sub_url:
            bot.send_message(
                chat_id, 
                f"{formatted_details}\n\n❌ Could not generate subscription URL. Please contact support.",
                parse_mode="Markdown"
            )
            return
        
        # Generate QR code for the subscription URL
        qr = qrcode.make(sub_url)
        bio = io.BytesIO()
        qr.save(bio, 'PNG')
        bio.seek(0)
        
        # Create message
        caption = f"{formatted_details}\n\nSubscription URL: `{sub_url}`"
        
        # Send the message with QR code
        bot.send_photo(
            chat_id,
            photo=bio,
            caption=caption,
            parse_mode="Markdown"
        )
        
    except Exception as e:
        bot.send_message(chat_id, f"❌ Error processing configuration: {str(e)}")


@bot.callback_query_handler(func=lambda call: call.data.startswith('view_config:'))
def handle_config_selection(call):
    try:
        bot.answer_callback_query(call.id)
        username = call.data.split(':')[1]
        
        # Get user details
        api_client = APIClient()
        user_details = api_client.get_user(username)
        
        # Send config details
        send_config_details(call.message.chat.id, username, user_details)
        
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ Error: {str(e)}")