import asyncio
import logging
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.utils.keyboard import (
    InlineKeyboardBuilder,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram import types
from aiogram.types.input_file import FSInputFile
from aiogram.types import InputFile
from aiogram.filters.command import Command
from aiogram import F
from promptAdapter import process_requests
import aiofiles
import json


# Включаем логирование, чтобы не пропустить важные сообщения
logging.basicConfig(level=logging.INFO)
DEFAULT_API_KEY = "d8a0d470d4abf0a20fa98b289c79116af6cb9c5794a3109931b720455bce28cb"
dp = Dispatcher()

users = {}
audio_keys = {}
video_keys = {}
admins = []
admin_statuses = {}
keys = []


# Класс reqApi с новыми переменными
class reqApi:
    def __init__(self, tgId, prompt):
        self.tgId = tgId
        self.textPrompt = prompt
        self.videoPrompt = [prompt]
        self.audioPrompt = ""
        self.video_header = {"X-API-Key": DEFAULT_API_KEY}
        self.audio_header = {"X-API-Key": DEFAULT_API_KEY}
        self.video_task = ""
        self.audio_task = ""
        self.negative_prompt = ""
        self.duration = 0  # Добавлено: длительность ролика
        self.screen_format = "16:9"  # Добавлено: формат экрана
        self.has_audio = True  # Добавлено: наличие аудио


class video_key:
    def __init__(self, key, c):
        self.key = key
        self.header = {"X-API-Key": key}
        self.operations = c
        self.curr_users = 0

    def to_dict(self):
        return {
            "key": self.key,
            "header": self.header,
            "operations": self.operations,
            "curr_users": self.curr_users,
        }


class audio_key:
    def __init__(self, key, c):
        self.key = key
        self.header = {"X-API-Key": key}
        self.operations = c
        self.curr_users = 0

    def to_dict(self):
        return {
            "key": self.key,
            "header": self.header,
            "operations": self.operations,
            "curr_users": self.curr_users,
        }


class User:
    def __init__(self, tgId):
        self.tgId = tgId
        self.generations = 1
        self.process_video = False
        self.feedback_status = ""
        self.generation_status = ""
        self.feedback_count = 2
        self.req_api_instance = None

    def to_dict(self):
        return {
            "tgId": self.tgId,
            "generations": self.generations,
            "process_video": self.process_video,
            "feedback_status": self.feedback_status,
            "generation_status": self.generation_status,
            "feedback_count": self.feedback_count,
            "req_api_instance": self.req_api_instance,
        }


# Функции для загрузки данных из файлов
def load_data():
    global users, audio_keys, video_keys, admins, keys
    try:
        with open("data.json", "r") as f:
            users_data = json.load(f)
            users = {k: User(**v) for k, v in users_data.items()}
    except FileNotFoundError:
        users = {}
    except TypeError as e:
        users = {}

    try:
        with open("audio_keys.json", "r") as f:
            audio_keys_data = json.load(f)
            audio_keys = {
                k: audio_key(v["key"], v["operations"])
                for k, v in audio_keys_data.items()
            }
    except FileNotFoundError:
        audio_keys = {}
    except TypeError as e:
        audio_keys = {}

    try:
        with open("video_keys.json", "r") as f:
            video_keys_data = json.load(f)
            video_keys = {
                k: video_key(v["key"], v["operations"])
                for k, v in video_keys_data.items()
            }
            keys = [v.key for v in video_keys.values()]
    except FileNotFoundError:
        video_keys = {}
    except TypeError as e:
        video_keys = {}

    try:
        with open("admins.json", "r") as f:
            admins = json.load(f)
    except FileNotFoundError:
        admins = []
    except TypeError as e:
        admins = []


# Функции для сохранения данных в файлы
def save_data(flag):
    if flag:
        with open("data.json", "w") as f:
            json.dump({k: v.to_dict() for k, v in users.items()}, f, indent=4)
    else:
        with open("audio_keys.json", "w") as f:
            json.dump({k: v.to_dict() for k, v in audio_keys.items()}, f, indent=4)

        with open("video_keys.json", "w") as f:
            json.dump({k: v.to_dict() for k, v in video_keys.items()}, f, indent=4)

        with open("admins.json", "w") as f:
            json.dump(admins, f, indent=4)


# Асинхронная функция для регулярного сохранения users раз в час
async def save_users_periodically():
    while True:
        save_data(flag=True)
        await asyncio.sleep(1800)


async def save_admins():
    save_data(flag=False)


async def find_audio_key():
    if not audio_keys:
        return None

    # Найти ключ с минимальным curr_users и максимальным operations
    best_key = min(audio_keys.values(), key=lambda k: (k.curr_users, -k.operations))
    return best_key.key


async def find_video_key():
    if not video_keys:
        return None

    # Найти ключ с минимальным curr_users и максимальным operations
    best_key = min(video_keys.values(), key=lambda k: (k.curr_users, -k.operations))
    return best_key.key


def get_user(tgId):
    if tgId not in users:
        users[tgId] = User(tgId)
    return users[tgId]


def set_user(tgId, user):
    users[tgId] = user


async def handle_video_request(user_id: int, req_api_instance, extend: bool):
    user = get_user(user_id)
    req_api_instance.video_header = video_keys[keys[0]].header
    req_api_instance.audio_header = audio_keys[keys[0]].header
    if req_api_instance:
        result = await process_requests(req_api_instance, extend, "30")
        final_video_path, updated_req = result
        if final_video_path:
            print(final_video_path)
            video = FSInputFile(final_video_path)
            await bot.send_video(user_id, video)
            user.req_api_instance = updated_req if not extend else None
            set_user(user_id, user)
            if extend:
                await bot.send_message(
                    user_id,
                    text="Панель управления",
                    reply_markup=get_start_keyboard(user_id),
                )
            return True
        else:
            return False
    else:
        return None


async def handle_video_request_noExtend(user_id: int, req_api_instance):
    user = get_user(user_id)
    req_api_instance.video_header = video_keys[keys[0]].header
    req_api_instance.audio_header = audio_keys[keys[0]].header
    if req_api_instance:
        result = await process_requests(
            req_api_instance, False, str(req_api_instance.duration)
        )
        final_video_path, updated_req = result
        if final_video_path:
            print(final_video_path)
            video = FSInputFile(final_video_path)
            await bot.send_video(user_id, video)
            user.req_api_instance = updated_req
            set_user(user_id, user)
            await bot.send_message(
                user_id,
                text="Панель управления",
                reply_markup=get_start_keyboard(user_id),
            )
            return True
        else:
            return False
    else:
        return None


async def get_yookassa_payment_url(amount, description, id):
    token = "381764678:TEST:92958"
    shop_id = "Ваш идентификатор магазина ЮКассы"
    url = f"https://api.yookassa.ru/v3/payments"

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    data = {
        "amount": {"value": amount, "currency": "RUB"},
        "payment_method_data": {"type": "bank_card"},
        "confirmation": {
            "type": "redirect",
            "return_url": "https://t.me/kagami_AiBot",
        },
        "description": description,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=data) as response:
            if response.status == 201:
                payment_id = (await response.json())["id"]
                payment_url = (await response.json())["confirmation"][
                    "confirmation_url"
                ]
                await bot.send_message(id, payment_url)
            else:
                await bot.send_message(id, "ОШИБКА")


# <--
# обращение к серверу Юкассы
# ---
# ---
# ---
# Ниже инициализация панелей и кнопки возврата
# -->


def get_admin_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="Узнать ID", callback_data="get_id"))
    builder.row(
        types.InlineKeyboardButton(text="Добавить админа", callback_data="add_admin")
    )
    builder.row(
        types.InlineKeyboardButton(text="Добавить токен", callback_data="add_token")
    )
    return builder.as_markup()


