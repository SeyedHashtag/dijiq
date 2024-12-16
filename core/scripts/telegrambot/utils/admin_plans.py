from telebot import types
from utils.command import *
from utils.common import create_main_markup
import json
import os

PLANS_FILE = '/etc/hysteria/core/scripts/telegrambot/plans.json'

def load_plans():
    try:
        if os.path.exists(PLANS_FILE):
            with open(PLANS_FILE, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    
    # Default plans if file doesn't exist
    return {
        "30": {"price": 1.80, "days": 30},
        "60": {"price": 3.00, "days": 30},
        "100": {"price": 4.20, "days": 30}
    }

def save_plans(plans):
    with open(PLANS_FILE, 'w') as f:
        json.dump(plans, f, indent=4)

def create_plans_markup():
    markup = types.InlineKeyboardMarkup(row_width=2)
    plans = load_plans()
    
    for gb, details in plans.items():
        markup.add(types.InlineKeyboardButton(
            f"{gb}GB - ${details['price']} - {details['days']}d",
            callback_data=f"edit_plan:{gb}"
        ))
    
    markup.add(
        types.InlineKeyboardButton("➕ Add Plan", callback_data="add_plan"),
        types.InlineKeyboardButton("❌ Cancel", callback_data="cancel_plan_edit")
    )
    return markup

@bot.message_handler(func=lambda message: is_admin(message.from_user.id) and message.text == '📝 Edit Plans')
def edit_plans(message):
    bot.reply_to(
        message,
        "Select a plan to edit or add a new one:",
        reply_markup=create_plans_markup()
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_plan:'))
def handle_plan_edit(call):
    gb = call.data.split(':')[1]
    plans = load_plans()
    plan = plans.get(gb, {})
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("💰 Price", callback_data=f"edit_plan_price:{gb}"),
        types.InlineKeyboardButton("📅 Days", callback_data=f"edit_plan_days:{gb}"),
        types.InlineKeyboardButton("❌ Delete Plan", callback_data=f"delete_plan:{gb}"),
        types.InlineKeyboardButton("⬅️ Back", callback_data="back_to_plans")
    )
    
    bot.edit_message_text(
        f"Editing {gb}GB Plan:\n"
        f"Current Price: ${plan['price']}\n"
        f"Current Days: {plan['days']}\n\n"
        "Select what to edit:",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data == "add_plan")
def handle_add_plan(call):
    msg = bot.edit_message_text(
        "Enter the plan size in GB (e.g., 30):",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id
    )
    bot.register_next_step_handler(msg, process_new_plan_gb)

def process_new_plan_gb(message):
    try:
        gb = int(message.text.strip())
        plans = load_plans()
        
        if str(gb) in plans:
            bot.reply_to(
                message,
                "This plan size already exists. Please choose a different size:",
                reply_markup=create_main_markup(is_admin=True)
            )
            return
        
        msg = bot.reply_to(message, f"Enter the price for {gb}GB plan (e.g., 1.80):")
        bot.register_next_step_handler(msg, process_new_plan_price, gb)
    except ValueError:
        bot.reply_to(
            message,
            "Invalid input. Please enter a number.",
            reply_markup=create_main_markup(is_admin=True)
        )

def process_new_plan_price(message, gb):
    try:
        price = float(message.text.strip())
        msg = bot.reply_to(message, f"Enter the duration in days for {gb}GB plan (e.g., 30):")
        bot.register_next_step_handler(msg, process_new_plan_days, gb, price)
    except ValueError:
        bot.reply_to(
            message,
            "Invalid input. Please enter a number.",
            reply_markup=create_main_markup(is_admin=True)
        )

def process_new_plan_days(message, gb, price):
    try:
        days = int(message.text.strip())
        plans = load_plans()
        plans[str(gb)] = {"price": price, "days": days}
        save_plans(plans)
        
        bot.reply_to(
            message,
            f"✅ New plan added successfully:\n{gb}GB - ${price} - {days} days",
            reply_markup=create_main_markup(is_admin=True)
        )
    except ValueError:
        bot.reply_to(
            message,
            "Invalid input. Please enter a number.",
            reply_markup=create_main_markup(is_admin=True)
        )

@bot.callback_query_handler(func=lambda call: call.data.startswith(('edit_plan_price:', 'edit_plan_days:')))
def handle_plan_detail_edit(call):
    action, gb = call.data.split(':')
    is_price = 'price' in action
    
    msg = bot.edit_message_text(
        f"Enter new {'price' if is_price else 'days'} for {gb}GB plan:",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id
    )
    bot.register_next_step_handler(
        msg,
        process_plan_detail_edit,
        gb,
        'price' if is_price else 'days'
    )

def process_plan_detail_edit(message, gb, field):
    try:
        value = float(message.text.strip()) if field == 'price' else int(message.text.strip())
        plans = load_plans()
        plans[gb][field] = value
        save_plans(plans)
        
        bot.reply_to(
            message,
            f"✅ Plan updated successfully!",
            reply_markup=create_main_markup(is_admin=True)
        )
    except ValueError:
        bot.reply_to(
            message,
            "Invalid input. Please enter a number.",
            reply_markup=create_main_markup(is_admin=True)
        )

@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_plan:'))
def handle_plan_delete(call):
    gb = call.data.split(':')[1]
    plans = load_plans()
    
    if gb in plans:
        del plans[gb]
        save_plans(plans)
    
    bot.edit_message_text(
        "✅ Plan deleted successfully!",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=create_plans_markup()
    )

@bot.callback_query_handler(func=lambda call: call.data in ["back_to_plans", "cancel_plan_edit"])
def handle_plan_navigation(call):
    if call.data == "cancel_plan_edit":
        bot.edit_message_text(
            "Operation canceled.",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id
        )
    else:
        bot.edit_message_text(
            "Select a plan to edit or add a new one:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=create_plans_markup()
        ) 
