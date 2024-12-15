from telebot import types
from utils.language import get_text


def create_main_markup():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('Add User', 'Show User')
    markup.row('Delete User', 'Server Info')
    markup.row('Backup Server')
    return markup
