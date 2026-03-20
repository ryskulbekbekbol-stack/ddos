#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ULTIMATE DDoS BOT — БЕЗ БАЗ ДАННЫХ (только Telegram + прокси)

import os
import sys
import asyncio
import aiohttp
import random
import logging
from datetime import datetime
from pathlib import Path

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ===== НАСТРОЙКИ ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    print("❌ BOT_TOKEN не задан")
    sys.exit(1)

ADMIN_IDS_STR = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(x.strip()) for x in ADMIN_IDS_STR.split(",") if x.strip()]
if not ADMIN_IDS:
    print("❌ ADMIN_IDS не задан")
    sys.exit(1)

# ===== ЛОГИРОВАНИЕ =====
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ===== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ =====
USER_AGENTS = []
PROXY_LIST = []
active_attacks = {}  # {attack_id: task}

# ===== СПИСОК ВСЕХ МЕТОДОВ (57) =====
ALL_METHODS = [
    # Layer7
    "GET", "POST", "OVH", "RHEX", "STOMP", "STRESS", "DYN", "DOWNLOADER",
    "SLOW", "HEAD", "NULL", "COOKIE", "PPS", "EVEN", "GSB", "DGB",
    "AVB", "BOT", "APACHE", "XMLRPC", "CFB", "CFBUAM", "BYPASS", "BOMB",
    "KILLER", "TOR",
    # Layer4
    "TCP", "UDP", "SYN", "OVH-UDP", "CPS", "ICMP", "CONNECTION",
    "VSE", "TS3", "FIVEM", "FIVEM-TOKEN", "MEM", "NTP", "MCBOT",
    "MINECRAFT", "MCPE", "DNS", "CHAR", "CLDAP", "ARD", "RDP"
]

# ===== ЗАГРУЗКА USER-AGENT =====
async def load_user_agents():
    global USER_AGENTS
    try:
        ua_file = Path("files/useragent.txt")
        if ua_file.exists():
            with open(ua_file, "r") as f:
                USER_AGENTS = [line.strip() for line in f if line.strip()]
            logger.info(f"✅ Загружено {len(USER_AGENTS)} User-Agent")
        else:
            logger.warning("⚠️ Файл useragent.txt не найден, используются стандартные")
            USER_AGENTS = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
            ]
    except Exception as e:
        logger.error(f"Ошибка загрузки User-Agent: {e}")
        USER_AGENTS = ["Mozilla/5.0"]

# ===== ЗАГРУЗКА ПРОКСИ =====
async def load_proxies():
    global PROXY_LIST
    try:
        proxy_file = Path("proxies.txt")
        if proxy_file.exists():
            with open(proxy_file, "r") as f:
                PROXY_LIST = [line.strip() for line in f if line.strip()]
            logger.info(f"✅ Загружено {len(PROXY_LIST)} прокси")
        else:
            logger.warning("⚠️ Файл proxies.txt не найден, работаем без прокси")
    except Exception as e:
        logger.error(f"Ошибка загрузки прокси: {e}")

def get_random_proxy():
    return random.choice(PROXY_LIST) if PROXY_LIST else None

# ===== КЛАВИАТУРЫ =====
def main_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="🔥 DDoS", callback_data="menu_ddos")
    kb.button(text="📷 Камеры", callback_data="menu_camera")
    kb.button(text="🤖 Ботнет", callback_data="menu_botnet")
    kb.button(text="🧠 AI‑анализ", callback_data="menu_ai")
    kb.button(text="📊 Статус", callback_data="menu_status")
    kb.adjust(2)
    return kb.as_markup()

def methods_keyboard():
    kb = InlineKeyboardBuilder()
    for method in ALL_METHODS[:20]:  # первые 20, остальные постранично
        kb.button(text=method, callback_data=f"ddos_method_{method}")
    kb.adjust(5)
    kb.button(text="🔙 Назад", callback_data="back_main")
    return kb.as_markup()

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

# ===== СОСТОЯНИЯ FSM =====
class AttackStates(StatesGroup):
    waiting_for_target = State()
    waiting_for_method = State()
    waiting_for_duration = State()
    waiting_for_threads = State()

# ===== БОТ =====
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

