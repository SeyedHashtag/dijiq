from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackContext, CallbackQueryHandler, MessageHandler, Filters
from src.utils.config import is_admin
from src.bot.keyboards import get_main_menu_keyboard
import json
import os

PLANS_FILE = 'data/plans.json'

def load_plans():
    try:
        if os.path.exists(PLANS_FILE):
            with open(PLANS_FILE, 'r') as f:
                return json.load(f)
    except Exception:
        pass
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
    markup = InlineKeyboardMarkup(row_width=3)
    plans = load_plans()
    sorted_plans = sorted(plans.items(), key=lambda x: int(x[0]))
    
    # Create plan list text
    plans_text = "📋 Current Plans:\n\n"
    for i, (gb, details) in enumerate(sorted_plans, 1):
        plans_text += f"{i}. {gb}GB - ${details['price']} - {details['days']}d\n"
    
    # Create numbered buttons
    buttons = []
    for i in range(len(sorted_plans)):
        buttons.append(InlineKeyboardButton(str(i + 1), callback_data=f"select_plan:{i}"))
    
    # Add buttons in rows of 3
    for i in range(0, len(buttons), 3):
        markup.add(*buttons[i:i+3])
    
    # Add Plan button
    markup.add(InlineKeyboardButton("➕ Add Plan", callback_data="add_plan"))
    
    return markup, plans_text, sorted_plans

def edit_plans(update: Update, context: CallbackContext) -> None:
    """Handle the edit plans command"""
    if not is_admin(update.effective_user.id):
        return
        
    markup, plans_text, _ = create_plans_markup()
    plans_text += "\nSelect a plan number to edit:"
    update.message.reply_text(plans_text, reply_markup=markup)

def handle_add_plan(update: Update, context: CallbackContext) -> None:
    """Handle add plan callback"""
    query = update.callback_query
    query.answer()
    
    context.bot.edit_message_text(
        text="Enter the plan size in GB (e.g., 30):",
        chat_id=query.message.chat.id,
        message_id=query.message.message_id
    )
    
    # Set a flag to recognize the next message as plan size
    context.user_data['waiting_for_plan_size'] = True

def handle_plan_select(update: Update, context: CallbackContext) -> None:
    """Handle plan selection callback"""
    query = update.callback_query
    query.answer()
    
    data_parts = query.data.split(':')
    if len(data_parts) != 2:
        return
        
    try:
        index = int(data_parts[1])
        _, _, sorted_plans = create_plans_markup()
        
        if 0 <= index < len(sorted_plans):
            gb, plan = sorted_plans[index]
            
            markup = InlineKeyboardMarkup()
            markup.add(
                InlineKeyboardButton("🗑️ Delete", callback_data=f"confirm_delete_plan:{gb}"),
                InlineKeyboardButton("⬅️ Back", callback_data="back_to_plans")
            )
            
            context.bot.edit_message_text(
                text=f"📦 Plan {gb}GB:\n\n"
                     f"💰 Price: ${plan['price']}\n"
                     f"📅 Days: {plan['days']}\n\n"
                     "Select an action:",
                chat_id=query.message.chat.id,
                message_id=query.message.message_id,
                reply_markup=markup
            )
    except Exception as e:
        print(f"Error in handle_plan_select: {str(e)}")

def handle_confirm_delete_plan(update: Update, context: CallbackContext) -> None:
    """Handle confirm delete plan callback"""
    query = update.callback_query
    query.answer()
    
    data_parts = query.data.split(':')
    if len(data_parts) != 2:
        return
    
    gb = data_parts[1]
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("✅ Yes", callback_data=f"delete_plan:{gb}"),
        InlineKeyboardButton("❌ No", callback_data="back_to_plans")
    )
    
    context.bot.edit_message_text(
        text=f"❗ Are you sure you want to delete the {gb}GB plan?",
        chat_id=query.message.chat.id,
        message_id=query.message.message_id,
        reply_markup=markup
    )

def handle_plan_delete(update: Update, context: CallbackContext) -> None:
    """Handle plan delete callback"""
    query = update.callback_query
    query.answer()
    
    data_parts = query.data.split(':')
    if len(data_parts) != 2:
        return
    
    gb = data_parts[1]
    plans = load_plans()
    
    if gb in plans:
        del plans[gb]
        save_plans(plans)
        
        markup, plans_text, _ = create_plans_markup()
        plans_text += "\nSelect a plan number to edit:"
        
        context.bot.edit_message_text(
            text=plans_text,
            chat_id=query.message.chat.id,
            message_id=query.message.message_id,
            reply_markup=markup
        )

