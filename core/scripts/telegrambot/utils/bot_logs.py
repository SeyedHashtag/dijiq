import logging
import os

from utils.bot_logging import get_bot_log_file
from utils.command import bot, is_admin


BOT_LOGS_BUTTON_TEXT = "📄 Bot Logs"


@bot.message_handler(func=lambda message: is_admin(message.from_user.id) and message.text == BOT_LOGS_BUTTON_TEXT)
def send_bot_logs(message):
    logger = logging.getLogger("dijiq.bot.admin_logs")
    log_file = get_bot_log_file()

    if not os.path.exists(log_file) or os.path.getsize(log_file) == 0:
        bot.reply_to(message, "Bot log file is missing or empty.")
        return

    try:
        with open(log_file, "rb") as document:
            bot.send_document(
                message.chat.id,
                document,
                visible_file_name=os.path.basename(log_file),
                caption="Current bot log file.",
            )
        logger.info("Admin downloaded bot logs user_id=%s log_file=%s", message.from_user.id, log_file)
    except Exception:
        logger.exception("Failed to send bot logs user_id=%s log_file=%s", message.from_user.id, log_file)
        bot.reply_to(message, "Failed to send bot logs. Check server file permissions.")
