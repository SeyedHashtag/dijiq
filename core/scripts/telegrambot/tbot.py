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

def payment_monitoring_thread():
    """Background thread to check pending payments periodically"""
    while True:
        try:
            from utils.purchase_plan import check_pending_payments
            check_pending_payments()
        except Exception as e:
            print(f"Error in payment monitoring: {e}")
        # Check every 5 minutes
        time.sleep(300)

if __name__ == '__main__':
    monitor_thread = threading.Thread(target=monitoring_thread, daemon=True)
    monitor_thread.start()
    version_thread = threading.Thread(target=version_monitoring, daemon=True)
    version_thread.start()
    payment_thread = threading.Thread(target=payment_monitoring_thread, daemon=True)
    payment_thread.start()
    bot.polling(none_stop=True)
