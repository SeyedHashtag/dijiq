from telebot import types
from .bot import bot
from .add_reseller import add_reseller_handler

def create_reseller_markup():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("Add Reseller", "Back")
    return markup

@bot.message_handler(func=lambda message: message.text == "Reseller")
def reseller_menu(message):
    markup = create_reseller_markup()
    bot.reply_to(message, "Reseller management:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "Back")
def back_to_main_menu(message):
    from .common import create_main_markup
    markup = create_main_markup()
    bot.reply_to(message, "Returning to main menu.", reply_markup=markup)