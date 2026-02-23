import os
import telebot
import random
import threading
from datetime import datetime, timedelta

bot = telebot.TeleBot(os.environ.get('BOT_TOKEN'))

active_games = {}

def get_display_name(user):
    if user.username:
        return f"@{user.username}"
    full = user.first_name
    if user.last_name:
        full += f" {user.last_name}"
    return full

def is_admin(chat_id, user_id):
    try:
        admins = bot.get_chat_administrators(chat_id)
        return any(admin.user.id == user_id for admin in admins)
    except:
        return False

def update_registration_message(chat_id):
    if chat_id not in active_games:
        return
    game = active_games[chat_id]
    players_list = "\n".join([f"▫️ {p['name']}" for p in game['players'].values()]) or "▫️ Пока никого"
    time_left = max(0, (game['expires_at'] - datetime.now()).seconds)
    text = (
        f"🎮 **Начался набор в игру UNO!**\n\n"
        f"🃏 Нажми кнопку ниже, чтобы присоединиться.\n\n"
        f"**Зарегистрировались:**\n{players_list}\n\n"
        f"⏳ Осталось: {time_left} сек."
    )
    try:
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=game['reg_message_id'],
            text=text,
            parse_mode="Markdown",
            reply_markup=telebot.types.InlineKeyboardMarkup().add(
                telebot.types.InlineKeyboardButton(
                    "🃏 Присоединиться!",
                    url=f"https://t.me/{bot.get_me().username}?start=join_{chat_id}"
                )
            )
        )
    except:
        pass

def cancel_registration(chat_id):
    if chat_id not in active_games:
        return
    game = active_games[chat_id]
    if game['timer']:
        game['timer'].cancel()
    bot.send_message(chat_id, "❌ Недостаточно игроков. Набор отменён.")
    try:
        bot.delete_message(chat_id, game['reg_message_id'])
    except:
        pass
    del active_games[chat_id]

def start_game(chat_id):
    if chat_id not in active_games:
        return
    game = active_games[chat_id]
    if len(game['players']) < 2:
        cancel_registration(chat_id)
        return
    try:
        bot.delete_message(chat_id, game['reg_message_id'])
        if game.get('cmd_message_id'):
            bot.delete_message(chat_id, game['cmd_message_id'])
    except:
        pass
    colors = ['🔴', '🟡', '🔵', '🟢']
    deck = [f"{c} {n}" for c in colors for n in range(0, 10) for _ in range(2 if n != 0 else 1)]
    random.shuffle(deck)
    for uid in game['players']:
        game['players'][uid]['hand'] = [deck.pop() for _ in range(7)]
    players_list = list(game['players'].keys())
    random.shuffle(players_list)
    game['queue'] = players_list
    game['current_turn'] = 0
    game['top_card'] = deck.pop()
    game['deck'] = deck
    game['discard'] = []
    game['status'] = 'playing'
    start_msg = (
        "🎮 **Набор окончен! Игра началась!**\n\n"
        f"🃏 Верхняя карта: {game['top_card']}\n"
        f"👤 Первым ходит: {game['players'][players_list[0]]['name']}\n\n"
        "📨 Ваши карты — в личном чате со мной (/hand)."
    )
    bot.send_message(chat_id, start_msg, parse_mode="Markdown")

def finish_registration_by_timer(chat_id):
    if chat_id in active_games and active_games[chat_id]['status'] == 'registration':
        start_game(chat_id)

@bot.message_handler(content_types=['new_chat_members'])
def welcome_in_group(message):
    for member in message.new_chat_members:
        if member.id == bot.get_me().id:
            text = (
                "🎉 Всем привет! Я — бот-ведущий UNO!\n\n"
                "📌 Чтобы я мог полноценно работать, **назначь меня администратором**.\n"
                "После этого ты сможешь запускать игры и управлять настройками.\n\n"
                "🃏 **Основные команды в группе:**\n"
                "/uno_start — начать регистрацию на новую игру\n"
                "/uno_extend  — продлить регистрацию на игру\n"
                "/uno_rules — правила игры\n"
                "/uno_stop — отменить регистрацию и начать игру\n"
                "/uno_remove — отменить игру\n\n"
                "👇 Жми кнопку, чтобы сразу начать!"
            )
            markup = telebot.types.InlineKeyboardMarkup()
            markup.add(telebot.types.InlineKeyboardButton("🚀 Начать игру", callback_data="group_start"))
            bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=markup)
            break

