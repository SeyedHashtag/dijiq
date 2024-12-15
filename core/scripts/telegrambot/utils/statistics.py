from telebot import types
from utils.command import bot, is_admin
from datetime import datetime, timedelta
import json
import os

CLIENTS_FILE = '/etc/hysteria/clients.json'

def create_stats_markup():
    """Create markup for statistics time range selection"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📅 Today", callback_data="stats:today"),
        types.InlineKeyboardButton("📅 Yesterday", callback_data="stats:yesterday"),
        types.InlineKeyboardButton("📅 This Week", callback_data="stats:week"),
        types.InlineKeyboardButton("📅 This Month", callback_data="stats:month"),
        types.InlineKeyboardButton("📅 All Time", callback_data="stats:all"),
        types.InlineKeyboardButton("❌ Close", callback_data="stats:close")
    )
    return markup

def load_clients():
    """Load clients data from JSON file"""
    if not os.path.exists(CLIENTS_FILE):
        return {}
    try:
        with open(CLIENTS_FILE, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}

def get_date_range(range_type):
    """Get date range based on selection"""
    now = datetime.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    if range_type == 'today':
        start_date = today
        end_date = now
    elif range_type == 'yesterday':
        start_date = today - timedelta(days=1)
        end_date = today
    elif range_type == 'week':
        start_date = today - timedelta(days=today.weekday())
        end_date = now
    elif range_type == 'month':
        start_date = today.replace(day=1)
        end_date = now
    else:  # all time
        start_date = datetime.min
        end_date = now
    
    return start_date, end_date

def calculate_stats(start_date, end_date):
    """Calculate statistics for given date range"""
    clients = load_clients()
    
    stats = {
        'total_revenue': 0,
        'successful_payments': 0,
        'failed_payments': 0,
        'plans_sold': {
            'basic': {'count': 0, 'revenue': 0},
            'premium': {'count': 0, 'revenue': 0},
            'ultimate': {'count': 0, 'revenue': 0}
        },
        'new_users': 0,
        'active_users': 0,
        'expired_users': 0
    }
    
    for user_id, user_data in clients.items():
        for entry in user_data:
            # Check if entry has payment info
            if 'payment' not in entry:
                continue
                
            payment_time = datetime.fromisoformat(entry['payment']['timestamp'])
            if start_date <= payment_time <= end_date:
                if entry['payment']['status'] in ('paid', 'paid_over'):
                    stats['successful_payments'] += 1
                    stats['total_revenue'] += float(entry['payment']['amount'])
                    
                    # Count plans
                    plan_name = entry['plan']['name'].lower()
                    if plan_name in stats['plans_sold']:
                        stats['plans_sold'][plan_name]['count'] += 1
                        stats['plans_sold'][plan_name]['revenue'] += float(entry['payment']['amount'])
                else:
                    stats['failed_payments'] += 1
            
            # Count user status
            if 'created_at' in entry:
                created_time = datetime.fromisoformat(entry['created_at'])
                if start_date <= created_time <= end_date:
                    stats['new_users'] += 1
                
                if entry.get('status') == 'active':
                    stats['active_users'] += 1
                else:
                    stats['expired_users'] += 1
    
    return stats

def format_stats_message(stats, range_type):
    """Format statistics message"""
    range_names = {
        'today': "Today's",
        'yesterday': "Yesterday's",
        'week': "This Week's",
        'month': "This Month's",
        'all': "All Time"
    }
    
    message = f"""*{range_names.get(range_type, '')} Statistics*

💰 *Revenue*
• Total Revenue: ${stats['total_revenue']:.2f}
• Successful Payments: {stats['successful_payments']}
• Failed Payments: {stats['failed_payments']}

📊 *Plans Sold*
• Basic Plan: {stats['plans_sold']['basic']['count']} (${stats['plans_sold']['basic']['revenue']:.2f})
• Premium Plan: {stats['plans_sold']['premium']['count']} (${stats['plans_sold']['premium']['revenue']:.2f})
• Ultimate Plan: {stats['plans_sold']['ultimate']['count']} (${stats['plans_sold']['ultimate']['revenue']:.2f})

👥 *Users*
• New Users: {stats['new_users']}
• Active Users: {stats['active_users']}
• Expired Users: {stats['expired_users']}

📈 *Conversion Rate*
• Payment Success Rate: { (stats['successful_payments'] / (stats['successful_payments'] + stats['failed_payments']) * 100):.1f }% if stats['successful_payments'] + stats['failed_payments'] > 0 else '0%'"""

    return message

@bot.message_handler(func=lambda message: is_admin(message.from_user.id) and message.text == '📊 Statistics')
def show_stats_menu(message):
    """Show statistics menu"""
    markup = create_stats_markup()
    bot.reply_to(
        message,
        "Select time range for statistics:",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('stats:'))
def handle_stats_selection(call):
    """Handle statistics time range selection"""
    if not is_admin(call.from_user.id):
        return
        
    action = call.data.split(':')[1]
    
    if action == 'close':
        bot.delete_message(call.message.chat.id, call.message.message_id)
        return
    
    start_date, end_date = get_date_range(action)
    stats = calculate_stats(start_date, end_date)
    stats_message = format_stats_message(stats, action)
    
    # Update message with statistics
    bot.edit_message_text(
        stats_message,
        call.message.chat.id,
        call.message.message_id,
        reply_markup=create_stats_markup(),
        parse_mode="Markdown"
    ) 

def show_statistics(message):
    language = get_user_language(message.from_user.id)
    stats = gather_statistics()
    stats_message = get_text(language, "statistics_summary").format(**stats)
    bot.reply_to(message, stats_message)
