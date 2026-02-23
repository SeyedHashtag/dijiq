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
        unlimited_text = " (Unlimited)" if details.get("unlimited") else " (Single User)"
        target = details.get("target", "both")
        target_text = ""
        if target == "reseller":
            target_text = " [Reseller Only]"
        elif target == "customer":
            target_text = " [Customer Only]"
        plans_text += f"{i}. {gb}GB - ${details['price']} - {details['days']}d{unlimited_text}{target_text}\n"
    
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
    if not is_admin(call.from_user.id):
        return
    bot.answer_callback_query(call.id)
    msg = bot.edit_message_text(
        "Enter the plan size in GB (e.g., 30):",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id
    )
    bot.register_next_step_handler(msg, process_new_plan_gb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("select_plan:"))
def handle_plan_select(call):
    if not is_admin(call.from_user.id):
        return
    try:
        bot.answer_callback_query(call.id)
        val = call.data.split(':')[1]
        _, _, sorted_plans = create_plans_markup()
        plans = load_plans()
        
        gb, plan = None, None
        
        # 1. Try as GB key directly
        if val in plans:
            gb = val
            plan = plans[val]
        # 2. Try as index
        elif val.isdigit():
            index = int(val)
            if 0 <= index < len(sorted_plans):
                gb, plan = sorted_plans[index]
        
        if gb and plan:
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton("✏️ Edit", callback_data=f"edit_plan:{gb}"),
                types.InlineKeyboardButton("🗑️ Delete", callback_data=f"confirm_delete_plan:{gb}"),
                types.InlineKeyboardButton("⬅️ Back", callback_data="admin_back_to_plans")
            )
            
            unlimited_text = "Yes" if plan.get("unlimited") else "Single User"
            target = plan.get("target", "both").capitalize()
            bot.edit_message_text(
                f"📦 Plan {gb}GB:\n\n"
                f"💰 Price: ${plan['price']}\n"
                f"📅 Days: {plan['days']}\n"
                f"♾️ Unlimited Users: {unlimited_text}\n"
                f"🎯 Target: {target}\n\n"
                "Select an action:",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=markup
            )
    except Exception as e:
        print(f"DEBUG: Error in handle_plan_select: {str(e)}")
        bot.answer_callback_query(call.id, text=f"Error: {str(e)}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("edit_plan:"))
def handle_edit_plan(call):
    if not is_admin(call.from_user.id):
        return
    try:
        bot.answer_callback_query(call.id)
        gb = call.data.split(':')[1]
        plans = load_plans()
        
        if str(gb) not in plans:
            bot.send_message(call.message.chat.id, "Plan not found.")
            return

        sorted_plans = sorted(plans.items(), key=lambda x: int(x[0]))
        index = -1
        for i, (k, _) in enumerate(sorted_plans):
            if k == str(gb):
                index = i
                break

        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("💰 Price", callback_data=f"edit_field:price:{gb}"),
            types.InlineKeyboardButton("📦 Size (GB)", callback_data=f"edit_field:gb:{gb}"),
            types.InlineKeyboardButton("📅 Days", callback_data=f"edit_field:days:{gb}"),
            types.InlineKeyboardButton("🎯 Target", callback_data=f"edit_field:target:{gb}"),
            types.InlineKeyboardButton("⬅️ Back", callback_data=f"select_plan:{index}")
        )
        
        bot.edit_message_text(
            f"📝 Editing {gb}GB Plan\nSelect what you want to change:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=markup
        )
    except Exception as e:
        print(f"DEBUG: Error in handle_edit_plan: {str(e)}")
        bot.answer_callback_query(call.id, text=f"Error: {str(e)}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("edit_field:"))
def handle_edit_field(call):
    if not is_admin(call.from_user.id):
        return
    try:
        bot.answer_callback_query(call.id)
        _, field, gb = call.data.split(':')
        
        if field == "price":
            msg = bot.send_message(call.message.chat.id, f"Enter new price for {gb}GB plan:")
            bot.register_next_step_handler(msg, process_update_price, gb)
        elif field == "gb":
            msg = bot.send_message(call.message.chat.id, f"Enter new size (GB) for {gb}GB plan:")
            bot.register_next_step_handler(msg, process_update_gb, gb)
        elif field == "days":
            msg = bot.send_message(call.message.chat.id, f"Enter new duration (days) for {gb}GB plan:")
            bot.register_next_step_handler(msg, process_update_days, gb)
        elif field == "target":
            markup = types.InlineKeyboardMarkup(row_width=3)
            markup.add(
                types.InlineKeyboardButton("Resellers", callback_data=f"update_target:reseller:{gb}"),
                types.InlineKeyboardButton("Customers", callback_data=f"update_target:customer:{gb}"),
                types.InlineKeyboardButton("Both", callback_data=f"update_target:both:{gb}")
            )
            bot.edit_message_text(
                f"Select new target audience for {gb}GB plan:",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=markup
            )
            
    except Exception as e:
        print(f"DEBUG: Error in handle_edit_field: {str(e)}")
        bot.answer_callback_query(call.id, text=f"Error: {str(e)}")

def process_update_price(message, gb):
    try:
        price = float(message.text.strip())
        if price <= 0: raise ValueError("Price must be > 0")
        
        plans = load_plans()
        if str(gb) in plans:
            plans[str(gb)]['price'] = price
            save_plans(plans)
            bot.reply_to(message, f"✅ Price updated to ${price}")
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("⬅️ Back to Plan", callback_data=f"select_plan:{gb}"))
            bot.send_message(message.chat.id, "Select an action:", reply_markup=markup)
        else:
             bot.reply_to(message, "❌ Plan not found.")
    except ValueError:
        bot.reply_to(message, "❌ Invalid price. Please enter a valid number.")

