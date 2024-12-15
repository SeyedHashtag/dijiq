from telebot import types
from utils.common import create_main_markup
from utils.language import *
from utils.client_menu import *
from utils.client_handlers import *
from utils.adduser import *
from utils.backup import *
from utils.command import *
from utils.deleteuser import *
from utils.edituser import *
from utils.search import *
from utils.serverinfo import *
from utils.payment_settings import *
from utils.statistics import *
from utils.plan_management import *
from utils.help_management import *
from utils.test_mode import *
from utils.anti_spam import *

# Anti-spam handler should be first to check all non-admin messages
@bot.message_handler(func=lambda message: not is_admin(message.from_user.id), content_types=['text'])
def check_message_spam(message):
    if check_spam(message):
        return
    # Continue with normal message handling

@bot.message_handler(commands=['start'])
def send_welcome(message):
    if is_admin(message.from_user.id):
        markup = create_main_markup()
        bot.reply_to(message, "Welcome to the Admin Panel!", reply_markup=markup)
    else:
        markup = get_language_markup()
        bot.reply_to(message, "Please select your language:", reply_markup=markup)

if __name__ == '__main__':
    bot.polling(none_stop=True)
