# Hysteria2 Management CLI Guide

This document provides a comprehensive guide to using the `cli.py` script, a command-line interface for managing Hysteria2 and related services.  It covers installation, user management, advanced configurations, and troubleshooting. The commands are organized into sections for clarity. Each command is described with its options, arguments, and expected behavior.

---
## Table of Contents

- [Installation & Setup](#installation--setup)
- [Command Categories](#command-categories)
  - [🚀 Hysteria2 Server Management](#-hysteria2-server-management)
    - [Install Hysteria2](#install-hysteria2)
    - [Server Operations](#server-operations)
    - [Backup & Restore](#backup--restore)
  - [👥 User Management](#-user-management)
    - [List and View Users](#list-and-view-users)
    - [Add New Users](#add-new-users)
    - [Edit Existing Users](#edit-existing-users)
    - [User Operations](#user-operations)
    - [User URI & QR Codes](#user-uri--qr-codes)
  - [🖥️ Server Information & Monitoring](#️-server-information--monitoring)
    - [Traffic and Status](#traffic-and-status)
    - [Server Information](#server-information)
    - [Service Status](#service-status)
  - [⚙️ Server Configuration](#️-server-configuration)
    - [Obfuscation Management](#obfuscation-management)
    - [IP Address Management](#ip-address-management)
    - [External Node Management](#external-node-management)
    - [Masquerade Configuration](#masquerade-configuration)
    - [Geo Files Update](#geo-files-update)
  - [🔧 Advanced Features](#-advanced-features)
    - [TCP Brutal Installation](#tcp-brutal-installation)
    - [WARP Integration](#warp-integration)
    - [Telegram Bot](#telegram-bot)
    - [Singbox Service](#singbox-service)
    - [Normal Subscription Service](#normal-subscription-service)
    - [Web Panel Management](#web-panel-management)
    - [IP Limiter Service](#ip-limiter-service)
- [Common Usage Examples](#common-usage-examples)
  - [Setting Up a New Server](#setting-up-a-new-server)
  - [User Management Workflow](#user-management-workflow)
  - [Advanced Server Configuration](#advanced-server-configuration)
- [Error Handling](#error-handling)
- [Tips & Best Practices](#tips--best-practices)
- [Troubleshooting](#troubleshooting)

## Command Categories

### 🚀 Hysteria2 Server Management

#### Install Hysteria2
```bash
# Install with required port and optional SNI
python3 cli.py install-hysteria2 --port 8080 --sni example.com
python3 cli.py install-hysteria2 -p 8080 -s example.com

# Install with default SNI (bts.com)
python3 cli.py install-hysteria2 --port 8080
```

#### Server Operations
```bash
# Uninstall Hysteria2
python3 cli.py uninstall-hysteria2

# Update Hysteria2
python3 cli.py update-hysteria2

# Restart Hysteria2 service
python3 cli.py restart-hysteria2

# Change server port
python3 cli.py change-hysteria2-port --port 9090

# Change SNI (Server Name Indication)
python3 cli.py change-hysteria2-sni --sni newdomain.com
```

#### Backup & Restore
```bash
# Create backup of Hysteria configuration
python3 cli.py backup-hysteria

# Restore from backup file
python3 cli.py restore-hysteria2 /path/to/backup.zip
```

### 👥 User Management

#### List and View Users
```bash
# List all users
python3 cli.py list-users

# Get specific user details
python3 cli.py get-user --username john_doe
python3 cli.py get-user -u john_doe
```

#### Add New Users
```bash
# Add user with basic settings
python3 cli.py add-user -u john_doe -t 50 -e 30

# Add user with custom password and creation date
python3 cli.py add-user \
  --username john_doe \
  --traffic-limit 100 \
  --expiration-days 60 \
  --password mypassword123 \
  --creation-date 2024-01-15

# Add unlimited user (no IP limit checks)
python3 cli.py add-user -u premium_user -t 500 -e 365 --unlimited
```

#### Edit Existing Users
```bash
# Change username
python3 cli.py edit-user -u old_name --new-username new_name

# Update traffic limit and expiration
python3 cli.py edit-user -u john_doe --new-traffic-limit 200 --new-expiration-days 90

# Renew password and creation date
python3 cli.py edit-user -u john_doe --renew-password --renew-creation-date

# Block/unblock user
python3 cli.py edit-user -u john_doe --blocked
python3 cli.py edit-user -u john_doe --unblocked

# Set unlimited IP access
python3 cli.py edit-user -u john_doe --unlimited-ip
python3 cli.py edit-user -u john_doe --limited-ip
```

#### User Operations
```bash
# Reset user (clears usage statistics)
python3 cli.py reset-user --username john_doe

# Remove user completely
python3 cli.py remove-user --username john_doe

# Kick user (disconnect active sessions)
python3 cli.py kick-user --username john_doe
```

#### User URI & QR Codes
```bash
# Show user connection URI
python3 cli.py show-user-uri --username john_doe

# Generate QR code for URI
python3 cli.py show-user-uri -u john_doe --qrcode

# Show IPv6 URI
python3 cli.py show-user-uri -u john_doe --ipv 6

# Show both IPv4 and IPv6 URIs with QR codes
python3 cli.py show-user-uri -u john_doe --all --qrcode

# Generate Singbox sublink
python3 cli.py show-user-uri -u john_doe --singbox

# Generate normal sublink
python3 cli.py show-user-uri -u john_doe --normalsub

# Get JSON format for multiple users
python3 cli.py show-user-uri-json user1 user2 user3
```

### 🖥️ Server Information & Monitoring

#### Traffic and Status
```bash
# Show traffic status for all users
python3 cli.py traffic-status

# Update traffic data without GUI (kicks expired users)
python3 cli.py traffic-status --no-gui
```

#### Server Information
```bash
# Display server information
python3 cli.py server-info

# Show current version
python3 cli.py show-version

# Check for updates
python3 cli.py check-version
```

#### Service Status
```bash
# Check all services status
python3 cli.py get-services-status

# Check web panel specific services
python3 cli.py get-webpanel-services-status
```

### ⚙️ Server Configuration

#### Obfuscation Management
```bash
# Check obfuscation status
python3 cli.py manage_obfs --check

# Enable obfuscation
python3 cli.py manage_obfs --generate

# Disable obfuscation
python3 cli.py manage_obfs --remove
```

#### IP Address Management
```bash
# Auto-detect and add IP addresses
python3 cli.py ip-address

# Manually edit IP addresses
python3 cli.py ip-address --edit --ipv4 192.168.1.100
python3 cli.py ip-address --edit --ipv6 2001:db8::1
python3 cli.py ip-address --edit -4 192.168.1.100 -6 2001:db8::1
```

#### External Node Management
```bash
# Add external node
python3 cli.py node add --name Node-DE --ip 45.67.89.123

# List all nodes
python3 cli.py node list

# Delete node
python3 cli.py node delete --name Node-DE
```

#### Masquerade Configuration
```bash
# Enable masquerade with domain
python3 cli.py masquerade --enable google.com

# Disable masquerade
python3 cli.py masquerade --remove
```

#### Geo Files Update
```bash
# Update geo files for Iran (default)
python3 cli.py update-geo

# Update for specific country
python3 cli.py update-geo --country china
python3 cli.py update-geo --country russia
python3 cli.py update-geo --country iran
```

### 🔧 Advanced Features

#### TCP Brutal Installation
```bash
# Install TCP Brutal optimization
python3 cli.py install-tcp-brutal
```

#### WARP Integration
```bash
# Install WARP
python3 cli.py install-warp

# Uninstall WARP
python3 cli.py uninstall-warp

# Check WARP status
python3 cli.py warp-status

# Configure WARP settings
python3 cli.py configure-warp --set-all on
python3 cli.py configure-warp --set-popular-sites off
python3 cli.py configure-warp --set-domestic-sites on
python3 cli.py configure-warp --set-block-adult-sites on

# Multiple WARP configurations
python3 cli.py configure-warp \
  --set-all off \
  --set-popular-sites on \
  --set-domestic-sites off \
  --set-block-adult-sites on
```

#### Telegram Bot
```bash
# Start Telegram bot
python3 cli.py telegram --action start --token YOUR_BOT_TOKEN --adminid YOUR_ADMIN_ID

# Stop Telegram bot
python3 cli.py telegram --action stop
```

#### Singbox Service
```bash
# Start Singbox service
python3 cli.py singbox --action start --domain example.com --port 8443

# Stop Singbox service
python3 cli.py singbox --action stop
```

#### Normal Subscription Service
```bash
# Start NormalSub service
python3 cli.py normal-sub --action start --domain example.com --port 8080

# Stop NormalSub service
python3 cli.py normal-sub --action stop

# Edit subpath
python3 cli.py normal-sub --action edit_subpath --subpath newpath123
```

#### Web Panel Management
```bash
# Start web panel
python3 cli.py webpanel \
  --action start \
  --domain panel.example.com \
  --port 8090 \
  --admin-username admin \
  --admin-password securepass123 \
  --expiration-minutes 60 \
  --debug

# Start with decoy site
python3 cli.py webpanel \
  --action start \
  --domain panel.example.com \
  --port 8090 \
  --admin-username admin \
  --admin-password securepass123 \
  --decoy-path /var/www/html

# Stop web panel
python3 cli.py webpanel --action stop

# Get web panel URL
python3 cli.py get-webpanel-url

# Get API token
python3 cli.py get-webpanel-api-token

# Reset credentials
python3 cli.py reset-webpanel-creds --new-username newadmin
python3 cli.py reset-webpanel-creds --new-password newpass123
python3 cli.py reset-webpanel-creds --new-username newadmin --new-password newpass123

# Setup decoy site
python3 cli.py setup-webpanel-decoy --domain panel.example.com --decoy-path /var/www/decoy

# Stop decoy site
python3 cli.py stop-webpanel-decoy
```

#### IP Limiter Service
```bash
# Start IP limiter
python3 cli.py start-ip-limit

# Stop IP limiter
python3 cli.py stop-ip-limit

# Configure IP limiter
python3 cli.py config-ip-limit --block-duration 3600 --max-ips 3
python3 cli.py config-ip-limit --block-duration 7200
python3 cli.py config-ip-limit --max-ips 5
```

## Common Usage Examples

### Setting Up a New Server
```bash
# 1. Install Hysteria2
python3 cli.py install-hysteria2 --port 8080 --sni google.com

# 2. Add IP addresses
python3 cli.py ip-address

# 3. Enable obfuscation
python3 cli.py manage_obfs --generate

# 4. Create first user
python3 cli.py add-user -u testuser -t 50 -e 30

# 5. Get user connection URI
python3 cli.py show-user-uri -u testuser --qrcode
```

### User Management Workflow
```bash
# Add premium user with unlimited access
python3 cli.py add-user -u premium_user -t 1000 -e 365 --unlimited

# Monitor user usage
python3 cli.py traffic-status

# Reset user if needed
python3 cli.py reset-user -u premium_user

# Generate connection details
python3 cli.py show-user-uri -u premium_user --all --qrcode
```

### Advanced Server Configuration
```bash
# Install optimizations
python3 cli.py install-tcp-brutal
python3 cli.py install-warp

# Configure WARP
python3 cli.py configure-warp --set-popular-sites on --set-block-adult-sites on

# Setup web panel with decoy
python3 cli.py webpanel \
  --action start \
  --domain admin.example.com \
  --port 8443 \
  --admin-username admin \
  --admin-password secure123 \
  --decoy-path /var/www/fake-site

# Start IP limiting
python3 cli.py start-ip-limit
python3 cli.py config-ip-limit --max-ips 2 --block-duration 3600
```

## Error Handling

The CLI includes comprehensive error handling. Common error scenarios:

- **Missing required parameters**: The CLI will show usage information
- **Invalid user operations**: Clear error messages for non-existent users
- **Service conflicts**: Warnings when services are already running/stopped
- **File permissions**: Errors for inaccessible backup files or paths
- **Network issues**: Connection errors during updates or installations

## Tips & Best Practices

1. **Regular Monitoring**: Use `traffic-status` regularly to monitor user usage
2. **Backup Strategy**: Create backups before major changes using `backup-hysteria`
3. **Security**: Use strong passwords for web panel and rotate them regularly
4. **Performance**: Enable TCP Brutal for better performance on high-latency connections
5. **Obfuscation**: Enable obfuscation in restrictive network environments
6. **User Management**: Use descriptive usernames and set appropriate traffic limits
7. **Monitoring**: Check service status regularly with `get-services-status`

## Troubleshooting

- **Service not starting**: Check `get-services-status` and system logs
- **Connection issues**: Verify firewall settings and port availability
- **User can't connect**: Check user status with `get-user` and verify URI generation
- **High resource usage**: Monitor with `traffic-status` and consider IP limiting
- **SSL issues**: Verify domain configuration for web panel and other services
