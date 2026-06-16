import telebot
import subprocess
import json
import os
import shlex
from dotenv import load_dotenv
from telebot import types
from utils.bot_logging import configure_logging, get_telegram_worker_count, instrument_bot
from utils.telegram_safe import install_safe_telegram_methods

load_dotenv()
configure_logging()

API_TOKEN = os.getenv('API_TOKEN')
ADMIN_USER_IDS = json.loads(os.getenv('ADMIN_USER_IDS'))
CLI_PATH = '/etc/dijiq/core/cli.py'
BACKUP_DIRECTORY = '/opt/hysbackup'
bot = telebot.TeleBot(API_TOKEN, threaded=True, num_threads=get_telegram_worker_count())
install_safe_telegram_methods(bot)
instrument_bot(bot)

def run_cli_command(command):
    try:
        args = shlex.split(command)
        result = subprocess.check_output(args, stderr=subprocess.STDOUT)
        return result.decode('utf-8').strip()
    except subprocess.CalledProcessError as e:
        return f'Error: {e.output.decode("utf-8")}'

def is_admin(user_id):
    return user_id in ADMIN_USER_IDS
