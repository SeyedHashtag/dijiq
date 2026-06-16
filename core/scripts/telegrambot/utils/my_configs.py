import qrcode
import io
import json
import os
import requests
import re
import time
import threading
from dotenv import load_dotenv
from telebot import types
from utils.command import bot
from utils.api_client import APIClient, MultiServerAPI
from utils.edit_plans import load_plans
from utils.translations import BUTTON_TRANSLATIONS, get_message_text, get_button_text
from utils.language import get_user_language
from utils.telegram_safe import safe_answer_callback_query, safe_delete_message, safe_edit_message_text, safe_send_message, safe_send_photo

MY_CONFIGS_CACHE_TTL_SECONDS = 300
MY_CONFIGS_INFLIGHT_LOCK = threading.Lock()
MY_CONFIGS_INFLIGHT = set()
SHOW_CONFIG_INFLIGHT = set()
MY_CONFIGS_REFRESH_LOCK = threading.Lock()
MY_CONFIGS_REFRESH_INFLIGHT = set()


def _my_configs_cache_notice(language):
    return get_message_text(language, "my_configs_cache_notice")


def _append_my_configs_cache_notice(text, language, show_cache_notice=True):
    if not show_cache_notice:
        return text
    notice = _my_configs_cache_notice(language)
    return f"{text}\n\n{notice}" if notice else text


def _refresh_my_configs_snapshot_async(include_disabled=False):
    key = bool(include_disabled)
    with MY_CONFIGS_REFRESH_LOCK:
        if key in MY_CONFIGS_REFRESH_INFLIGHT:
            return
        MY_CONFIGS_REFRESH_INFLIGHT.add(key)

    def refresh():
        try:
            MultiServerAPI().get_user_snapshot_entries(
                include_disabled=include_disabled,
                force_refresh=True,
                cache_ttl_seconds=MY_CONFIGS_CACHE_TTL_SECONDS,
            )
        except Exception as e:
            print(f"[MyConfigs] background refresh failed: {e}")
        finally:
            with MY_CONFIGS_REFRESH_LOCK:
                MY_CONFIGS_REFRESH_INFLIGHT.discard(key)

    threading.Thread(target=refresh, daemon=True, name="my-configs-refresh").start()


def _get_my_configs_snapshot_entries(multi_api, include_disabled=False):
    cached_entries = multi_api.get_cached_user_snapshot_entries(
        include_disabled=include_disabled,
        cache_ttl_seconds=MY_CONFIGS_CACHE_TTL_SECONDS,
        allow_expired=True,
    )
    if cached_entries is not None:
        if getattr(multi_api, "last_user_snapshot_cache_stale", False):
            _refresh_my_configs_snapshot_async(include_disabled=include_disabled)
        return cached_entries

    return multi_api.get_user_snapshot_entries(
        include_disabled=include_disabled,
        cache_ttl_seconds=MY_CONFIGS_CACHE_TTL_SECONDS,
    )


def _iter_users_from_snapshot_entries(entries):
    for entry in entries:
        client = entry["client"]
        users = entry["users"]
        if users is None:
            continue
        if isinstance(users, dict):
            for username, data in users.items():
                yield client, username, data
        elif isinstance(users, list):
            for data in users:
                if isinstance(data, dict):
                    yield client, data.get("username"), data


def _find_cached_user(multi_api, username, preferred_server_id=None):
    for include_disabled in (False, True):
        entries = multi_api.get_cached_user_snapshot_entries(
            include_disabled=include_disabled,
            cache_ttl_seconds=MY_CONFIGS_CACHE_TTL_SECONDS,
            allow_expired=True,
        )
        if entries is None:
            continue

        fallback = None
        for api_client, cached_username, user_data in _iter_users_from_snapshot_entries(entries):
            if str(cached_username) != str(username):
                continue
            if preferred_server_id and api_client.server_id == preferred_server_id:
                return api_client, user_data
            if fallback is None:
                fallback = (api_client, user_data)
        if fallback is not None:
            return fallback
    return None, None


def _reply_config_selection(message, user_configs, language):
    markup = types.InlineKeyboardMarkup()

    for username, user_data, api_client in user_configs:
        max_traffic_gb = user_data.get('max_download_bytes', 0) / (1024 ** 3)
        button_text = f"{username} - {max_traffic_gb:.2f} GB"
        markup.add(types.InlineKeyboardButton(button_text, callback_data=f"show_config:{api_client.server_id}:{username}"))

    bot.reply_to(
        message,
        _append_my_configs_cache_notice("📱 Select a configuration to view:", language),
        reply_markup=markup
    )


