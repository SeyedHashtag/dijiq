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
    "/etc/dijiq/core/scripts/telegrambot/payments.json"
    "/etc/dijiq/core/scripts/telegrambot/support_info.json"
    "/etc/dijiq/core/scripts/telegrambot/user_languages.json"
    "/etc/dijiq/core/scripts/telegrambot/referrals.json"
    "/etc/dijiq/core/scripts/telegrambot/resellers.json"
    "/etc/dijiq/core/scripts/telegrambot/traffic_alerts.json"
)

zip -j "$BACKUP_FILE" "${FILES_TO_BACKUP[@]}" >/dev/null

if [ $? -eq 0 ]; then
    echo "Backup successfully created"
else
    echo "Backup failed!"
fi
