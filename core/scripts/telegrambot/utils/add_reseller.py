from telebot import types
from .bot import bot
import json
import os

DATA_FILE = "resellers.json"

@bot.message_handler(func=lambda message: message.text == "Add Reseller")
def add_reseller_handler(message):
    bot.reply_to(message, "Please enter the reseller's Telegram numerical ID:")
    bot.register_next_step_handler(message, get_reseller_id)

def get_reseller_id(message):
    try:
        reseller_id = int(message.text)
        if not os.path.exists(DATA_FILE):
            with open(DATA_FILE, "w") as f:
                json.dump([], f)
        
        with open(DATA_FILE, "r+") as f:
            data = json.load(f)
            if reseller_id in data:
                bot.reply_to(message, "Reseller already exists.")
            else:
                data.append(reseller_id)
                f.seek(0)
                json.dump(data, f, indent=4)
                bot.reply_to(message, "Reseller added successfully.")
    except ValueError:
        bot.reply_to(message, "Invalid ID. Please enter a numerical ID.")
