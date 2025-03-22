#!/bin/bash

# Set terminal colors
GREEN="\033[0;32m"
YELLOW="\033[1;33m"
RED="\033[0;31m"
NC="\033[0m" # No Color
CHECKMARK="✅"

# Check if script is run as root
if [ "$(id -u)" -ne 0 ]; then
    echo -e "${RED}This script must be run as root.${NC}"
    exit 1
fi

# Check OS compatibility
check_os_version() {
    local os_name os_version

    if [ -f /etc/os-release ]; then
        os_name=$(grep '^ID=' /etc/os-release | cut -d= -f2)
        os_version=$(grep '^VERSION_ID=' /etc/os-release | cut -d= -f2 | tr -d '"')
    else
        echo -e "${RED}Unsupported OS or unable to determine OS version.${NC}"
        exit 1
    fi

    if ! command -v bc &> /dev/null; then
        apt update && apt install -y bc
    fi

    if [[ "$os_name" == "ubuntu" && $(echo "$os_version >= 20" | bc) -eq 1 ]] ||
       [[ "$os_name" == "debian" && $(echo "$os_version >= 10" | bc) -eq 1 ]]; then
        return 0
    else
        echo -e "${RED}This script is only supported on Ubuntu 20+ or Debian 10+.${NC}"
        exit 1
    fi
}

# Install required packages
install_dependencies() {
    REQUIRED_PACKAGES=("python3" "python3-pip" "python3-venv" "git" "curl" "jq")
    MISSING_PACKAGES=()

    for package in "${REQUIRED_PACKAGES[@]}"; do
        if ! command -v "$package" &> /dev/null; then
            MISSING_PACKAGES+=("$package")
        else
            echo -e "Package $package ${GREEN}$CHECKMARK${NC}"
        fi
    done

    if [ ${#MISSING_PACKAGES[@]} -ne 0 ]; then
        echo -e "${YELLOW}Installing missing packages: ${MISSING_PACKAGES[@]}${NC}"
        apt update -qq && apt upgrade -y -qq
        for package in "${MISSING_PACKAGES[@]}"; do
            apt install -y -qq "$package" &> /dev/null && echo -e "Installed $package ${GREEN}$CHECKMARK${NC}"
        done
    else
        echo -e "${GREEN}All required packages are already installed.${NC}"
    fi
}

# Set up the Dijiq VPN Bot
setup_dijiq() {
    INSTALL_DIR="/opt/dijiq"
    
    if [ -d "$INSTALL_DIR" ]; then
        echo -e "${YELLOW}Dijiq installation found. Updating...${NC}"
        cd "$INSTALL_DIR"
        git pull
    else
        echo -e "${GREEN}Cloning Dijiq VPN Bot...${NC}"
        git clone https://github.com/SeyedHashtag/dijiq.git "$INSTALL_DIR"
        cd "$INSTALL_DIR"
    fi
    
    # Create Python virtual environment
    echo -e "${GREEN}Setting up Python environment...${NC}"
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt && echo -e "Installed Python requirements ${GREEN}$CHECKMARK${NC}"
    
    # Configure the bot
    if [ ! -f "config.json" ]; then
        echo -e "${YELLOW}Please provide the following credentials for your bot:${NC}"
        
        # Ask for Telegram bot token
        read -p "Enter your Telegram bot token: " telegram_token
        
        # Ask for VPN API URL
        read -p "Enter your VPN API URL: " api_url
        
        # Ask for admin Telegram user ID
        read -p "Enter your Telegram user ID (for admin access): " admin_id
        
        # Create the config file
        cat > config.json << EOF
{
  "telegram_token": "$telegram_token",
  "vpn_api_url": "$api_url",
  "admin_users": [$admin_id]
}
EOF
        echo -e "Configuration file created ${GREEN}$CHECKMARK${NC}"
    else
        echo -e "Configuration file already exists ${GREEN}$CHECKMARK${NC}"
    fi
}

# Create a systemd service for auto-start
create_service() {
    cat > /etc/systemd/system/dijiq.service << EOF
[Unit]
Description=Dijiq VPN Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/dijiq
ExecStart=/opt/dijiq/venv/bin/python /opt/dijiq/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable dijiq.service
    echo -e "Created systemd service ${GREEN}$CHECKMARK${NC}"
}

# Create a bash alias for controlling the bot
create_alias() {
    if ! grep -q "alias dijiq=" ~/.bashrc; then
        echo "alias dijiq='cd /opt/dijiq && source venv/bin/activate && python main.py'" >> ~/.bashrc
        echo -e "Created 'dijiq' command alias ${GREEN}$CHECKMARK${NC}"
    fi
}

# Main installation process
main() {
    echo -e "${GREEN}Installing Dijiq VPN Bot...${NC}"
    
    check_os_version
    install_dependencies
    setup_dijiq
    create_service
    create_alias
    
    echo -e "${GREEN}Installation complete!${NC}"
    echo -e "${YELLOW}The bot has been installed as a system service.${NC}"
    echo -e "- ${GREEN}Start${NC}: systemctl start dijiq"
    echo -e "- ${YELLOW}Status${NC}: systemctl status dijiq"
    echo -e "- ${RED}Stop${NC}:  systemctl stop dijiq"
    echo -e "${YELLOW}You can also run the bot manually using the 'dijiq' command after restarting your shell.${NC}"
    
    read -p "Do you want to start the bot now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        systemctl start dijiq
        echo -e "${GREEN}Bot started! Check status with: systemctl status dijiq${NC}"
    fi
}

# Execute the installation
main