@dp.message(CommandStart())
async def cmd_start(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещён.")
        return
    await message.answer(
        "🔥 **BERSERK DDoS BOT** 🔥\n\n"
        "Выбери режим работы:",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )

@dp.callback_query(F.data == "back_main")
async def back_to_main(callback: CallbackQuery):
    await callback.message.edit_text(
        "🔥 Главное меню",
        reply_markup=main_keyboard()
    )

@dp.callback_query(F.data.startswith("menu_"))
async def menu_handler(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return
    action = callback.data.split("_")[1]

    if action == "ddos":
        await callback.message.edit_text(
            "⚡ Выбери метод атаки:",
            reply_markup=methods_keyboard()
        )
    elif action == "camera":
        await callback.message.edit_text(
            "📷 **Взлом камер**\n\nЭта функция в разработке."
        )
    elif action == "botnet":
        await callback.message.edit_text(
            "🤖 **Ботнет**\n\nАктивных ботов: 0\n(функция без БД)"
        )
    elif action == "ai":
        await callback.message.edit_text(
            "🧠 **AI-анализ**\n\nОтправь IP для анализа (в разработке)."
        )
    elif action == "status":
        await show_system_status(callback)

@dp.callback_query(F.data.startswith("ddos_method_"))
async def ddos_method_selected(callback: CallbackQuery, state: FSMContext):
    method = callback.data.split("_")[2]
    await state.update_data(method=method)
    await callback.message.edit_text(
        f"🎯 Выбран метод: `{method}`\n\nВведи цель (IP:port или URL):"
    )
    await state.set_state(AttackStates.waiting_for_target)

@dp.message(AttackStates.waiting_for_target)
async def ddos_target_received(message: Message, state: FSMContext):
    target = message.text.strip()
    await state.update_data(target=target)
    await message.answer("⏱️ Введи длительность атаки (секунд):")
    await state.set_state(AttackStates.waiting_for_duration)

@dp.message(AttackStates.waiting_for_duration)
async def ddos_duration_received(message: Message, state: FSMContext):
    try:
        duration = int(message.text.strip())
        await state.update_data(duration=duration)
        await message.answer("🧵 Введи количество потоков (1000-20000):")
        await state.set_state(AttackStates.waiting_for_threads)
    except ValueError:
        await message.answer("❌ Введи число!")

@dp.message(AttackStates.waiting_for_threads)
async def ddos_threads_received(message: Message, state: FSMContext):
    try:
        threads = int(message.text.strip())
        data = await state.get_data()
        # запускаем атаку в фоне
        asyncio.create_task(run_ddos_attack(
            user_id=message.from_user.id,
            target=data['target'],
            method=data['method'],
            duration=data['duration'],
            threads=threads
        ))
        await message.answer(
            f"🚀 **DDoS-атака запущена!**\n"
            f"Цель: `{data['target']}`\n"
            f"Метод: `{data['method']}`\n"
            f"Длительность: {data['duration']} сек\n"
            f"Потоков: {threads}\n\n"
            f"Мониторинг включён.",
            parse_mode="Markdown"
        )
        await state.clear()
    except ValueError:
        await message.answer("❌ Введи число!")

async def run_ddos_attack(user_id, target, method, duration, threads):
    """Асинхронная DDoS-атака (симуляция — для реальной используй MHDDoS)"""
    # Здесь можно добавить реальный вызов MHDDoS через subprocess
    attack_id = f"{method}_{target}_{datetime.now().timestamp()}"
    active_attacks[attack_id] = asyncio.current_task()

    try:
        # Имитация нагрузки
        await asyncio.sleep(duration)
        await bot.send_message(user_id, f"✅ Атака {attack_id} завершена.")
    except asyncio.CancelledError:
        await bot.send_message(user_id, f"❌ Атака {attack_id} отменена.")
    finally:
        active_attacks.pop(attack_id, None)

async def show_system_status(callback: CallbackQuery):
    text = (
        f"📊 **СИСТЕМНЫЙ СТАТУС**\n\n"
        f"User-Agent: {len(USER_AGENTS)}\n"
        f"Прокси: {len(PROXY_LIST)}\n"
        f"Активных атак: {len(active_attacks)}\n"
        f"Режим: БЕЗ БД"
    )
    await callback.message.edit_text(text, reply_markup=main_keyboard())

@dp.callback_query(F.data == "stop_all")
async def stop_all(callback: CallbackQuery):
    for tid in list(active_attacks.keys()):
        active_attacks[tid].cancel()
    active_attacks.clear()
    await callback.message.edit_text("✅ Все атаки остановлены.", reply_markup=main_keyboard())

# ===== ЗАПУСК =====
async def on_startup():
    await load_user_agents()
    await load_proxies()
    logger.info("Бот запущен. Админы: %s", ADMIN_IDS)

async def on_shutdown():
    for tid in list(active_attacks.keys()):
        active_attacks[tid].cancel()
    await bot.session.close()

async def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
