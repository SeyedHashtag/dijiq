from utils.command import *

@bot.message_handler(func=lambda message: is_admin(message.from_user.id) and message.text == '🔗 Get Webpanel URL')
def get_webpanel_url_handler(message):
    command = f"python3 {CLI_PATH} get-webpanel-url --url-only"
    result = run_cli_command(command)
    bot.send_chat_action(message.chat.id, 'typing')
    bot.reply_to(message, "🌐 Webpanel URL:\n" + result)