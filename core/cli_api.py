import os
import subprocess
from enum import Enum
from datetime import datetime, timedelta
import json
from typing import Any
from dotenv import dotenv_values

DEBUG = False
SCRIPT_DIR = '/etc/dijiq/core/scripts'
CONFIG_ENV_FILE = '/etc/dijiq/.configs.env'


class Command(Enum):
    '''Contains path to command's script'''
    IP_ADD = os.path.join(SCRIPT_DIR, 'dijiq', 'ip.sh')
    SERVER_INFO = os.path.join(SCRIPT_DIR, 'dijiq', 'server_info.sh')
    BACKUP_DIJIQ = os.path.join(SCRIPT_DIR, 'dijiq', 'backup.sh')
    RESTORE_DIJIQ = os.path.join(SCRIPT_DIR, 'dijiq', 'restore.sh')
    INSTALL_TELEGRAMBOT = os.path.join(SCRIPT_DIR, 'telegrambot', 'runbot.sh')
    SERVICES_STATUS = os.path.join(SCRIPT_DIR, 'services_status.sh')
    VERSION = os.path.join(SCRIPT_DIR, 'dijiq', 'version.py')

import psutil
import requests
import sys

# region Custom Exceptions


class dijiqError(Exception):
    '''Base class for dijiq-related exceptions.'''
    pass


class CommandExecutionError(dijiqError):
    '''Raised when a command execution fails.'''
    pass


class InvalidInputError(dijiqError):
    '''Raised when the provided input is invalid.'''
    pass


class PasswordGenerationError(dijiqError):
    '''Raised when password generation fails.'''
    pass


class ScriptNotFoundError(dijiqError):
    '''Raised when a required script is not found.'''
    pass

# region Utils


def run_cmd(command: list[str]) -> str | None:
    '''
    Runs a command and returns the output.
    Could raise subprocess.CalledProcessError
    '''
    if (DEBUG) and not (Command.GET_USER.value in command or Command.LIST_USERS.value in command):
        print(' '.join(command))
    try:
        result = subprocess.check_output(command, stderr=subprocess.STDOUT, shell=False)
        if result:
            result = result.decode().strip()
            return result
    except subprocess.CalledProcessError as e:
        if DEBUG:
            raise CommandExecutionError(f'Command execution failed: {e}\nOutput: {e.output.decode()}')
        else:
            return None
    return None


def generate_password() -> str:
    '''
    Generates a random password using pwgen for user.
    Could raise subprocess.CalledProcessError
    '''
    try:
        return subprocess.check_output(['pwgen', '-s', '32', '1'], shell=False).decode().strip()
    except subprocess.CalledProcessError as e:
        raise PasswordGenerationError(f'Failed to generate password: {e}')

# endregion

# region APIs

# region dijiq


def backup_dijiq():
    '''Backups dijiq configuration.  Raises an exception on failure.'''
    try:
        run_cmd(['bash', Command.BACKUP_DIJIQ.value])
    except subprocess.CalledProcessError as e:
        raise Exception(f"Backup failed: {e}")
    except Exception as ex:
        raise


def restore_dijiq(backup_file_path: str):
    '''Restores dijiq configuration from the given backup file.'''
    try:
        run_cmd(['bash', Command.RESTORE_DIJIQ.value, backup_file_path])
    except subprocess.CalledProcessError as e:
        raise Exception(f"Restore failed: {e}")
    except Exception as ex:
        raise


def get_dijiq_config_file() -> dict[str, Any]:
    with open(CONFIG_FILE, 'r') as f:
        return json.loads(f.read())


def set_dijiq_config_file(data: dict[str, Any]):
    content = json.dumps(data, indent=4)

    with open(CONFIG_FILE, 'w') as f:
        f.write(content)
# endregion

# region Server


def traffic_status():
    '''Fetches traffic status.'''
    traffic.traffic_status()


