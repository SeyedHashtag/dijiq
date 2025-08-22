#!/bin/bash

setup_hysteria_scheduler() {
  
    chmod +x /etc/hysteria/core/scripts/scheduler.py

    cat > /etc/systemd/system/hysteria-scheduler.service << 'EOF'
[Unit]
Description=Hysteria2 Scheduler Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/etc/hysteria
ExecStart=/etc/hysteria/hysteria2_venv/bin/python3 /etc/hysteria/core/scripts/scheduler.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=hysteria-scheduler

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable hysteria-scheduler.service
    systemctl start hysteria-scheduler.service
    (crontab -l | grep -v "hysteria2_venv.*traffic-status" | grep -v "hysteria2_venv.*backup-hysteria") | crontab -
}

check_scheduler_service() {
    if systemctl is-active --quiet hysteria-scheduler.service; then
        return 0
    else
        return 1
    fi
}

setup_hysteria_auth_server() {
    chmod +x /etc/hysteria/core/scripts/hysteria2/auth_server.py

    cat > /etc/systemd/system/hysteria-auth.service << 'EOF'
[Unit]
Description=Hysteria aiohttp Auth Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/etc/hysteria/core/scripts/hysteria2
ExecStart=/etc/hysteria/hysteria2_venv/bin/python3 /etc/hysteria/core/scripts/hysteria2/auth_server.py
Restart=always
RestartSec=3
Environment="USERS_FILE=/etc/hysteria/users.json"
Environment="CONFIG_FILE=/etc/hysteria/config.json"

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable hysteria-auth.service
    systemctl start hysteria-auth.service
}

check_auth_server_service() {
    if systemctl is-active --quiet hysteria-auth.service; then
        return 0
    else
        return 1
    fi
}