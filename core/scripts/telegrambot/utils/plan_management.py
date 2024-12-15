import json
import os
from telebot import types
from utils.command import bot, is_admin
from utils.language import get_text, get_user_language

PLANS_FILE = '/etc/hysteria/plans.json'
DEFAULT_PLANS = {
    'basic': {
        'name': '🚀 Basic Plan',
        'traffic': 30,
        'days': 30,
        'price': 1.8
    },
    'premium': {
        'name': '⚡️ Premium Plan',
        'traffic': 100,
        'days': 30,
        'price': 3.0
    },
    'ultimate': {
        'name': '💎 Ultimate Plan',
        'traffic': 200,
        'days': 30,
        'price': 4.2
    }
}

def load_plans():
    """Load plans from JSON file"""
    if not os.path.exists(PLANS_FILE):
        save_plans(DEFAULT_PLANS)
        return DEFAULT_PLANS
    try:
        with open(PLANS_FILE, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return DEFAULT_PLANS

def save_plans(plans):
    """Save plans to JSON file"""
    os.makedirs(os.path.dirname(PLANS_FILE), exist_ok=True)
    with open(PLANS_FILE, 'w') as f:
        json.dump(plans, f, indent=4)

def create_plan_management_markup():
    """Create markup for plan management"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    plans = load_plans()
    
    for plan_id, plan in plans.items():
        markup.add(types.InlineKeyboardButton(
            plan['name'],
            callback_data=f"edit_plan:{plan_id}"
        ))
    
    markup.add(types.InlineKeyboardButton("❌ Close", callback_data="close_plan_menu"))
    return markup

@bot.message_handler(func=lambda message: is_admin(message.from_user.id) and message.text == '⚙️ Manage Plans')
def show_plan_management(message):
    """Show plan management menu"""
    markup = create_plan_management_markup()
    bot.reply_to(
        message,
        "Select a plan to edit:",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_plan:'))
def handle_plan_edit(call):
    """Handle plan editing"""
    if not is_admin(call.from_user.id):
        return
        
    plan_id = call.data.split(':')[1]
    plans = load_plans()
    plan = plans.get(plan_id)
    
    if not plan:
        bot.answer_callback_query(call.id, "Plan not found!")
        return
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📊 Traffic", callback_data=f"set_plan:{plan_id}:traffic"),
        types.InlineKeyboardButton("📅 Days", callback_data=f"set_plan:{plan_id}:days"),
        types.InlineKeyboardButton("💰 Price", callback_data=f"set_plan:{plan_id}:price"),
        types.InlineKeyboardButton("↩️ Back", callback_data="show_plans_menu")
    )
    
    bot.edit_message_text(
        f"""*{plan['name']}*
        
Current Settings:
• Traffic: {plan['traffic']} GB
• Duration: {plan['days']} days
• Price: ${plan['price']}

Select what you want to edit:""",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('set_plan:'))
def handle_plan_setting(call):
    """Handle plan parameter setting"""
    if not is_admin(call.from_user.id):
        return
        
    _, plan_id, param = call.data.split(':')
    param_names = {
        'traffic': 'traffic (in GB)',
        'days': 'duration (in days)',
        'price': 'price (in USD)'
    }
    
    msg = bot.edit_message_text(
        f"Enter new {param_names[param]} for this plan:",
        call.message.chat.id,
        call.message.message_id
    )
    
    bot.register_next_step_handler(msg, process_plan_setting, plan_id, param)

def process_plan_setting(message, plan_id, param):
    """Process plan setting value"""
    try:
        value = float(message.text.strip())
        plans = load_plans()
        
        if plan_id in plans:
            plans[plan_id][param] = value
            save_plans(plans)
            
            markup = create_plan_management_markup()
            bot.reply_to(
                message,
                f"✅ Plan updated successfully!",
                reply_markup=markup
            )
    except ValueError:
        bot.reply_to(message, "❌ Please enter a valid number!")
        return

@bot.callback_query_handler(func=lambda call: call.data == "show_plans_menu")
def show_plans_menu(call):
    """Show plans menu"""
    if not is_admin(call.from_user.id):
        return
        
    markup = create_plan_management_markup()
    bot.edit_message_text(
        "Select a plan to edit:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data == "close_plan_menu")
def close_plan_menu(call):
    """Close plan management menu"""
    bot.delete_message(call.message.chat.id, call.message.message_id) 
