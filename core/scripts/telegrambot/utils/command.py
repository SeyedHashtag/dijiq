import telebot
import subprocess
import json
import os
import shlex
from dotenv import load_dotenv
from telebot import types

load_dotenv()

API_TOKEN = os.getenv('API_TOKEN')
if not API_TOKEN:
    raise ValueError("No API_TOKEN found in environment variables")

ADMIN_USER_IDS = json.loads(os.getenv('ADMIN_USER_IDS', '[]'))
CLI_PATH = '/etc/hysteria/core/cli.py'
BACKUP_DIRECTORY = '/opt/hysbackup'

print(f"Initializing bot with token: {API_TOKEN[:6]}...{API_TOKEN[-4:]}")
bot = telebot.TeleBot(API_TOKEN)

MERCHANT_ID = os.getenv('CRYPTOMUS_MERCHANT_ID')
PAYMENT_API_KEY = os.getenv('CRYPTOMUS_API_KEY')

def run_cli_command(command):
    try:
        args = shlex.split(command)
        result = subprocess.check_output(args, stderr=subprocess.STDOUT)
        return result.decode('utf-8').strip()
    except subprocess.CalledProcessError as e:
        return get_text("en", "cli_error").format(error=e.output.decode("utf-8"))

def is_admin(user_id):
    return user_id in ADMIN_USER_IDS
