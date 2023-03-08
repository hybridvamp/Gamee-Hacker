import functools
import logging
import random
import re
import sys
from collections import deque

from babel.support import Translations
from decouple import config as env
from models import Game, User, app, db
from numpy.random import normal as np_normal
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.ext import (
    CallbackContext,
    CallbackQueryHandler,
    CommandHandler,
    Filters,
    MessageHandler,
    Updater,
)

try:
    from ..gameeHacker.core import GameeHacker
except ImportError:
    sys.path.insert(0, "../gameeHacker/")
    from core import GameeHacker

TELEGRAM_TOKEN = env("TELEGRAM_TOKEN")

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

logger = logging.getLogger(__name__)


def divide_chunks(string_or_list, n):
    for i in range(0, len(string_or_list), n):
        yield string_or_list[i : i + n]


def is_url(str):
    regex = (
        "((http|https)://)(www.)?"
        + "[a-zA-Z0-9@:%._\\+~#?&//=]"
        + "{2,256}\\.[a-z]"
        + "{2,6}\\b([-a-zA-Z0-9@:%"
        + "._\\+~#?&//=]*)"
    )
    p = re.compile(regex)
    if re.search(p, str):
        return True
    else:
        return False


def is_score(str):
    str = str.strip()
    regex = "^[0-9]+$"
    p = re.compile(regex)
    if re.search(p, str):
        return True
    else:
        return False


def check_add_admin_pattern(str):
    str = str.strip()
    regex = "^admin [0-9]+$"
    p = re.compile(regex)
    if re.search(p, str):
        return True
    else:
        return False


def user_preferences(func):
    @functools.wraps(func)
    def wrapper_user_preferences(*args, **kwargs):
        try:
            chat_id = str(args[0]["message"]["chat"]["id"])
            username = args[0]["message"]["chat"]["username"]
            message = args[0]["message"]["text"]
        except TypeError:
            chat_id = str(args[0]["callback_query"]["message"]["chat"]["id"])
            username = args[0]["callback_query"]["message"]["chat"]["username"]
            message = args[0]["callback_query"]["message"]["text"]
        language = get_user_language(chat_id)
        user_pref = {
            "lang": language,
            "chat_id": chat_id,
            "username": username,
            "message": message,
        }
        if not check_user_exists(chat_id):
            create_user(user_pref)
        args = list(args)
        args.append(user_pref)
        args = tuple(args)
        value = func(*args, **kwargs)
        return value

    return wrapper_user_preferences


def is_user_joined_channel(func):
    @functools.wraps(func)
    def wrapper_is_user_joined_channel(*args, **kwargs):
        user_id = str(args[0]["message"]["chat"]["id"])
        # Get the chat status of the user in the channel
        chat_member = args[1].bot.get_chat_member(chat_id="@Gamee_donation", user_id=int(user_id))
        # Check if the user is a member of the channel
        if chat_member.status == "left":
            # Prompt the user to join the channel
            language = get_user_language(user_id)
            _ = Translations.load("locales", [language]).gettext
            args[0].message.reply_text(
                _(
                    "Please join the channel @Gamee_donation to continue.\nAfter you've joined the channel, just resend your score."
                )
            )
        else:
            value = func(*args, **kwargs)
            return value

    return wrapper_is_user_joined_channel


def admin_required(func):
    @functools.wraps(func)
    def wrapper_admin_required(*args, **kwargs):
        chat_id = str(args[0]["message"]["chat"]["id"])
        user = get_user(chat_id)
        if user.is_admin:
            value = func(*args, **kwargs)
            return value
        else:
            language = get_user_language(chat_id)
            _ = Translations.load("locales", [language]).gettext
            args[0].message.reply_text(_("Access forbidden."))

    return wrapper_admin_required


@user_preferences
def settings(update: Update, context: CallbackContext, user_pref=None) -> None:
    _ = Translations.load("locales", [user_pref["lang"]]).gettext
    keyboard = [[_("Change language") + " 🗣", _("Contribute") + " 🤝"], [_("Return") + " ↩️"]]
    message = _("Please select one item:")
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    update.message.reply_text(message, reply_markup=reply_markup)


