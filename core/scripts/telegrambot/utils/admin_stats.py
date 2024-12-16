from telebot import types
from utils.command import *
from utils.common import create_main_markup
from utils.payment_records import load_payment_records
from datetime import datetime, timedelta
import json

def create_stats_markup():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('📊 Last 7 Days', '📈 Last 30 Days')
    markup.row('👥 User Stats', '❌ Back')
    return markup

def get_financial_stats(days):
    payment_records = load_payment_records()
    cutoff_date = datetime.now() - timedelta(days=days)
    
    total_profit = 0
    successful_payments = 0
    payment_amounts = []
    test_payments = 0
    test_amount = 0
    
    for record in payment_records:
        try:
            payment_date = datetime.fromtimestamp(record.get('timestamp', 0))
            if payment_date >= cutoff_date and record.get('status') == 'completed':
                amount = float(record.get('amount', 0))
                is_test = record.get('is_test', False)
                
                if is_test:
                    test_payments += 1
                    test_amount += amount
                else:
                    total_profit += amount
                    successful_payments += 1
                    payment_amounts.append(amount)
        except:
            continue
    
    avg_payment = sum(payment_amounts) / len(payment_amounts) if payment_amounts else 0
    
    return {
        'total_profit': round(total_profit, 2),
        'successful_payments': successful_payments,
        'avg_payment': round(avg_payment, 2),
        'test_payments': test_payments,
        'test_amount': round(test_amount, 2)
    }

def get_user_stats(days=None):
    command = f"python3 {CLI_PATH} list-users"
    result = run_cli_command(command)
    
    try:
        users = json.loads(result)
        total_users = 0
        active_users = 0
        expired_users = 0
        recent_users = 0
        paying_users = 0
        
        cutoff_date = datetime.now() - timedelta(days=days) if days else None
        
        for username, details in users.items():
            if username.startswith('id'):  # Skip if not a user config
                continue
            
            total_users += 1
            
            # Check user status
            if details.get('blocked', True):
                expired_users += 1
            else:
                active_users += 1
            
            # Check if user has any active or past configs
            if details.get('configs', []):
                paying_users += 1
            
            # Check recent activity if days parameter is provided
            if days and 'last_active' in details:
                try:
                    last_active = datetime.fromtimestamp(details['last_active'])
                    if last_active >= cutoff_date:
                        recent_users += 1
                except:
                    pass
        
        stats = {
            'total_users': total_users,
            'active_users': active_users,
            'expired_users': expired_users,
            'paying_users': paying_users
        }
        
        if days:
            stats['recent_users'] = recent_users
            
        return stats
    except Exception as e:
        print(f"Error getting user stats: {str(e)}")
        return {
            'total_users': 0,
            'active_users': 0,
            'expired_users': 0,
            'paying_users': 0,
            'recent_users': 0 if days else None
        }

@bot.message_handler(func=lambda message: is_admin(message.from_user.id) and message.text == '📊 Statistics')
def show_stats_menu(message):
    bot.reply_to(
        message,
        "📊 Statistics Menu\n\nSelect a report type:",
        reply_markup=create_stats_markup()
    )

@bot.message_handler(func=lambda message: is_admin(message.from_user.id) and message.text in ['📊 Last 7 Days', '📈 Last 30 Days', '👥 User Stats'])
def show_stats(message):
    if message.text == '👥 User Stats':
        stats = get_user_stats()
        report = (
            "👥 User Statistics\n\n"
            f"Client Overview:\n"
            f"• Total Users: {stats['total_users']}\n"
            f"• Active Users: {stats['active_users']}\n"
            f"• Expired Users: {stats['expired_users']}\n"
            f"• Paying Users: {stats['paying_users']}\n"
            f"• Active Rate: {round(stats['active_users'] / stats['total_users'] * 100 if stats['total_users'] > 0 else 0, 1)}%\n"
            f"• Conversion Rate: {round(stats['paying_users'] / stats['total_users'] * 100 if stats['total_users'] > 0 else 0, 1)}%"
        )
    else:
        days = 7 if message.text == '📊 Last 7 Days' else 30
        fin_stats = get_financial_stats(days)
        user_stats = get_user_stats(days)
        
        report = (
            f"📊 {days}-Day Report\n\n"
            f"User Activity:\n"
            f"• Recent Active Users: {user_stats['recent_users']}\n"
            f"• New Paying Users: {user_stats['paying_users']}\n\n"
            f"Real Transactions:\n"
            f"• Total Profit: ${fin_stats['total_profit']}\n"
            f"• Successful Payments: {fin_stats['successful_payments']}\n"
            f"• Average Payment: ${fin_stats['avg_payment']}\n"
            f"• Daily Average: ${round(fin_stats['total_profit']/days, 2)}\n\n"
            f"Test Transactions:\n"
            f"• Test Payments: {fin_stats['test_payments']}\n"
            f"• Test Amount: ${fin_stats['test_amount']}"
        )
    
    bot.reply_to(message, report, reply_markup=create_stats_markup())

@bot.message_handler(func=lambda message: is_admin(message.from_user.id) and message.text == '❌ Back')
def back_to_main(message):
    bot.reply_to(message, "Returning to main menu.", reply_markup=create_main_markup(is_admin=True)) 
