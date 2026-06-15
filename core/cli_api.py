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

TELEGRAM_UTILS_PATH = '/etc/dijiq/core/scripts/telegrambot'
ONLINE_USERS_URL = "http://127.0.0.1:25413/online"
PAID_STATUSES = {'completed', 'paid', 'success', 'succeeded'}
FAILED_STATUSES = {'rejected', 'failed', 'canceled', 'cancelled', 'error'}
EXPIRED_STATUSES = {'expired'}
PENDING_STATUSES = {'pending', 'pending_approval', 'processing', 'waiting', 'unpaid'}
SERVER_INFO_SECTIONS = {'overview', 'business', 'customers', 'tech', 'traffic', 'alerts', 'full'}

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


def _ensure_telegram_utils_path():
    if TELEGRAM_UTILS_PATH not in sys.path:
        sys.path.append(TELEGRAM_UTILS_PATH)


def _safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return default


def _safe_int(value, default: int = 0) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return default


def _safe_weight(value) -> float:
    weight = _safe_float(value, 1.0)
    return weight if weight > 0 else 1.0


def _parse_datetime(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    raw = str(value).strip()
    if raw.endswith('Z'):
        raw = raw[:-1] + '+00:00'
    try:
        parsed = datetime.fromisoformat(raw)
        return parsed.replace(tzinfo=None)
    except ValueError:
        pass
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
        try:
            return datetime.strptime(str(value), fmt)
        except ValueError:
            continue
    return None


def _empty_order_bucket():
    return {'revenue': 0.0, 'orders': 0, 'paid': 0, 'failed': 0, 'expired': 0, 'pending': 0}


def _bump_order_bucket(bucket: dict, status: str, price: float):
    bucket['orders'] += 1
    if status in PAID_STATUSES:
        bucket['paid'] += 1
        bucket['revenue'] += price
    elif status in FAILED_STATUSES:
        bucket['failed'] += 1
    elif status in EXPIRED_STATUSES:
        bucket['expired'] += 1
    elif status in PENDING_STATUSES:
        bucket['pending'] += 1


def _iter_named_user_records(users):
    if isinstance(users, dict):
        for username, data in users.items():
            if isinstance(data, dict):
                yield str(data.get("username") or username), data
    elif isinstance(users, list):
        for data in users:
            if isinstance(data, dict) and data.get("username"):
                yield str(data.get("username")), data


def _format_bytes(value) -> str:
    amount = float(value or 0)
    units = ("B", "KB", "MB", "GB", "TB", "PB")
    unit = units[0]
    for unit in units:
        if amount < 1024 or unit == units[-1]:
            break
        amount /= 1024
    if unit == "B":
        return f"{int(amount)}B"
    return f"{amount:.2f}{unit}"


def _sum_online_value(value):
    if isinstance(value, bool):
        return int(value), True
    if isinstance(value, (int, float)):
        return int(value), True
    if isinstance(value, str):
        try:
            return int(float(value)), True
        except ValueError:
            return 0, False
    if isinstance(value, dict):
        total = 0
        found = False
        for item in value.values():
            count, has_number = _sum_online_value(item)
            total += count
            found = found or has_number
        return total, found
    if isinstance(value, list):
        total = 0
        found = False
        for item in value:
            count, has_number = _sum_online_value(item)
            total += count
            found = found or has_number
        return total, found
    return 0, False


def parse_online_users_payload(payload):
    total, found = _sum_online_value(payload)
    return total if found else None


def fetch_online_users(api_client_module=None) -> dict:
    try:
        if api_client_module is None:
            _ensure_telegram_utils_path()
            from utils import api_client as api_client_module
        servers = api_client_module.get_server_configs()
    except Exception as e:
        return {"count": None, "status": "error", "error": str(e)}

    enabled_servers = [server for server in servers if server.get("enabled", True)]
    if not enabled_servers:
        return {"count": None, "status": "unavailable", "error": "No enabled VPN server configured."}

    token = enabled_servers[0].get("token")
    if not token:
        return {"count": None, "status": "unavailable", "error": "No VPN API token configured."}

    try:
        resp = requests.get(ONLINE_USERS_URL, headers={'Authorization': token}, timeout=5)
        if resp.status_code != 200:
            return {"count": None, "status": "error", "error": f"HTTP {resp.status_code}"}
        count = parse_online_users_payload(resp.json())
        if count is None:
            return {"count": None, "status": "error", "error": "Unsupported online users payload."}
        return {"count": count, "status": "ok", "error": None}
    except Exception as e:
        return {"count": None, "status": "error", "error": str(e)}


def build_online_users_from_userlist(vpn: dict) -> dict:
    enabled_servers = [server for server in vpn.get("servers", []) if server.get("enabled", True)]
    if not enabled_servers:
        return {"count": None, "status": "unavailable", "error": "No enabled VPN server configured."}

    healthy_servers = [server for server in enabled_servers if server.get("healthy")]
    if not healthy_servers:
        return {"count": None, "status": "error", "error": "No enabled VPN server userlist available."}

    count = sum(_safe_int(server.get("active_count", 0)) for server in healthy_servers)
    return {"count": count, "status": "ok", "error": None}


def _collect_payment_stats(payments: dict, now: datetime) -> dict:
    current_month = now.strftime('%Y-%m')
    current_day = now.strftime('%Y-%m-%d')
    last_30_days_start = now - timedelta(days=30)
    seven_day_start = now.date() - timedelta(days=6)

    buckets = {
        'all': _empty_order_bucket(),
        'month': _empty_order_bucket(),
        'today': _empty_order_bucket(),
        'last30': _empty_order_bucket(),
    }
    daily_sales = []
    daily_sales_by_date = {}
    for offset in range(7):
        date_key = now.date() - timedelta(days=offset)
        entry = {"date": date_key.isoformat(), "label": date_key.strftime("%b %d"), "revenue": 0.0, "paid": 0}
        daily_sales.append(entry)
        daily_sales_by_date[date_key] = entry

    plan_revenue = {}
    plan_count = {}

    for payment in payments.values():
        if not isinstance(payment, dict):
            continue
        status = str(payment.get('status', '')).lower()
        price = _safe_float(payment.get('price', 0))
        date_to_check = payment.get('updated_at') or payment.get('created_at') or ''
        payment_dt = _parse_datetime(date_to_check)
        in_month = str(date_to_check).startswith(current_month) if date_to_check else False
        in_today = str(date_to_check).startswith(current_day) if date_to_check else False
        in_last30 = payment_dt is not None and payment_dt >= last_30_days_start

        _bump_order_bucket(buckets['all'], status, price)
        if in_month:
            _bump_order_bucket(buckets['month'], status, price)
        if in_today:
            _bump_order_bucket(buckets['today'], status, price)
        if in_last30:
            _bump_order_bucket(buckets['last30'], status, price)

        if status in PAID_STATUSES:
            if payment_dt and seven_day_start <= payment_dt.date() <= now.date():
                daily_sales_by_date[payment_dt.date()]["revenue"] += price
                daily_sales_by_date[payment_dt.date()]["paid"] += 1
            plan = str(payment.get('plan_gb') or 'Unknown')
            plan_revenue[plan] = plan_revenue.get(plan, 0.0) + price
            plan_count[plan] = plan_count.get(plan, 0) + 1

    def aov(bucket: str) -> float:
        paid = buckets[bucket]['paid']
        return buckets[bucket]['revenue'] / paid if paid else 0.0

    return {
        "buckets": buckets,
        "aov": {"all": aov('all'), "last30": aov('last30')},
        "daily_sales": daily_sales,
        "top_plans_revenue": sorted(plan_revenue.items(), key=lambda item: item[1], reverse=True)[:3],
        "top_plans_orders": sorted(plan_count.items(), key=lambda item: item[1], reverse=True)[:3],
    }


def _empty_sold_traffic_bucket():
    return {"used_bytes": 0, "sold_bytes": 0, "matched_configs": 0, "sold_configs": 0}


def _plan_gb_to_bytes(value) -> int:
    return int(max(0.0, _safe_float(value, 0.0)) * (1024 ** 3))


def _sold_traffic_snapshot():
    return {
        "direct": _empty_sold_traffic_bucket(),
        "reseller": _empty_sold_traffic_bucket(),
        "total": {"used_bytes": 0, "sold_bytes": 0, "usage_percent": None},
        "missing_configs": 0,
        "skipped_no_username": 0,
        "unavailable_servers": 0,
    }


def _collect_vpn_and_live_users(api_client_module=None) -> tuple[dict, dict]:
    vpn = {
        "configured": 0,
        "enabled": 0,
        "disabled": 0,
        "healthy": 0,
        "unhealthy": 0,
        "active_configs": 0,
        "servers": [],
        "error": None,
    }
    live_users = {"by_server": {}, "by_username": {}, "unavailable_servers": set()}
    try:
        if api_client_module is None:
            _ensure_telegram_utils_path()
            from utils import api_client as api_client_module
        multi_api = api_client_module.MultiServerAPI()
        for index, (server, client) in enumerate(multi_api.iter_clients(include_disabled=True)):
            server_id = str(server.get("id") or getattr(client, "server_id", None) or f"server{index + 1}")
            users = client.get_users()
            healthy = users is not None
            active_count = multi_api.active_user_count(users) if healthy else None
            weight = _safe_weight(server.get("weight", 1))
            enabled = bool(server.get("enabled", True))

            vpn["configured"] += 1
            vpn["enabled" if enabled else "disabled"] += 1
            vpn["healthy" if healthy else "unhealthy"] += 1
            if active_count is not None:
                vpn["active_configs"] += active_count

            server_status = {
                "id": server_id,
                "name": server.get("name") or server_id,
                "enabled": enabled,
                "healthy": healthy,
                "active_count": active_count,
                "weight": weight,
                "load_ratio": (active_count / weight) if healthy else None,
            }
            vpn["servers"].append(server_status)

            if healthy:
                for username, user in _iter_named_user_records(users):
                    username_key = username.lower()
                    live_users["by_server"][(server_id, username_key)] = user
                    live_users["by_username"].setdefault(username_key, user)
            else:
                live_users["unavailable_servers"].add(server_id)
    except Exception as e:
        vpn["error"] = str(e)
    return vpn, live_users


def _is_regular_paid_payment(record: dict) -> bool:
    if not isinstance(record, dict):
        return False
    if str(record.get("status", "")).lower() not in PAID_STATUSES:
        return False
    if record.get("type") == "settlement" or record.get("plan_gb") == "Settlement":
        return False
    return True


def _find_live_sold_user(live_users: dict, server_id, username):
    username_key = str(username).lower()
    if server_id:
        matched = live_users.get("by_server", {}).get((str(server_id), username_key))
        if matched is not None:
            return matched
    return live_users.get("by_username", {}).get(username_key)


def _add_sold_config(traffic: dict, live_users: dict, seen: set, source: str, username, quota_gb, server_id=None):
    if not username:
        traffic["skipped_no_username"] += 1
        return

    username = str(username)
    server_key = str(server_id or "")
    key = (source, server_key, username.lower())
    if key in seen:
        return
    seen.add(key)

    bucket = traffic[source]
    bucket["sold_configs"] += 1
    quota_bytes = _plan_gb_to_bytes(quota_gb)
    bucket["sold_bytes"] += quota_bytes
    traffic["total"]["sold_bytes"] += quota_bytes

    live_user = _find_live_sold_user(live_users, server_id, username)
    if not live_user:
        traffic["missing_configs"] += 1
        return

    used_bytes = _safe_int(live_user.get("upload_bytes", 0)) + _safe_int(live_user.get("download_bytes", 0))
    bucket["used_bytes"] += used_bytes
    bucket["matched_configs"] += 1
    traffic["total"]["used_bytes"] += used_bytes


def _collect_sold_traffic_stats(payments: dict, live_users: dict, reseller_module=None) -> dict:
    traffic = _sold_traffic_snapshot()
    traffic["unavailable_servers"] = len(live_users.get("unavailable_servers", set()))
    seen = set()

    for record in (payments or {}).values():
        if not _is_regular_paid_payment(record):
            continue
        _add_sold_config(
            traffic,
            live_users,
            seen,
            "direct",
            record.get("username"),
            record.get("plan_gb"),
            server_id=record.get("server_id"),
        )

    try:
        if reseller_module is None:
            _ensure_telegram_utils_path()
            from utils import reseller as reseller_module
        resellers = reseller_module.get_all_resellers()
    except Exception:
        resellers = {}

    if isinstance(resellers, dict):
        for reseller_data in resellers.values():
            configs = reseller_data.get("configs", []) if isinstance(reseller_data, dict) else []
            if not isinstance(configs, list):
                continue
            for config in configs:
                if not isinstance(config, dict):
                    continue
                _add_sold_config(
                    traffic,
                    live_users,
                    seen,
                    "reseller",
                    config.get("username"),
                    config.get("gb"),
                    server_id=config.get("server_id"),
                )

    if traffic["total"]["sold_bytes"] > 0:
        traffic["total"]["usage_percent"] = (traffic["total"]["used_bytes"] / traffic["total"]["sold_bytes"]) * 100
    return traffic


def _collect_customer_growth_stats(payments: dict, now: datetime) -> dict:
    today = now.date()
    seven_day_start = today - timedelta(days=6)
    last_30_days_start = now - timedelta(days=30)
    first_purchase_by_user = {}
    purchase_dates_by_user = {}
    last30_purchase_users = set()
    returning_30d_users = set()
    paid_orders_without_user_id = 0
    regular_paid_orders = 0

    for record in (payments or {}).values():
        if not _is_regular_paid_payment(record):
            continue
        regular_paid_orders += 1
        payment_dt = _parse_datetime(record.get('updated_at') or record.get('created_at'))
        user_id = str(record.get('user_id') or '').strip()
        if not user_id:
            paid_orders_without_user_id += 1
            continue
        if not payment_dt:
            continue
        current_first = first_purchase_by_user.get(user_id)
        if current_first is None or payment_dt < current_first:
            first_purchase_by_user[user_id] = payment_dt
        purchase_dates_by_user.setdefault(user_id, []).append(payment_dt)

    for user_id, dates in purchase_dates_by_user.items():
        sorted_dates = sorted(dates)
        for index, payment_dt in enumerate(sorted_dates):
            if payment_dt >= last_30_days_start:
                last30_purchase_users.add(user_id)
                if index > 0:
                    returning_30d_users.add(user_id)

    first_purchase_dates = [value.date() for value in first_purchase_by_user.values()]
    new_today = sum(1 for value in first_purchase_dates if value == today)
    new_7d = sum(1 for value in first_purchase_dates if seven_day_start <= value <= today)
    new_30d = sum(1 for value in first_purchase_by_user.values() if value >= last_30_days_start)

    return {
        "all_time_paying_customers": len(first_purchase_by_user),
        "regular_paid_orders": regular_paid_orders,
        "paid_orders_without_user_id": paid_orders_without_user_id,
        "new_today": new_today,
        "new_7d": new_7d,
        "new_30d": new_30d,
        "active_30d": len(last30_purchase_users),
        "returning_30d": len(returning_30d_users),
    }


def _collect_referral_stats(referral_module) -> dict:
    try:
        referral_data = referral_module.load_referrals()
    except Exception:
        referral_data = {}
    total_payouts = 0.0
    if isinstance(referral_data, dict) and 'stats' in referral_data:
        for stat in referral_data['stats'].values():
            if isinstance(stat, dict):
                total_payouts += _safe_float(stat.get('total_earnings', 0))
    return {"total_rewards": total_payouts}


def _collect_language_stats(language_module, translations_module) -> dict:
    try:
        lang_prefs = language_module.load_user_languages()
    except Exception:
        lang_prefs = {}
    lang_counts = {}
    if isinstance(lang_prefs, dict):
        for lang in lang_prefs.values():
            lang_counts[lang] = lang_counts.get(lang, 0) + 1
    total_prefs = sum(lang_counts.values())
    languages = []
    for code, count in sorted(lang_counts.items(), key=lambda item: item[1], reverse=True):
        percent = (count / total_prefs) * 100 if total_prefs else 0
        lang_name = getattr(translations_module, "LANGUAGES", {}).get(code, code)
        languages.append({"code": code, "name": lang_name, "count": count, "percent": percent})
    return {"total": total_prefs, "languages": languages}


def build_server_info_snapshot(now=None) -> dict:
    '''Collects server information as structured data.'''
    _ensure_telegram_utils_path()
    from utils import payment_records, referral, language, translations, api_client, reseller

    now = now or datetime.now()
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    payments = payment_records.load_payments()
    if not isinstance(payments, dict):
        payments = {}

    vpn, live_users = _collect_vpn_and_live_users(api_client)
    traffic = _collect_sold_traffic_stats(payments, live_users, reseller)
    sales = _collect_payment_stats(payments, now)
    customers = _collect_customer_growth_stats(payments, now)
    online = build_online_users_from_userlist(vpn)
    referrals = _collect_referral_stats(referral)
    languages = _collect_language_stats(language, translations)

    return {
        "generated_at": now,
        "system": {
            "cpu_percent": psutil.cpu_percent(interval=1),
            "ram_percent": ram.percent,
            "ram_used_mb": ram.used // (1024 * 1024),
            "ram_total_mb": ram.total // (1024 * 1024),
            "disk_percent": disk.percent,
            "disk_used_gb": disk.used // (1024 * 1024 * 1024),
            "disk_total_gb": disk.total // (1024 * 1024 * 1024),
        },
        "online": online,
        "vpn": vpn,
        "traffic": traffic,
        "sales": sales,
        "customers": customers,
        "referrals": referrals,
        "languages": languages,
    }


def _dashboard_status(snapshot: dict) -> str:
    system = snapshot.get("system", {})
    vpn = snapshot.get("vpn", {})
    sales = snapshot.get("sales", {}).get("buckets", {})
    pending = sales.get("all", {}).get("pending", 0)
    disk_percent = _safe_float(system.get("disk_percent", 0))

    if disk_percent >= 95 or (vpn.get("configured", 0) and vpn.get("healthy", 0) == 0):
        return "🔴 Attention needed"
    if disk_percent >= 85 or vpn.get("unhealthy", 0) or pending or snapshot.get("online", {}).get("status") != "ok":
        return "🟡 Watch"
    return "🟢 Healthy"


def _format_orders(bucket: dict) -> str:
    return (
        f"${bucket['revenue']:,.2f} • {bucket['orders']} orders "
        f"(✅ {bucket['paid']} • ❌ {bucket['failed']} • ⌛ {bucket['expired']} • ⏳ {bucket['pending']})"
    )


def _online_text(online: dict) -> str:
    return str(online.get("count")) if online.get("count") is not None else "N/A"


def _traffic_usage_text(total_traffic: dict) -> str:
    usage_percent = total_traffic.get("usage_percent")
    return f" ({usage_percent:.1f}%)" if usage_percent is not None else ""


def _notable_servers(vpn: dict, limit: int = 3) -> list:
    return sorted(
        vpn.get("servers", []),
        key=lambda item: (item.get("healthy", True), -(item.get("load_ratio") or 0)),
    )[:limit]


def _build_server_info_alerts(snapshot: dict) -> list[str]:
    system = snapshot.get("system", {})
    online = snapshot.get("online", {})
    vpn = snapshot.get("vpn", {})
    traffic = snapshot.get("traffic", {})
    sales = snapshot.get("sales", {})
    customers = snapshot.get("customers", {})
    buckets = sales.get("buckets", {})
    alerts = []

    disk_percent = _safe_float(system.get("disk_percent", 0))
    if disk_percent >= 95:
        alerts.append(f"🔴 Disk critical: {disk_percent}% used")
    elif disk_percent >= 85:
        alerts.append(f"🟡 Disk high: {disk_percent}% used")

    if vpn.get("configured", 0) and vpn.get("healthy", 0) == 0:
        alerts.append("🔴 No healthy enabled VPN userlist is available")
    elif vpn.get("unhealthy", 0):
        alerts.append(f"🟡 Unhealthy VPN servers: {vpn.get('unhealthy', 0)}")
    if vpn.get("error"):
        alerts.append(f"🟡 VPN check error: {vpn.get('error')}")

    if online.get("status") not in (None, "ok"):
        alerts.append(f"🟡 Online users unavailable: {online.get('status')} ({online.get('error')})")

    pending = buckets.get("all", {}).get("pending", 0)
    if pending:
        alerts.append(f"🟡 Pending payments: {pending}")
    if traffic.get("missing_configs"):
        alerts.append(f"🟡 Missing sold configs: {traffic.get('missing_configs')}")
    if traffic.get("unavailable_servers"):
        alerts.append(f"🟡 Servers unavailable for traffic matching: {traffic.get('unavailable_servers')}")
    if customers.get("paid_orders_without_user_id"):
        alerts.append(f"🟡 Paid orders without user ID: {customers.get('paid_orders_without_user_id')}")

    return alerts


def _format_business_section(snapshot: dict) -> list[str]:
    sales = snapshot.get("sales", {})
    buckets = sales.get("buckets", {})
    referrals = snapshot.get("referrals", {})
    output = ["💰 **Business**"]
    output.append(f"Today: {_format_orders(buckets.get('today', _empty_order_bucket()))}")
    output.append(f"This Month: {_format_orders(buckets.get('month', _empty_order_bucket()))}")
    output.append(f"Last 30 Days: {_format_orders(buckets.get('last30', _empty_order_bucket()))}")
    output.append(f"All Time: {_format_orders(buckets.get('all', _empty_order_bucket()))}")
    output.append(f"AOV: ${sales.get('aov', {}).get('all', 0):,.2f} all • ${sales.get('aov', {}).get('last30', 0):,.2f} 30d")
    pending = buckets.get('all', {}).get('pending', 0)
    if pending:
        output.append(f"⚠️ Pending Payments: {pending}")
    output.append(f"Referral Rewards: ${referrals.get('total_rewards', 0):,.2f}")
    all_revenue = buckets.get('all', {}).get('revenue', 0)
    if all_revenue > 0:
        output.append(f"Referral Share: {(referrals.get('total_rewards', 0) / all_revenue) * 100:.1f}%")

    output.append("")
    output.append("📆 **Last 7 Days Sales**")
    for day in sales.get("daily_sales", []):
        output.append(f"{day['label']}: ${day['revenue']:,.2f} • {day['paid']} paid")

    if sales.get("top_plans_revenue") or sales.get("top_plans_orders"):
        output.append("")
        output.append("🏷️ **Top Plans**")
        if sales.get("top_plans_revenue"):
            revenue_parts = [f"{plan}: ${amount:,.2f}" for plan, amount in sales.get("top_plans_revenue", [])]
            output.append("Revenue: " + " • ".join(revenue_parts))
        if sales.get("top_plans_orders"):
            order_parts = [f"{plan}: {count}" for plan, count in sales.get("top_plans_orders", [])]
            output.append("Orders: " + " • ".join(order_parts))
    return output


def _format_customers_section(snapshot: dict) -> list[str]:
    customers = snapshot.get("customers", {})
    traffic = snapshot.get("traffic", {})
    languages = snapshot.get("languages", {})
    direct_traffic = traffic.get("direct", {})
    reseller_traffic = traffic.get("reseller", {})
    output = ["📈 **Customers**"]
    output.append(f"New Paying Customers: {customers.get('new_today', 0)} today • {customers.get('new_7d', 0)} 7d • {customers.get('new_30d', 0)} 30d")
    output.append(f"Active Paying Customers 30d: {customers.get('active_30d', 0)}")
    output.append(f"Returning Customers 30d: {customers.get('returning_30d', 0)}")
    output.append(f"All-Time Paying Customers: {customers.get('all_time_paying_customers', 0)}")
    output.append(f"Regular Paid Orders: {customers.get('regular_paid_orders', 0)}")
    if customers.get("paid_orders_without_user_id"):
        output.append(f"Paid Orders Without User ID: {customers.get('paid_orders_without_user_id')}")
    output.append("")
    output.append("👥 **Segments**")
    output.append(f"Direct Sold Configs: {direct_traffic.get('sold_configs', 0)} sold • {direct_traffic.get('matched_configs', 0)} live")
    output.append(f"Reseller Sold Configs: {reseller_traffic.get('sold_configs', 0)} sold • {reseller_traffic.get('matched_configs', 0)} live")
    output.append("")
    output.append("🌐 **Languages**")
    if languages.get("languages"):
        for lang in languages["languages"][:5]:
            output.append(f"{lang['name']}: {lang['percent']:.1f}% ({lang['count']})")
    else:
        output.append("No language data available.")
    return output


def _format_tech_section(snapshot: dict) -> list[str]:
    system = snapshot.get("system", {})
    online = snapshot.get("online", {})
    vpn = snapshot.get("vpn", {})
    output = ["🖥️ **Tech**"]
    output.append(f"CPU: {system.get('cpu_percent', 0)}%")
    output.append(f"RAM: {system.get('ram_percent', 0)}% ({system.get('ram_used_mb', 0)}MB/{system.get('ram_total_mb', 0)}MB)")
    output.append(f"Disk: {system.get('disk_percent', 0)}% ({system.get('disk_used_gb', 0)}GB/{system.get('disk_total_gb', 0)}GB)")
    output.append(f"Online Users: {_online_text(online)}")
    if online.get("status") not in (None, "ok"):
        output.append(f"Online Check: {online.get('status')} ({online.get('error')})")
    output.append("")
    output.append("⚖️ **VPN**")
    output.append(
        f"Servers: {vpn.get('configured', 0)} configured • {vpn.get('enabled', 0)} enabled • "
        f"{vpn.get('healthy', 0)} healthy • {vpn.get('unhealthy', 0)} unhealthy"
    )
    output.append(f"Active Configs: {vpn.get('active_configs', 0)}")
    for server in _notable_servers(vpn):
        health = "healthy" if server.get("healthy") else "unhealthy"
        load_ratio = server.get("load_ratio")
        load_text = f"{load_ratio:.2f}" if load_ratio is not None else "N/A"
        output.append(f"- {server.get('name')}: {health} • active {server.get('active_count', 'N/A')} • load {load_text}")
    if vpn.get("error"):
        output.append(f"VPN Check: error ({vpn.get('error')})")
    return output


def _format_traffic_section(snapshot: dict) -> list[str]:
    traffic = snapshot.get("traffic", {})
    total_traffic = traffic.get("total", {})
    direct_traffic = traffic.get("direct", {})
    reseller_traffic = traffic.get("reseller", {})
    output = ["🚦 **Traffic**"]
    output.append(
        f"Total Sold: {_format_bytes(total_traffic.get('used_bytes', 0))} served / "
        f"{_format_bytes(total_traffic.get('sold_bytes', 0))} sold{_traffic_usage_text(total_traffic)}"
    )
    output.append(
        f"Direct: {_format_bytes(direct_traffic.get('used_bytes', 0))} / "
        f"{_format_bytes(direct_traffic.get('sold_bytes', 0))} • "
        f"{direct_traffic.get('matched_configs', 0)} configs"
    )
    output.append(
        f"Reseller: {_format_bytes(reseller_traffic.get('used_bytes', 0))} / "
        f"{_format_bytes(reseller_traffic.get('sold_bytes', 0))} • "
        f"{reseller_traffic.get('matched_configs', 0)} configs"
    )
    if traffic.get("missing_configs"):
        output.append(f"Missing Sold Configs: {traffic.get('missing_configs')}")
    if traffic.get("skipped_no_username"):
        output.append(f"Sold Records Without Username: {traffic.get('skipped_no_username')}")
    if traffic.get("unavailable_servers"):
        output.append(f"Unavailable Servers For Traffic: {traffic.get('unavailable_servers')}")
    return output


def _format_alerts_section(snapshot: dict) -> list[str]:
    output = ["⚠️ **Alerts**"]
    alerts = _build_server_info_alerts(snapshot)
    if alerts:
        output.extend(alerts)
    else:
        output.append("No active alerts.")
    return output


def _format_overview_section(snapshot: dict) -> list[str]:
    sales = snapshot.get("sales", {})
    buckets = sales.get("buckets", {})
    customers = snapshot.get("customers", {})
    online = snapshot.get("online", {})
    vpn = snapshot.get("vpn", {})
    alerts = _build_server_info_alerts(snapshot)
    today_bucket = buckets.get("today", _empty_order_bucket())
    last30_bucket = buckets.get("last30", _empty_order_bucket())
    output = ["📌 **Overview**"]
    output.append(f"Status: {_dashboard_status(snapshot)}")
    output.append(f"Today Revenue: ${today_bucket.get('revenue', 0):,.2f} • {today_bucket.get('paid', 0)} paid")
    output.append(f"30d Revenue: ${last30_bucket.get('revenue', 0):,.2f} • {last30_bucket.get('paid', 0)} paid")
    output.append(f"Online Users: {_online_text(online)}")
    output.append(f"Active Configs: {vpn.get('active_configs', 0)}")
    output.append(f"New Customers: {customers.get('new_today', 0)} today • {customers.get('new_7d', 0)} 7d • {customers.get('new_30d', 0)} 30d")
    output.append(f"Returning Customers 30d: {customers.get('returning_30d', 0)}")
    output.append(f"Top Alert: {alerts[0] if alerts else 'No active alerts.'}")
    return output


def format_server_info_section(snapshot: dict, section: str = "overview") -> str:
    normalized = str(section or "overview").lower()
    if normalized not in SERVER_INFO_SECTIONS:
        normalized = "overview"
    if normalized == "full":
        return format_server_info(snapshot)

    formatters = {
        "overview": _format_overview_section,
        "business": _format_business_section,
        "customers": _format_customers_section,
        "tech": _format_tech_section,
        "traffic": _format_traffic_section,
        "alerts": _format_alerts_section,
    }
    output = formatters[normalized](snapshot)
    generated_at = snapshot.get("generated_at")
    if isinstance(generated_at, datetime):
        output.append("")
        output.append(f"Updated: {generated_at.strftime('%Y-%m-%d %H:%M:%S')}")
    return "\n".join(output)


def format_server_info(snapshot: dict) -> str:
    '''Formats a server information snapshot for Telegram/CLI output.'''
    system = snapshot.get("system", {})
    online = snapshot.get("online", {})
    vpn = snapshot.get("vpn", {})
    traffic = snapshot.get("traffic", {})
    sales = snapshot.get("sales", {})
    buckets = sales.get("buckets", {})
    referrals = snapshot.get("referrals", {})
    languages = snapshot.get("languages", {})

    online_text = _online_text(online)
    total_traffic = traffic.get("total", {})
    direct_traffic = traffic.get("direct", {})
    reseller_traffic = traffic.get("reseller", {})
    usage_text = _traffic_usage_text(total_traffic)

    output = []
    output.append("📊 **Server Info**")
    output.append(f"Status: {_dashboard_status(snapshot)}")
    output.append("")
    output.append("🖥️ **System**")
    output.append(f"CPU: {system.get('cpu_percent', 0)}% • RAM: {system.get('ram_percent', 0)}% ({system.get('ram_used_mb', 0)}MB/{system.get('ram_total_mb', 0)}MB)")
    output.append(f"Disk: {system.get('disk_percent', 0)}% ({system.get('disk_used_gb', 0)}GB/{system.get('disk_total_gb', 0)}GB)")
    output.append(f"Online Users: {online_text}")
    if online.get("status") not in (None, "ok"):
        output.append(f"Online Check: {online.get('status')} ({online.get('error')})")
    output.append("")
    output.append("⚖️ **VPN**")
    output.append(
        f"Servers: {vpn.get('configured', 0)} configured • {vpn.get('enabled', 0)} enabled • "
        f"{vpn.get('healthy', 0)} healthy • {vpn.get('unhealthy', 0)} unhealthy"
    )
    output.append(f"Active Configs: {vpn.get('active_configs', 0)}")
    for server in _notable_servers(vpn):
        health = "healthy" if server.get("healthy") else "unhealthy"
        load_ratio = server.get("load_ratio")
        load_text = f"{load_ratio:.2f}" if load_ratio is not None else "N/A"
        output.append(f"- {server.get('name')}: {health} • active {server.get('active_count', 'N/A')} • load {load_text}")
    if vpn.get("error"):
        output.append(f"VPN Check: error ({vpn.get('error')})")
    output.append("")
    output.append("🚦 **Traffic**")
    output.append(
        f"Total Sold: {_format_bytes(total_traffic.get('used_bytes', 0))} served / "
        f"{_format_bytes(total_traffic.get('sold_bytes', 0))} sold{usage_text}"
    )
    output.append(
        f"Direct: {_format_bytes(direct_traffic.get('used_bytes', 0))} / "
        f"{_format_bytes(direct_traffic.get('sold_bytes', 0))} • "
        f"{direct_traffic.get('matched_configs', 0)} configs"
    )
    output.append(
        f"Reseller: {_format_bytes(reseller_traffic.get('used_bytes', 0))} / "
        f"{_format_bytes(reseller_traffic.get('sold_bytes', 0))} • "
        f"{reseller_traffic.get('matched_configs', 0)} configs"
    )
    if traffic.get("missing_configs"):
        output.append(f"Missing Sold Configs: {traffic.get('missing_configs')}")
    if traffic.get("skipped_no_username"):
        output.append(f"Sold Records Without Username: {traffic.get('skipped_no_username')}")
    if traffic.get("unavailable_servers"):
        output.append(f"Unavailable Servers For Traffic: {traffic.get('unavailable_servers')}")
    output.append("")
    output.append("💰 **Sales**")
    output.append(f"Today: {_format_orders(buckets.get('today', _empty_order_bucket()))}")
    output.append(f"This Month: {_format_orders(buckets.get('month', _empty_order_bucket()))}")
    output.append(f"Last 30 Days: {_format_orders(buckets.get('last30', _empty_order_bucket()))}")
    output.append(f"All Time: {_format_orders(buckets.get('all', _empty_order_bucket()))}")
    output.append(f"AOV: ${sales.get('aov', {}).get('all', 0):,.2f} all • ${sales.get('aov', {}).get('last30', 0):,.2f} 30d")
    pending = buckets.get('all', {}).get('pending', 0)
    if pending:
        output.append(f"⚠️ Pending Payments: {pending}")
    output.append(f"Referral Rewards: ${referrals.get('total_rewards', 0):,.2f}")
    all_revenue = buckets.get('all', {}).get('revenue', 0)
    if all_revenue > 0:
        output.append(f"Referral Share: {(referrals.get('total_rewards', 0) / all_revenue) * 100:.1f}%")
    output.append("")
    output.append("📆 **Last 7 Days Sales**")
    for day in sales.get("daily_sales", []):
        output.append(f"{day['label']}: ${day['revenue']:,.2f} • {day['paid']} paid")

    if sales.get("top_plans_revenue") or sales.get("top_plans_orders"):
        output.append("")
        output.append("🏷️ **Top Plans**")
        if sales.get("top_plans_revenue"):
            revenue_parts = [f"{plan}: ${amount:,.2f}" for plan, amount in sales.get("top_plans_revenue", [])]
            output.append("Revenue: " + " • ".join(revenue_parts))
        if sales.get("top_plans_orders"):
            order_parts = [f"{plan}: {count}" for plan, count in sales.get("top_plans_orders", [])]
            output.append("Orders: " + " • ".join(order_parts))

    output.append("")
    output.append("🌐 **Languages**")
    if languages.get("languages"):
        for lang in languages["languages"][:5]:
            output.append(f"{lang['name']}: {lang['percent']:.1f}% ({lang['count']})")
    else:
        output.append("No language data available.")

    return "\n".join(output)


def server_info(section: str = "full") -> str | None:
    '''Retrieves server information.'''
    try:
        snapshot = build_server_info_snapshot()
        if str(section or "full").lower() == "full":
            return format_server_info(snapshot)
        return format_server_info_section(snapshot, section)
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
