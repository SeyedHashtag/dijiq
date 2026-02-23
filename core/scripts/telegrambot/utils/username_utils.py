import datetime
import json


def format_username_timestamp():
    """Return username metadata timestamp in YYMMDDHHMMSS format."""
    return datetime.datetime.now().strftime("%y%m%d%H%M%S")


def format_readable_timestamp():
    """Return human-readable timestamp in YYYY-MM-DD HH:MM format."""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")


def extract_existing_usernames(users_payload):
    """Collect usernames from API responses (dict or list forms)."""
    usernames = set()
    if isinstance(users_payload, dict):
        for username in users_payload.keys():
            if isinstance(username, str) and username:
                usernames.add(username)
    elif isinstance(users_payload, list):
        for item in users_payload:
            if not isinstance(item, dict):
                continue
            username = item.get("username")
            if isinstance(username, str) and username:
                usernames.add(username)
    return usernames


def _alpha_suffix(index):
    """Convert 0-based index to suffix: 0->'', 1->a, 26->z, 27->aa ..."""
    if index <= 0:
        return ""
    chars = []
    value = index
    while value > 0:
        value -= 1
        chars.append(chr(ord("a") + (value % 26)))
        value //= 26
    return "".join(reversed(chars))


def allocate_username(prefix, telegram_id, existing_usernames):
    """Allocate first available username using alphabetical collision suffixes."""
    base = f"{prefix}{telegram_id}"
    existing_lower = {
        username.lower()
        for username in existing_usernames
        if isinstance(username, str) and username
    }

    index = 0
    while True:
        candidate = f"{base}{_alpha_suffix(index)}"
        if candidate.lower() not in existing_lower:
            return candidate
        index += 1


def build_user_note(
    username,
    traffic_limit,
    expiration_days,
    password="",
    creation_date="",
    unlimited=False,
    note_text="",
    timestamp=None,
):
    """Build note as a human-readable formatted string."""
    ts = timestamp or format_readable_timestamp()
    note_str = str(note_text or "N/A")
    return f"📅 {ts} | 📝 {note_str} | ✏️ "
