#!/bin/bash

# Get the directory of the script
SCRIPT_DIR="$(dirname "$(realpath "$0")")"

# Check if Python and required modules are installed
python3 -c "import requests, dotenv" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "Required Python modules not found. Installing..."
    pip3 install requests python-dotenv
fi

# Convert bash arguments to appropriate format for Python script
if [ "$4" == "" ]; then
    python3 "$SCRIPT_DIR/add_user.py" "$1" "$2" "$3"
elif [ "$5" == "" ]; then
    python3 "$SCRIPT_DIR/add_user.py" "$1" "$2" "$3" --password "$4"
else
    python3 "$SCRIPT_DIR/add_user.py" "$1" "$2" "$3" --password "$4" --creation_date "$5"
fi
