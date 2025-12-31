import time
from utils.command import bot, is_admin
from utils.test_config import load_test_configs
from utils.common import create_main_markup
from utils.translations import get_message_text
from utils.language import get_user_language

@bot.message_handler(func=lambda message: message.text == '🔄 Update Keyboards' and is_admin(message.from_user.id))
def handle_update_keyboards(message):
    """
    Admin command to update the main keyboard for all users in the test config list.
    """
    bot.reply_to(message, "⏳ Starting keyboard update for test config users...")
    
    configs = load_test_configs()
    user_ids = list(configs.keys())
    
    if not user_ids:
        bot.reply_to(message, "❌ No users found in the test config list.")
        return
        
    success_count = 0
    fail_count = 0
    total_users = len(user_ids)
    
    status_msg = bot.send_message(
        message.chat.id, 
        f"📊 Processing: 0/{total_users}\n✅ Success: 0\n❌ Failed: 0"
    )
    
    for i, user_id_str in enumerate(user_ids):
        try:
            user_id = int(user_id_str)
            language = get_user_language(user_id)
            
            # Send a message with the new keyboard
            # We use a generic update message.
            update_text = get_message_text(language, "menu_updated_notification")
            # If translation key doesn't exist, fallback to English
            if update_text == "menu_updated_notification":
                 update_text = "🔄 We have updated our menu to serve you better. Here is the latest version!"
            
            bot.send_message(
                user_id,
                update_text,
                reply_markup=create_main_markup(is_admin=False, user_id=user_id)
            )
            success_count += 1
            
        except Exception as e:
            # Common errors: user blocked bot, user not found, etc.
            print(f"Failed to update keyboard for user {user_id_str}: {e}")
            fail_count += 1
            
        # Update status every 10 users or at the end
        if (i + 1) % 10 == 0 or (i + 1) == total_users:
            try:
                bot.edit_message_text(
                    f"📊 Processing: {i + 1}/{total_users}\n✅ Success: {success_count}\n❌ Failed: {fail_count}",
                    chat_id=status_msg.chat.id,
                    message_id=status_msg.message_id
                )
            except Exception:
                pass
                
        # Small delay to avoid hitting rate limits
        time.sleep(0.1)
        
    bot.send_message(
        message.chat.id,
        f"✅ Keyboard update completed!\n\nTarget Users: {total_users}\nSuccess: {success_count}\nFailed: {fail_count}"
    )