# TODO: it's better to return json
def server_info() -> str | None:
    '''Retrieves server information.'''
    try:
        # Add path for utils
        sys.path.append('/etc/dijiq/core/scripts/telegrambot')
        from utils import payment_records, referral, language, translations
        
        # 1. System Stats
        cpu = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # 2. Online Users
        online_users = 0
        try:
            # Load env for token
            env_vars = dotenv_values('/etc/dijiq/core/scripts/telegrambot/.env')
            token = env_vars.get('TOKEN')
            url = "http://127.0.0.1:25413/online"
            if token:
                headers = {'Authorization': token}
                resp = requests.get(url, headers=headers, timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, dict):
                         online_users = sum(data.values())
                    elif isinstance(data, list):
                         online_users = sum(data)
        except Exception:
             pass 
             
        # 3. Sales Stats
        payments = payment_records.load_payments()
        paid_statuses = {'completed', 'paid', 'success', 'succeeded'}
        failed_statuses = {'rejected', 'failed', 'canceled', 'cancelled', 'error'}
        expired_statuses = {'expired'}
        pending_statuses = {'pending', 'pending_approval', 'processing', 'waiting', 'unpaid'}

        now = datetime.now()
        current_month = now.strftime('%Y-%m')
        current_day = now.strftime('%Y-%m-%d')
        last_30_days_start = now - timedelta(days=30)

        def parse_date(value: str):
            if not value:
                return None
            if isinstance(value, datetime):
                return value
            for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
                try:
                    return datetime.strptime(str(value), fmt)
                except ValueError:
                    continue
            return None

        stats = {
            'all': {'revenue': 0.0, 'orders': 0, 'paid': 0, 'failed': 0, 'expired': 0, 'pending': 0},
            'month': {'revenue': 0.0, 'orders': 0, 'paid': 0, 'failed': 0, 'expired': 0, 'pending': 0},
            'today': {'revenue': 0.0, 'orders': 0, 'paid': 0, 'failed': 0, 'expired': 0, 'pending': 0},
            'last30': {'revenue': 0.0, 'orders': 0, 'paid': 0, 'failed': 0, 'expired': 0, 'pending': 0},
        }

        plan_revenue = {}
        plan_count = {}

        for p in payments.values():
            status = str(p.get('status', '')).lower()
            price_raw = p.get('price', 0)
            try:
                price = float(price_raw or 0)
            except (ValueError, TypeError):
                price = 0.0

            date_to_check = p.get('updated_at') or p.get('created_at') or ''
            payment_dt = parse_date(date_to_check)
            in_month = str(date_to_check).startswith(current_month) if date_to_check else False
            in_today = str(date_to_check).startswith(current_day) if date_to_check else False
            in_last30 = payment_dt is not None and payment_dt >= last_30_days_start

            def bump(bucket: str):
                stats[bucket]['orders'] += 1
                if status in paid_statuses:
                    stats[bucket]['paid'] += 1
                    stats[bucket]['revenue'] += price
                elif status in failed_statuses:
                    stats[bucket]['failed'] += 1
                elif status in expired_statuses:
                    stats[bucket]['expired'] += 1
                elif status in pending_statuses:
                    stats[bucket]['pending'] += 1

            bump('all')
            if in_month:
                bump('month')
            if in_today:
                bump('today')
            if in_last30:
                bump('last30')

            if status in paid_statuses:
                plan = p.get('plan_gb', 'Unknown')
                plan_revenue[plan] = plan_revenue.get(plan, 0.0) + price
                plan_count[plan] = plan_count.get(plan, 0) + 1

        def aov(bucket: str) -> float:
            paid = stats[bucket]['paid']
            return stats[bucket]['revenue'] / paid if paid else 0.0

        # 4. Referral Stats
        referral_data = referral.load_referrals()
        total_payouts = 0.0
        if 'stats' in referral_data:
             for stat in referral_data['stats'].values():
                 total_payouts += float(stat.get('total_earnings', 0))

        # 5. Language Stats
        lang_prefs = language.load_user_languages()
        total_prefs = len(lang_prefs)
        lang_counts = {}
        for lang in lang_prefs.values():
            lang_counts[lang] = lang_counts.get(lang, 0) + 1

        # Format Output
        output = []
        output.append("📊 **Server Statistics**")
        output.append(f"💻 **CPU Usage:** {cpu}%")
        output.append(f"🧠 **RAM Usage:** {ram.percent}% ({ram.used // (1024*1024)}MB / {ram.total // (1024*1024)}MB)")
        output.append(f"💾 **Disk Usage:** {disk.percent}% ({disk.used // (1024*1024*1024)}GB / {disk.total // (1024*1024*1024)}GB)")
        output.append(f"👥 **Online Users:** {online_users}")
        output.append("")
        output.append("💰 **Business Statistics**")
        output.append(f"💵 **Total Revenue:** ${stats['all']['revenue']:,.2f}")
        output.append(f"📦 **Total Orders:** {stats['all']['orders']} (✅ {stats['all']['paid']} • ❌ {stats['all']['failed']} • ⌛ {stats['all']['expired']} • ⏳ {stats['all']['pending']})")
        output.append(f"🧾 **AOV (All Time):** ${aov('all'):,.2f}")
        output.append("")
        output.append(f"📆 **Today:** ${stats['today']['revenue']:,.2f} • {stats['today']['orders']} orders (✅ {stats['today']['paid']} • ❌ {stats['today']['failed']} • ⌛ {stats['today']['expired']} • ⏳ {stats['today']['pending']})")
        output.append(f"📅 **This Month:** ${stats['month']['revenue']:,.2f} • {stats['month']['orders']} orders (✅ {stats['month']['paid']} • ❌ {stats['month']['failed']} • ⌛ {stats['month']['expired']} • ⏳ {stats['month']['pending']})")
        output.append(f"🗓️ **Last 30 Days:** ${stats['last30']['revenue']:,.2f} • {stats['last30']['orders']} orders (✅ {stats['last30']['paid']} • ❌ {stats['last30']['failed']} • ⌛ {stats['last30']['expired']} • ⏳ {stats['last30']['pending']})")
        output.append(f"🧾 **AOV (30 Days):** ${aov('last30'):,.2f}")
        output.append(f"🤝 **Total Referral Rewards:** ${total_payouts:,.2f}")
        if stats['all']['revenue'] > 0:
            share = (total_payouts / stats['all']['revenue']) * 100
            output.append(f"🤝 **Referral Share of Revenue:** {share:.1f}%")

        if plan_revenue:
            output.append("")
            output.append("🏷️ **Top Plans (Revenue)**")
            for plan, amount in sorted(plan_revenue.items(), key=lambda item: item[1], reverse=True)[:3]:
                output.append(f"   - {plan}: ${amount:,.2f}")
        if plan_count:
            output.append("🏷️ **Top Plans (Orders)**")
            for plan, count in sorted(plan_count.items(), key=lambda item: item[1], reverse=True)[:3]:
                output.append(f"   - {plan}: {count}")
        output.append("")
        output.append("🌐 **Language Distribution**")
        
        if total_prefs > 0:
            sorted_langs = sorted(lang_counts.items(), key=lambda item: item[1], reverse=True)
            for code, count in sorted_langs:
                percent = (count / total_prefs) * 100
                lang_name = translations.LANGUAGES.get(code, code)
                # Remove flag emoji for cleaner CLI output if needed, but keeping for now
                output.append(f"   - {lang_name}: {percent:.1f}% ({count})")
        else:
            output.append("   No language data available.")
        
        return "\n".join(output)

    except Exception as e:
        return f"Error generating server info: {str(e)}"


