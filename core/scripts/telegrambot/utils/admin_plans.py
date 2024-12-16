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
    os.makedirs(os.path.dirname(PLANS_FILE), exist_ok=True)
    with open(PLANS_FILE, 'w') as f:
        json.dump(plans, f, indent=4)

def create_plans_markup():
    markup = types.InlineKeyboardMarkup(row_width=1)  # Changed to row_width=1 for better layout
    plans = load_plans()
    
    # Sort plans by GB size
    sorted_plans = sorted(plans.items(), key=lambda x: int(x[0]))
    
    for gb, details in sorted_plans:
        markup.add(types.InlineKeyboardButton(
            f"📦 {gb}GB - ${details['price']} - {details['days']}d",
            callback_data=f"edit_plan:{gb}"
        ))
    
    markup.row(
        types.InlineKeyboardButton("➕ Add Plan", callback_data="add_plan"),
        types.InlineKeyboardButton("❌ Cancel", callback_data="cancel_plan_edit")
    )
    return markup

def create_edit_plan_markup(gb):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("💰 Edit Price", callback_data=f"edit_plan_price:{gb}"),
        types.InlineKeyboardButton("📅 Edit Days", callback_data=f"edit_plan_days:{gb}")
    )
    markup.row(types.InlineKeyboardButton("🗑️ Delete Plan", callback_data=f"confirm_delete_plan:{gb}"))
    markup.row(types.InlineKeyboardButton("⬅️ Back", callback_data="back_to_plans"))
    return markup

@bot.message_handler(func=lambda message: is_admin(message.from_user.id) and message.text == '📝 Edit Plans')
def edit_plans(message):
    bot.reply_to(
        message,
        "📋 Current Plans:\nSelect a plan to edit or add a new one:",
        reply_markup=create_plans_markup()
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_plan:'))
def handle_plan_edit(call):
    gb = call.data.split(':')[1]
    plans = load_plans()
    plan = plans.get(gb, {})
    
    bot.edit_message_text(
        f"📦 Editing {gb}GB Plan:\n\n"
        f"💰 Current Price: ${plan['price']}\n"
        f"📅 Current Days: {plan['days']}\n\n"
        "Select what to edit:",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=create_edit_plan_markup(gb)
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('confirm_delete_plan:'))
def handle_confirm_delete_plan(call):
    gb = call.data.split(':')[1]
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ Yes", callback_data=f"delete_plan:{gb}"),
        types.InlineKeyboardButton("❌ No", callback_data=f"edit_plan:{gb}")
    )
    
    bot.edit_message_text(
        f"❗ Are you sure you want to delete the {gb}GB plan?",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith(('edit_plan_price:', 'edit_plan_days:')))
def handle_plan_detail_edit(call):
    action, gb = call.data.split(':')
    is_price = 'price' in action
    
    plans = load_plans()
    current_value = plans[gb]['price' if is_price else 'days']
    
    msg = bot.edit_message_text(
        f"Current {'price' if is_price else 'days'}: {current_value}\n"
        f"Enter new {'price' if is_price else 'days'} for {gb}GB plan:",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id
    )
    bot.register_next_step_handler(msg, process_plan_detail_edit, gb, 'price' if is_price else 'days')

def process_plan_detail_edit(message, gb, field):
    try:
        value = float(message.text.strip()) if field == 'price' else int(message.text.strip())
        
        if field == 'price' and value <= 0:
            raise ValueError("Price must be greater than 0")
        if field == 'days' and value <= 0:
            raise ValueError("Days must be greater than 0")
        
        plans = load_plans()
        plans[gb][field] = value
        save_plans(plans)
        
        bot.reply_to(
            message,
            f"✅ Plan updated successfully!\n\n"
            f"New {field}: {value}",
            reply_markup=create_main_markup(is_admin=True)
        )
        
        # Show updated plans list
        bot.send_message(
            message.chat.id,
            "Current Plans:",
            reply_markup=create_plans_markup()
        )
    except ValueError as e:
        error_msg = str(e) if str(e) != "could not convert string to float: ''" else "Invalid input"
        bot.reply_to(
            message,
            f"❌ {error_msg}. Please enter a valid number.",
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
            f"✅ Plan {gb}GB deleted successfully!\n\nCurrent Plans:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=create_plans_markup()
        )
    else:
        bot.answer_callback_query(call.id, "Plan not found!")

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
            "📋 Current Plans:\nSelect a plan to edit or add a new one:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=create_plans_markup()
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
        if price <= 0:
            raise ValueError("Price must be greater than 0")
            
        msg = bot.reply_to(message, f"Enter the duration in days for {gb}GB plan (e.g., 30):")
        bot.register_next_step_handler(msg, process_new_plan_days, gb, price)
    except ValueError as e:
        error_msg = str(e) if str(e) != "could not convert string to float: ''" else "Invalid input"
        bot.reply_to(
            message,
            f"❌ {error_msg}. Please enter a valid number.",
            reply_markup=create_main_markup(is_admin=True)
        )

def process_new_plan_days(message, gb, price):
    try:
        days = int(message.text.strip())
        if days <= 0:
            raise ValueError("Days must be greater than 0")
            
        plans = load_plans()
        plans[str(gb)] = {"price": price, "days": days}
        save_plans(plans)
        
        bot.reply_to(
            message,
            f"✅ New plan added successfully:\n{gb}GB - ${price} - {days} days",
            reply_markup=create_main_markup(is_admin=True)
        )
        
        # Show updated plans list
        bot.send_message(
            message.chat.id,
            "Current Plans:",
            reply_markup=create_plans_markup()
        )
    except ValueError as e:
        error_msg = str(e) if str(e) != "could not convert string to float: ''" else "Invalid input"
        bot.reply_to(
            message,
            f"❌ {error_msg}. Please enter a valid number.",
            reply_markup=create_main_markup(is_admin=True)
        ) 
