import io
import subprocess
from utils.command import bot, is_admin

LOG_SERVICES = [
    "dijiq-server.service",
    "dijiq-telegram-bot.service",
]
LOG_LINES = 200


def _get_service_logs(service, lines=LOG_LINES):
    cmd = [
        "journalctl",
        "-u",
        service,
        "-n",
        str(lines),
        "--no-pager",
        "--output=short-iso",
    ]
    try:
        return subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
    except FileNotFoundError:
        return "journalctl not available on this system."
    except subprocess.CalledProcessError as e:
        return f"Error reading logs for {service}: {e.output}"


def _build_logs_text():
    sections = []
    for service in LOG_SERVICES:
        sections.append(f"===== {service} (last {LOG_LINES} lines) =====")
        sections.append(_get_service_logs(service).rstrip())
        sections.append("")
    return "\n".join(sections).strip() + "\n"


@bot.message_handler(func=lambda message: is_admin(message.from_user.id) and message.text == "📜 Logs")
def send_logs(message):
    chat_id = message.chat.id
    bot.send_message(chat_id, "Collecting logs...")
    logs_text = _build_logs_text()

    log_file = io.BytesIO(logs_text.encode("utf-8"))
    log_file.name = "dijiq_logs.txt"
    bot.send_document(chat_id, log_file, caption="Latest logs (server time).")