def get_back_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="Назад", callback_data="back_to_admin"))
    return builder.as_markup()


# Обработчик нажатия на кнопку "Добавить токен"
@dp.callback_query(F.data == "add_token")
async def process_add_token(callback_query: types.CallbackQuery):
    admin_statuses[callback_query.from_user.id] = "b"
    await callback_query.message.edit_text(
        "Присылайте токен PyApi", reply_markup=get_back_keyboard()
    )
    await callback_query.answer()


# Обработчик текстового сообщения от пользователя
@dp.callback_query(F.data == "get_id")
async def process_add_token(callback_query: types.CallbackQuery):
    await callback_query.message.answer("Ваш Id - " + str(callback_query.from_user.id))
    await callback_query.answer()


@dp.callback_query(F.data == "add_admin")
async def process_add_token(callback_query: types.CallbackQuery):
    admin_statuses[callback_query.from_user.id] = "a"
    await callback_query.message.edit_text(
        "Присылайте id нового админа", reply_markup=get_back_keyboard()
    )
    await callback_query.answer()


# Обработчик нажатия на кнопку "Назад"
@dp.callback_query(F.data == "back_to_admin")
async def process_back_to_admin(callback_query: types.CallbackQuery):
    await callback_query.message.edit_text(
        "Вы в админ панели", reply_markup=get_admin_keyboard()
    )


