#!/bin/bash

# Set terminal colors
GREEN="\033[0;32m"
YELLOW="\033[1;33m"
RED="\033[0;31m"
NC="\033[0m" # No Color
CHECKMARK="✅"

# Log file
LOG_FILE="/var/log/dijiq-update.log"
INSTALL_DIR="/opt/dijiq"

# Function to log messages
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
    echo -e "$1"
}

# Check if script is run as root
if [ "$(id -u)" -ne 0 ]; then
    log_message "${RED}This script must be run as root.${NC}"
    exit 1
fi

# Function to compare version strings
version_gt() {
    test "$(printf '%s\n' "$@" | sort -V | head -n 1)" != "$1"
}

# Function to check for updates
check_for_updates() {
    cd "$INSTALL_DIR" || exit 1
    
    # Get current local version
    LOCAL_VERSION=$(cat VERSION 2>/dev/null || echo "0.0.0")
    
    # Fetch latest changes without merging
    git fetch origin --quiet
    
    # Get remote version from the repo
    REMOTE_VERSION=$(git show origin/main:VERSION 2>/dev/null || echo "0.0.0")
    
    log_message "Local version: $LOCAL_VERSION, Remote version: $REMOTE_VERSION"
    
    # Compare versions
    if version_gt "$REMOTE_VERSION" "$LOCAL_VERSION"; then
        return 0  # Update available
    else
        return 1  # No update available
    fi
}

# Function to update the bot
update_bot() {
    log_message "${YELLOW}Update found! Updating Dijiq from $LOCAL_VERSION to $REMOTE_VERSION...${NC}"
    
    # Check if service is running
    SERVICE_WAS_RUNNING=false
    if systemctl is-active --quiet dijiq.service; then
        SERVICE_WAS_RUNNING=true
        log_message "${YELLOW}Stopping service for update...${NC}"
        systemctl stop dijiq.service
    fi
    
    # Perform update
    log_message "Pulling latest changes..."
    git pull origin main
    
    # Update Python dependencies if requirements changed
    if git diff --name-only HEAD@{1} HEAD | grep -q "requirements.txt"; then
        log_message "Requirements changed, updating Python packages..."
        source venv/bin/activate
        pip install -r requirements.txt
        deactivate
    fi
    
    # Restart service if it was running
    if [ "$SERVICE_WAS_RUNNING" = true ]; then
        log_message "${GREEN}Restarting service...${NC}"
        systemctl restart dijiq.service
    fi
    
    log_message "${GREEN}Update completed successfully! New version: $(cat VERSION)${NC}"
    
    # Display changelog if available
    if [ -f "CHANGELOG.md" ]; then
        log_message "${YELLOW}Changelog:${NC}"
        cat CHANGELOG.md | head -n 10 >> "$LOG_FILE"  # Log first 10 lines
    fi
    
    return 0
}

# Main function
main() {
    log_message "Checking for Dijiq updates..."
    
    if check_for_updates; then
        update_bot
    else
        log_message "${GREEN}No updates available. Current version: $LOCAL_VERSION${NC}"
    fi
}

# Execute main function
main
