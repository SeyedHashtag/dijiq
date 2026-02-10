from telebot import types
from utils import *
import threading
import time
import datetime

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    
    # Check for referral
    args = message.text.split()
    if len(args) > 1:
        referral_code = args[1]
        try:
            success, result = process_referral(user_id, referral_code)
            lang = get_user_language(user_id)
            if success:
                 bot.send_message(user_id, get_message_text(lang, "referral_registered").format(referrer_id=result))
        except Exception as e:
            print(f"Error processing referral: {e}")

    if is_admin(user_id):
        markup = create_main_markup(is_admin=True)
        bot.reply_to(message, "Welcome to the Admin Dashboard!", reply_markup=markup)
    else:
        # Automatically create test config if not already used
        if not has_used_test_config(user_id):
            create_test_config(user_id, message.chat.id, is_automatic=True, language=get_user_language(user_id), telegram_username=message.from_user.username)
            
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

def traffic_monitoring_thread():
    """Background thread to notify users when nearing traffic quota"""
    while True:
        try:
            monitor_user_traffic()
        except Exception as e:
            print(f"Error in traffic monitoring: {e}")
        # Check every 2 hours
        time.sleep(7200)

def _seconds_until_next_backup_window(now=None):
    """Return seconds until next 6-hour boundary in local server time."""
    if now is None:
        now = datetime.datetime.now()

    next_hour = ((now.hour // 6) + 1) * 6
    next_day = now.date()
    if next_hour >= 24:
        next_hour = 0
        next_day = now.date() + datetime.timedelta(days=1)

    next_run = datetime.datetime.combine(
        next_day,
        datetime.time(hour=next_hour, minute=0, second=0, microsecond=0),
    )
    delta = (next_run - now).total_seconds()
    return max(0, int(delta))


def automated_backup_thread():
    """Background thread to run automated backups at fixed 6-hour boundaries."""
    while True:
        sleep_seconds = _seconds_until_next_backup_window()
        time.sleep(sleep_seconds)
        try:
            run_backup_and_send_to_admins()
        except Exception as e:
            print(f"Error in automated backup: {e}")

if __name__ == '__main__':
    monitor_thread = threading.Thread(target=monitoring_thread, daemon=True)
    monitor_thread.start()
    version_thread = threading.Thread(target=version_monitoring, daemon=True)
    version_thread.start()
    payment_thread = threading.Thread(target=payment_monitoring_thread, daemon=True)
    payment_thread.start()
    traffic_thread = threading.Thread(target=traffic_monitoring_thread, daemon=True)
    traffic_thread.start()
    backup_thread = threading.Thread(target=automated_backup_thread, daemon=True)
    backup_thread.start()
    bot.polling(none_stop=True)