@admin_required
@user_preferences
def admin_panel(update: Update, context: CallbackContext, user_pref=None) -> None:
    _ = Translations.load("locales", [user_pref["lang"]]).gettext
    keyboard = [
        [_("Get users summery") + " 📜", _("Get full data") + " 🗄"],
        [_("Add admin") + " ➕"],
        [_("Return") + " ↩️"],
    ]
    message = _("Please select one item:")
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    update.message.reply_text(message, reply_markup=reply_markup)


@admin_required
@user_preferences
def create_admin(update: Update, context: CallbackContext, user_pref=None) -> None:
    _ = Translations.load("locales", [user_pref["lang"]]).gettext
    message = _("Please send admin telegram_id in following format: admin <ID>")
    update.message.reply_text(message)


@user_preferences
def donate_us(update: Update, context: CallbackContext, user_pref=None) -> None:
    _ = Translations.load("locales", [user_pref["lang"]]).gettext
    message = _(
        """
Hello dear friend 👋
This bot is open source, so anyone can run it and use it via a server (for personal and public use).

And this bot continued to work completely free of charge for the few months it was active. No money was taken from my pocket or yours, and it was supposed to continue like this so everyone could use it and enjoy it 🦄

But the free server that this bot used to run no longer provides free service: https://help.heroku.com/RSBRUH58/removal-of-heroku-free-product-plans-faq

And I had become indifferent to this bot. However, upon request from several friends, I will put a wallet address for your donations. The bot will continue its activity for free if the donation is paid and the service fee is paid.

In some channels, some people profit from this free bot by charging users a fee to hack games!👀

📍 @Gamee_donation ❤️
📍 @GameeHacker_bot 🎮
	"""
    )

    wallet = """
💵 ETH (ERC20) 👇
0x2fd31A0FF4Fc7b10dd8DB919AEb1762927998595

💵 BINANCE SMART CHAIN (BEP20) 👇
0x2fd31A0FF4Fc7b10dd8DB919AEb1762927998595

💵 TRX TRON (TRC20) (ONLY USDT) 👇 
TTNS6i8F6Awewm7Ps2jJfbACdo9n3qBGwq

💵 BTC 👇 
bc1q9wd96jus3pqyn6tvs786we8k24622apymyq2fj

💵 DOGE COIN 👇
D5up12Y3HxUVgokMtFKcT56HMckDJJMb1r

📍 @Gamee_donation ❤️
📍 @GameeHacker_bot 🎮
	"""
    update.message.reply_text(message)
    update.message.reply_text(wallet)


@admin_required
@user_preferences
def create_admin_telegram(update: Update, context: CallbackContext, user_pref=None) -> None:
    id = user_pref["message"].replace("admin", "").strip()
    message = add_admin(id)
    update.message.reply_text(message)


@admin_required
@user_preferences
def users_summery(update: Update, context: CallbackContext, user_pref=None) -> None:
    _ = Translations.load("locales", [user_pref["lang"]]).gettext
    number_of_users_messages = "👤 " + _("Number of users: ")
    number_of_games_messages = "🧩 " + _("Number of games: ")
    number_of_users = User.query.count()
    number_of_games = Game.query.count()
    message = (
        f"{number_of_users_messages}{number_of_users}\n{number_of_games_messages}{number_of_games}"
    )
    update.message.reply_text(message)


def chunck_tel_messages(text, chunck=4096):
    start = 0
    texts = []

    while True:
        chuncked_text, start = clean_chunck(text, start, chunck)
        if len(chuncked_text) == 0:
            break
        texts.append(chuncked_text)

    return texts


def clean_chunck(text, start, chunck):
    text = text[start : start + chunck]
    end_text = chunck
    while not validata_tags(text):
        end_text = text.rfind("<a")
        text = text[0:end_text]
    return text, end_text + start


def validata_tags(text):
    open_tag = text.count("<a")
    closed_tag = text.count("</a>")
    return open_tag == closed_tag


