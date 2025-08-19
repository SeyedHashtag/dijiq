#!/usr/bin/env python3

import sys
import json
import asyncio
import aiofiles
import time
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from hysteria2_api import Hysteria2Client
from init_paths import *
from paths import *


@lru_cache(maxsize=1)
def get_secret() -> str:
    if not CONFIG_FILE.exists():
        print("Error: config.json file not found!", file=sys.stderr)
        sys.exit(1)

    with CONFIG_FILE.open() as f:
        data = json.load(f)

    secret = data.get("trafficStats", {}).get("secret")
    if not secret:
        print("Error: secret not found in config.json!", file=sys.stderr)
        sys.exit(1)

    return secret


def convert_bytes(bytes_val: int) -> str:
    if bytes_val >= (1 << 40):
        return f"{bytes_val / (1 << 40):.2f} TB"
    elif bytes_val >= (1 << 30):
        return f"{bytes_val / (1 << 30):.2f} GB"
    elif bytes_val >= (1 << 20):
        return f"{bytes_val / (1 << 20):.2f} MB"
    elif bytes_val >= (1 << 10):
        return f"{bytes_val / (1 << 10):.2f} KB"
    return f"{bytes_val} B"


def convert_speed(bytes_per_second: int) -> str:
    if bytes_per_second >= (1 << 40):
        return f"{bytes_per_second / (1 << 40):.2f} TB/s"
    elif bytes_per_second >= (1 << 30):
        return f"{bytes_per_second / (1 << 30):.2f} GB/s"
    elif bytes_per_second >= (1 << 20):
        return f"{bytes_per_second / (1 << 20):.2f} MB/s"
    elif bytes_per_second >= (1 << 10):
        return f"{bytes_per_second / (1 << 10):.2f} KB/s"
    return f"{int(bytes_per_second)} B/s"


async def read_file_async(filepath: str) -> str:
    try:
        async with aiofiles.open(filepath, 'r') as f:
            return await f.read()
    except FileNotFoundError:
        return ""


def format_uptime(seconds: float) -> str:
    seconds = int(seconds)
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, _ = divmod(remainder, 60)
    return f"{days}d {hours}h {minutes}m"


async def get_uptime_and_boottime() -> tuple[str, str]:
    try:
        content = await read_file_async("/proc/uptime")
        uptime_seconds = float(content.split()[0])
        boot_time_epoch = time.time() - uptime_seconds
        boot_time_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(boot_time_epoch))
        uptime_str = format_uptime(uptime_seconds)
        return uptime_str, boot_time_str
    except (FileNotFoundError, IndexError, ValueError):
        return "N/A", "N/A"


def parse_cpu_stats(content: str) -> tuple[int, int]:
    if not content:
        return 0, 0
    line = content.split('\n')[0]
    fields = list(map(int, line.strip().split()[1:]))
    idle, total = fields[3], sum(fields)
    return idle, total


async def get_cpu_usage(interval: float = 0.1) -> float:
    content1 = await read_file_async("/proc/stat")
    idle1, total1 = parse_cpu_stats(content1)
    
    await asyncio.sleep(interval)
    
    content2 = await read_file_async("/proc/stat")
    idle2, total2 = parse_cpu_stats(content2)

    idle_delta = idle2 - idle1
    total_delta = total2 - total1
    cpu_usage = 100.0 * (1 - idle_delta / total_delta) if total_delta else 0.0
    return round(cpu_usage, 1)


def parse_meminfo(content: str) -> tuple[int, int]:
    if not content:
        return 0, 0
    
    mem_info = {}
    for line in content.split('\n'):
        if ':' in line:
            parts = line.split()
            if len(parts) >= 2:
                key = parts[0].rstrip(':')
                if parts[1].isdigit():
                    mem_info[key] = int(parts[1])

    mem_total_kb = mem_info.get("MemTotal", 0)
    mem_free_kb = mem_info.get("MemFree", 0)
    buffers_kb = mem_info.get("Buffers", 0)
    cached_kb = mem_info.get("Cached", 0)
    sreclaimable_kb = mem_info.get("SReclaimable", 0)

    used_kb = mem_total_kb - mem_free_kb - buffers_kb - cached_kb - sreclaimable_kb

    used_kb = max(0, used_kb)
    return mem_total_kb // 1024, used_kb // 1024


async def get_memory_usage() -> tuple[int, int]:
    content = await read_file_async("/proc/meminfo")
    return parse_meminfo(content)


def parse_network_stats(content: str) -> tuple[int, int]:
    if not content:
        return 0, 0
    
    rx_bytes, tx_bytes = 0, 0
    lines = content.split('\n')
    
    for line in lines[2:]:
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) < 10:
            continue
        iface = parts[0].strip().replace(':', '')
        if iface == 'lo':
            continue
        try:
            rx_bytes += int(parts[1])
            tx_bytes += int(parts[9])
        except (IndexError, ValueError):
            continue
    
    return rx_bytes, tx_bytes


