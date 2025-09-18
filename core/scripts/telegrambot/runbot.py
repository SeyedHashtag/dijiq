#!/usr/bin/env python3

import sys
import subprocess
from pathlib import Path
import os

core_scripts_dir = Path(__file__).resolve().parents[1]
if str(core_scripts_dir) not in sys.path:
    sys.path.append(str(core_scripts_dir))

from paths import TELEGRAM_ENV

def update_env_file(api_token, admin_user_ids, backup_interval):
    TELEGRAM_ENV.write_text(f"""API_TOKEN={api_token}
ADMIN_USER_IDS=[{admin_user_ids}]
BACKUP_INTERVAL_HOUR={backup_interval}
""")

def create_service_file():
    Path("/etc/systemd/system/hysteria-telegram-bot.service").write_text("""[Unit]
Description=Hysteria Telegram Bot
After=network.target

[Service]
ExecStart=/bin/bash -c 'source /etc/hysteria/hysteria2_venv/bin/activate && /etc/hysteria/hysteria2_venv/bin/python /etc/hysteria/core/scripts/telegrambot/tbot.py'
WorkingDirectory=/etc/hysteria/core/scripts/telegrambot
Restart=always

[Install]
WantedBy=multi-user.target
""")

def start_service(api_token, admin_user_ids, backup_interval=12):
    if subprocess.run(["systemctl", "is-active", "--quiet", "hysteria-telegram-bot.service"]).returncode == 0:
        print("The hysteria-telegram-bot.service is already running.")
        return

    update_env_file(api_token, admin_user_ids, backup_interval)
    create_service_file()

    subprocess.run(["systemctl", "daemon-reload"])
    subprocess.run(["systemctl", "enable", "hysteria-telegram-bot.service"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["systemctl", "start", "hysteria-telegram-bot.service"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    if subprocess.run(["systemctl", "is-active", "--quiet", "hysteria-telegram-bot.service"]).returncode == 0:
        print("Hysteria bot setup completed. The service is now running.\n")
    else:
        print("Hysteria bot setup completed. The service failed to start.")

def stop_service():
    subprocess.run(["systemctl", "stop", "hysteria-telegram-bot.service"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["systemctl", "disable", "hysteria-telegram-bot.service"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    TELEGRAM_ENV.unlink(missing_ok=True)
    print("\nHysteria bot service stopped and disabled. .env file removed.")

def set_backup_interval(backup_interval):
    if not os.path.exists(TELEGRAM_ENV):
        print("Error: The .env file does not exist. Please start the bot first.")
        sys.exit(1)

    with open(TELEGRAM_ENV, 'r') as f:
        lines = f.readlines()

    with open(TELEGRAM_ENV, 'w') as f:
        found = False
        for line in lines:
            if line.strip().startswith("BACKUP_INTERVAL_HOUR"):
                f.write(f"BACKUP_INTERVAL_HOUR={backup_interval}\n")
                found = True
            else:
                f.write(line)
        if not found:
            f.write(f"BACKUP_INTERVAL_HOUR={backup_interval}\n")

    print(f"Backup interval has been set to {backup_interval} hour(s). Restarting the bot to apply changes...")
    subprocess.run(["systemctl", "restart", "hysteria-telegram-bot.service"])

def print_usage():
    print("Usage:")
    print("  python3 runbot.py start <API_TOKEN> <ADMIN_USER_IDS> [BACKUP_INTERVAL_HOUR]")
    print("  python3 runbot.py stop")
    print("  python3 runbot.py set_backup_interval <BACKUP_INTERVAL_HOUR>")
    print("\nDefault BACKUP_INTERVAL_HOUR is 12.")
    sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print_usage()

    action = sys.argv[1]

    if action == "start":
        if not (4 <= len(sys.argv) <= 5):
            print_usage()
        
        api_token = sys.argv[2]
        admin_user_ids = sys.argv[3]
        
        if len(sys.argv) == 5:
            backup_interval = sys.argv[4]
            start_service(api_token, admin_user_ids, backup_interval)
        else:
            start_service(api_token, admin_user_ids)
            
    elif action == "stop":
        stop_service()
    elif action == "set_backup_interval":
        if len(sys.argv) != 3:
            print_usage()
        set_backup_interval(sys.argv[2])
    else:
        print_usage()