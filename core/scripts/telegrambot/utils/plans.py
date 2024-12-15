from telebot import types
from utils.command import bot
from utils.language import get_text, get_user_language
from utils.client_menu import handle_client_menu
from utils.payment_tracking import can_request_payment, track_payment_request
from datetime import datetime
from utils.test_mode import is_test_mode, handle_test_config

PLANS = {
    "basic": {
        "traffic": 30,
        "days": 30,
        "price": 1.8
    },
    "premium": {
        "traffic": 100,
        "days": 30,
        "price": 3.0
    },
    "ultimate": {
        "traffic": 200,
        "days": 30,
        "price": 4.2
    }
}

def create_plans_markup(user_id):
    language = get_user_language(user_id)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(types.KeyboardButton(get_text(language, "basic_plan")))
    markup.row(types.KeyboardButton(get_text(language, "premium_plan")))
    markup.row(types.KeyboardButton(get_text(language, "ultimate_plan")))
    markup.row(types.KeyboardButton(get_text(language, "back_to_menu")))
    return markup

def show_plans(message):
    language = get_user_language(message.from_user.id)
    markup = create_plans_markup(message.from_user.id)
    bot.reply_to(message, get_text(language, "select_plan"), reply_markup=markup)

def handle_plan_selection(message):
    language = get_user_language(message.from_user.id)
    
    if message.text == get_text(language, "back_to_menu"):
        handle_client_menu(message)
        return
        
    plan_map = {
        get_text(language, "basic_plan"): ("basic", PLANS["basic"]),
        get_text(language, "premium_plan"): ("premium", PLANS["premium"]),
        get_text(language, "ultimate_plan"): ("ultimate", PLANS["ultimate"])
    }
    
    if message.text not in plan_map:
        return False
        
    plan_id, plan_details = plan_map[message.text]
    
    # Check for test mode
    if is_test_mode():
        if handle_test_config(message, plan_id, plan_details):
            bot.reply_to(
                message,
                "🧪 Test mode: Creating your configuration...",
                reply_markup=create_plans_markup(message.from_user.id)
            )
            return True
    
    # Check if user can request payment
    can_request, existing_payment = can_request_payment(message.from_user.id, plan_id)
    
    if not can_request:
        # Calculate remaining time
        expires_at = datetime.fromisoformat(existing_payment['expires_at'])
        remaining_minutes = int((expires_at - datetime.now()).total_seconds() / 60)
        
        bot.reply_to(
            message,
            f"You already have an active payment link for this plan. "
            f"Please wait {remaining_minutes} minutes before requesting a new one, "
            f"or complete/cancel the existing payment.",
            reply_markup=types.InlineKeyboardMarkup([[
                types.InlineKeyboardButton(
                    "Check Payment Status",
                    callback_data=f"check_payment:{existing_payment['payment_id']}"
                )
            ]])
        )
        return True
    
    plan_text = get_text(language, "plan_details").format(
        name=message.text,
        traffic=plan_details["traffic"],
        days=plan_details["days"],
        price=plan_details["price"]
    )
    
    # Create payment button
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(
        f"💳 Pay ${plan_details['price']}", 
        callback_data=f"pay_plan:{plan_id}"
    ))
    
    bot.reply_to(message, plan_text, reply_markup=markup, parse_mode="Markdown")
    return True 
