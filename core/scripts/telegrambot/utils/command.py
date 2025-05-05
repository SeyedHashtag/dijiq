import telebot
import subprocess
import json
import os
import shlex
from dotenv import load_dotenv
from telebot import types

load_dotenv()

API_TOKEN = os.getenv('API_TOKEN')
ADMIN_USER_IDS = json.loads(os.getenv('ADMIN_USER_IDS'))
CLI_PATH = '/etc/dijiq/core/cli.py'
BACKUP_DIRECTORY = '/opt/hysbackup'
bot = telebot.TeleBot(API_TOKEN)

def run_cli_command(command):
    try:
        args = shlex.split(command)
        result = subprocess.check_output(args, stderr=subprocess.STDOUT)
        return result.decode('utf-8').strip()
    except subprocess.CalledProcessError as e:
        return f'Error: {e.output.decode("utf-8")}'

def is_admin(user_id):
    return user_id in ADMIN_USER_IDS

# Dictionary to track if users have seen the language selection prompt
first_time_users = {}

@bot.message_handler(commands=['start', 'help'])
def start_command(message):
    """Handle /start and /help commands"""
    user_id = message.from_user.id
    
    # Check if this is the first time the user is interacting with the bot
    if user_id not in first_time_users:
        # Show language selection first
        from utils.language import show_language_selection
        show_language_selection(message.chat.id)
        
        # Mark user as having seen the language selection
        first_time_users[user_id] = True
    else:
        # Show normal welcome for returning users
        from utils.common import send_welcome
        send_welcome(message)

@bot.message_handler(func=lambda message: message.text == '🌐 Language' or message.text == '🌐 زبان')
def language_button_handler(message):
    """Handle language button click"""
    from utils.language import show_language_selection
    show_language_selection(message.chat.id)