@bot.message_handler(func=lambda message: any(
    message.text == translations["my_configs"] 
    for translations in BUTTON_TRANSLATIONS.values()
))
def my_configs(message):
    """Handle the My Configs button click"""
    user_id = message.from_user.id
    with MY_CONFIGS_INFLIGHT_LOCK:
        if user_id in MY_CONFIGS_INFLIGHT:
            bot.send_chat_action(message.chat.id, 'typing')
            return
        MY_CONFIGS_INFLIGHT.add(user_id)
    started_at = time.monotonic()
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        language = get_user_language(user_id)
        
        multi_api = MultiServerAPI()
        if not multi_api.servers:
            bot.reply_to(message, "⚠️ Error connecting to API. Please try again later.")
            return
        
        # Look for usernames that match this user's Telegram ID pattern
        user_configs = []

        # Supported patterns include new formats (s{id}, t{id}) and legacy timestamped formats.
        paid_patterns = (
            re.compile(rf"^s{user_id}[a-z]*$", re.IGNORECASE),
            re.compile(rf"^{user_id}t"),
            re.compile(rf"^sell{user_id}t"),
        )
        test_patterns = (
            re.compile(rf"^t{user_id}[a-z]*$", re.IGNORECASE),
            re.compile(rf"^test{user_id}t"),
        )

        paid_configs = []
        test_configs = []
        entries = _get_my_configs_snapshot_entries(multi_api, include_disabled=False)
        for api_client, username, config_data in _iter_users_from_snapshot_entries(entries):
            if username and any(pattern.match(username) for pattern in paid_patterns):
                paid_configs.append((username, config_data, api_client))
            elif username and any(pattern.match(username) for pattern in test_patterns):
                test_configs.append((username, config_data, api_client))

        user_configs = paid_configs or test_configs
        elapsed_ms = int((time.monotonic() - started_at) * 1000)
        cache_hit = getattr(multi_api, "last_user_snapshot_cache_hit", None)
        cache_state = "hit" if cache_hit is True else "miss" if cache_hit is False else "unknown"
        print(
            f"[MyConfigs] user_id={user_id} configs={len(user_configs)} "
            f"servers={len(multi_api.servers)} cache={cache_state} elapsed_ms={elapsed_ms}"
        )

        if not user_configs:
            bot.reply_to(
                message,
                _append_my_configs_cache_notice(get_message_text(language, "no_active_configs"), language)
            )
            return

        _reply_config_selection(message, user_configs, language)
    except Exception as e:
        elapsed_ms = int((time.monotonic() - started_at) * 1000)
        print(f"[MyConfigs] user_id={user_id} error={type(e).__name__} elapsed_ms={elapsed_ms}")
        bot.reply_to(message, f"⚠️ Error processing user data: {str(e)}")
        return
    finally:
        with MY_CONFIGS_INFLIGHT_LOCK:
            MY_CONFIGS_INFLIGHT.discard(user_id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('show_config:'))
def handle_show_config(call):
    """Handle the selection of a specific config"""
    key = (call.from_user.id, call.data)
    with MY_CONFIGS_INFLIGHT_LOCK:
        if key in SHOW_CONFIG_INFLIGHT:
            safe_answer_callback_query(bot, call.id)
            return
        SHOW_CONFIG_INFLIGHT.add(key)
    try:
        safe_answer_callback_query(bot, call.id)
        parts = call.data.split(':')
        if len(parts) >= 3:
            server_id, username = parts[1], parts[2]
        else:
            server_id, username = None, parts[1]

        multi_api = MultiServerAPI()
        api_client, user_data = _find_cached_user(multi_api, username, preferred_server_id=server_id)
        if user_data is None:
            api_client, user_data = multi_api.find_user(username, preferred_server_id=server_id)
        
        if user_data:
            # Show the config
            display_config(
                call.message.chat.id,
                username,
                user_data,
                api_client,
                is_callback=True,
                message_id=call.message.message_id,
                user_id=call.from_user.id,
                show_cache_notice=True,
            )
        else:
            safe_edit_message_text(
                bot,
                f"⚠️ Error: User '{username}' not found or API error.",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id
            )
    except Exception as e:
        print(f"Error in handle_show_config: {str(e)}")
        safe_edit_message_text(
            bot,
            f"⚠️ Error processing your request: {str(e)}",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id
        )
    finally:
        with MY_CONFIGS_INFLIGHT_LOCK:
            SHOW_CONFIG_INFLIGHT.discard(key)

