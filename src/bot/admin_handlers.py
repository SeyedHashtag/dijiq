from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ParseMode
from telegram.ext import CallbackContext, ConversationHandler, CommandHandler, MessageHandler, Filters, CallbackQueryHandler
import logging
from typing import Dict, Any, List, Tuple
from src.utils.config import is_admin
from src.db.storage import Database
from src.bot.keyboards import get_main_menu_keyboard, get_cancel_keyboard

# Initialize the database
db = Database()

# Logging
logger = logging.getLogger(__name__)

# States for plan creation conversation
PLAN_NAME, PLAN_DESC, PLAN_TRAFFIC, PLAN_DURATION, PLAN_PRICE, PLAN_CONFIRM = range(6)

# States for plan editing conversation
SELECT_PLAN, EDIT_FIELD, EDIT_VALUE, CONFIRM_EDIT = range(4)

# Command handler for admin plan management
def plans_command(update: Update, context: CallbackContext) -> None:
    """Show plan management options for admins."""
    user = update.effective_user
    
    if not is_admin(user.id):
        update.message.reply_text("Sorry, you don't have permission to manage plans.")
        return
    
    # Fetch all plans from the database
    plans = db.get_all_plans(active_only=False)
    
    if not plans:
        update.message.reply_text(
            "No plans found. Use /addplan to create a new plan."
        )
        return
    
    # Create plan list text
    message = "*Available Plans:*\n\n"
    for plan in plans:
        status = "✅ Active" if plan['active'] else "❌ Inactive"
        message += f"*{plan['name']}* - {plan['price']} {plan['currency']} ({status})\n"
        message += f"Traffic: {plan['traffic_limit']} GB, Duration: {plan['duration_days']} days\n"
        message += f"_{plan['description']}_\n\n"
    
    # Add management options
    message += "Use /addplan to create a new plan.\n"
    message += "Use /editplan to modify an existing plan.\n"
    message += "Use /deleteplan to remove a plan."
    
    update.message.reply_text(
        message,
        parse_mode=ParseMode.MARKDOWN
    )

# Add plan conversation
def add_plan_start(update: Update, context: CallbackContext) -> int:
    """Start the add plan conversation."""
    user = update.effective_user
    
    if not is_admin(user.id):
        update.message.reply_text("Sorry, you don't have permission to add plans.")
        return ConversationHandler.END
    
    update.message.reply_text(
        "Let's create a new VPN plan.\n\n"
        "What should be the plan name?",
        reply_markup=get_cancel_keyboard()
    )
    return PLAN_NAME

def plan_name_handler(update: Update, context: CallbackContext) -> int:
    """Handle plan name input."""
    name = update.message.text.strip()
    context.user_data['plan_name'] = name
    
    update.message.reply_text(
        f"Plan Name: {name}\n\n"
        "Now, enter a description for this plan:",
        reply_markup=get_cancel_keyboard()
    )
    return PLAN_DESC

def plan_desc_handler(update: Update, context: CallbackContext) -> int:
    """Handle plan description input."""
    description = update.message.text.strip()
    context.user_data['plan_description'] = description
    
    update.message.reply_text(
        f"Description: {description}\n\n"
        "Enter the traffic limit in GB (e.g., 50):",
        reply_markup=get_cancel_keyboard()
    )
    return PLAN_TRAFFIC

def plan_traffic_handler(update: Update, context: CallbackContext) -> int:
    """Handle traffic limit input."""
    try:
        traffic_limit = int(update.message.text.strip())
        if traffic_limit <= 0:
            raise ValueError("Traffic limit must be positive")
        
        context.user_data['plan_traffic'] = traffic_limit
        update.message.reply_text(
            f"Traffic limit: {traffic_limit} GB\n\n"
            "Enter the duration in days (e.g., 30):",
            reply_markup=get_cancel_keyboard()
        )
        return PLAN_DURATION
    
    except ValueError:
        update.message.reply_text(
            "Please enter a valid positive number for traffic limit:",
            reply_markup=get_cancel_keyboard()
        )
        return PLAN_TRAFFIC

def plan_duration_handler(update: Update, context: CallbackContext) -> int:
    """Handle duration input."""
    try:
        duration = int(update.message.text.strip())
        if duration <= 0:
            raise ValueError("Duration must be positive")
        
        context.user_data['plan_duration'] = duration
        update.message.reply_text(
            f"Duration: {duration} days\n\n"
            "Enter the price in USDT (e.g., 9.99):",
            reply_markup=get_cancel_keyboard()
        )
        return PLAN_PRICE
    
    except ValueError:
        update.message.reply_text(
            "Please enter a valid positive number for duration:",
            reply_markup=get_cancel_keyboard()
        )
        return PLAN_DURATION

