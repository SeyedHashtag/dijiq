#!/bin/bash

BACKUP_DIR="/opt/hysbackup"
BACKUP_FILE="$BACKUP_DIR/hysteria_backup_$(date +%Y%m%d_%H%M%S).zip"

if [ ! -d "$BACKUP_DIR" ]; then
    mkdir -p "$BACKUP_DIR"
fi

FILES_TO_BACKUP=(
    "/etc/hysteria/ca.key"
    "/etc/hysteria/ca.crt"
    "/etc/hysteria/users.json"
    "/etc/hysteria/config.json"
    "/etc/hysteria/core/scripts/telegrambot/.env"
    "/etc/hysteria/.configs.env"
    "/etc/hysteria/payments.json"
    "/etc/hysteria/plans.json"
    "/etc/hysteria/test_mode.json"
    "/etc/hysteria/statistics.json"
)

zip -j "$BACKUP_FILE" "${FILES_TO_BACKUP[@]}" >/dev/null

if [ $? -eq 0 ]; then
    echo "Backup successfully created"
else
    echo "Backup failed!"
fi
