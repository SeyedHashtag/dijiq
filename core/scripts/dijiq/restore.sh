#!/bin/bash
source /etc/dijiq/core/scripts/path.sh

# Usage: ./restore.sh <backup_zip_file>

set -e 

BACKUP_ZIP_FILE="$1"
RESTORE_DIR="/tmp/dijiq_restore_$(date +%Y%m%d_%H%M%S)"
TARGET_DIR="/etc/dijiq"

if [ -z "$BACKUP_ZIP_FILE" ]; then
  echo "Error: Backup file path is required."
  exit 1
fi

if [ ! -f "$BACKUP_ZIP_FILE" ]; then
  echo "Error: Backup file not found: $BACKUP_ZIP_FILE"
  exit 1
fi

if [[ "$BACKUP_ZIP_FILE" != *.zip ]]; then
  echo "Error: Backup file must be a .zip file."
  exit 1
fi

mkdir -p "$RESTORE_DIR"

unzip -l "$BACKUP_ZIP_FILE" >/dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "Error: Invalid ZIP file."
    rm -rf "$RESTORE_DIR" 
    exit 1
fi

unzip -o "$BACKUP_ZIP_FILE" -d "$RESTORE_DIR" >/dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "Error: Could not extract the ZIP file."
    rm -rf "$RESTORE_DIR"
    exit 1
fi

backup_has_relative_paths=false
if unzip -Z1 "$BACKUP_ZIP_FILE" 2>/dev/null | grep -q '^core/scripts/telegrambot/'; then
    backup_has_relative_paths=true
fi

required_files=(
    ".configs.env"
)

for file in "${required_files[@]}"; do
    if [ ! -f "$RESTORE_DIR/$file" ]; then
        echo "Error: Required file '$file' is missing from the backup."
        rm -rf "$RESTORE_DIR"
        exit 1
    fi
    if [ ! -f "$RESTORE_DIR/$file" ]; then
        echo "Error: '$file' in the backup is not a regular file."
        rm -rf "$RESTORE_DIR"
        exit 1
    fi
done

collect_current_state_files() {
    shopt -s nullglob dotglob
    local files=(
        "$TARGET_DIR"/*.env
        "$TARGET_DIR"/*.json
        "$TARGET_DIR/core/scripts/telegrambot"/*.env
        "$TARGET_DIR/core/scripts/telegrambot"/*.json
    )
    shopt -u nullglob dotglob

    for file in "${files[@]}"; do
        if [ -f "$file" ]; then
            echo "${file#$TARGET_DIR/}"
        fi
    done
}

restore_root_file() {
    local source_file="$1"
    local target_file="$TARGET_DIR/$(basename "$source_file")"

    mkdir -p "$TARGET_DIR"
    cp -p "$source_file" "$target_file"
    if [ $? -ne 0 ]; then
        echo "Error: replace Configuration Files '$(basename "$source_file")'."
        rm -rf "$existing_backup_dir"
        rm -rf "$RESTORE_DIR"
        exit 1
    fi
}

restore_root_state_files() {
    local source_dir="$1"

    if [ ! -d "$source_dir" ]; then
        return
    fi

    shopt -s nullglob dotglob
    local files=(
        "$source_dir"/*.env
        "$source_dir"/*.json
    )
    shopt -u nullglob dotglob

    for source_file in "${files[@]}"; do
        if [ -f "$source_file" ]; then
            restore_root_file "$source_file"
        fi
    done
}

restore_telegram_state_files() {
    local source_dir="$1"

    if [ ! -d "$source_dir" ]; then
        return
    fi

    shopt -s nullglob dotglob
    local files=(
        "$source_dir"/*.env
        "$source_dir"/*.json
    )
    shopt -u nullglob dotglob

    for source_file in "${files[@]}"; do
        if [ ! -f "$source_file" ]; then
            continue
        fi

        local backup_name
        backup_name="$(basename "$source_file")"
        if [ "$backup_name" = ".configs.env" ]; then
            continue
        fi

        local target_file="$TARGET_DIR/core/scripts/telegrambot/$backup_name"
        mkdir -p "$(dirname "$target_file")"
        cp -p "$source_file" "$target_file"
        if [ $? -ne 0 ]; then
            echo "Error: replace Telegram bot state file '$backup_name'."
            rm -rf "$existing_backup_dir"
            rm -rf "$RESTORE_DIR"
            exit 1
        fi
    done
}

timestamp=$(date +%Y%m%d_%H%M%S)
existing_backup_dir="/opt/hysbackup/restore_pre_backup_$timestamp"
mkdir -p "$existing_backup_dir"
while IFS= read -r file; do
  if [ -f "$TARGET_DIR/$file" ]; then
    mkdir -p "$existing_backup_dir/$(dirname "$file")"
    cp -p "$TARGET_DIR/$file" "$existing_backup_dir/$file"
    if [ $? -ne 0 ]; then
      echo "Error creating backup file before restore from '$TARGET_DIR/$file'."
      exit 1
    fi
  fi
done < <(collect_current_state_files)

for file in "${required_files[@]}"; do
    restore_root_file "$RESTORE_DIR/$file"
done

if [ "$backup_has_relative_paths" = true ]; then
    restore_root_state_files "$RESTORE_DIR"
    restore_telegram_state_files "$RESTORE_DIR/core/scripts/telegrambot"
else
    restore_telegram_state_files "$RESTORE_DIR"
fi

rm -rf "$RESTORE_DIR"
echo "dijiq configuration restored successfully."

python3 "$CLI_PATH" restart-dijiq > /dev/null 2>&1
if [ $? -ne 0 ]; then
      echo "Error: Restart service failed'."
      rm -rf "$existing_backup_dir"
      exit 1
fi

if [[ "$existing_backup_dir" != "" ]]; then
    rm -rf "$existing_backup_dir"
fi

exit 0