@bot.callback_query_handler(func=lambda call: call.data == "group_start")
def group_start_callback(call):
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, "/uno_start")

@bot.message_handler(commands=['uno_start'])
def uno_start(message):
    chat_id = message.chat.id
    if message.chat.type not in ['group', 'supergroup']:
        bot.reply_to(message, "❌ Эта команда работает только в групповых чатах.")
        return
    if chat_id in active_games:
        bot.reply_to(message, "⚠️ В этом чате уже идёт игра или набор.")
        return
    game = {
        'chat_id': chat_id,
        'players': {},
        'status': 'registration',
        'reg_message_id': None,
        'cmd_message_id': message.message_id,
        'expires_at': datetime.now() + timedelta(seconds=60),
        'timer': None
    }
    active_games[chat_id] = game
    text = (
        "🎮 **Начался набор в игру UNO!**\n\n"
        "🃏 Нажми кнопку ниже, чтобы присоединиться.\n\n"
        "**Зарегистрировались:**\n"
        "▫️ Пока никого"
    )
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton(
        "🃏 Присоединиться!",
        url=f"https://t.me/{bot.get_me().username}?start=join_{chat_id}"
    ))
    sent = bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=markup)
    game['reg_message_id'] = sent.message_id
    timer = threading.Timer(60.0, finish_registration_by_timer, args=[chat_id])
    timer.start()
    game['timer'] = timer

@bot.message_handler(commands=['uno_extend'])
def uno_extend(message):
    chat_id = message.chat.id
    if message.chat.type not in ['group', 'supergroup']:
        bot.reply_to(message, "❌ Эта команда работает только в группах.")
        return
    if chat_id not in active_games or active_games[chat_id]['status'] != 'registration':
        bot.reply_to(message, "❌ Сейчас нет активного набора.")
        return
    game = active_games[chat_id]
    game['expires_at'] += timedelta(seconds=30)
    if game['timer']:
        game['timer'].cancel()
    timer = threading.Timer((game['expires_at'] - datetime.now()).seconds, finish_registration_by_timer, args=[chat_id])
    timer.start()
    game['timer'] = timer
    bot.reply_to(message, "⏳ Регистрация продлена! +30 секунд к регистрации!")
    update_registration_message(chat_id)

@bot.message_handler(commands=['uno_stop'])
def uno_stop(message):
    chat_id = message.chat.id
    if message.chat.type not in ['group', 'supergroup']:
        bot.reply_to(message, "❌ Эта команда работает только в группах.")
        return
    if chat_id not in active_games or active_games[chat_id]['status'] != 'registration':
        bot.reply_to(message, "❌ Нет активной регистрации.")
        return
    if active_games[chat_id]['timer']:
        active_games[chat_id]['timer'].cancel()
    bot.reply_to(message, "🛑 Регистрация остановлена. Игра начинается!")
    start_game(chat_id)

@bot.message_handler(commands=['uno_remove'])
def uno_remove(message):
    chat_id = message.chat.id
    if message.chat.type not in ['group', 'supergroup']:
        bot.reply_to(message, "❌ Эта команда работает только в группах.")
        return
    if chat_id not in active_games:
        bot.reply_to(message, "❌ Нет активной игры или регистрации.")
        return
    game = active_games[chat_id]
    if game['timer']:
        game['timer'].cancel()
    try:
        bot.delete_message(chat_id, game['reg_message_id'])
    except:
        pass
    del active_games[chat_id]
    bot.reply_to(message, "❌ Игра отменена.")

@bot.message_handler(commands=['uno_rules'])
def uno_rules(message):
    bot.reply_to(message, "📚 Правила UNO появятся здесь позже.")