def plan_price_handler(update: Update, context: CallbackContext) -> int:
    """Handle price input."""
    try:
        price = float(update.message.text.strip())
        if price <= 0:
            raise ValueError("Price must be positive")
        
        context.user_data['plan_price'] = price
        context.user_data['plan_currency'] = 'USDT'  # Default to USDT
        
        # Show summary for confirmation
        update.message.reply_text(
            "Please confirm the following plan details:\n\n"
            f"Name: {context.user_data['plan_name']}\n"
            f"Description: {context.user_data['plan_description']}\n"
            f"Traffic: {context.user_data['plan_traffic']} GB\n"
            f"Duration: {context.user_data['plan_duration']} days\n"
            f"Price: {context.user_data['plan_price']} {context.user_data['plan_currency']}\n\n"
            "Type 'confirm' to add this plan or 'cancel' to abort.",
            reply_markup=get_cancel_keyboard()
        )
        return PLAN_CONFIRM
    
    except ValueError:
        update.message.reply_text(
            "Please enter a valid positive number for price:",
            reply_markup=get_cancel_keyboard()
        )
        return PLAN_PRICE

def plan_confirm_handler(update: Update, context: CallbackContext) -> int:
    """Handle plan confirmation input."""
    decision = update.message.text.strip().lower()
    
    if decision == 'confirm':
        try:
            # Add plan to database
            plan_id = db.add_plan(
                name=context.user_data['plan_name'],
                description=context.user_data['plan_description'],
                traffic_limit=context.user_data['plan_traffic'],
                duration_days=context.user_data['plan_duration'],
                price=context.user_data['plan_price'],
                currency=context.user_data['plan_currency']
            )
            
            update.message.reply_text(
                f"✅ Plan successfully added with ID: {plan_id}",
                reply_markup=get_main_menu_keyboard()
            )
            
        except Exception as e:
            logger.error(f"Error adding plan: {str(e)}")
            update.message.reply_text(
                f"❌ Failed to add plan: {str(e)}",
                reply_markup=get_main_menu_keyboard()
            )
    else:
        update.message.reply_text(
            "Plan creation cancelled.",
            reply_markup=get_main_menu_keyboard()
        )
    
    # Clear user data
    context.user_data.clear()
    return ConversationHandler.END

