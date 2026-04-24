import os
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

print("--- Telegram String Session Generator ---")
API_ID = input("Masukkan API_ID: ")
API_HASH = input("Masukkan API_HASH: ")

with TelegramClient(StringSession(), int(API_ID), API_HASH) as client:
    print("\nBerikut adalah SESSION_STRING Anda. SIMPAN DENGAN AMAN!")
    print("--------------------------------------------------")
    print(client.session.save())
    print("--------------------------------------------------")
    print("\nSalin string di atas dan masukkan ke Environment Variable 'SESSION_STRING' di platform hosting Anda.")
