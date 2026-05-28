from telebot import types

from utils.api_client import MultiServerAPI, get_server_configs, save_server_configs
from utils.command import bot, is_admin


server_admin_state = {}


def _format_status_line(status):
    enabled = "enabled" if status.get("enabled", True) else "disabled"
    health = "healthy" if status.get("healthy") else "unhealthy"
    active_count = status.get("active_count")
    load_ratio = status.get("load_ratio")
    active_text = str(active_count) if active_count is not None else "N/A"
    ratio_text = f"{load_ratio:.2f}" if load_ratio is not None else "N/A"
    weight = status.get("weight", 1)
    return (
        f"*{status.get('name', status.get('id'))}* (`{status.get('id')}`)\n"
        f"Status: `{enabled}` | Health: `{health}`\n"
        f"Active configs: `{active_text}` | Weight: `{weight}` | Load: `{ratio_text}`"
    )


def _build_servers_menu():
    statuses = MultiServerAPI().get_server_statuses()
    if not statuses:
        return "⚠️ No VPN servers are configured.", types.InlineKeyboardMarkup()

    text = "⚖️ *VPN Servers*\n\n" + "\n\n".join(_format_status_line(status) for status in statuses)
    markup = types.InlineKeyboardMarkup(row_width=2)
    for status in statuses:
        server_id = status["id"]
        toggle_label = "Disable" if status.get("enabled", True) else "Enable"
        markup.add(
            types.InlineKeyboardButton(f"{toggle_label} {status.get('name', server_id)}", callback_data=f"vpn_server:toggle:{server_id}"),
            types.InlineKeyboardButton(f"Weight {status.get('name', server_id)}", callback_data=f"vpn_server:weight:{server_id}"),
        )
    markup.add(types.InlineKeyboardButton("Refresh", callback_data="vpn_server:refresh"))
    return text, markup


@bot.message_handler(func=lambda message: is_admin(message.from_user.id) and message.text == '⚖️ VPN Servers')
def show_vpn_servers(message):
    text, markup = _build_servers_menu()
    bot.reply_to(message, text, reply_markup=markup, parse_mode="Markdown")


@bot.callback_query_handler(func=lambda call: call.data.startswith("vpn_server:"))
def handle_vpn_server_callback(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "Unauthorized.")
        return

    parts = call.data.split(":")
    action = parts[1] if len(parts) > 1 else ""

    if action == "refresh":
        text, markup = _build_servers_menu()
        bot.answer_callback_query(call.id)
        bot.edit_message_text(text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup, parse_mode="Markdown")
        return

    if len(parts) < 3:
        bot.answer_callback_query(call.id, "Invalid request.")
        return

    server_id = parts[2]
    servers = get_server_configs()
    target = next((server for server in servers if server["id"] == server_id), None)
    if not target:
        bot.answer_callback_query(call.id, "Server not found.")
        return

    if action == "toggle":
        target["enabled"] = not bool(target.get("enabled", True))
        save_server_configs(servers)
        text, markup = _build_servers_menu()
        bot.answer_callback_query(call.id, "Server updated.")
        bot.edit_message_text(text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup, parse_mode="Markdown")
        return

    if action == "weight":
        server_admin_state[call.from_user.id] = {"state": "waiting_server_weight", "server_id": server_id}
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, f"Enter a new positive weight for {target.get('name', server_id)}:")
        return

    bot.answer_callback_query(call.id, "Invalid action.")


@bot.message_handler(func=lambda message: is_admin(message.from_user.id) and server_admin_state.get(message.from_user.id, {}).get("state") == "waiting_server_weight")
def handle_server_weight_input(message):
    state = server_admin_state.get(message.from_user.id, {})
    server_id = state.get("server_id")
    try:
        weight = float(message.text.strip())
        if weight <= 0:
            raise ValueError
    except (TypeError, ValueError):
        bot.reply_to(message, "Weight must be a positive number.")
        return

    servers = get_server_configs()
    updated = False
    for server in servers:
        if server["id"] == server_id:
            server["weight"] = weight
            updated = True
            break

    if not updated or not save_server_configs(servers):
        bot.reply_to(message, "Failed to update server weight.")
        server_admin_state.pop(message.from_user.id, None)
        return

    server_admin_state.pop(message.from_user.id, None)
    text, markup = _build_servers_menu()
    bot.reply_to(message, text, reply_markup=markup, parse_mode="Markdown")
