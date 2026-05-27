import os
import re
import time
import logging
import asyncio
import humanize
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

from database import Database
from api_client import APIClient
from blockchain import BlockchainClient

load_dotenv()

# Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Config
BOT_TOKEN = os.getenv("BOT_TOKEN")
db = Database()
api = APIClient()
bc = BlockchainClient()

# Regex for CA and Links
CA_PATTERN = r"0x[a-fA-F0-9]{40}"
DEX_PATTERN = r"dexscreener\.com/base/(0x[a-fA-F0-9]{40})"
GECKO_PATTERN = r"geckoterminal\.com/base/pools/(0x[a-fA-F0-9]{40})"

def format_duration(timestamp):
    delta = datetime.now() - datetime.fromtimestamp(timestamp)
    return humanize.naturaltime(delta)

async def get_token_info_message(ca, chat_id, user):
    dex_data = await api.get_dex_data(ca)
    if not dex_data:
        return None, None

    platform, platform_data = await api.identify_platform(ca)
    
    # DB Operations
    existing_token = await db.get_token(ca, chat_id)
    current_price = float(dex_data.get("priceUsd", 0))
    current_mc = float(dex_data.get("fdv", 0))
    
    if not existing_token:
        await db.save_token(ca, platform, current_price, current_mc, user.id, user.full_name, chat_id)
        existing_token = await db.get_token(ca, chat_id)
        is_first_share = True
    else:
        await db.update_ath(ca, current_mc)
        existing_token = await db.get_token(ca, chat_id)
        is_first_share = False

    # Extract Data
    name = dex_data.get("baseToken", {}).get("name", "N/A")
    symbol = dex_data.get("baseToken", {}).get("symbol", "N/A")
    liq_usd = dex_data.get("liquidity", {}).get("usd", 0)
    vol_24h = dex_data.get("volume", {}).get("h24", 0)
    change_1h = dex_data.get("priceChange", {}).get("h1", 0)
    change_24h = dex_data.get("priceChange", {}).get("h24", 0)
    
    ath_mc = existing_token[3]
    first_price = existing_token[2]
    first_sharer_name = existing_token[6]
    first_share_time = existing_token[7]
    
    # Stats
    multiplier = int(current_price / first_price) if first_price > 0 else 1
    pnl_percent = ((current_price - first_price) / first_price) * 100 if first_price > 0 else 0
    pnl_str = f"(+{pnl_percent:.2f}%)" if pnl_percent >= 0 else f"({pnl_percent:.2f}%)"

    # Socials
    links = dex_data.get("info", {}).get("websites", []) + dex_data.get("info", {}).get("socials", [])
    social_str = ""
    for link in links:
        label = link.get("type", "Link").capitalize()
        social_str += f"[{label}]({link.get('url')}) "

    # Platform Emoji
    platform_emoji = "🏦" if platform == "Bankr" else ("🤖" if platform == "Clanker" else "🌐")
    
    # Message Construction
    text = (
        f"{platform_emoji} **{platform} Protocol**\n\n"
        f"**{name} ({symbol})**\n"
        f"`{ca}`\n\n"
        f"💰 **Harga**: ${current_price:.8f}\n"
        f"📊 **MC**: ${humanize.intword(current_mc)} (ATH: ${humanize.intword(ath_mc)})\n"
        f"💧 **Liquidity**: ${humanize.intword(liq_usd)}\n"
        f"📈 **Vol 24h**: ${humanize.intword(vol_24h)}\n"
        f"🕒 **Change**: 1h: {change_1h}% | 24h: {change_24h}%\n\n"
        f"🔗 **Socials**: {social_str if social_str else 'N/A'}\n\n"
        f"👤 **First Sharer**: {first_sharer_name}\n"
        f"📅 **Shared**: {format_duration(first_share_time)}\n"
        f"📈 **PnL**: x{multiplier} {pnl_str}\n"
    )
    
    if is_first_share:
        text += "\n✨ *Pertama kali di-share di grup ini!*"

    # Buttons
    keyboard = [
        [
            InlineKeyboardButton("DexScreener", url=f"https://dexscreener.com/base/{ca}"),
            InlineKeyboardButton("Basescan", url=f"https://basescan.org/token/{ca}"),
            InlineKeyboardButton("Buy", url=f"https://app.uniswap.org/#/swap?outputCurrency={ca}&chain=base")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    return text, reply_markup

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text
    cas = re.findall(CA_PATTERN, text)
    
    # Also check for links
    dex_links = re.findall(DEX_PATTERN, text)
    gecko_links = re.findall(GECKO_PATTERN, text)
    
    all_cas = list(set(cas + dex_links + gecko_links))
    
    for ca in all_cas:
        info_text, reply_markup = await get_token_info_message(ca, update.effective_chat.id, update.effective_user)
        if info_text:
            await update.message.reply_text(info_text, reply_markup=reply_markup, parse_mode="Markdown")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot Pemantau Token Base Chain Aktif! Kirim CA atau link DexScreener untuk info.")

if __name__ == "__main__":
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # Init DB
    loop = asyncio.get_event_loop()
    loop.run_until_complete(db.init())
    
    start_handler = MessageHandler(filters.COMMAND & filters.Regex("/start"), start)
    msg_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), message_handler)
    
    application.add_handler(start_handler)
    application.add_handler(msg_handler)
    
    logger.info("Bot started...")
    application.run_polling()