def process_update_gb(message, old_gb):
    try:
        new_gb = int(message.text.strip())
        if new_gb <= 0: raise ValueError("Size must be > 0")
        
        plans = load_plans()
        if str(old_gb) in plans:
            if str(new_gb) in plans:
                bot.reply_to(message, f"❌ Plan with {new_gb}GB already exists.")
                return

            # Update key
            plans[str(new_gb)] = plans.pop(str(old_gb))
            save_plans(plans)
            bot.reply_to(message, f"✅ Size updated to {new_gb}GB")
            
            # Return to plan view (with new gb)
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("⬅️ Back to Plan", callback_data=f"select_plan:{new_gb}"),
                       types.InlineKeyboardButton("📋 Back to List", callback_data="admin_back_to_plans"))
            bot.send_message(message.chat.id, "Select an action:", reply_markup=markup)

        else:
             bot.reply_to(message, "❌ Plan not found.")
    except ValueError:
        bot.reply_to(message, "❌ Invalid size. Please enter a valid number.")

def process_update_days(message, gb):
    try:
        days = int(message.text.strip())
        if days <= 0: raise ValueError("Days must be > 0")
        
        plans = load_plans()
        if str(gb) in plans:
            plans[str(gb)]['days'] = days
            save_plans(plans)
            bot.reply_to(message, f"✅ Duration updated to {days} days")
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("⬅️ Back to Plan", callback_data=f"select_plan:{gb}"))
            bot.send_message(message.chat.id, "Select an action:", reply_markup=markup)
        else:
             bot.reply_to(message, "❌ Plan not found.")
    except ValueError:
        bot.reply_to(message, "❌ Invalid duration. Please enter a valid number.")