#
# обработка админ панели
#
#


def get_start_keyboard(user_id):
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(
            text="Сгенерировать видео", callback_data="generate_video"
        )
    )
    builder.row(
        types.InlineKeyboardButton(
            text="Управление подпиской", callback_data="subscription"
        )
    )
    builder.row(
        types.InlineKeyboardButton(text="Обратная связь", callback_data="feedback")
    )
    return builder.as_markup()


def get_video_options_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(
            text="Продлить", callback_data="approve_extend_video"
        )
    )
    builder.row(
        types.InlineKeyboardButton(
            text="Сгенерировать новое видео", callback_data="approve_generate_new"
        )
    )
    builder.row(
        types.InlineKeyboardButton(text="Назад", callback_data="approve_backToMenu"),
    )
    return builder.as_markup()


def get_subscription_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(
            text="Продлить подписку", callback_data="extend_subscription"
        )
    )
    builder.row(types.InlineKeyboardButton(text="Назад", callback_data="backToStart"))
    return builder.as_markup()


def get_approve_extend_video_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="Продлить видео", callback_data="extend_video")
    )
    builder.row(
        types.InlineKeyboardButton(
            text="Вернуться к выбору опций", callback_data="video_options_keyboard"
        )
    )
    return builder.as_markup()


def get_approve_generate_new_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(
            text="Сгенерировать видео", callback_data="generate_new"
        )
    )
    builder.row(
        types.InlineKeyboardButton(
            text="Вернуться к выбору опций", callback_data="video_options_keyboard"
        )
    )
    return builder.as_markup()


def get_approve_backToMenu_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(
            text="Отменить генерацию видео", callback_data="backToMenu"
        )
    )
    builder.row(
        types.InlineKeyboardButton(
            text="Вернуться к выбору опций", callback_data="video_options_keyboard"
        )
    )
    return builder.as_markup()


async def get_payment_keyboard(id):
    amount = 100
    description = "Оплата за услугу"
    await get_yookassa_payment_url(amount, description, id)
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="ЮКасса", callback_data="u"))
    builder.row(types.InlineKeyboardButton(text="Тон", callback_data="ton"))
    builder.row(
        types.InlineKeyboardButton(text="Назад", callback_data="backToSubscibe")
    )
    return builder.as_markup()


@dp.callback_query(F.data == "backToSubscibe")
async def extend_subscription(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "Сейчас вам доступно", reply_markup=get_subscription_keyboard()
    )
    await callback.answer()


@dp.callback_query(F.data == "backToStart")
async def go_back(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    await callback.message.edit_text(
        "Выберите действие", reply_markup=get_start_keyboard(user_id)
    )
    await callback.answer()


@dp.callback_query(F.data == "backToMenu")
async def go_backToMenu(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    if user.generation_status == "generating":
        await callback.message.edit_text("Генерация отменена")
        await callback.message.answer(
            "Выберите действие", reply_markup=get_start_keyboard(user_id)
        )
    await callback.answer()


# <--
# Инициализация панели кнопок и хендлеров на все кнопки back
# ---
# ---
#

#
# Создание клавиатур и кнопки назад
# -->
#


def get_duration_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="10 секунд", callback_data="duration_10")
    )
    builder.row(
        types.InlineKeyboardButton(text="20 секунд", callback_data="duration_20")
    )
    builder.row(
        types.InlineKeyboardButton(text="30 секунд", callback_data="duration_30")
    )
    builder.row(types.InlineKeyboardButton(text="Назад", callback_data="back_to_start"))
    return builder.as_markup()


def get_format_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="Горизонтальное", callback_data="format_16_9")
    )
    builder.row(
        types.InlineKeyboardButton(text="Вертикальное", callback_data="format_9_16")
    )
    builder.row(types.InlineKeyboardButton(text="1 к 1", callback_data="format_1_1"))
    builder.row(
        types.InlineKeyboardButton(text="Назад", callback_data="back_to_duration")
    )
    return builder.as_markup()


def get_audio_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="Да", callback_data="audio_yes"))
    builder.row(types.InlineKeyboardButton(text="Нет", callback_data="audio_no"))
    builder.row(
        types.InlineKeyboardButton(text="Назад", callback_data="back_to_format")
    )
    return builder.as_markup()


