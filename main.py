import os
import asyncio
import logging
from io import BytesIO
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from telethon.tl.functions.contacts import SearchRequest
from telethon.tl.functions.messages import SearchGlobalRequest
from telethon.tl.types import (
    InputMessagesFilterPhotos, InputMessagesFilterVideo, 
    InputMessagesFilterDocument, InputMessagesFilterMusic, 
    InputMessagesFilterUrl, InputPeerEmpty, InputMessagesFilterEmpty
)

# Konfigurasi Logging yang diperbaiki
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
log_stream = BytesIO()
# Gunakan handler yang mendukung string untuk BytesIO
class StringStreamHandler(logging.StreamHandler):
    def emit(self, record):
        try:
            msg = self.format(record)
            self.stream.write(msg.encode('utf-8') + b'\n')
            self.flush()
        except Exception:
            self.handleError(record)

stream_handler = StringStreamHandler(log_stream)
logger.addHandler(stream_handler)

# Konfigurasi dari Environment Variables
API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
SESSION_STRING = os.getenv("SESSION_STRING", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

if not API_ID or not API_HASH:
    raise ValueError("API_ID and API_HASH must be set as environment variables.")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN must be set as an environment variable.")

# Global clients
bot_client = None
user_client = None
search_cache = {}

CATEGORIES = {
    'all': 'Semua', 'channel': 'Channel', 'group': 'Grup', 'bot': 'Bot',
    'video': 'Video', 'photo': 'Gambar', 'file': 'File', 'music': 'Musik', 'link': 'Link'
}

TYPE_EMOJIS = {
    "Channel": "📢", "Grup": "👥", "Bot": "🤖", "Pesan": "💬",
    "Video": "📹", "Photo": "🖼️", "File": "📁", "Music": "🎵", "Link": "🔗"
}

def get_filter(category):
    filters = {
        'video': InputMessagesFilterVideo(),
        'photo': InputMessagesFilterPhotos(),
        'file': InputMessagesFilterDocument(),
        'music': InputMessagesFilterMusic(),
        'link': InputMessagesFilterUrl()
    }
    return filters.get(category)

async def perform_search(query, category='all'):
    results = []
    logger.info(f"Memulai pencarian: query='{query}', category='{category}'")
    
    # 1. Cari Channel, Grup, dan Bot
    if category in ['all', 'channel', 'group', 'bot']:
        try:
            # Gunakan bot_client jika user_client tidak tersedia untuk pencarian publik
            client = user_client if user_client else bot_client
            search_res = await client(SearchRequest(q=query, limit=100))
            for chat in search_res.chats:
                is_bot = getattr(chat, 'bot', False)
                is_channel = getattr(chat, 'broadcast', False)
                is_group = not is_channel and not is_bot
                
                if category == 'channel' and not is_channel: continue
                if category == 'group' and not is_group: continue
                if category == 'bot' and not is_bot: continue
                
                type_str = "Channel" if is_channel else ("Bot" if is_bot else "Grup")
                link = f"https://t.me/{chat.username}" if chat.username else f"https://t.me/c/{str(chat.id).replace('-100', '')}/1"
                
                results.append({'title': chat.title, 'link': link, 'type': type_str})
            logger.info(f"Ditemukan {len(results)} entitas")
        except Exception as e:
            logger.error(f"Error entity search: {e}")

    # 2. Cari Pesan/Media (Global Message Search) - WAJIB USER_CLIENT
    if user_client and category in ['all', 'video', 'photo', 'file', 'music', 'link']:
        msg_filter = get_filter(category)
        try:
            msg_res = await user_client(SearchGlobalRequest(
                q=query,
                filter=msg_filter or InputMessagesFilterEmpty(),
                min_date=None, max_date=None, offset_rate=0, offset_id=0,
                offset_peer=InputPeerEmpty(), limit=100
            ))
            
            msg_count = 0
            for msg in msg_res.messages:
                try:
                    chat = await msg.get_chat()
                    if not chat: continue
                    
                    title = getattr(chat, 'title', 'Pesan')
                    username = getattr(chat, 'username', None)
                    link = f"https://t.me/{username}/{msg.id}" if username else f"https://t.me/c/{str(chat.id).replace('-100', '')}/{msg.id}"
                    
                    m_type = "Pesan"
                    if msg.video: m_type = "Video"
                    elif msg.photo: m_type = "Photo"
                    elif msg.audio or msg.voice: m_type = "Music"
                    elif msg.document: m_type = "File"
                    elif msg.entities:
                        from telethon.tl.types import MessageEntityUrl, MessageEntityTextUrl
                        if any(isinstance(e, (MessageEntityUrl, MessageEntityTextUrl)) for e in msg.entities):
                            m_type = "Link"
                    
                    results.append({
                        'title': f"{title} ({m_type})",
                        'link': link,
                        'type': m_type
                    })
                    msg_count += 1
                except:
                    continue
            logger.info(f"Ditemukan {msg_count} pesan/media")
        except Exception as e:
            logger.error(f"Error message search: {e}")
    elif not user_client and category not in ['all', 'channel', 'group', 'bot']:
        logger.warning("Pencarian media dilewati karena user_client tidak aktif.")

    return results

def create_pagination_keyboard(query, category, page, total_pages):
    rows = [
        [Button.inline("All", data=f"cat_{query}_all_{page}"), Button.inline("Channel", data=f"cat_{query}_channel_{page}"), Button.inline("Grup", data=f"cat_{query}_group_{page}")],
        [Button.inline("Bot", data=f"cat_{query}_bot_{page}"), Button.inline("Video", data=f"cat_{query}_video_{page}"), Button.inline("Gambar", data=f"cat_{query}_photo_{page}")],
        [Button.inline("File", data=f"cat_{query}_file_{page}"), Button.inline("Musik", data=f"cat_{query}_music_{page}"), Button.inline("Link", data=f"cat_{query}_link_{page}")]
    ]
    nav_row = []
    if page > 0: nav_row.append(Button.inline("⬅️ Back", data=f"nav_{query}_{category}_{page-1}"))
    nav_row.append(Button.inline(f"{page+1}/{total_pages}", data="ignore"))
    if page < total_pages - 1: nav_row.append(Button.inline("Next ➡️", data=f"nav_{query}_{category}_{page+1}"))
    rows.append(nav_row)
    return rows

async def main():
    global bot_client, user_client
    bot_client = TelegramClient("bot_session", API_ID, API_HASH)
    await bot_client.start(bot_token=BOT_TOKEN)
    
    user_status = "❌ Tidak Terhubung (Session String Kosong)"
    if SESSION_STRING:
        try:
            user_client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
            await user_client.start()
            me = await user_client.get_me()
            user_status = f"✅ Terhubung sebagai {me.first_name} (@{me.username})"
            logger.info(f"User client aktif: {me.username}")
        except Exception as e:
            user_status = f"⚠️ Error Session: {str(e)}"
            user_client = None # Pastikan None jika gagal
            logger.error(f"Gagal memulai user client: {e}")

    @bot_client.on(events.NewMessage(pattern='/start'))
    async def start_handler(event):
        await event.respond("👋 **Halo! Selamat datang di Global Search Bot.**\n\nKetik kata kunci untuk mencari (min. 3 karakter).\n\nKategori: Channel, Grup, Bot, Video, Gambar, File, Musik, Link.")

    @bot_client.on(events.NewMessage(pattern='/status'))
    async def status_handler(event):
        if event.sender_id == ADMIN_ID:
            await event.respond(f"📊 **Status Sistem**\n\n🔹 **Bot:** ✅ Aktif\n🔹 **User Session:** {user_status}\n\n💡 *Jika error AuthKeyDuplicated, silakan buat SESSION_STRING baru.*")

    @bot_client.on(events.NewMessage(pattern='/logs'))
    async def logs_handler(event):
        if event.sender_id == ADMIN_ID:
            log_stream.seek(0)
            logs = log_stream.read().decode('utf-8', errors='ignore')[-4000:]
            await event.respond(f"📜 **Internal Logs:**\n\n`{logs}`" if logs else "Log kosong.")

    @bot_client.on(events.NewMessage(pattern='^(?!/).*'))
    async def handler(event):
        query = event.text
        if len(query) < 3: return await event.respond("Keyword terlalu pendek.")
        
        msg = await event.respond(f"🔍 Mencari '{query}'...")
        results = await perform_search(query)
        
        if not results:
            err_msg = f"❌ Tidak ditemukan hasil untuk '{query}'."
            if not user_client:
                err_msg += "\n\n⚠️ **Peringatan:** Session String Anda tidak aktif. Pencarian media (Video/Musik/Pesan) tidak dapat dilakukan."
            return await msg.edit(err_msg)
        
        search_cache[query] = results
        total_pages = (len(results) + 9) // 10
        text = f"🔎 Hasil Pencarian: **{query}**\n\n"
        for i, res in enumerate(results[0:10], 1):
            text += f"{i}. {TYPE_EMOJIS.get(res['type'], '🔹')} [{res['title']}]({res['link']}) ({res['type']})\n"
        
        await msg.edit(text, buttons=create_pagination_keyboard(query, 'all', 0, total_pages), link_preview=False)

    @bot_client.on(events.CallbackQuery(data=lambda d: d.startswith(b'nav_') or d.startswith(b'cat_')))
    async def callback_handler(event):
        data = event.data.decode().split('_')
        action, query, category, page = data[0], data[1], data[2], int(data[3])
        
        if action == 'cat':
            await event.answer(f"Kategori: {category}")
            results = await perform_search(query, category)
            search_cache[f"{query}_{category}"] = results
            current_results = results
        else:
            current_results = search_cache.get(f"{query}_{category}") or search_cache.get(query)
            if not current_results:
                current_results = await perform_search(query, category)
                search_cache[f"{query}_{category}"] = current_results

        if not current_results: return await event.edit("Data tidak ditemukan.")

        total_pages = (len(current_results) + 9) // 10
        start, end = page * 10, (page * 10) + 10
        text = f"🔎 Hasil Pencarian: **{query}** ({category})\n\n"
        for i, res in enumerate(current_results[start:end], start + 1):
            text += f"{i}. {TYPE_EMOJIS.get(res['type'], '🔹')} [{res['title']}]({res['link']}) ({res['type']})\n"
        
        await event.edit(text, buttons=create_pagination_keyboard(query, category, page, total_pages), link_preview=False)

    print("Bot sedang berjalan...")
    await asyncio.gather(bot_client.run_until_disconnected(), user_client.run_until_disconnected() if user_client else asyncio.sleep(0))

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
