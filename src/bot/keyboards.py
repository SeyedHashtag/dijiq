from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton

# Main menu keyboard
MAIN_MENU_KEYBOARD = ReplyKeyboardMarkup([
    ['➕ Add New User', '📊 Status'],
    ['⚙️ Settings', '❓ Help']
], resize_keyboard=True)

# Cancel keyboard
CANCEL_KEYBOARD = ReplyKeyboardMarkup([
    ['❌ Cancel']
], resize_keyboard=True)

# Get the cancel keyboard
def get_cancel_keyboard():
    return CANCEL_KEYBOARD

# Get the main menu keyboard
def get_main_menu_keyboard():
    return MAIN_MENU_KEYBOARD

# Remove keyboard
def get_remove_keyboard():
    return ReplyKeyboardRemove()
