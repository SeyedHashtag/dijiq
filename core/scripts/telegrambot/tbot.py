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
from utils.client_welcome import handle_start, register_handlers
from utils.spam_protection import spam_protection

@bot.middleware_handler(update_types=['message'])
def handle_messages(bot_instance, message):
    # Skip spam protection for admins
    if is_admin(message.from_user.id):
        return message
        
    # Check for spam
    if not spam_protection.can_send_message(message.from_user.id):
        bot.reply_to(message, "⚠️ You are sending messages too quickly. Please wait a minute and try again.")
        return None
    return message

@bot.message_handler(commands=['start'])
def send_welcome(message):
    if is_admin(message.from_user.id):
        markup = create_main_markup(is_admin=True)
        bot.reply_to(message, "Welcome to the Admin Panel!", reply_markup=markup)
    else:
        handle_start(message)

# Register client handlers
register_handlers()

if __name__ == '__main__':
    bot.polling(none_stop=True)
