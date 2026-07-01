from telebot import types
from utils import *
from concurrent.futures import ThreadPoolExecutor
import threading
import time
import traceback
import os
from utils.telegram_safe import safe_reply_to, safe_send_message

EXPIRED_CLEANUP_INTERVAL_SECONDS = 3600


def _int_env(name, default, minimum=1):
    try:
        value = int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default
    return value if value >= minimum else default


START_TEST_CONFIG_EXECUTOR = ThreadPoolExecutor(
    max_workers=_int_env("DIJIQ_START_JOB_WORKERS", 2),
    thread_name_prefix="dijiq-start",
)
START_TEST_CONFIG_LOCK = threading.Lock()
START_TEST_CONFIG_INFLIGHT = set()


def _create_automatic_test_config_job(user_id, chat_id, telegram_username, language):
    try:
        create_test_config(
            user_id,
            chat_id,
            is_automatic=True,
            language=language,
            telegram_username=telegram_username,
        )
    except Exception as e:
        print(f"Error creating automatic test config for {user_id}: {e}")
    finally:
        with START_TEST_CONFIG_LOCK:
            START_TEST_CONFIG_INFLIGHT.discard(user_id)


def enqueue_automatic_test_config(user_id, chat_id, telegram_username=None, language=None):
    with START_TEST_CONFIG_LOCK:
        if user_id in START_TEST_CONFIG_INFLIGHT:
            return False
        START_TEST_CONFIG_INFLIGHT.add(user_id)
    try:
        START_TEST_CONFIG_EXECUTOR.submit(
            _create_automatic_test_config_job,
            user_id,
            chat_id,
            telegram_username,
            language,
        )
    except Exception:
        with START_TEST_CONFIG_LOCK:
            START_TEST_CONFIG_INFLIGHT.discard(user_id)
        raise
    return True

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    
    # Check for referral
    args = message.text.split()
    if len(args) > 1:
        referral_code = args[1]
        try:
            success, result = process_referral(
                user_id,
                referral_code,
                telegram_username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name
            )
            lang = get_user_language(user_id)
            if success:
                safe_send_message(bot, user_id, get_message_text(lang, "referral_registered").format(referrer_id=result))
        except Exception as e:
            print(f"Error processing referral: {e}")

    if is_admin(user_id):
        markup = create_main_markup(is_admin=True)
        safe_reply_to(bot, message, "Welcome to the Admin Dashboard!", reply_markup=markup)
    else:
        language = get_user_language(user_id)
        markup = create_main_markup(is_admin=False, user_id=user_id)
        safe_reply_to(bot, message, "Welcome!", reply_markup=markup)

        # Automatically create a test config when enabled; otherwise preserve interest silently.
        if not has_used_test_config(user_id):
            if is_test_creation_disabled():
                add_to_waiting_list(user_id, message.from_user.username, language)
            else:
                enqueue_automatic_test_config(
                    user_id,
                    message.chat.id,
                    telegram_username=message.from_user.username,
                    language=language,
                )


@bot.message_handler(func=lambda message: is_admin(message.from_user.id) and message.text == "❌ Cancel")
def handle_admin_cancel_fallback(message):
    safe_reply_to(
        bot,
        message,
        "Operation canceled.",
        reply_markup=create_main_markup(is_admin=True),
    )


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

def expired_cleanup_monitoring_thread():
    """Background thread to run expired user cleanup on its own cadence"""
    while True:
        try:
            from utils.expired_cleanup import (
                EXPIRED_CLEANUP_GRACE_HOURS,
                get_expired_cleanup_startup_delay,
                run_expired_user_cleanup_with_metadata,
            )
            delay_seconds = get_expired_cleanup_startup_delay(
                interval_seconds=EXPIRED_CLEANUP_INTERVAL_SECONDS
            )
            if delay_seconds > 0:
                time.sleep(delay_seconds)
                continue
            run_expired_user_cleanup_with_metadata(grace_hours=EXPIRED_CLEANUP_GRACE_HOURS)
        except Exception as e:
            print(f"Error in expired cleanup: {e}")
        time.sleep(EXPIRED_CLEANUP_INTERVAL_SECONDS)

def traffic_monitoring_thread():
    """Background thread to notify users when nearing traffic quota"""
    while True:
        try:
            monitor_user_traffic()
        except Exception as e:
            print(f"Error in traffic monitoring: {e}")
        # Check every 2 hours
        time.sleep(7200)

def automated_backup_thread():
    """Background thread to run automated backups every 3 hours"""
    while True:
        try:
            run_backup_and_send_to_admins()
        except Exception as e:
            print(f"Error in automated backup: {e}")
        # Run every 3 hours
        time.sleep(10800)


def run_polling_forever():
    """Keep polling alive across transient Telegram/network failures."""
    retry_delay_seconds = 3
    max_retry_delay_seconds = 60

    while True:
        try:
            bot.polling(none_stop=True, timeout=25, long_polling_timeout=25)
            retry_delay_seconds = 3
        except Exception as e:
            print(f"Telegram polling crashed: {e}")
            traceback.print_exc()
            time.sleep(retry_delay_seconds)
            retry_delay_seconds = min(max_retry_delay_seconds, retry_delay_seconds * 2)

if __name__ == '__main__':
    monitor_thread = threading.Thread(target=monitoring_thread, daemon=True)
    monitor_thread.start()
    version_thread = threading.Thread(target=version_monitoring, daemon=True)
    version_thread.start()
    payment_thread = threading.Thread(target=payment_monitoring_thread, daemon=True)
    payment_thread.start()
    expired_cleanup_thread = threading.Thread(target=expired_cleanup_monitoring_thread, daemon=True)
    expired_cleanup_thread.start()
    traffic_thread = threading.Thread(target=traffic_monitoring_thread, daemon=True)
    traffic_thread.start()
    backup_thread = threading.Thread(target=automated_backup_thread, daemon=True)
    backup_thread.start()
    run_polling_forever()