@bot.message_handler(commands=['start'])
def start_command(message):
    text = message.text
    if ' ' in text:
        param = text.split(' ', 1)[1]
        if param.startswith('join_'):
            try:
                chat_id = int(param.split('_')[1])
            except:
                bot.reply_to(message, "❌ Неверная ссылка.")
                return
            if chat_id not in active_games or active_games[chat_id]['status'] != 'registration':
                bot.reply_to(message, "❌ Набор в эту игру уже завершён или не существует.")
                return
            game = active_games[chat_id]
            user_id = message.from_user.id
            if user_id in game['players']:
                bot.reply_to(message, "⚠️ Вы уже зарегистрированы в этой игре.")
                return
            name = get_display_name(message.from_user)
            admin_flag = is_admin(chat_id, user_id)
            game['players'][user_id] = {'name': name, 'hand': [], 'is_admin': admin_flag}
            bot.reply_to(message, f"✅ Вы успешно присоединились к игре в чате «{bot.get_chat(chat_id).title}»!")
            update_registration_message(chat_id)
            return
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        telebot.types.KeyboardButton("🎲 Добавить бота в чат"),
        telebot.types.KeyboardButton("✈️ Официальный канал"),
        telebot.types.KeyboardButton("💸 Поддержать автора"),
        telebot.types.KeyboardButton("🪪 Профиль"),
        telebot.types.KeyboardButton("🃏 Карты")
    )
    bot.send_message(message.chat.id, "Привет, я бот ведущий в игре UNO! 🃏", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "🎲 Добавить бота в чат")
def add_to_chat(message):
    bot_username = bot.get_me().username
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("➕ Выбрать чат для добавления", url=f"https://t.me/{bot_username}?startgroup=true"))
    bot.send_message(message.chat.id, "Нажмите кнопку ниже чтобы добавить бота в чат:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "✈️ Официальный канал")
def channel(message):
    bot.send_message(message.chat.id, "https://t.me/unodeveloper")

@bot.message_handler(func=lambda m: m.text == "💸 Поддержать автора")
def support(message):
    bot.send_message(message.chat.id, "https://dalink.to/unogamemoneta")

@bot.message_handler(func=lambda m: m.text == "🪪 Профиль")
def profile(message):
    user = message.from_user
    if user.username:
        name_display = f"@{user.username}"
    else:
        name_display = user.first_name
        if user.last_name:
            name_display += f" {user.last_name}"
    text = (f"👤 {name_display}\n\n"
            f"💵 Деньги: none\n"
            f"🦆 Утки: none\n"
            f"🃏 Купленных спец-карт: none\n"
            f"✅ Проверок карт: none")
    markup = telebot.types.InlineKeyboardMarkup(row_width=3)
    markup.add(
        telebot.types.InlineKeyboardButton("🛒 Магазин", callback_data="shop"),
        telebot.types.InlineKeyboardButton("💵 Купить", callback_data="buy_money"),
        telebot.types.InlineKeyboardButton("🦆 Купить", callback_data="buy_ducks")
    )
    bot.send_message(message.chat.id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "shop")
def shop_callback(call):
    bot.answer_callback_query(call.id)
    text = ("🛒 <b>Магазин</b>\n\n"
            "▫️ <b>🃏 Спец-карта</b> — поможет, если не хотите всю игру играть скучными картами!\n"
            "▫️ <b>✅ Проверка карт соперника</b> — узнайте, что использовать против противника!\n\n"
            "<i>Выберите товар:</i>")
    markup = telebot.types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        telebot.types.InlineKeyboardButton("🃏 Спец-карта — 200 💵", callback_data="buy_special_card"),
        telebot.types.InlineKeyboardButton("✅ Проверка карт — 1 🦆", callback_data="buy_check")
    )
    bot.send_message(call.message.chat.id, text, parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "buy_special_card")
def buy_special_card(call):
    bot.answer_callback_query(call.id, "❌ Недостаточно средств.", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == "buy_check")
def buy_check(call):
    bot.answer_callback_query(call.id, "❌ Недостаточно средств.", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == "buy_money")
def buy_money(call):
    bot.answer_callback_query(call.id, "❌ Недостаточно средств для обмена!", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == "buy_ducks")