def display_config(chat_id, username, user_data, api_client, is_callback=False, message_id=None, user_id=None, show_cache_notice=False):
    """Display user configuration details and QR code"""
    
    # Check if the user is blocked/expired
    is_blocked = user_data.get('blocked', False)
    
    try:
        # Extract user statistics with default values to prevent NoneType errors
        upload_bytes = user_data.get('upload_bytes', 0) or 0  # Convert None to 0
        download_bytes = user_data.get('download_bytes', 0) or 0  # Convert None to 0
        status = user_data.get('status', 'Unknown')
        max_download_bytes = user_data.get('max_download_bytes', 0) or 0  # Convert None to 0
        expiration_days = user_data.get('expiration_days', 0)
        account_creation_date = user_data.get('account_creation_date', 'Unknown')

        # Calculate traffic with safety checks
        upload_gb = upload_bytes / (1024 ** 3)  # Convert bytes to GB
        download_gb = download_bytes / (1024 ** 3)  # Convert bytes to GB
        total_usage_gb = upload_gb + download_gb
        max_traffic_gb = max_download_bytes / (1024 ** 3)
        
        # Format user details
        if upload_bytes == 0 and download_bytes == 0:
            traffic_message = "**Traffic Data:**\nNo traffic data available."
        else:
            traffic_message = (
                f"🔼 Upload: {upload_gb:.2f} GB\n"
                f"🔽 Download: {download_gb:.2f} GB\n"
                f"📊 Total Usage: {total_usage_gb:.2f} GB"
            )
            if max_traffic_gb > 0:
                traffic_message += f" / {max_traffic_gb:.2f} GB"
            traffic_message += f"\n🌐 Status: {status}"

        traffic_limit_display = f"{max_traffic_gb:.2f} GB" if max_traffic_gb > 0 else "Unlimited"
        
        formatted_details = (
            f"\n🆔 Username: {username}\n"
            f"📊 Traffic Limit: {traffic_limit_display}\n"
            f"📅 Days Remaining: {expiration_days}\n"
            f"⏳ Creation Date: {account_creation_date}\n"
            f"💡 Status: {'❌ Blocked/Expired' if is_blocked else '✅ Active'}\n\n"
            f"{traffic_message}"
        )
        
        if is_blocked:
            # User is blocked/expired
            language = get_user_language(user_id or chat_id)
            renewal_markup = None
            message = (
                f"❌ **Your configuration has expired!**\n{formatted_details}\n\n"
                "Please use the '💰 Purchase Plan' button to buy a new subscription."
            )

            try:
                from utils.renewal import find_customer_renewal_offer, format_renewal_offer

                offer = find_customer_renewal_offer(
                    user_id or chat_id,
                    username,
                    api_client,
                    user_data,
                    load_plans(),
                )
                if offer.get('eligible'):
                    message = (
                        f"❌ **Your configuration has expired!**\n{formatted_details}\n\n"
                        f"{format_renewal_offer(language, offer, include_payment_prompt=False)}"
                    )
                    renewal_markup = types.InlineKeyboardMarkup()
                    renewal_markup.add(
                        types.InlineKeyboardButton(
                            get_button_text(language, "renew_plan") or "Renew Plan",
                            callback_data=f"renew_plan:{offer['token']}"
                        )
                    )
            except Exception as renewal_error:
                print(f"Error building renewal offer for {username}: {renewal_error}")

            message = _append_my_configs_cache_notice(message, language, show_cache_notice)
            
            if is_callback:
                safe_edit_message_text(bot, message, chat_id=chat_id, message_id=message_id, parse_mode="Markdown", reply_markup=renewal_markup)
            else:
                safe_send_message(bot, chat_id, message, parse_mode="Markdown", reply_markup=renewal_markup)
            return
        
        # User is active, get subscription URL using the new API endpoint
        user_uri_data = api_client.get_user_uri(username)
        if not user_uri_data or 'normal_sub' not in user_uri_data:
            if is_callback:
                safe_edit_message_text(
                    bot,
                    f"⚠️ Error: Could not generate subscription URL for '{username}'. Please contact support.",
                    chat_id=chat_id,
                    message_id=message_id
                )
            else:
                safe_send_message(
                    bot,
                    chat_id,
                    f"⚠️ Error: Could not generate subscription URL for '{username}'. Please contact support."
                )
            return
        sub_url = user_uri_data['normal_sub']
        ipv4_url = user_uri_data.get('ipv4', '')
        
        # Create QR code for IPv4 URL when available.
        qr_code = qrcode.make(ipv4_url or sub_url)
        bio = io.BytesIO()
        qr_code.save(bio, 'PNG')
        bio.seek(0)
        
        # Prepare caption with formatted details and subscription URL
        caption = f"{formatted_details}\n\n"
        if ipv4_url:
            caption += f"IPv4 URL: `{ipv4_url}`\n\n"
            
        caption += f"Subscription URL:\n{sub_url}"
        caption = _append_my_configs_cache_notice(
            caption,
            get_user_language(user_id or chat_id),
            show_cache_notice,
        )
        
        # Send QR code with details
        if is_callback:
            safe_delete_message(bot, chat_id=chat_id, message_id=message_id)
            safe_send_photo(
                bot,
                chat_id,
                photo=bio,
                caption=caption,
                parse_mode="Markdown"
            )
        else:
            safe_send_photo(
                bot,
                chat_id,
                photo=bio,
                caption=caption,
                parse_mode="Markdown"
            )
    except Exception as e:
        error_message = f"⚠️ Error displaying configuration: {str(e)}"
        print(f"Error in display_config: {str(e)}")
        if is_callback:
            safe_edit_message_text(bot, error_message, chat_id=chat_id, message_id=message_id)
        else:
            safe_send_message(bot, chat_id, error_message)
