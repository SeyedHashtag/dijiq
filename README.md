# Dijiq VPN Bot

A Telegram bot for managing VPN users through your service API.

## Features

- Add new VPN users with custom settings
- Automatic secure password generation
- Automatic username generation based on Telegram ID
- Role-based access control
- Modular design for easy extension
- Automatic updates via built-in updater

## Quick Installation (Linux)

Install with a single command:

```bash
bash <(curl -s https://raw.githubusercontent.com/SeyedHashtag/dijiq/main/install.sh)
```

This will:
- Install all required packages
- Clone the repository to /opt/dijiq
- Set up a Python virtual environment
- Ask for your credentials and set up environment variables
- Create a systemd service for auto-starting the bot
- Add a convenient command alias

## Manual Installation

1. Clone the repository
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Set required environment variables:
   ```
   cp .env.example .env
   # Edit .env with your credentials
   ```
4. Start the bot:
   ```
   python main.py
   ```

## Environment Variables

The bot requires the following environment variables:

- `TELEGRAM_TOKEN`: Your Telegram bot token
- `VPN_API_URL`: URL of your VPN service API
- `ADMIN_USERS`: Comma-separated list of Telegram user IDs with admin access

You can set these directly in your environment for production use:

```bash
export TELEGRAM_TOKEN="your_token_here"
export VPN_API_URL="https://your-api-url.com"
export ADMIN_USERS="123456789,987654321"
```

Or use a `.env` file which will be loaded automatically.

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

## License

MIT License