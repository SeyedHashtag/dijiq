#!/bin/bash

python3 /etc/dijiq/core/cli.py traffic-status > /dev/null 2>&1
if systemctl restart dijiq-server.service; then
    echo "dijiq server restarted successfully."
else
    echo "Error: Failed to restart the dijiq server."
fi