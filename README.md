# Dijiq VPN Bot

A Telegram bot for managing VPN users through your service API.

## Features

- Add new VPN users with custom settings
- Role-based access control
- Modular design for easy extension

## Quick Installation (Linux)

Install with a single command:

```bash
bash <(curl -s https://raw.githubusercontent.com/SeyedHashtag/dijiq/main/install.sh)
```

This will:
- Install all required packages
- Clone the repository to /opt/dijiq
- Set up a Python virtual environment
- Ask for your Telegram bot token and API URL
- Create a systemd service for auto-starting the bot
- Add a convenient command alias

## Manual Installation

1. Clone the repository
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Copy `config.example.json` to `config.json` and update with your settings:
   ```
   cp config.example.json config.json
   ```
4. Edit `config.json` with your Telegram bot token and API URL
5. Add your Telegram user ID to the `admin_users` list

## Usage

After installation, you can:

- Control the bot with systemd:
  ```
  systemctl start dijiq   # Start the bot
  systemctl status dijiq  # Check status
  systemctl stop dijiq    # Stop the bot
  ```

- Run manually with the `dijiq` command (after restarting your shell)

### Bot Commands

- `/start` - Start the bot and show main menu
- `/adduser` - Start the process of adding a new user
- `/help` - Show help information

## Configuration

The `config.json` file contains:

- `telegram_token`: Your Telegram bot token
- `vpn_api_url`: URL of your VPN service API
- `admin_users`: List of Telegram user IDs allowed to use the bot

## License

MIT License