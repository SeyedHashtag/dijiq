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
    IS_UPDATE=false
    
    if [ -d "$INSTALL_DIR" ]; then
        echo -e "${YELLOW}Dijiq installation found. Updating...${NC}"
        cd "$INSTALL_DIR"
        
        # Check if the service is running before updating
        SERVICE_WAS_RUNNING=false
        if systemctl is-active --quiet dijiq.service; then
            SERVICE_WAS_RUNNING=true
            echo -e "${YELLOW}Stopping service for update...${NC}"
            systemctl stop dijiq.service
        fi
        
        # Store current version before update
        PREV_VERSION=""
        if [ -f "VERSION" ]; then
            PREV_VERSION=$(cat VERSION)
        fi
        
        # Perform the update
        git pull
        
        # Set flag to indicate this is an update
        IS_UPDATE=true
        
        # If there's a version file, check if version changed
        if [ -f "VERSION" ]; then
            CURR_VERSION=$(cat VERSION)
            if [ "$PREV_VERSION" != "$CURR_VERSION" ] && [ ! -z "$PREV_VERSION" ]; then
                echo -e "${GREEN}Updated from version $PREV_VERSION to $CURR_VERSION${NC}"
                
                # Display changelog if available
                if [ -f "CHANGELOG.md" ]; then
                    echo -e "${YELLOW}Changelog:${NC}"
                    cat CHANGELOG.md | head -n 20  # Show first 20 lines of changelog
                    echo -e "${YELLOW}...(see full changelog in CHANGELOG.md)${NC}"
                fi
            fi
        fi
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
    
    # Configure the bot using environment variables
    if [ ! -f ".env" ]; then
        echo -e "${YELLOW}Please provide the following credentials for your bot:${NC}"
        
        # Ask for Telegram bot token
        read -p "Enter your Telegram bot token: " telegram_token
        
        # Ask for VPN API URL
        read -p "Enter your VPN API URL: " api_url
        
        # Ask for admin Telegram user ID
        read -p "Enter your Telegram user ID (for admin access): " admin_id
        
        # Ask for API key (optional)
        read -p "Enter your VPN API key (leave blank if not required): " api_key
        
        # Create the .env file
        cat > "$INSTALL_DIR/.env" << EOF
# Telegram Bot Token
TELEGRAM_TOKEN=$telegram_token

# VPN API URL
VPN_API_URL=$api_url

# Admin User IDs (comma-separated list)
ADMIN_USERS=$admin_id

# API Key for authentication
API_KEY=$api_key

# Set to false by default, can be enabled for debugging
DEBUG=false
EOF
        echo -e "Environment configuration file created ${GREEN}$CHECKMARK${NC}"
    else
        echo -e "Environment configuration file already exists ${GREEN}$CHECKMARK${NC}"
    fi
    
    # Export variables for later use
    export IS_UPDATE SERVICE_WAS_RUNNING
}

# Create a systemd service for auto-start with environment variables
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
# Environment variables are loaded from .env file using python-dotenv

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
        echo "alias dijiq='cd /opt/dijiq && source venv/bin/activate && python cli.py'" >> ~/.bashrc
        echo -e "Created 'dijiq' command alias ${GREEN}$CHECKMARK${NC}"
    fi
}

# Create a symlink for global access to CLI
create_symlink() {
    SYMLINK_PATH="/usr/local/bin/dijiq"
    
    cat > "$SYMLINK_PATH" << EOF
#!/bin/bash
cd /opt/dijiq && source venv/bin/activate && python cli.py "\$@"
EOF
    
    chmod +x "$SYMLINK_PATH"
    echo -e "Created 'dijiq' command in /usr/local/bin ${GREEN}$CHECKMARK${NC}"
}

# Main installation process
main() {
    echo -e "${GREEN}Installing Dijiq VPN Bot...${NC}"
    
    check_os_version
    install_dependencies
    setup_dijiq
    create_service
    create_alias
    create_symlink
    
    echo -e "${GREEN}Installation complete!${NC}"
    echo -e "${YELLOW}The bot has been installed as a system service.${NC}"
    echo -e "- ${GREEN}Start${NC}: systemctl start dijiq"
    echo -e "- ${YELLOW}Status${NC}: systemctl status dijiq"
    echo -e "- ${RED}Stop${NC}:  systemctl stop dijiq"
    echo -e "${YELLOW}You can also run the bot using the 'dijiq' command.${NC}"
    
    echo -e "${YELLOW}SECURITY NOTE: For production use, consider setting environment variables directly${NC}"
    echo -e "${YELLOW}in the system rather than using a .env file for better security.${NC}"
    
    # If this is an update and the service was running, restart it automatically
    if [ "$IS_UPDATE" = true ]; then
        if [ "$SERVICE_WAS_RUNNING" = true ]; then
            echo -e "${YELLOW}Restarting service to apply updates...${NC}"
            systemctl restart dijiq
            echo -e "${GREEN}Service restarted successfully!${NC}"
        else
            # For updates where the service wasn't running, ask if they want to start it
            read -p "Do you want to start the bot now? (y/n) " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                systemctl start dijiq
                echo -e "${GREEN}Bot started! Check status with: systemctl status dijiq${NC}"
            fi
        fi
    else
        # For fresh installations, ask if they want to start it
        read -p "Do you want to start the bot now? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            systemctl start dijiq
            echo -e "${GREEN}Bot started! Check status with: systemctl status dijiq${NC}"
        fi
    fi
}

# Execute the installation
main