def get_ip_address() -> tuple[str | None, str | None]:
    '''
    Retrieves the IP address from the .configs.env file.
    '''
    env_vars = dotenv_values(CONFIG_ENV_FILE)

    return env_vars.get('IP4'), env_vars.get('IP6')


def add_ip_address():
    '''
    Adds IP addresses from the environment to the .configs.env file.
    '''
    run_cmd(['bash', Command.IP_ADD.value, 'add'])


def edit_ip_address(ipv4: str, ipv6: str):
    '''
    Edits the IP address configuration based on provided IPv4 and/or IPv6 addresses.

    :param ipv4: The new IPv4 address to be configured. If provided, the IPv4 address will be updated.
    :param ipv6: The new IPv6 address to be configured. If provided, the IPv6 address will be updated.
    :raises InvalidInputError: If neither ipv4 nor ipv6 is provided.
    '''

    if not ipv4 and not ipv6:
        raise InvalidInputError('Error: --edit requires at least one of --ipv4 or --ipv6.')
    if ipv4:
        run_cmd(['bash', Command.IP_ADD.value, 'edit', '-4', ipv4])
    if ipv6:
        run_cmd(['bash', Command.IP_ADD.value, 'edit', '-6', ipv6])


# endregion

# region Advanced Menu


def start_telegram_bot(token: str, adminid: str, api_url: str, api_key: str, servers=None):
    '''Starts the Telegram bot.'''
    if not token or not adminid:
        raise InvalidInputError('Error: token and adminid are required for the start action.')
    command_servers = None
    if servers:
        parsed_servers = []
        for item in servers:
            if '=' not in item or ',' not in item:
                raise InvalidInputError('Error: --server must use id=url,token format.')
            server_id, rest = item.split('=', 1)
            parts = rest.split(',')
            if len(parts) < 2:
                raise InvalidInputError('Error: --server must use id=url,token format.')
            server_url, server_token = parts[0], parts[1]
            weight = 1
            enabled = True
            if len(parts) >= 3 and parts[2].strip():
                try:
                    weight = float(parts[2].strip())
                except ValueError:
                    raise InvalidInputError('Error: --server weight must be a number.')
            if len(parts) >= 4 and parts[3].strip():
                enabled = parts[3].strip().lower() not in ('0', 'false', 'no', 'disabled')
            server_id = server_id.strip()
            server_url = server_url.strip()
            server_token = server_token.strip()
            if not server_id or not server_url or not server_token:
                raise InvalidInputError('Error: --server must include non-empty id, url, and token.')
            parsed_servers.append({
                'id': server_id,
                'name': server_id,
                'url': server_url,
                'token': server_token,
                'enabled': enabled,
                'weight': weight,
            })
        if parsed_servers and (not api_url or not api_key):
            api_url = parsed_servers[0]['url']
            api_key = parsed_servers[0]['token']
        command_servers = json.dumps(parsed_servers, separators=(',', ':'))
    if not api_url or not api_key:
        raise InvalidInputError('Error: api_url and api_key are required when no --server is provided.')
    command = ['bash', Command.INSTALL_TELEGRAMBOT.value, 'start', token, adminid, api_url, api_key]
    if command_servers:
        command.append(command_servers)
    run_cmd(command)


def stop_telegram_bot():
    '''Stops the Telegram bot.'''
    run_cmd(['bash', Command.INSTALL_TELEGRAMBOT.value, 'stop'])


def get_services_status() -> dict[str, bool] | None:
    '''Gets the status of all project services.'''
    if res := run_cmd(['bash', Command.SERVICES_STATUS.value]):
        return json.loads(res)

def show_version() -> str | None:
    """Displays the currently installed version of the panel."""
    return run_cmd(['python3', Command.VERSION.value, 'show-version'])


def check_version() -> str | None:
    """Checks if the current version is up-to-date and displays changelog if not."""
    return run_cmd(['python3', Command.VERSION.value, 'check-version'])
# endregion