async def get_network_stats() -> tuple[int, int]:
    content = await read_file_async('/proc/net/dev')
    return parse_network_stats(content)


async def get_network_speed(interval: float = 0.5) -> tuple[int, int]:
    rx1, tx1 = await get_network_stats()
    await asyncio.sleep(interval)
    rx2, tx2 = await get_network_stats()
    
    rx_speed = (rx2 - rx1) / interval
    tx_speed = (tx2 - tx1) / interval
    return int(rx_speed), int(tx_speed)


def parse_connection_counts(tcp_content: str, udp_content: str) -> tuple[int, int]:
    tcp_count = len(tcp_content.split('\n')) - 2 if tcp_content else 0
    udp_count = len(udp_content.split('\n')) - 2 if udp_content else 0
    return max(0, tcp_count), max(0, udp_count)


async def get_connection_counts() -> tuple[int, int]:
    tcp_task = read_file_async('/proc/net/tcp')
    udp_task = read_file_async('/proc/net/udp')
    tcp_content, udp_content = await asyncio.gather(tcp_task, udp_task)
    return parse_connection_counts(tcp_content, udp_content)


def get_online_user_count_sync(secret: str) -> int:
    try:
        client = Hysteria2Client(
            base_url=API_BASE_URL,
            secret=secret
        )
        online_users = client.get_online_clients()
        return sum(user.connections for user in online_users.values() if user.is_online)
    except Exception as e:
        print(f"Error getting online users: {e}", file=sys.stderr)
        return 0


async def get_online_user_count(secret: str) -> int:
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as executor:
        return await loop.run_in_executor(executor, get_online_user_count_sync, secret)


def parse_total_traffic(content: str) -> tuple[int, int]:
    if not content:
        return 0, 0
    
    try:
        users = json.loads(content)
        total_upload = sum(int(user_data.get("upload_bytes", 0) or 0) for user_data in users.values())
        total_download = sum(int(user_data.get("download_bytes", 0) or 0) for user_data in users.values())
        return total_upload, total_download
    except (json.JSONDecodeError, ValueError, AttributeError):
        return 0, 0


async def get_user_traffic() -> tuple[int, int]:
    if not USERS_FILE.exists():
        return 0, 0
    
    try:
        async with aiofiles.open(USERS_FILE, 'r') as f:
            content = await f.read()
        return parse_total_traffic(content)
    except Exception as e:
        print(f"Error parsing traffic data: {e}", file=sys.stderr)
        return 0, 0


async def main():
    secret = get_secret()
    
    tasks = [
        get_uptime_and_boottime(),
        get_memory_usage(),
        get_connection_counts(),
        get_online_user_count(secret),
        get_user_traffic(),
        get_cpu_usage(0.1),
        get_network_speed(0.3),
        get_network_stats()
    ]
    
    results = await asyncio.gather(*tasks)
    
    uptime_str, boot_time_str = results[0]
    mem_total, mem_used = results[1]
    tcp_connections, udp_connections = results[2]
    online_users = results[3]
    user_upload, user_download = results[4]
    cpu_usage = results[5]
    download_speed, upload_speed = results[6]
    reboot_rx, reboot_tx = results[7]

    print(f"🕒 Uptime: {uptime_str} (since {boot_time_str})")
    print(f"📈 CPU Usage: {cpu_usage}%")
    print(f"💻 Used RAM: {mem_used}MB / {mem_total}MB")
    print(f"👥 Online Users: {online_users}")
    print()
    print(f"🔼 Upload Speed: {convert_speed(upload_speed)}")
    print(f"🔽 Download Speed: {convert_speed(download_speed)}")
    print(f"📡 TCP Connections: {tcp_connections}")
    print(f"📡 UDP Connections: {udp_connections}")
    print()
    print("📊 Traffic Since Last Reboot:")
    print(f"   🔼 Total Uploaded: {convert_bytes(reboot_tx)}")
    print(f"   🔽 Total Downloaded: {convert_bytes(reboot_rx)}")
    print(f"   📈 Combined Traffic: {convert_bytes(reboot_tx + reboot_rx)}")
    print()
    print("📊 User Traffic (All Time):")
    print(f"   🔼 Uploaded Traffic: {convert_bytes(user_upload)}")
    print(f"   🔽 Downloaded Traffic: {convert_bytes(user_download)}")
    print(f"   📈 Total Traffic: {convert_bytes(user_upload + user_download)}")


if __name__ == "__main__":
    asyncio.run(main())