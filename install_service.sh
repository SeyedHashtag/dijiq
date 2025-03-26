#!/bin/bash

# Set terminal colors
GREEN="\033[0;32m"
YELLOW="\033[1;33m"
RED="\033[0;31m"
NC="\033[0m" # No Color
CHECKMARK="✅"

update_env_file() {
    local api_token=$1
    local admin_user_ids=$2
    local env_file=".env"

    # Save existing Cryptomus credentials if they exist
    local merchant_id=""
    local api_key=""
    if [ -f "$env_file" ]; then
        merchant_id=$(grep CRYPTOMUS_MERCHANT_ID "$env_file" | cut -d '=' -f2)
        api_key=$(grep CRYPTOMUS_API_KEY "$env_file" | cut -d '=' -f2)
    fi

    # Create new .env file
    cat <<EOL > "$env_file"
# Telegram Bot Token
TELEGRAM_TOKEN=$api_token

# Admin User IDs (comma-separated list of Telegram user IDs)
ADMIN_USERS=$admin_user_ids

# Default VPN API URL - adjust as needed
VPN_API_URL=http://localhost:8080
EOL

    # Add back Cryptomus credentials if they existed
    if [ ! -z "$merchant_id" ]; then
        echo "CRYPTOMUS_MERCHANT_ID=$merchant_id" >> "$env_file"
    fi
    if [ ! -z "$api_key" ]; then
        echo "CRYPTOMUS_API_KEY=$api_key" >> "$env_file"
    fi
    
    # Add a debug flag (off by default)
    echo "DEBUG=false" >> "$env_file"
}

create_service_file() {
    SERVICE_FILE="/etc/systemd/system/dijiq-bot.service"
    CURRENT_DIR=$(pwd)
    
    cat <<EOL | sudo tee $SERVICE_FILE > /dev/null
[Unit]
Description=Dijiq Telegram Bot
After=network.target

[Service]
Type=simple
WorkingDirectory=$CURRENT_DIR
ExecStart=$CURRENT_DIR/venv/bin/python $CURRENT_DIR/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOL
}

setup_virtualenv() {
    # Check if virtualenv is installed
    if ! command -v virtualenv &> /dev/null; then
        echo -e "${YELLOW}Installing virtualenv...${NC}"
        pip3 install virtualenv
    fi

    # Create virtual environment if it doesn't exist
    if [ ! -d "venv" ]; then
        echo -e "${GREEN}Creating virtual environment...${NC}"
        virtualenv venv
    fi

    # Activate virtual environment and install requirements
    echo -e "${GREEN}Installing dependencies...${NC}"
    source venv/bin/activate
    pip install -r requirements.txt
    deactivate
}

start_service() {
    local api_token=$1
    local admin_user_ids=$2

    update_env_file "$api_token" "$admin_user_ids"
    setup_virtualenv
    create_service_file

    # Create data directory if it doesn't exist
    mkdir -p data

    sudo systemctl daemon-reload
    sudo systemctl enable dijiq-bot.service
    sudo systemctl start dijiq-bot.service

    if systemctl is-active --quiet dijiq-bot.service; then
        echo -e "${GREEN}Bot setup completed. The service is now running.${NC}"
    else
        echo -e "${RED}Bot setup completed, but the service failed to start.${NC}"
    fi
}

stop_service() {
    sudo systemctl stop dijiq-bot.service
    sudo systemctl disable dijiq-bot.service
    sudo rm -f /etc/systemd/system/dijiq-bot.service
    
    echo -e "${YELLOW}Bot service stopped and removed.${NC}"
}

case "$1" in
    start)
        if [ $# -lt 3 ]; then
            echo "Usage: $0 start <API_TOKEN> <ADMIN_USER_IDS>"
            exit 1
        fi
        start_service "$2" "$3"
        ;;
    stop)
        stop_service
        ;;
    *)
        echo "Usage: $0 {start|stop} [API_TOKEN ADMIN_USER_IDS]"
        exit 1
        ;;
esac
