import json
import os
from telebot import types
from utils.command import bot, is_admin
from utils.language import get_text, get_user_language

HELP_FILE = '/etc/hysteria/help_messages.json'
DEFAULT_HELP = {
    "en": """*Need Help?*

🔹 *How to Use:*
1. Choose a plan from our available options
2. Complete the payment
3. Get your VPN configuration
4. Download the app for your device
5. Import your configuration and connect!

🔸 *Common Issues:*
• Connection problems? Try switching between different apps
• Slow speed? Try changing the server location
• Payment issues? Contact support

For more assistance, contact @admin"""
}

def load_help_messages():
    """Load help messages from JSON file"""
    if not os.path.exists(HELP_FILE):
        save_help_messages(DEFAULT_HELP)
        return DEFAULT_HELP
    try:
        with open(HELP_FILE, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return DEFAULT_HELP

def save_help_messages(messages):
    """Save help messages to JSON file"""
    os.makedirs(os.path.dirname(HELP_FILE), exist_ok=True)
    with open(HELP_FILE, 'w') as f:
        json.dump(messages, f, indent=4)

@bot.message_handler(func=lambda message: is_admin(message.from_user.id) and message.text == '📝 Edit Help')
def edit_help_message(message):
    """Start help message editing process"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    help_messages = load_help_messages()
    
    for lang_code in help_messages.keys():
        markup.add(types.InlineKeyboardButton(
            f"Edit {lang_code.upper()}",
            callback_data=f"edit_help:{lang_code}"
        ))
    
    markup.add(types.InlineKeyboardButton("❌ Close", callback_data="close_help_menu"))
    
    bot.reply_to(
        message,
        "Select language to edit help message:",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_help:'))
def handle_help_edit(call):
    """Handle help message editing"""
    if not is_admin(call.from_user.id):
        return
        
    lang_code = call.data.split(':')[1]
    help_messages = load_help_messages()
    current_message = help_messages.get(lang_code, DEFAULT_HELP['en'])
    
    msg = bot.edit_message_text(
        f"Current help message for {lang_code.upper()}:\n\n{current_message}\n\nSend new help message (supports Markdown):",
        call.message.chat.id,
        call.message.message_id
    )
    
    bot.register_next_step_handler(msg, save_help_message, lang_code)

def save_help_message(message, lang_code):
    """Save new help message"""
    try:
        # Test markdown formatting
        bot.send_message(
            message.chat.id,
            message.text,
            parse_mode="Markdown"
        )
        
        help_messages = load_help_messages()
        help_messages[lang_code] = message.text
        save_help_messages(help_messages)
        
        bot.reply_to(message, "✅ Help message updated successfully!")
        
    except Exception as e:
        bot.reply_to(
            message,
            f"❌ Error saving message: {str(e)}\nMake sure the markdown formatting is correct."
        )

@bot.message_handler(func=lambda message: not is_admin(message.from_user.id) and message.text == get_text(get_user_language(message.from_user.id), "support"))
def show_help(message):
    """Show help message to users"""
    language = get_user_language(message.from_user.id)
    help_messages = load_help_messages()
    help_text = help_messages.get(language, help_messages['en'])
    
    bot.reply_to(
        message,
        help_text,
        parse_mode="Markdown"
    ) 