@admin_required
@user_preferences
def users_full(update: Update, context: CallbackContext, user_pref=None) -> None:
    _ = Translations.load("locales", [user_pref["lang"]]).gettext
    all_users = User.query.all()
    message = ""
    for user in all_users:
        user_id = "🆔 " + _("User ID: ")
        username = "👤 " + _("Username: ")
        language = "🗣 " + _("Language: ")
        user_id_href = f"<a href='tg://openmessage?user_id={user.id}'>{user.id}</a>"
        username_with_sign = f"@{user.username}" if user.username else "-"
        message += f"🔹\n{user_id}{user_id_href}\n{username}{username_with_sign}\n{language}{user.language}\n"
        message += "\n"
        user_games = Game.query.filter_by(user_id=user.id).all()
        for game in user_games:
            game_title = "🎳 " + _("Title: ")
            game_rank = "🏆 " + _("Rank: ")
            game_score = "🎗 " + _("Score: ")
            href = f"<a href='{game.url}'>{game.title}</a>"
            message += f"🔻\n{game_title}{href}\n{game_rank}{game.rank}\n{game_score}{game.score}\n"

    messages = chunck_tel_messages(message)
    for message in messages:
        update.message.reply_text(message, parse_mode="html", disable_web_page_preview=True)


@user_preferences
def add_game(update: Update, context: CallbackContext, user_pref=None) -> None:
    _ = Translations.load("locales", [user_pref["lang"]]).gettext
    message = _("Please send game URL:")
    update.message.reply_text(message)


@user_preferences
def get_game_url(update: Update, context: CallbackContext, user_pref=None) -> None:
    with app.app_context():
        user = get_user(user_pref["chat_id"])
        user.last_url = user_pref["message"]
        db.session.add(user)
        db.session.commit()
    _ = Translations.load("locales", [user_pref["lang"]]).gettext
    message = _("Please send your score:")
    update.message.reply_text(message)


def generate_random_game_play_time(score):
    if score < 100:
        time = random.randint(1, 6)
    elif score < 1000:
        time = random.randint(6, 16)
    elif score < 10000:
        time = random.randint(16, 41)
    elif score < 100000:
        time = random.randint(41, 71)
    elif score < 1000000:
        time = random.randint(71, 121)
    else:
        time = random.randint(121, 301)
    return time


@user_preferences
@is_user_joined_channel
def start_hacking(update: Update, context: CallbackContext, user_pref=None) -> None:
    _ = Translations.load("locales", [user_pref["lang"]]).gettext
    score = int(user_pref["message"].strip())
    chat_id = user_pref["chat_id"]
    url = get_user_last_url(chat_id)
    if url:
        logger.info(
            f"START HACKING: user: {user_pref['chat_id']} username:{user_pref['username']}"
        )
        message = _("Please wait a moment...")
        update.message.reply_text(message)
        time = generate_random_game_play_time(score)
        game_obj = GameeHacker(url, score, time)
        game_obj.send_score()
        image = game_obj.get_game_img()
        name = game_obj.get_game_name()
        rank = game_obj.get_user_rank()
        record = game_obj.get_user_record()
        if game_obj.check_ban_status():
            message = _("You are banned!") + " 🗿"
            update.message.reply_text(message)
        else:
            with app.app_context():
                new_game = create_new_game(url, chat_id, image, name, rank, record)
                send_user_game_info(update, context, user_pref, new_game)
        games(update, context)
    else:
        message = _("Please send game URL:")
        update.message.reply_text(message)


def get_bot_username(context):
    data = context.bot.get_me()
    return data["username"]


def add_footer(context, message):
    username = f"@{get_bot_username(context)}"
    message += "\n\n"
    message += username
    return message


def send_user_game_info(update, context, user_pref, game_object):
    logger.info(
        f"SEND USER GAME INFO: user: {user_pref['chat_id']} username:{user_pref['username']}"
    )
    name = game_object.title
    record = game_object.score
    rank = game_object.rank
    image = game_object.photo_url
    message = user_game_status(user_pref["lang"], name, rank, record)
    new_message = add_footer(context, message)
    context.bot.send_photo(
        photo=image, caption=new_message, parse_mode="html", chat_id=str(update.message.chat_id)
    )


def user_game_status(lang, name, rank, record):
    _ = Translations.load("locales", [lang]).gettext
    game_name = "🎳 " + _("Game name: ")
    user_rank = get_rank_emoji(rank) + _("Your rank: ")
    user_record = "🏆 " + _("Your record: ")
    message = f"{game_name}{name}\n{user_record}{record}\n{user_rank}{rank}"
    return message


