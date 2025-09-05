import json
from pathlib import Path
from telebot import types
from utils.command import *
from utils.common import create_main_markup


def create_reseller_markup():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.row(types.KeyboardButton('Add Reseller'))
    markup.row(types.KeyboardButton('⬅️ Back'), types.KeyboardButton('❌ Cancel'))
    return markup


@bot.message_handler(func=lambda message: is_admin(message.from_user.id) and message.text == 'Reseller')
def reseller_menu(message):
    bot.reply_to(message, "Reseller Menu:", reply_markup=create_reseller_markup())


@bot.message_handler(func=lambda message: is_admin(message.from_user.id) and message.text == '⬅️ Back')
def reseller_back(message):
    # Generic back to main menu
    bot.reply_to(message, "Back to main menu.", reply_markup=create_main_markup())


@bot.message_handler(func=lambda message: is_admin(message.from_user.id) and message.text == 'Add Reseller')
def add_reseller_start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.row(types.KeyboardButton('❌ Cancel'))
    msg = bot.reply_to(message, "Enter numerical user ID to add as reseller:", reply_markup=markup)
    bot.register_next_step_handler(msg, process_add_reseller_id)


def process_add_reseller_id(message):
    if message.text == '❌ Cancel':
        bot.reply_to(message, "Process canceled.", reply_markup=create_main_markup())
        return

    user_id_text = message.text.strip()
    if not user_id_text.isdigit():
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup.row(types.KeyboardButton('❌ Cancel'))
        msg = bot.reply_to(message, "Invalid input. Please enter a numerical user ID:", reply_markup=markup)
        bot.register_next_step_handler(msg, process_add_reseller_id)
        return

    user_id = int(user_id_text)

    data_file = Path(__file__).resolve().parents[1] / 'resellers.json'
    data_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        if data_file.exists():
            with data_file.open('r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = []

        if not isinstance(data, list):
            data = []

        if user_id in data:
            bot.reply_to(message, f"User ID {user_id} is already a reseller.", reply_markup=create_main_markup())
            return

        data.append(user_id)

        with data_file.open('w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

        bot.reply_to(message, f"User ID {user_id} added to resellers.", reply_markup=create_main_markup())
    except Exception as e:
        bot.reply_to(message, f"Error saving reseller: {str(e)}", reply_markup=create_main_markup())
