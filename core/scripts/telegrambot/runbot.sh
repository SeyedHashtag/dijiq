#!/bin/bash
source /etc/dijiq/core/scripts/utils.sh
define_colors

update_env_file() {
    local api_token=$1
    local admin_user_ids=$2

    cat <<EOL > /etc/dijiq/core/scripts/telegrambot/.env
API_TOKEN=$api_token
ADMIN_USER_IDS=[$admin_user_ids]
EOL
}

create_service_file() {
    cat <<EOL > /etc/systemd/system/dijiq-telegram-bot.service
[Unit]
Description=dijiq Telegram Bot
After=network.target

[Service]
ExecStart=/bin/bash -c 'source /etc/dijiq/dijiq_venv/bin/activate && /etc/dijiq/dijiq_venv/bin/python /etc/dijiq/core/scripts/telegrambot/tbot.py'
WorkingDirectory=/etc/dijiq/core/scripts/telegrambot
Restart=always

[Install]
WantedBy=multi-user.target
EOL
}

start_service() {
    local api_token=$1
    local admin_user_ids=$2

    if systemctl is-active --quiet dijiq-telegram-bot.service; then
        echo "The dijiq-telegram-bot.service is already running."
        return
    fi

    update_env_file "$api_token" "$admin_user_ids"
    create_service_file

    systemctl daemon-reload
    systemctl enable dijiq-telegram-bot.service > /dev/null 2>&1
    systemctl start dijiq-telegram-bot.service > /dev/null 2>&1

    if systemctl is-active --quiet dijiq-telegram-bot.service; then
        echo -e "${green}dijiq bot setup completed. The service is now running. ${NC}"
        echo -e "\n\n"
    else
        echo "dijiq bot setup completed. The service failed to start."
    fi
}

stop_service() {
    systemctl stop dijiq-telegram-bot.service > /dev/null 2>&1
    systemctl disable dijiq-telegram-bot.service > /dev/null 2>&1

    rm -f /etc/dijiq/core/scripts/telegrambot/.env
    echo -e "\n"

    echo "dijiq bot service stopped and disabled. .env file removed."
}

case "$1" in
    start)
        start_service "$2" "$3"
        ;;
    stop)
        stop_service
        ;;
    *)
        echo "Usage: $0 {start|stop} <API_TOKEN> <ADMIN_USER_IDS>"
        exit 1
        ;;
esac

define_colors
