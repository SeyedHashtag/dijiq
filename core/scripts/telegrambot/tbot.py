from telebot import types
from utils import *
import threading
import time

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    if is_admin(user_id):
        markup = create_main_markup(is_admin=True)
        bot.reply_to(message, "Welcome to the Admin Dashboard!", reply_markup=markup)
    else:
        markup = create_main_markup(is_admin=False, user_id=user_id)
        bot.reply_to(message, "Welcome to Dijiq VPN services!", reply_markup=markup)

def monitoring_thread():
    while True:
        monitor_system_resources()
        time.sleep(60)

if __name__ == '__main__':
    monitor_thread = threading.Thread(target=monitoring_thread, daemon=True)
    monitor_thread.start()
    version_thread = threading.Thread(target=version_monitoring, daemon=True)
    version_thread.start()
    bot.polling(none_stop=True)
