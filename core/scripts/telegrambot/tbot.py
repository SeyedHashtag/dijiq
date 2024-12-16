from telebot import types
from utils.common import create_main_markup
from utils.adduser import *
from utils.backup import *
from utils.command import *
from utils.deleteuser import *
from utils.edituser import *
from utils.search import *
from utils.serverinfo import *
from utils.client import *
from utils.admin_payment import *
from utils.admin_plans import *
from utils.admin_test_mode import *
from utils.admin_support import *
from utils.admin_broadcast import *

@bot.message_handler(commands=['start'])
def send_welcome(message):
    is_admin_user = is_admin(message.from_user.id)
    markup = create_main_markup(is_admin=is_admin_user)
    
    if is_admin_user:
        bot.reply_to(message, "Welcome to the Admin Panel!", reply_markup=markup)
    else:
        welcome_text = (
            "Welcome to our VPN Service! 🌐\n\n"
            "Here you can:\n"
            "📱 View your configs\n"
            "💰 Purchase new plans\n"
            "⬇️ Download our apps\n"
            "📞 Get support\n\n"
            "Please use the menu below to get started!"
        )
        bot.reply_to(message, welcome_text, reply_markup=markup)

if __name__ == '__main__':
    bot.polling(none_stop=True)
