from telebot import types
from utils.command import bot, is_admin
from utils.common import create_main_markup
import json
import os

PLANS_FILE = '/etc/dijiq/core/scripts/telegrambot/plans.json'

def load_plans():
    try:
        if os.path.exists(PLANS_FILE):
            with open(PLANS_FILE, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return {
        "40": {"price": 1.20, "days": 30},
        "60": {"price": 1.50, "days": 30},
        "100": {"price": 2.00, "days": 30}
    }

def save_plans(plans):
    os.makedirs(os.path.dirname(PLANS_FILE), exist_ok=True)
    with open(PLANS_FILE, 'w') as f:
        json.dump(plans, f, indent=4)

def create_plans_markup():
    markup = types.InlineKeyboardMarkup(row_width=3)
    plans = load_plans()
    sorted_plans = sorted(plans.items(), key=lambda x: int(x[0]))
    
    # Create plan list text
    plans_text = "📋 Current Plans:\n\n"
    for i, (gb, details) in enumerate(sorted_plans, 1):
        plans_text += f"{i}. {gb}GB - ${details['price']} - {details['days']}d\n"
    
    # Create numbered buttons
    buttons = []
    for i in range(len(sorted_plans)):
        buttons.append(types.InlineKeyboardButton(str(i + 1), callback_data=f"select_plan:{i}"))
    
    # Add buttons in rows of 3
    for i in range(0, len(buttons), 3):
        markup.row(*buttons[i:i+3])
    
    # Add Plan button
    markup.row(types.InlineKeyboardButton("➕ Add Plan", callback_data="add_plan"))
    
    return markup, plans_text, sorted_plans

@bot.message_handler(func=lambda message: is_admin(message.from_user.id) and message.text == '📝 Edit Plans')
def edit_plans(message):
    markup, plans_text, _ = create_plans_markup()
    plans_text += "\nSelect a plan number to edit:"
    bot.reply_to(message, plans_text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "add_plan")
def handle_add_plan(call):
    bot.answer_callback_query(call.id)
    msg = bot.edit_message_text(
        "Enter the plan size in GB (e.g., 30):",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id
    )
    bot.register_next_step_handler(msg, process_new_plan_gb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("select_plan:"))
def handle_plan_select(call):
    try:
        bot.answer_callback_query(call.id)
        index = int(call.data.split(':')[1])
        _, _, sorted_plans = create_plans_markup()
        
        if 0 <= index < len(sorted_plans):
            gb, plan = sorted_plans[index]
            
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton("🗑️ Delete", callback_data=f"confirm_delete_plan:{gb}"),
                types.InlineKeyboardButton("⬅️ Back", callback_data="back_to_plans")
            )
            
            bot.edit_message_text(
                f"📦 Plan {gb}GB:\n\n"
                f"💰 Price: ${plan['price']}\n"
                f"📅 Days: {plan['days']}\n\n"
                "Select an action:",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=markup
            )
    except Exception as e:
        print(f"DEBUG: Error in handle_plan_select: {str(e)}")
        bot.answer_callback_query(call.id, text=f"Error: {str(e)}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("confirm_delete_plan:"))
def handle_confirm_delete_plan(call):
    try:
        bot.answer_callback_query(call.id)
        gb = call.data.split(':')[1]
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("✅ Yes", callback_data=f"delete_plan:{gb}"),
            types.InlineKeyboardButton("❌ No", callback_data=f"select_plan:{gb}")
        )
        
        bot.edit_message_text(
            f"❗ Are you sure you want to delete the {gb}GB plan?",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=markup
        )
    except Exception as e:
        print(f"DEBUG: Error in handle_confirm_delete_plan: {str(e)}")
        bot.answer_callback_query(call.id, text=f"Error: {str(e)}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("delete_plan:"))
def handle_plan_delete(call):
    try:
        bot.answer_callback_query(call.id)
        gb = call.data.split(':')[1]
        plans = load_plans()
        
        if gb in plans:
            del plans[gb]
            save_plans(plans)
            
            markup, plans_text, _ = create_plans_markup()
            plans_text += "\nSelect a plan number to edit:"
            
            bot.edit_message_text(
                plans_text,
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=markup
            )
        else:
            bot.answer_callback_query(call.id, text="Plan not found!")
    except Exception as e:
        print(f"DEBUG: Error in handle_plan_delete: {str(e)}")
        bot.answer_callback_query(call.id, text=f"Error: {str(e)}")

@bot.callback_query_handler(func=lambda call: call.data == "back_to_plans")
def handle_plan_navigation(call):
    try:
        bot.answer_callback_query(call.id)
        markup, plans_text, _ = create_plans_markup()
        plans_text += "\nSelect a plan number to edit:"
        
        bot.edit_message_text(
            plans_text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=markup
        )
    except Exception as e:
        print(f"DEBUG: Error in handle_plan_navigation: {str(e)}")
        bot.answer_callback_query(call.id, text=f"Error: {str(e)}")

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
        bot.reply_to(
            message,
            f"❌ Error: {str(e)}",
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
        
        markup, plans_text, _ = create_plans_markup()
        plans_text += "\nSelect a plan number to edit:"
        bot.send_message(
            message.chat.id,
            plans_text,
            reply_markup=markup
        )
    except ValueError as e:
        bot.reply_to(
            message,
            f"❌ Error: {str(e)}",
            reply_markup=create_main_markup(is_admin=True)
        )