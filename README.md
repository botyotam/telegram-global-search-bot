# Base Chain Token Monitor Bot

Telegram Bot untuk memantau token baru di Base Chain (Bankr, Clanker, Virtuals Protocol).

## Fitur
- **Deteksi Otomatis**: Mendeteksi Contract Address (CA) atau link DexScreener/GeckoTerminal tanpa perintah.
- **Info Lengkap**: Harga, Market Cap, ATH, Liquidity, Volume, Social Media, dll.
- **Statistik Grup**: Melacak kenaikan (PnL) dan pengirim pertama (First Sharer) di grup.
- **Platform**: Mendukung identifikasi token dari Bankr, Clanker, dan Virtuals.

## Cara Install & Jalankan

1. Clone repository ini.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy `.env.example` ke `.env` dan isi `BOT_TOKEN`.
4. Jalankan bot:
   ```bash
   python main.py
   ```

## Deploy ke Railway
1. Push kode ke GitHub.
2. Hubungkan repository ke Railway.
3. Tambahkan Variable `BOT_TOKEN` di Railway Dashboard.
4. Railway akan otomatis menjalankan bot menggunakan `Procfile`.

## Spesifikasi Teknis
- Bahasa: Python 3.10+
- Library: `python-telegram-bot` v20+, `httpx`, `aiosqlite`, `web3`.
- Database: SQLite (local file).
