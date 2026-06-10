#!/bin/bash

BACKUP_DIR="/opt/hysbackup"
BACKUP_FILE="$BACKUP_DIR/dijiq_backup_$(date +%Y%m%d_%H%M%S).zip"

if [ ! -d "$BACKUP_DIR" ]; then
    mkdir -p "$BACKUP_DIR"
fi

FILES_TO_BACKUP=(
    "/etc/dijiq/.configs.env"
    "/etc/dijiq/core/scripts/telegrambot/.env"
    "/etc/dijiq/core/scripts/telegrambot/plans.json"
    "/etc/dijiq/core/scripts/telegrambot/test_configs.json"
    "/etc/dijiq/core/scripts/telegrambot/test_settings.json"
    "/etc/dijiq/core/scripts/telegrambot/waiting_test_users.json"
    "/etc/dijiq/core/scripts/telegrambot/payments.json"
    "/etc/dijiq/core/scripts/telegrambot/support_info.json"
    "/etc/dijiq/core/scripts/telegrambot/user_languages.json"
    "/etc/dijiq/core/scripts/telegrambot/referrals.json"
    "/etc/dijiq/core/scripts/telegrambot/resellers.json"
    "/etc/dijiq/core/scripts/telegrambot/checker_settlements.json"
    "/etc/dijiq/core/scripts/telegrambot/traffic_alerts.json"
    "/etc/dijiq/core/scripts/telegrambot/broadcast_failed_users.json"
    "/etc/dijiq/core/scripts/telegrambot/expired_user_cleanup.json"
)

EXISTING_FILES=()
for FILE in "${FILES_TO_BACKUP[@]}"; do
    if [ -f "$FILE" ]; then
        EXISTING_FILES+=("$FILE")
    fi
done

zip -j "$BACKUP_FILE" "${EXISTING_FILES[@]}" >/dev/null

if [ $? -eq 0 ]; then
    echo "Backup successfully created"
else
    echo "Backup failed!"
fi