def get_rank_emoji(rank):
    emojies = "🥇🥈🥉🎗"
    if rank in range(1, 4):
        return f"{emojies[rank-1]} "
    return f"{emojies[3]} "


def create_new_game(url, chat_id, image, name, rank, record):
    logger.info(f"NEW GAME CREATED: {chat_id}")
    game = Game.query.filter_by(user_id=chat_id, url=url).first()
    if game:
        if record >= game.score:
            game.score = record
            game.rank = rank
            game.title = name
            game.photo_url = image
            db.session.commit()
        new_game = game
    else:
        new_game = Game(
            user_id=chat_id, title=name, url=url, photo_url=image, score=record, rank=rank
        )
        db.session.add(new_game)
        db.session.commit()
    return new_game


def get_all_user_games(chat_id):
    games = Game.query.filter_by(user_id=chat_id).all()
    return games


def get_user_last_url(chat_id):
    user = get_user(chat_id)
    url = user.last_url
    return url


@user_preferences
def set_en(update: Update, context: CallbackContext, user_pref=None) -> None:
    chat_id = user_pref["chat_id"]
    lang = "en_US"
    _ = Translations.load("locales", [lang]).gettext
    change_user_language(chat_id, lang)
    message = _("Language changed to english.")
    keyboard = [[_("فارسی") + " 🇮🇷", _("English") + " 🇺🇸"], [_("Return") + " ↩️"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    update.message.reply_text(message, reply_markup=reply_markup)


@user_preferences
def set_fa(update: Update, context: CallbackContext, user_pref=None) -> None:
    chat_id = user_pref["chat_id"]
    lang = "fa_IR"
    _ = Translations.load("locales", [lang]).gettext
    change_user_language(chat_id, lang)
    message = _("Language changed to persian.")
    keyboard = [[_("فارسی") + " 🇮🇷", _("English") + " 🇺🇸"], [_("Return") + " ↩️"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    update.message.reply_text(message, reply_markup=reply_markup)


def change_user_language(chat_id, lang):
    user = get_user(chat_id)
    user.language = lang
    db.session.add(user)
    db.session.commit()


@user_preferences
def games(update: Update, context: CallbackContext, user_pref=None) -> None:
    _ = Translations.load("locales", user_pref["lang"]).gettext
    user_games = get_all_user_games(user_pref["chat_id"])
    user_game_keyboard = user_games_keyboard(user_games)
    chunked_keys = list(divide_chunks(user_game_keyboard, 4))
    keyboard = deque()
    keyboard.extend(chunked_keys)
    keyboard.extend([[_("New game") + " ➕", _("Remove game") + " ❌"], [_("Return") + " ↩️"]])
    keyboard = list(keyboard)
    message = _("Please select your game:")
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    try:
        update.message.reply_text(message, reply_markup=reply_markup)
    except AttributeError:
        query = update.callback_query
        query.message.reply_text(message, reply_markup=reply_markup)


def user_games_keyboard(games):
    key = []
    for game in games:
        key.append(game.title)
    return list(set(key))


@user_preferences
def view_game(update: Update, context: CallbackContext, user_pref=None) -> None:
    _ = Translations.load("locales", user_pref["lang"]).gettext
    game_object = Game.query.filter_by(
        user_id=user_pref["chat_id"], title=user_pref["message"]
    ).all()[-1]
    send_user_game_info(update, context, user_pref, game_object)
    set_user_last_url(user_pref, game_object)


def set_user_last_url(user_pref, game_object):
    logger.info(
        f"SET USER LAST URL: user: {user_pref['chat_id']} username:{user_pref['username']}"
    )
    with app.app_context():
        new_user = User.query.filter_by(id=user_pref["chat_id"]).first()
        new_user.last_url = game_object.url
        db.session.add(new_user)
        db.session.commit()


@user_preferences
def change_language(update: Update, context: CallbackContext, user_pref=None) -> None:
    _ = Translations.load("locales", user_pref["lang"]).gettext
    keyboard = [[_("فارسی") + " 🇮🇷", _("English") + " 🇺🇸"], [_("Return") + " ↩️"]]
    message = _("Please select your language:")
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    update.message.reply_text(message, reply_markup=reply_markup)


@user_preferences
def main_menu(update: Update, context: CallbackContext, user_pref=None) -> None:
    _ = Translations.load("locales", user_pref["lang"]).gettext
    keyboard = [[_("Settings") + " ⚙️", _("Games") + " 🧩"], [_("Donate us") + " ❤️"]]
    if get_user(user_pref["chat_id"]).is_admin:
        keyboard.append([_("Admin panel") + " 👤"])
    message = _("Please select one item:")
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    update.message.reply_text(message, reply_markup=reply_markup)


@user_preferences
def is_in_user_games(update: Update, context: CallbackContext, user_pref=None) -> None:
    chat_id = user_pref["chat_id"]
    message = user_pref["message"]
    all_games = get_all_user_games(chat_id)
    games_name = user_games_keyboard(all_games)
    if message in games_name:
        return True
    return False


@user_preferences
def contribute(update: Update, context: CallbackContext, user_pref=None) -> None:
    _ = Translations.load("locales", user_pref["lang"]).gettext
    message = _("First if you enjoyed this bot please star 🌟 us on our github: ")
    link = _("Link") + " 🔗"
    github_url = f"<a href='https://github.com/mohamadkhalaj/Gamee-Hacker'>{link}</a>"
    message += github_url + "\n"
    message += _(
        "You can make a pull request and add your features, or help for translating and add your native language to this bot."
    )
    update.message.reply_text(message, parse_mode="html", disable_web_page_preview=True)


@user_preferences
def function_caller(update: Update, context: CallbackContext, user_pref=None) -> None:
    """Echo the user message."""
    _ = Translations.load("locales", user_pref["lang"]).gettext
    user = get_user(user_pref["chat_id"])
    not_in_stack = [set_fa, set_en, add_game]
    functions = {
        _("menu"): main_menu,
        _("Settings") + " ⚙️": settings,
        _("Change language") + " 🗣": change_language,
        _("Games") + " 🧩": games,
        _("فارسی") + " 🇮🇷": set_fa,
        _("English") + " 🇺🇸": set_en,
        _("New game") + " ➕": add_game,
        _("Admin panel") + " 👤": admin_panel,
        _("Contribute") + " 🤝": contribute,
        _("Get users summery") + " 📜": users_summery,
        _("Get full data") + " 🗄": users_full,
        _("Add admin") + " ➕": create_admin,
        _("Remove game") + " ❌": remove_game,
        _("Donate us") + " ❤️": donate_us,
    }
    function = functions.get(update.message.text, None)
    with app.app_context():
        if function:
            logger.info(
                f"{function.__name__}: user: {user_pref['chat_id']} username:{user_pref['username']}"
            )
            if not function in user.return_stack and function not in not_in_stack:
                logger.info(
                    f"APPEND TO STACK: user: {user_pref['chat_id']} username:{user_pref['username']}"
                )
                stack = user.return_stack
                stack.append(function)
                db.session.add(user)
                db.session.commit()
            function(update, context)
        elif update.message.text == _("Return") + " ↩️":
            logger.info(f"RETURN: user: {user_pref['chat_id']} username:{user_pref['username']}")
            try:
                stack = user.return_stack
                stack.pop()
                stack.pop()(update, context)
                db.session.add(user)
                db.session.commit()
            except IndexError:
                main_menu(update, context)
        elif is_url(update.message.text):
            logger.info(f"GAME URL: user: {user_pref['chat_id']} username:{user_pref['username']}")
            get_game_url(update, context)
        elif is_score(update.message.text):
            logger.info(
                f"GAME SCORE: user: {user_pref['chat_id']} username:{user_pref['username']}"
            )
            start_hacking(update, context)
        elif is_in_user_games(update, context):
            logger.info(
                f"VIEW GAME: user: {user_pref['chat_id']} username:{user_pref['username']}"
            )
            view_game(update, context)
        elif check_add_admin_pattern(update.message.text):
            create_admin_telegram(update, context)
        else:
            logger.info(
                f"COMMAND NOT FOUND: user: {user_pref['chat_id']} username:{user_pref['username']}"
            )
            message = f"❌❗️ '{update.message.text}'"
            update.message.reply_text(message)


def get_user_language(chat_id):
    with app.app_context():
        language = User.query.filter_by(id=chat_id).first()
        if language:
            return language.language
        return "en_US"


def get_user(chat_id):
    with app.app_context():
        user = User.query.filter_by(id=chat_id).first()
        return user


@user_preferences
def remove_game(update: Update, context: CallbackContext, user_pref=None) -> None:
    _ = Translations.load("locales", user_pref["lang"]).gettext
    user_games = get_all_user_games(user_pref["chat_id"])
    if user_games:
        user_game_inline_keyboard = create_inline_keyboard_button(user_games)
        keyboard = list(divide_chunks(user_game_inline_keyboard, 4))
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text(_("Please select one item:"), reply_markup=reply_markup)
    else:
        message = _("There is not any games to show.")
        update.message.reply_text(message)


def create_inline_keyboard_button(games):
    key = []
    for game in games:
        temp = InlineKeyboardButton(str(game.title), callback_data=game.id)
        key.append(temp)
    return key


@user_preferences
def call_back(update: Update, context: CallbackContext, user_pref=None) -> None:
    _ = Translations.load("locales", user_pref["lang"]).gettext
    query = update.callback_query
    query.answer()
    game_id = query.data
    with app.app_context():
        game = get_game_by_id(game_id)
        if game:
            game_name = game.title
            db.session.delete(game)
            db.session.commit()
            remove_message = _("removed successfully.")
            query.edit_message_text(text=f"{game_name} {remove_message}")
        else:
            not_found_message = _("not found!")
            query.edit_message_text(text=f"{not_found_message}")
        games(update, context)


def get_game_by_id(id):
    game = Game.query.filter_by(id=id).first()
    if game:
        return game
    return None


def check_user_exists(chat_id):
    with app.app_context():
        user = User.query.filter_by(id=chat_id).first()
        if not user:
            return False
        return True


def create_user(user_pref):
    username = user_pref["username"]
    chat_id = user_pref["chat_id"]
    lang = user_pref["lang"]
    with app.app_context():
        user = User.query.filter_by(id=chat_id).first()
        if not user:
            new_user = User(id=chat_id, username=username, return_stack=[main_menu], language=lang)
            db.session.add(new_user)
            db.session.commit()
            logger.info(
                f"ADDING USER TO DB: user: {user_pref['chat_id']} username:{user_pref['username']} added."
            )
        else:
            logger.info(
                f"ADDING USER TO DB: user: {user_pref['chat_id']} username:{user_pref['username']} already exists."
            )


# Define a few command handlers. These usually take the two arguments update and
# context.
@user_preferences
def start(update: Update, context: CallbackContext, user_pref=None) -> None:
    """Send a message when the command /start is issued."""
    logger.info(f"Bot started by user: {user_pref['chat_id']} username:{user_pref['username']}")
    create_user(user_pref)
    main_menu(update, context)


def main() -> None:
    """Start the bot."""
    # Create the Updater and pass it your bot's token.
    updater = Updater(TELEGRAM_TOKEN)

    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher

    # on different commands - answer in Telegram
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CallbackQueryHandler(call_back))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, function_caller))

    # Start the Bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


def create_super_user():
    user_id = input("Enter telegram numeric ID: ")
    add_admin(user_id)
    exit(0)


def add_admin(user_id):
    with app.app_context():
        user = User.query.filter_by(id=user_id).first()
        _ = Translations.load("locales", get_user_language(user_id)).gettext
        if user:
            if user.is_admin:
                logger.info(f"This user: '{user_id}' already is admin.")
                return _("This user already is admin.")
            else:
                user.is_admin = True
                db.session.add(user)
                db.session.commit()
                logger.info(f'User: "{user_id}" previllage escalated successfully.')
                return _("User previllage escalated successfully.")
        else:
            new_user = User(id=user_id)
            new_user.is_admin = True
            new_user.return_stack = [main_menu]
            new_user.language = "en_US"
            db.session.add(new_user)
            db.session.commit()
            logger.info(f"Superuser: '{user_id}' created successfully.")
            return _("Superuser created successfully.")


if len(sys.argv) == 2 and sys.argv[1] == "createsuperuser":
    create_super_user()

if __name__ == "__main__":
    main()