# Edit plan conversation
def edit_plan_start(update: Update, context: CallbackContext) -> int:
    """Start the edit plan conversation."""
    user = update.effective_user
    
    if not is_admin(user.id):
        update.message.reply_text("Sorry, you don't have permission to edit plans.")
        return ConversationHandler.END
    
    # Fetch all plans from the database
    plans = db.get_all_plans(active_only=False)
    
    if not plans:
        update.message.reply_text(
            "No plans found to edit. Use /addplan to create a new plan.",
            reply_markup=get_main_menu_keyboard()
        )
        return ConversationHandler.END
    
    # Create inline keyboard with plans
    keyboard = []
    for plan in plans:
        keyboard.append([InlineKeyboardButton(
            f"{plan['name']} - {plan['price']} {plan['currency']}",
            callback_data=f"edit_plan_{plan['id']}"
        )])
    
    keyboard.append([InlineKeyboardButton("Cancel", callback_data="cancel_edit")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text(
        "Select a plan to edit:",
        reply_markup=reply_markup
    )
    return SELECT_PLAN

def select_plan_handler(update: Update, context: CallbackContext) -> int:
    """Handle plan selection for editing."""
    query = update.callback_query
    query.answer()
    
    if query.data == "cancel_edit":
        query.edit_message_text(
            "Plan editing cancelled.",
            reply_markup=None
        )
        return ConversationHandler.END
    
    plan_id = int(query.data.split('_')[-1])
    plan = db.get_plan(plan_id)
    
    if not plan:
        query.edit_message_text(
            "Plan not found. The plan may have been deleted.",
            reply_markup=None
        )
        return ConversationHandler.END
    
    # Store the plan in user_data
    context.user_data['edit_plan'] = plan
    
    # Create field selection keyboard
    keyboard = [
        [InlineKeyboardButton("Name", callback_data="edit_field_name")],
        [InlineKeyboardButton("Description", callback_data="edit_field_description")],
        [InlineKeyboardButton("Traffic Limit", callback_data="edit_field_traffic_limit")],
        [InlineKeyboardButton("Duration", callback_data="edit_field_duration_days")],
        [InlineKeyboardButton("Price", callback_data="edit_field_price")],
        [InlineKeyboardButton("Active Status", callback_data="edit_field_active")],
        [InlineKeyboardButton("Cancel", callback_data="cancel_edit")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Show plan details and field options
    query.edit_message_text(
        f"Editing plan: *{plan['name']}*\n\n"
        f"Description: {plan['description']}\n"
        f"Traffic: {plan['traffic_limit']} GB\n"
        f"Duration: {plan['duration_days']} days\n"
        f"Price: {plan['price']} {plan['currency']}\n"
        f"Active: {'Yes' if plan['active'] else 'No'}\n\n"
        "Select a field to edit:",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )
    return EDIT_FIELD

def edit_field_handler(update: Update, context: CallbackContext) -> int:
    """Handle field selection for editing."""
    query = update.callback_query
    query.answer()
    
    if query.data == "cancel_edit":
        query.edit_message_text(
            "Plan editing cancelled.",
            reply_markup=None
        )
        return ConversationHandler.END
    
    field = query.data.split('_')[-1]
    context.user_data['edit_field'] = field
    
    # Handle active status differently (toggle instead of value input)
    if field == 'active':
        plan = context.user_data['edit_plan']
        new_active = not plan['active']
        
        # Update in database
        db.update_plan(plan['id'], active=new_active)
        
        query.edit_message_text(
            f"Plan '{plan['name']}' active status updated to: {'Active' if new_active else 'Inactive'}",
            reply_markup=None
        )
        return ConversationHandler.END
    
    # For other fields, ask for new value
    field_name = field.replace('_', ' ').title()
    query.edit_message_text(
        f"Enter new value for {field_name}:",
        reply_markup=None
    )
    
    # Store current value
    context.user_data['current_value'] = context.user_data['edit_plan'][field]
    
    return EDIT_VALUE

def edit_value_handler(update: Update, context: CallbackContext) -> int:
    """Handle new value input for plan field."""
    field = context.user_data['edit_field']
    plan = context.user_data['edit_plan']
    new_value = update.message.text.strip()
    
    # Validate and convert value based on field type
    try:
        if field in ('traffic_limit', 'duration_days'):
            new_value = int(new_value)
            if new_value <= 0:
                update.message.reply_text(
                    f"Please enter a valid positive number for {field}:"
                )
                return EDIT_VALUE
        elif field == 'price':
            new_value = float(new_value)
            if new_value <= 0:
                update.message.reply_text(
                    "Please enter a valid positive number for price:"
                )
                return EDIT_VALUE
    except ValueError:
        update.message.reply_text(
            f"Invalid value. Please enter a valid value for {field}:"
        )
        return EDIT_VALUE
    
    # Show confirmation
    field_name = field.replace('_', ' ').title()
    
    # Save new value for later
    context.user_data['new_value'] = new_value
    
    update.message.reply_text(
        f"Change {field_name} from '{context.user_data['current_value']}' to '{new_value}'?\n\n"
        "Type 'confirm' to save this change or 'cancel' to abort."
    )
    return CONFIRM_EDIT

def confirm_edit_handler(update: Update, context: CallbackContext) -> int:
    """Handle confirmation of plan edit."""
    decision = update.message.text.strip().lower()
    
    if decision == 'confirm':
        try:
            # Update in database
            field = context.user_data['edit_field']
            plan_id = context.user_data['edit_plan']['id']
            new_value = context.user_data['new_value']
            
            # Create kwargs for the specific field
            kwargs = {field: new_value}
            
            # Update the plan
            db.update_plan(plan_id, **kwargs)
            
            field_name = field.replace('_', ' ').title()
            update.message.reply_text(
                f"✅ Plan updated: {field_name} changed to '{new_value}'",
                reply_markup=get_main_menu_keyboard()
            )
            
        except Exception as e:
            logger.error(f"Error updating plan: {str(e)}")
            update.message.reply_text(
                f"❌ Failed to update plan: {str(e)}",
                reply_markup=get_main_menu_keyboard()
            )
    else:
        update.message.reply_text(
            "Plan update cancelled.",
            reply_markup=get_main_menu_keyboard()
        )
    
    # Clear user data
    context.user_data.clear()
    return ConversationHandler.END

# Delete plan handler
def delete_plan_start(update: Update, context: CallbackContext) -> None:
    """Start the delete plan process."""
    user = update.effective_user
    
    if not is_admin(user.id):
        update.message.reply_text("Sorry, you don't have permission to delete plans.")
        return
    
    # Fetch all plans from the database
    plans = db.get_all_plans(active_only=False)
    
    if not plans:
        update.message.reply_text(
            "No plans found to delete.",
            reply_markup=get_main_menu_keyboard()
        )
        return
    
    # Create inline keyboard with plans
    keyboard = []
    for plan in plans:
        keyboard.append([InlineKeyboardButton(
            f"{plan['name']} - {plan['price']} {plan['currency']}",
            callback_data=f"delete_plan_{plan['id']}"
        )])
    
    keyboard.append([InlineKeyboardButton("Cancel", callback_data="cancel_delete")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text(
        "Select a plan to delete (this will deactivate the plan, not permanently delete it):",
        reply_markup=reply_markup
    )

def handle_plan_delete_callback(update: Update, context: CallbackContext) -> None:
    """Handle callback for plan deletion."""
    query = update.callback_query
    query.answer()
    
    if query.data == "cancel_delete":
        query.edit_message_text(
            "Plan deletion cancelled.",
            reply_markup=None
        )
        return
    
    # Get plan ID from callback data
    plan_id = int(query.data.split('_')[-1])
    
    try:
        # Get plan details first
        plan = db.get_plan(plan_id)
        
        if not plan:
            query.edit_message_text(
                "Plan not found. It may have been deleted already.",
                reply_markup=None
            )
            return
        
        # Delete (deactivate) the plan
        db.delete_plan(plan_id)
        
        query.edit_message_text(
            f"✅ Plan '{plan['name']}' has been deactivated.",
            reply_markup=None
        )
    
    except Exception as e:
        logger.error(f"Error deleting plan: {str(e)}")
        query.edit_message_text(
            f"❌ Failed to delete plan: {str(e)}",
            reply_markup=None
        )

# Set up all admin handlers
def setup_admin_handlers(dispatcher):
    """Set up all admin command and conversation handlers."""
    # Plan management commands
    dispatcher.add_handler(CommandHandler("plans", plans_command))
    
    # Add plan conversation
    add_plan_handler = ConversationHandler(
        entry_points=[CommandHandler('addplan', add_plan_start)],
        states={
            PLAN_NAME: [MessageHandler(Filters.text & ~Filters.command, plan_name_handler)],
            PLAN_DESC: [MessageHandler(Filters.text & ~Filters.command, plan_desc_handler)],
            PLAN_TRAFFIC: [MessageHandler(Filters.text & ~Filters.command, plan_traffic_handler)],
            PLAN_DURATION: [MessageHandler(Filters.text & ~Filters.command, plan_duration_handler)],
            PLAN_PRICE: [MessageHandler(Filters.text & ~Filters.command, plan_price_handler)],
            PLAN_CONFIRM: [MessageHandler(Filters.text & ~Filters.command, plan_confirm_handler)]
        },
        fallbacks=[
            CommandHandler('cancel', lambda u, c: ConversationHandler.END),
            MessageHandler(Filters.regex('^❌ Cancel$'), lambda u, c: ConversationHandler.END)
        ]
    )
    dispatcher.add_handler(add_plan_handler)
    
    # Edit plan conversation
    edit_plan_handler = ConversationHandler(
        entry_points=[CommandHandler('editplan', edit_plan_start)],
        states={
            SELECT_PLAN: [CallbackQueryHandler(select_plan_handler, pattern=r'^(edit_plan_|cancel_edit)')],
            EDIT_FIELD: [CallbackQueryHandler(edit_field_handler, pattern=r'^(edit_field_|cancel_edit)')],
            EDIT_VALUE: [MessageHandler(Filters.text & ~Filters.command, edit_value_handler)],
            CONFIRM_EDIT: [MessageHandler(Filters.text & ~Filters.command, confirm_edit_handler)]
        },
        fallbacks=[
            CommandHandler('cancel', lambda u, c: ConversationHandler.END),
            MessageHandler(Filters.regex('^❌ Cancel$'), lambda u, c: ConversationHandler.END)
        ]
    )
    dispatcher.add_handler(edit_plan_handler)
    
    # Delete plan handler
    dispatcher.add_handler(CommandHandler('deleteplan', delete_plan_start))
    dispatcher.add_handler(CallbackQueryHandler(handle_plan_delete_callback, pattern=r'^(delete_plan_|cancel_delete)'))