def handle_plan_navigation(update: Update, context: CallbackContext) -> None:
    """Handle navigation back to plans list"""
    query = update.callback_query
    query.answer()
    
    markup, plans_text, _ = create_plans_markup()
    plans_text += "\nSelect a plan number to edit:"
    
    context.bot.edit_message_text(
        text=plans_text,
        chat_id=query.message.chat.id,
        message_id=query.message.message_id,
        reply_markup=markup
    )

def process_new_plan_input(update: Update, context: CallbackContext) -> None:
    """Process the input for new plan creation"""
    # Check if we're waiting for plan size
    if context.user_data.get('waiting_for_plan_size'):
        try:
            gb = int(update.message.text.strip())
            plans = load_plans()
            
            if str(gb) in plans:
                update.message.reply_text(
                    "This plan size already exists. Please choose a different size:"
                )
                return
            
            context.user_data['waiting_for_plan_size'] = False
            context.user_data['waiting_for_plan_price'] = True
            context.user_data['new_plan_gb'] = gb
            
            update.message.reply_text(f"Enter the price for {gb}GB plan (e.g., 1.80):")
            return
        except ValueError:
            update.message.reply_text("Invalid input. Please enter a number.")
            return
            
    # Check if we're waiting for plan price
    if context.user_data.get('waiting_for_plan_price'):
        try:
            price = float(update.message.text.strip())
            if price <= 0:
                raise ValueError("Price must be greater than 0")
            
            context.user_data['waiting_for_plan_price'] = False
            context.user_data['waiting_for_plan_days'] = True
            context.user_data['new_plan_price'] = price
            
            update.message.reply_text(f"Enter the duration in days for {context.user_data['new_plan_gb']}GB plan (e.g., 30):")
            return
        except ValueError as e:
            update.message.reply_text(f"❌ Error: {str(e)}")
            return
            
    # Check if we're waiting for plan days
    if context.user_data.get('waiting_for_plan_days'):
        try:
            days = int(update.message.text.strip())
            if days <= 0:
                raise ValueError("Days must be greater than 0")
            
            context.user_data['waiting_for_plan_days'] = False
            
            gb = context.user_data['new_plan_gb']
            price = context.user_data['new_plan_price']
            
            plans = load_plans()
            plans[str(gb)] = {"price": price, "days": days}
            save_plans(plans)
            
            update.message.reply_text(
                f"✅ New plan added successfully:\n{gb}GB - ${price} - {days} days",
                reply_markup=get_main_menu_keyboard(is_admin=True)
            )
            
            # Clear user data
            for key in ['waiting_for_plan_size', 'waiting_for_plan_price', 'waiting_for_plan_days', 'new_plan_gb', 'new_plan_price']:
                if key in context.user_data:
                    del context.user_data[key]
                    
            # Show the updated plans list
            markup, plans_text, _ = create_plans_markup()
            plans_text += "\nSelect a plan number to edit:"
            update.message.reply_text(
                plans_text,
                reply_markup=markup
            )
            return
        except ValueError as e:
            update.message.reply_text(f"❌ Error: {str(e)}")
            return

def setup_admin_plans_handlers(dispatcher):
    """Register admin plans handlers"""
    dispatcher.add_handler(MessageHandler(Filters.regex('^📝 Edit Plans$') & Filters.user(is_admin), edit_plans))
    
    # Callback handlers
    dispatcher.add_handler(CallbackQueryHandler(handle_add_plan, pattern='^add_plan$'))
    dispatcher.add_handler(CallbackQueryHandler(handle_plan_select, pattern='^select_plan:[0-9]+$'))
    dispatcher.add_handler(CallbackQueryHandler(handle_confirm_delete_plan, pattern='^confirm_delete_plan:[0-9]+$'))
    dispatcher.add_handler(CallbackQueryHandler(handle_plan_delete, pattern='^delete_plan:[0-9]+$'))
    dispatcher.add_handler(CallbackQueryHandler(handle_plan_navigation, pattern='^back_to_plans$'))
    
    # Plan input handler (must be after other message handlers)
    dispatcher.add_handler(MessageHandler(
        Filters.text & ~Filters.command & Filters.user(is_admin),
        process_new_plan_input
    ))
