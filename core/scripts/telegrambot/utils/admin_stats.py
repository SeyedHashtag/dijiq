from telebot import types
from utils.command import *
from utils.common import create_main_markup
from utils.payment_records import load_payment_records
from datetime import datetime, timedelta
import json

def create_stats_markup():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('📊 Last 7 Days', '📈 Last 30 Days')
    markup.row('❌ Back')
    return markup

def get_stats(days):
    # Get payment stats
    payment_records = load_payment_records()
    cutoff_date = datetime.now() - timedelta(days=days)
    
    total_profit = 0
    successful_payments = 0
    test_payments = 0
    test_amount = 0
    
    # Process payments
    for record in payment_records:
        try:
            payment_date = datetime.fromtimestamp(record.get('timestamp', 0))
            if payment_date >= cutoff_date and record.get('status') == 'completed':
                amount = float(record.get('amount', 0))
                if record.get('is_test', False):
                    test_payments += 1
                    test_amount += amount
                else:
                    total_profit += amount
                    successful_payments += 1
        except:
            continue
    
    # Get user stats
    command = f"python3 {CLI_PATH} list-users"
    result = run_cli_command(command)
    
    active_users = 0
    expired_users = 0
    
    try:
        users = json.loads(result)
        for username, details in users.items():
            if username.startswith('id'):
                continue
            if details.get('blocked', True):
                expired_users += 1
            else:
                active_users += 1
    except:
        pass
    
    return {
        'total_profit': round(total_profit, 2),
        'successful_payments': successful_payments,
        'test_payments': test_payments,
        'test_amount': round(test_amount, 2),
        'active_users': active_users,
        'expired_users': expired_users,
        'total_users': active_users + expired_users
    }

@bot.message_handler(func=lambda message: is_admin(message.from_user.id) and message.text == '📊 Statistics')
def show_stats_menu(message):
    bot.reply_to(
        message,
        "📊 Statistics Menu\n\nSelect a period:",
        reply_markup=create_stats_markup()
    )

@bot.message_handler(func=lambda message: is_admin(message.from_user.id) and message.text in ['📊 Last 7 Days', '📈 Last 30 Days'])
def show_stats(message):
    days = 7 if message.text == '📊 Last 7 Days' else 30
    stats = get_stats(days)
    
    report = (
        f"📊 {days}-Day Report\n\n"
        f"Users:\n"
        f"• Total Users: {stats['total_users']}\n"
        f"• Active Users: {stats['active_users']}\n"
        f"• Expired Users: {stats['expired_users']}\n\n"
        f"Real Transactions:\n"
        f"• Total Profit: ${stats['total_profit']}\n"
        f"• Successful Payments: {stats['successful_payments']}\n"
        f"• Daily Average: ${round(stats['total_profit']/days, 2)}\n\n"
        f"Test Transactions:\n"
        f"• Test Payments: {stats['test_payments']}\n"
        f"• Test Amount: ${stats['test_amount']}"
    )
    
    bot.reply_to(message, report, reply_markup=create_stats_markup())

@bot.message_handler(func=lambda message: is_admin(message.from_user.id) and message.text == '❌ Back')
def back_to_main(message):
    bot.reply_to(message, "Returning to main menu.", reply_markup=create_main_markup(is_admin=True)) 