@bot.callback_query_handler(func=lambda call: call.data.startswith("update_target:"))
def handle_update_target(call):
    if not is_admin(call.from_user.id):
        return
    try:
        bot.answer_callback_query(call.id)
        _, target, gb = call.data.split(':')
        
        plans = load_plans()
        if str(gb) in plans:
            plans[str(gb)]['target'] = target
            save_plans(plans)
            
            bot.edit_message_text(
                f"✅ Target updated to {target.capitalize()}",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id
            )
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("⬅️ Back to Plan", callback_data=f"select_plan:{gb}"))
            bot.send_message(call.message.chat.id, "Select an action:", reply_markup=markup)
        else:
             bot.edit_message_text("❌ Plan not found.", chat_id=call.message.chat.id, message_id=call.message.message_id)
    except Exception as e:
        print(f"DEBUG: Error in handle_update_target: {str(e)}")
        bot.answer_callback_query(call.id, text=f"Error: {str(e)}")



@bot.callback_query_handler(func=lambda call: call.data.startswith("confirm_delete_plan:"))
def handle_confirm_delete_plan(call):
    if not is_admin(call.from_user.id):
        return
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
    if not is_admin(call.from_user.id):
        return
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

@bot.callback_query_handler(func=lambda call: call.data == "admin_back_to_plans")
def handle_plan_navigation(call):
    if not is_admin(call.from_user.id):
        return
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
        
        markup = types.InlineKeyboardMarkup()
        markup.row(types.InlineKeyboardButton("✅ Yes", callback_data=f"unlimited_choice:yes:{gb}:{price}:{days}"),
                   types.InlineKeyboardButton("❌ No", callback_data=f"unlimited_choice:no:{gb}:{price}:{days}"))
        bot.reply_to(message, "Is this plan for unlimited users?", reply_markup=markup)

    except ValueError as e:
        bot.reply_to(
            message,
            f"❌ Error: {str(e)}",
            reply_markup=create_main_markup(is_admin=True)
        )
@bot.callback_query_handler(func=lambda call: call.data.startswith("unlimited_choice:"))
def process_unlimited_choice(call):
    if not is_admin(call.from_user.id):
        return
    try:
        bot.answer_callback_query(call.id)
        _, choice, gb, price, days = call.data.split(':')
        
        markup = types.InlineKeyboardMarkup(row_width=3)
        markup.add(
            types.InlineKeyboardButton("Resellers", callback_data=f"newplan_target:reseller:{choice}:{gb}:{price}:{days}"),
            types.InlineKeyboardButton("Customers", callback_data=f"newplan_target:customer:{choice}:{gb}:{price}:{days}"),
            types.InlineKeyboardButton("Both", callback_data=f"newplan_target:both:{choice}:{gb}:{price}:{days}")
        )
        
        bot.edit_message_text(
            "👥 Who is this plan for?",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=markup
        )
        
    except Exception as e:
        bot.reply_to(
            call.message,
            f"? Error: {str(e)}",
            reply_markup=create_main_markup(is_admin=True)
        )

@bot.callback_query_handler(func=lambda call: call.data.startswith("newplan_target:"))
def process_newplan_target(call):
    if not is_admin(call.from_user.id):
        return
    try:
        bot.answer_callback_query(call.id)
        _, target, choice, gb, price, days = call.data.split(':')
        gb, price, days = int(gb), float(price), int(days)
        unlimited = choice == 'yes'
        
        plans = load_plans()
        plans[str(gb)] = {"price": price, "days": days, "unlimited": unlimited, "target": target}
        save_plans(plans)
        
        unlimited_text = "Yes" if unlimited else "No"
        bot.edit_message_text(
            f"✅ Plan saved successfully:\n{gb}GB - ${price} - {days} days\nUnlimited Users: {unlimited_text}\nTarget: {target.capitalize()}",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id
        )
        
        markup, plans_text, _ = create_plans_markup()
        plans_text += "\nSelect a plan number to edit:"
        bot.send_message(
            call.message.chat.id,
            plans_text,
            reply_markup=markup
        )
    except Exception as e:
        bot.reply_to(
            call.message,
            f"? Error: {str(e)}",
            reply_markup=create_main_markup(is_admin=True)
        )