@dp.callback_query(F.data.startswith("back_to_"))
async def go_back(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if callback.data == "back_to_start":
        await callback.message.edit_text(
            "Выберите действие:", reply_markup=get_start_keyboard(user_id)
        )
    elif callback.data == "back_to_duration":
        await callback.message.edit_text(
            "Выбери длительность ролика (учти, что в зависимости от этого время генерации будет различаться)",
            reply_markup=get_duration_keyboard(),
        )
    elif callback.data == "back_to_format":
        await callback.message.edit_text(
            "Круто! В каком формате требуется видео?",
            reply_markup=get_format_keyboard(),
        )
    elif callback.data == "back_to_audio":
        await callback.message.edit_text(
            "Нужно ли аудиосопровождение в ролике?", reply_markup=get_audio_keyboard()
        )
    await callback.answer()


#
# <--
# Создание клавиатур и кнопки назад
#

#
# ---
# Обработка команд на отображение панелей подтверждения создания видео
# -->


@dp.callback_query(F.data == "approve_extend_video")
async def approve_extend_video(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "Желаете продлить видео?", reply_markup=get_approve_extend_video_keyboard()
    )


@dp.callback_query(F.data == "approve_generate_new")
async def approve_generate_new(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "Желаете сгенерировать новое видео?",
        reply_markup=get_approve_generate_new_keyboard(),
    )


@dp.callback_query(F.data == "approve_backToMenu")
async def approve_backToMenu(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "Желаете вернуться в меню?", reply_markup=get_approve_backToMenu_keyboard()
    )


@dp.callback_query(F.data == "video_options_keyboard")
async def set_video_options_keyboard(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "Вы хотите продлить видео или создать новое?",
        reply_markup=get_video_options_keyboard(),
    )


#
#
#
#
#


# Хэндлер на команду /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    if str(user_id) in admins:
        await message.answer("Админ панель", reply_markup=get_admin_keyboard())
    else:
        await message.answer(
            "Панель управления", reply_markup=get_start_keyboard(user_id)
        )


@dp.message(Command("menu"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    if str(user_id) in admins:
        await message.answer("Админ панель", reply_markup=get_admin_keyboard())
    else:
        await message.answer(
            "Панель управления", reply_markup=get_start_keyboard(user_id)
        )


#
#
# Начало промежуточных этапов генерации
# --->
#


@dp.callback_query(F.data == "generate_video")
async def generate_video(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    new_req = reqApi(user_id, "")
    user.req_api_instance = new_req
    set_user(user_id, user)
    await callback.message.edit_text(
        "Выбери длительность ролика (учти, что в зависимости от этого время генерации будет различаться)",
        reply_markup=get_duration_keyboard(),
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("duration_"))
async def set_duration(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    duration = int(callback.data.split("_")[1])
    user = get_user(user_id)

    # Создаем новый запрос reqApi или используем существующий
    if not user.req_api_instance or user.req_api_instance == None:
        user.req_api_instance = reqApi(user_id, "")
    user.req_api_instance.duration = duration

    set_user(user_id, user)
    await callback.message.edit_text(
        "Круто! В каком формате требуется видео?", reply_markup=get_format_keyboard()
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("format_"))
async def set_format(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    format_map = {"format_16_9": "16:9", "format_9_16": "9:16", "format_1_1": "1:1"}
    format_value = format_map[callback.data]
    user = get_user(user_id)
    if not user.req_api_instance or user.req_api_instance == None:
        user.req_api_instance = reqApi(user_id, "")
    user.req_api_instance.screen_format = format_value
    set_user(user_id, user)
    await callback.message.edit_text(
        "Нужно ли аудиосопровождение в ролике?", reply_markup=get_audio_keyboard()
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("audio_"))
async def set_audio(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    if not user.req_api_instance or user.req_api_instance == None:
        user.req_api_instance = reqApi(user_id, "")
    if callback.data == "audio_yes":
        user.req_api_instance.has_audio = True
    elif callback.data == "audio_no":
        user.req_api_instance.has_audio = False

    user.generation_status = "awaiting_video_text"
    set_user(user_id, user)

    await callback.message.edit_text(
        "Отлично! Введи описание ролика. Это может быть просто краткое описание или набор ассоциаций, которые помогут сделать релевантное видео.",
        reply_markup=InlineKeyboardBuilder()
        .row(types.InlineKeyboardButton(text="Назад", callback_data="back_to_audio"))
        .as_markup(),
    )
    await callback.answer()


#
# <---
# Промежуточные этапы генерации завершены
#
#


# Хэндлер на текстовый ввод после generate_video
@dp.message()
async def get_video_text(message: types.Message):
    user_id = message.from_user.id
    user = get_user(user_id)

    if (
        user.generation_status == "awaiting_video_text"
        and user.req_api_instance.duration == 30
    ):
        prompt = message.text
        user.req_api_instance.textPrompt = prompt
        user.req_api_instance.videoPrompt = [prompt]
        result = await handle_video_request(user_id, user.req_api_instance, False)
        user.generation_status = "generating"
        await message.answer("Есть! Теперь ждём получившийся ролик!")
        set_user(user_id, user)
        if result is True:
            await message.answer(
                "Вы хотите продлить видео или создать новое?",
                reply_markup=get_video_options_keyboard(),
            )
    elif user.generation_status == "awaiting_video_text":
        prompt = message.text
        user.req_api_instance.textPrompt = prompt
        user.req_api_instance.videoPrompt = [prompt]
        await message.answer("Есть! Теперь ждём получившийся ролик!")
        result = await handle_video_request_noExtend(user_id, user.req_api_instance)
        set_user(user_id, user)
    elif user.feedback_status == "awaiting_feedback" and user.feedback_count > 0:
        feedback_text = message.text
        # Здесь нужно сохранить отзыв в массив
        user.feedback_status = ""
        user.feedback_count = user.feedback_count - 1
        set_user(user_id, user)
        await message.answer("Спасибо за отзыв!")
    elif str(message.from_user.id) in admins:
        if admin_statuses[message.from_user.id] == "b":
            user_key = message.text
            video_keys[user_key] = video_key(user_key, 0)
            audio_keys[user_key] = audio_key(user_key, 0)
            keys.append(user_key)
            admin_statuses[message.from_user.id] = ""
            save_data(False)
            await message.answer("Админ панель:", reply_markup=get_admin_keyboard())
        elif admin_statuses[message.from_user.id] == "a":
            new_admin_id = message.text
            admins.append(new_admin_id)
            admin_statuses[message.from_user.id] = ""
            save_data(False)
            await message.answer("Админ панель:", reply_markup=get_admin_keyboard())


# Хэндлер на колбэк subscription
@dp.callback_query(F.data == "subscription")
async def subscription(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "Сейчас вам доступно", reply_markup=get_subscription_keyboard()
    )
    await callback.answer()


# Хэндлер на колбэк extend_subscription
@dp.callback_query(F.data == "extend_subscription")
async def extend_subscription(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "Оплата", reply_markup=await get_payment_keyboard(callback.from_user.id)
    )
    await callback.answer()


# Хэндлер на колбэк feedback
@dp.callback_query(F.data == "feedback")
async def feedback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    user.feedback_status = "awaiting_feedback"
    set_user(user_id, user)
    await callback.message.answer("Напишите текст отзыва")
    await callback.answer()


# Хэндлер на колбэк extend_subscription


@dp.callback_query(F.data == "extend_video")
async def extend_video(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    await callback.message.edit_text(
        "Видео генерируется, это может занять какое-то время"
    )
    await callback.answer()
    if user.generation_status == "generating":
        result = await handle_video_request(user_id, user.req_api_instance, True)
        if result is True:
            user.generation_status = " "
            set_user(user_id, user)


@dp.callback_query(F.data == "generate_new")
async def generate_new(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    await callback.message.edit_text(
        "Видео генерируется, это может занять какое-то время"
    )
    await callback.answer()
    if user.req_api_instance and user.generation_status == "generating":
        prompt = user.req_api_instance.videoPrompt[0]
        user.req_api_instance.videoPrompt[0] = prompt
        user.req_api_instance.textPrompt = prompt
        result = await handle_video_request(user_id, user.req_api_instance, False)

        if result is True:
            await callback.message.answer(
                "Новое видео создано!", reply_markup=get_video_options_keyboard()
            )
        elif result is False:
            await callback.message.answer("Ошибка при создании нового видео.")
    else:
        await callback.message.answer("Нет активной заявки на видео.")


async def main():
    load_data()  # Предзагрузка данных при старте программы

    # Инициализация бота и диспетчера (dp)
    await dp.start_polling(bot)
    # Запуск задачи по сохранению данных users раз в час
    asyncio.create_task(save_users_periodically())


if __name__ == "__main__":

    asyncio.run(main())
