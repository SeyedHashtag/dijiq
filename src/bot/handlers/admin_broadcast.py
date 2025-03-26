from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import CallbackContext, MessageHandler, Filters, ConversationHandler, CommandHandler
from src.utils.config import is_admin
from src.bot.keyboards import get_main_menu_keyboard
import json

# Define conversation states
SELECT_AUDIENCE, COMPOSE_MESSAGE = range(2)

def create_broadcast_markup():
    markup = ReplyKeyboardMarkup(
        [['👥 All Users', '✅ Active Users'], 
         ['⛔️ Expired Users', '❌ Cancel']], 
        resize_keyboard=True
    )
    return markup

def get_user_ids(filter_type):
    """Get user IDs based on filter type"""
    # In an API-based approach, we'd need to get this from wherever users are stored
    # For now, returning a placeholder. This would need to be implemented with your API.
    return []

def start_broadcast(update: Update, context: CallbackContext) -> int:
    """Start the broadcast process"""
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    
    update.message.reply_text(
        "Select the target users for your broadcast:",
        reply_markup=create_broadcast_markup()
    )
    return SELECT_AUDIENCE

def process_broadcast_target(update: Update, context: CallbackContext) -> int:
    """Process the selected audience"""
    if update.message.text == "❌ Cancel":
        update.message.reply_text(
            "Broadcast canceled.",
            reply_markup=get_main_menu_keyboard(is_admin=True)
        )
        return ConversationHandler.END
        
    target_map = {
        '👥 All Users': 'all',
        '✅ Active Users': 'active',
        '⛔️ Expired Users': 'expired'
    }
    
    if update.message.text not in target_map:
        update.message.reply_text(
            "Invalid selection. Please use the provided buttons.",
            reply_markup=create_broadcast_markup()
        )
        return SELECT_AUDIENCE
        
    context.user_data['broadcast_target'] = target_map[update.message.text]
    
    update.message.reply_text(
        "Enter the message you want to broadcast:",
        reply_markup=ReplyKeyboardMarkup([['❌ Cancel']], resize_keyboard=True)
    )
    return COMPOSE_MESSAGE

def send_broadcast(update: Update, context: CallbackContext) -> int:
    """Send the broadcast message"""
    if update.message.text == "❌ Cancel":
        update.message.reply_text(
            "Broadcast canceled.",
            reply_markup=get_main_menu_keyboard(is_admin=True)
        )
        return ConversationHandler.END
        
    broadcast_text = update.message.text.strip()
    if not broadcast_text:
        update.message.reply_text(
            "Message cannot be empty. Please try again:",
            reply_markup=ReplyKeyboardMarkup([['❌ Cancel']], resize_keyboard=True)
        )
        return COMPOSE_MESSAGE
        
    target = context.user_data.get('broadcast_target', 'all')
    user_ids = get_user_ids(target)
    
    if not user_ids:
        update.message.reply_text(
            "No users found in the selected category.",
            reply_markup=get_main_menu_keyboard(is_admin=True)
        )
        return ConversationHandler.END
        
    success_count = 0
    fail_count = 0
    
    status_msg = update.message.reply_text(f"Broadcasting message to {len(user_ids)} users...")
    
    for user_id in user_ids:
        try:
            context.bot.send_message(int(user_id), broadcast_text)
            success_count += 1
        except Exception as e:
            print(f"Failed to send broadcast to {user_id}: {str(e)}")
            fail_count += 1
            
        # Update status every 10 users
        if (success_count + fail_count) % 10 == 0:
            try:
                context.bot.edit_message_text(
                    f"Broadcasting: {success_count + fail_count}/{len(user_ids)} completed...",
                    chat_id=status_msg.chat.id,
                    message_id=status_msg.message_id
                )
            except:
                pass
    
    final_report = (
        "📢 Broadcast Completed\n\n"
        f"Target: {update.message.text}\n"
        f"Total Users: {len(user_ids)}\n"
        f"✅ Successful: {success_count}\n"
        f"❌ Failed: {fail_count}"
    )
    
    update.message.reply_text(
        final_report,
        reply_markup=get_main_menu_keyboard(is_admin=True)
    )
    return ConversationHandler.END

def cancel_broadcast(update: Update, context: CallbackContext) -> int:
    update.message.reply_text(
        "Broadcast canceled.",
        reply_markup=get_main_menu_keyboard(is_admin=True)
    )
    return ConversationHandler.END

def setup_admin_broadcast_handlers(dispatcher):
    """Register admin broadcast handlers"""
    broadcast_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(Filters.regex('^📢 Broadcast Message$') & Filters.user(is_admin), start_broadcast)],
        states={
            SELECT_AUDIENCE: [MessageHandler(Filters.text & ~Filters.command, process_broadcast_target)],
            COMPOSE_MESSAGE: [MessageHandler(Filters.text & ~Filters.command, send_broadcast)]
        },
        fallbacks=[CommandHandler('cancel', cancel_broadcast)]
    )
    
    dispatcher.add_handler(broadcast_conv_handler)