def buy_ducks(call):
    text = ("🦆 <b>Покупка уток</b>\n\n"
            "Какое количество уток вы хотите приобрести?\n"
            "Оплата может быть произведена только в <b>звёздах Telegram</b> ⭐\n\n"
            "test1 🦆 — 1 ⭐\n"
            "1 🦆 = 50 ⭐\n"
            "5 🦆 = 200 ⭐\n"
            "10 🦆 = 400 ⭐\n"
            "15 🦆 = 700 ⭐\n"
            "30 🦆 = 1400 ⭐\n"
            "50 🦆 = 2300 ⭐\n\n"
            "<i>Платёжная система в разработке. Скоро здесь можно будет купить уток!</i>")
    bot.send_message(call.message.chat.id, text, parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "🃏 Карты")
def cards_menu(message):
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        telebot.types.InlineKeyboardButton("🔴 Красные", callback_data="cards_red"),
        telebot.types.InlineKeyboardButton("🟡 Жёлтые", callback_data="cards_yellow"),
        telebot.types.InlineKeyboardButton("🔵 Синие", callback_data="cards_blue"),
        telebot.types.InlineKeyboardButton("🟢 Зелёные", callback_data="cards_green"),
        telebot.types.InlineKeyboardButton("⚫ Специальные", callback_data="cards_special")
    )
    bot.send_message(message.chat.id, "🃏 <b>Карты UNO</b>\n\nВыберите цвет или категорию:", 
                     parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('cards_'))
def cards_callback(call):
    category = call.data.split('_')[1]
    if category == "red":
        text = ("🔴 <b>Красные карты</b>\n\n"
                "▫️ <b>Красная карта (0–9)</b> — обычная карта без особых преимуществ.\n"
                "▫️ <b>Красный доп. ход</b> — вы можете поставить ещё одну карту того же цвета.\n"
                "▫️ <b>Красный пропуск хода</b> — следующий игрок пропускает ход, а игрок после него должен положить карту того же цвета.")
    elif category == "yellow":
        text = ("🟡 <b>Жёлтые карты</b>\n\n"
                "▫️ <b>Жёлтая карта (0–9)</b> — обычная карта без особых преимуществ.\n"
                "▫️ <b>Жёлтый доп. ход</b> — вы можете поставить ещё одну карту того же цвета.\n"
                "▫️ <b>Жёлтый пропуск хода</b> — следующий игрок пропускает ход, а игрок после него должен положить карту того же цвета.")
    elif category == "blue":
        text = ("🔵 <b>Синие карты</b>\n\n"
                "▫️ <b>Синяя карта (0–9)</b> — обычная карта без особых преимуществ.\n"
                "▫️ <b>Синий доп. ход</b> — вы можете поставить ещё одну карту того же цвета.\n"
                "▫️ <b>Синий пропуск хода</b> — следующий игрок пропускает ход, а игрок после него должен положить карту того же цвета.")
    elif category == "green":
        text = ("🟢 <b>Зелёные карты</b>\n\n"
                "▫️ <b>Зелёная карта (0–9)</b> — обычная карта без особых преимуществ.\n"
                "▫️ <b>Зелёный доп. ход</b> — вы можете поставить ещё одну карту того же цвета.\n"
                "▫️ <b>Зелёный пропуск хода</b> — следующий игрок пропускает ход, а игрок после него должен положить карту того же цвета.")
    elif category == "special":
        text = ("⚫ <b>Специальные карты</b>\n\n"
                "▫️ <b>Заказ цвета</b> — вы выбираете следующий цвет.\n"
                "▫️ <b>Заказ цвета +4</b> — вы выбираете цвет, следующий игрок берёт 4 карты и пропускает ход.\n\n"
                "<i>Другие специальные карты появятся в будущем.</i>")
    else:
        return
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, text, parse_mode="HTML")

@bot.message_handler(func=lambda m: m.chat.type in ['group', 'supergroup'])
def delete_non_player_messages(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    if chat_id not in active_games:
        return
    game = active_games[chat_id]
    if game['status'] != 'playing':
        return
    if user_id in game['players']:
        return
    if message.text and message.text.startswith('!'):
        if is_admin(chat_id, user_id):
            return
        else:
            try:
                bot.delete_message(chat_id, message.message_id)
            except:
                pass
            return
    try:
        bot.delete_message(chat_id, message.message_id)
    except:
        pass

print("✅ Бот запущен! Иди в Telegram и пиши /start")
bot.polling(none_stop=True)
