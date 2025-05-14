#!/bin/bash

cd /root/
TEMP_DIR=$(mktemp -d)

FILES=(
    "/etc/dijiq/users.json"
    "/etc/dijiq/.configs.env"
    "/etc/dijiq/core/scripts/telegrambot/.env"
    "/etc/dijiq/core/scripts/telegrambot/plans.json"
    "/etc/dijiq/core/scripts/telegrambot/test_configs.json"
    "/etc/dijiq/core/scripts/telegrambot/payments.json"
    "/etc/dijiq/core/scripts/telegrambot/support_info.json"
    "/etc/dijiq/core/scripts/telegrambot/user_languages.json"
)

echo "Backing up and stopping all cron jobs"
crontab -l > /tmp/crontab_backup
crontab -r

echo "Backing up files to $TEMP_DIR"
for FILE in "${FILES[@]}"; do
    mkdir -p "$TEMP_DIR/$(dirname "$FILE")"
    cp "$FILE" "$TEMP_DIR/$FILE"
done

echo "Checking and renaming old systemd service files"
declare -A SERVICE_MAP=(
    ["/etc/systemd/system/dijiq-bot.service"]="dijiq-telegram-bot.service"
)

for OLD_SERVICE in "${!SERVICE_MAP[@]}"; do
    NEW_SERVICE="/etc/systemd/system/${SERVICE_MAP[$OLD_SERVICE]}"

    if [[ -f "$OLD_SERVICE" ]]; then
        echo "Stopping old service: $(basename "$OLD_SERVICE")"
        systemctl stop "$(basename "$OLD_SERVICE")" 2>/dev/null

        echo "Renaming $OLD_SERVICE to $NEW_SERVICE"
        mv "$OLD_SERVICE" "$NEW_SERVICE"

        echo "Reloading systemd daemon"
        systemctl daemon-reload
    fi
done

echo "Removing /etc/dijiq directory"
rm -rf /etc/dijiq/

echo "Cloning dijiq repository"
git clone https://github.com/SeyedHashtag/dijiq /etc/dijiq

echo "Restoring backup files"
for FILE in "${FILES[@]}"; do
    cp "$TEMP_DIR/$FILE" "$FILE"
done


CONFIG_ENV="/etc/dijiq/.configs.env"
if [ ! -f "$CONFIG_ENV" ]; then
    echo ".configs.env not found, creating it with default values."
    echo "SNI=bts.com" > "$CONFIG_ENV"
fi

export $(grep -v '^#' "$CONFIG_ENV" | xargs 2>/dev/null)

if [[ -z "$IP4" ]]; then
    echo "IP4 not found, fetching from ip.gs..."
    IP4=$(curl -s -4 ip.gs || echo "")
    echo "IP4=${IP4:-}" >> "$CONFIG_ENV"
fi

if [[ -z "$IP6" ]]; then
    echo "IP6 not found, fetching from ip.gs..."
    IP6=$(curl -s -6 ip.gs || echo "")
    echo "IP6=${IP6:-}" >> "$CONFIG_ENV"
fi

echo "Setting ownership and permissions"
chown -R dijiq:dijiq /etc/dijiq/core/scripts/telegrambot

echo "Setting execute permissions for user.sh and kick.sh"
chmod +x /etc/dijiq/core/scripts/dijiq/user.sh
chmod +x /etc/dijiq/core/scripts/dijiq/kick.sh

cd /etc/dijiq
python3 -m venv dijiq_venv
source /etc/dijiq/dijiq_venv/bin/activate
pip install -r requirements.txt

echo "Restarting other dijiq services"
systemctl restart dijiq-server.service
systemctl restart dijiq-telegram-bot.service


echo "Checking dijiq-server.service status"
if systemctl is-active --quiet dijiq-server.service; then
    echo "Upgrade completed successfully"
else
    echo "Upgrade failed: dijiq-server.service is not active"
fi

echo "Restoring cron jobs"
crontab /tmp/crontab_backup
rm /tmp/crontab_backup

chmod +x menu.sh
./menu.sh
