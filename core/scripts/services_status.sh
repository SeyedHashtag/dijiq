#!/bin/bash

declare -a services=(
    "dijiq-server.service"
    "dijiq-telegram-bot.service"
)

status_json="{"
for service in "${services[@]}"; do
    if systemctl is-active --quiet "$service"; then
        status_json+="\"$service\":true,"
    else
        status_json+="\"$service\":false,"
    fi
done

# Remove trailing comma and close JSON properly
status_json="${status_json%,}}"

# Format output as valid JSON
echo "$status_json" | jq -M .
