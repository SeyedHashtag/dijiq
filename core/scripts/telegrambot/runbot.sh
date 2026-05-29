#!/bin/bash
source /etc/dijiq/core/scripts/utils.sh
define_colors

update_env_file() {
    local api_token=$1
    local admin_user_ids=$2
    local api_url=$3
    local api_key=$4
    local servers_json=$5
    local env_file="/etc/dijiq/core/scripts/telegrambot/.env"
    local preserved_env
    preserved_env=$(mktemp)

    if [ -f "$env_file" ]; then
        grep -Ev '^(API_TOKEN|ADMIN_USER_IDS|URL|TOKEN|SERVERS_JSON)=' "$env_file" > "$preserved_env" || true
    fi

    {
        printf 'API_TOKEN=%s\n' "$api_token"
        printf 'ADMIN_USER_IDS=[%s]\n' "$admin_user_ids"
        printf 'URL=%s\n' "$api_url"
        printf 'TOKEN=%s\n' "$api_key"
        if [ -n "$servers_json" ]; then
            printf 'SERVERS_JSON=%s\n' "$servers_json"
        fi
        if [ -s "$preserved_env" ]; then
            cat "$preserved_env"
        fi
    } > "$env_file"

    rm -f "$preserved_env"
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
    local api_url=$3
    local api_key=$4
    local servers_json=$5

    if systemctl is-active --quiet dijiq-telegram-bot.service; then
        echo "The dijiq-telegram-bot.service is already running."
        return
    fi

    update_env_file "$api_token" "$admin_user_ids" "$api_url" "$api_key" "$servers_json"
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
        start_service "$2" "$3" "$4" "$5" "$6"
        ;;
    stop)
        stop_service
        ;;
    *)
        echo "Usage: $0 {start|stop} <API_TOKEN> <ADMIN_USER_IDS> <API_URL> <API_KEY> [SERVERS_JSON]"
        exit 1
        ;;
esac

define_colors
