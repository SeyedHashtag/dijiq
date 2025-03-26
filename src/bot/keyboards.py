from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton

# Main menu keyboard
MAIN_MENU_KEYBOARD = ReplyKeyboardMarkup([
    ['➕ Add New User', '📊 Status'],
    ['💰 Purchase VPN', '❓ Help']  # Added Purchase option
], resize_keyboard=True)

# Admin menu keyboard (separate from user menu)
ADMIN_MENU_KEYBOARD = ReplyKeyboardMarkup([
    ['➕ Add New User', '📊 Status'],
    ['⚙️ Settings', '❓ Help']
], resize_keyboard=True)

# Cancel keyboard
CANCEL_KEYBOARD = ReplyKeyboardMarkup([
    ['❌ Cancel']
], resize_keyboard=True)

# Confirm keyboard
CONFIRM_KEYBOARD = ReplyKeyboardMarkup([
    ['✅ Confirm', '❌ Cancel']
], resize_keyboard=True)

# Get the cancel keyboard
def get_cancel_keyboard():
    return CANCEL_KEYBOARD

# Get the confirm keyboard
def get_confirm_keyboard():
    return CONFIRM_KEYBOARD

# Get the main menu keyboard - detect if admin or regular user
def get_main_menu_keyboard(is_admin_user=False):
    return ADMIN_MENU_KEYBOARD if is_admin_user else MAIN_MENU_KEYBOARD

# Remove keyboard
def get_remove_keyboard():
    return ReplyKeyboardRemove()

# Create a payment button
def get_payment_button(payment_url):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(text="💳 Pay Now", url=payment_url)]
    ])
    return keyboard
