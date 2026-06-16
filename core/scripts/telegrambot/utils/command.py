import telebot
import subprocess
import json
import os
import shlex
from dotenv import load_dotenv
from telebot import types

load_dotenv()


def _env_int(name, default, minimum=1):
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default
    return max(minimum, value)


API_TOKEN = os.getenv('API_TOKEN')
ADMIN_USER_IDS = json.loads(os.getenv('ADMIN_USER_IDS'))
CLI_PATH = '/etc/dijiq/core/cli.py'
BACKUP_DIRECTORY = '/opt/hysbackup'
BOT_WORKER_THREADS = _env_int("BOT_WORKER_THREADS", 8)
bot = telebot.TeleBot(API_TOKEN, threaded=True, num_threads=BOT_WORKER_THREADS)

def run_cli_command(command):
    try:
        args = shlex.split(command)
        result = subprocess.check_output(args, stderr=subprocess.STDOUT)
        return result.decode('utf-8').strip()
    except subprocess.CalledProcessError as e:
        return f'Error: {e.output.decode("utf-8")}'

def is_admin(user_id):
    return user_id in ADMIN_USER_IDS
