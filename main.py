import os
import asyncio
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from telethon.tl.functions.contacts import SearchRequest
from telethon.tl.functions.messages import SearchGlobalRequest
from telethon.tl.types import InputMessagesFilterPhotos, InputMessagesFilterVideo, InputMessagesFilterDocument, InputMessagesFilterMusic, InputMessagesFilterUrl, InputPeerEmpty, InputMessagesFilterEmpty

# Konfigurasi dari Environment Variables
API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
SESSION_STRING = os.getenv("SESSION_STRING", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0)) # Tambahkan ADMIN_ID di environment

if not API_ID or not API_HASH:
    raise ValueError("API_ID and API_HASH must be set as environment variables.")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN must be set as an environment variable.")

# Global clients
bot_client = None
user_client = None

# Cache sederhana untuk menyimpan hasil pencarian (untuk paginasi)
search_cache = {}

CATEGORIES = {
    'all': 'Semua',
    'channel': 'Channel',
    'group': 'Grup',
    'bot': 'Bot',
    'video': 'Video',
    'photo': 'Gambar',
    'file': 'File',
    'music': 'Musik',
    'link': 'Link'
}

TYPE_EMOJIS = {
    "Channel": "📢",
    "Grup": "👥",
    "Bot": "🤖",
    "Pesan": "💬",
    "Video": "📹",
    "Photo": "🖼️",
    "File": "📁",
    "Music": "🎵",
    "Link": "🔗"
}

def get_filter(category):
    if category == 'video': return InputMessagesFilterVideo()
    if category == 'photo': return InputMessagesFilterPhotos()
    if category == 'file': return InputMessagesFilterDocument()
    if category == 'music': return InputMessagesFilterMusic()
    if category == 'link': return InputMessagesFilterUrl()
    return None

async def perform_search(query, category='all'):
    results = []
    # SESSION_STRING sangat penting untuk pencarian pesan, media, dan bot secara global
    if not user_client:
        print("User client tidak aktif. Pencarian terbatas pada entitas publik.")
    
    # 1. Cari Channel, Grup, dan Bot (Global Search)
    if category in ['all', 'channel', 'group', 'bot']:
        try:
            # SearchRequest bekerja lebih baik untuk mencari entitas (Channel/Grup/Bot)
            search_res = await user_client(SearchRequest(q=query, limit=100))
            for chat in search_res.chats:
                is_bot = getattr(chat, 'bot', False)
                is_channel = getattr(chat, 'broadcast', False)
                is_group = not is_channel and not is_bot
                
                if category == 'channel' and not is_channel: continue
                if category == 'group' and not is_group: continue
                if category == 'bot' and not is_bot: continue
                
                type_str = "Channel" if is_channel else ("Bot" if is_bot else "Grup")
                if chat.username:
                    link = f"https://t.me/{chat.username}"
                else:
                    cid = str(chat.id)
                    if cid.startswith("-100"): cid = cid[4:]
                    link = f"https://t.me/c/{cid}/1"
                
                results.append({
                    'title': chat.title,
                    'link': link,
                    'type': type_str
                })
        except Exception as e:
            print(f"Error during entity search: {e}")

    # 2. Cari Pesan/Media (Global Message Search) - MEMBUTUHKAN USER_CLIENT (SESSION_STRING)
    if user_client and category in ['all', 'video', 'photo', 'file', 'music', 'link']:
        msg_filter = get_filter(category)
        try:
            msg_res = await user_client(SearchGlobalRequest(
                q=query,
                filter=msg_filter or InputMessagesFilterEmpty(),
                min_date=None,
                max_date=None,
                offset_rate=0,
                offset_id=0,
                offset_peer=InputPeerEmpty(),
                limit=100
            ))
            
            for msg in msg_res.messages:
                try:
                    chat = await msg.get_chat()
                    title = getattr(chat, 'title', 'Pesan')
                    username = getattr(chat, 'username', None)
                    
                    if username:
                        link = f"https://t.me/{username}/{msg.id}"
                    else:
                        cid = str(chat.id)
                        if cid.startswith("-100"): cid = cid[4:]
                        link = f"https://t.me/c/{cid}/{msg.id}"
                    
                    # Tentukan tipe berdasarkan media jika kategori 'all'
                    m_type = "Pesan"
                    if msg.video: m_type = "Video"
                    elif msg.photo: m_type = "Photo"
                    elif msg.document:
                        if any(msg.document.mime_type.startswith(x) for x in ['audio', 'music']): m_type = "Music"
                        else: m_type = "File"
                    
                    results.append({
                        'title': f"{title} ({m_type})",
                        'link': link,
                        'type': m_type if category == 'all' else category.capitalize()
                    })
                except:
                    continue
        except Exception as e:
            print(f"Error during global message search: {e}")

    return results

def create_pagination_keyboard(query, category, page, total_pages):
    row1 = [
        Button.inline("All", data=f"cat_{query}_all_{page}"),
        Button.inline("Channel", data=f"cat_{query}_channel_{page}"),
        Button.inline("Grup", data=f"cat_{query}_group_{page}")
    ]
    row2 = [
        Button.inline("Bot", data=f"cat_{query}_bot_{page}"),
        Button.inline("Video", data=f"cat_{query}_video_{page}"),
        Button.inline("Gambar", data=f"cat_{query}_photo_{page}")
    ]
    row3 = [
        Button.inline("File", data=f"cat_{query}_file_{page}"),
        Button.inline("Musik", data=f"cat_{query}_music_{page}"),
        Button.inline("Link", data=f"cat_{query}_link_{page}")
    ]
    nav_row = []
    if page > 0:
        nav_row.append(Button.inline("⬅️ Back", data=f"nav_{query}_{category}_{page-1}"))
    nav_row.append(Button.inline(f"{page+1}/{total_pages}", data="ignore"))
    if page < total_pages - 1:
        nav_row.append(Button.inline("Next ➡️", data=f"nav_{query}_{category}_{page+1}"))
    
    return [row1, row2, row3, nav_row]

async def main():
    global bot_client, user_client
    
    bot_client = TelegramClient("bot_session", API_ID, API_HASH)
    await bot_client.start(bot_token=BOT_TOKEN)
    
    user_status = "❌ Tidak Terhubung"
    if SESSION_STRING:
        try:
            user_client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
            await user_client.start()
            me = await user_client.get_me()
            user_status = f"✅ Terhubung sebagai {me.first_name} (@{me.username})"
        except Exception as e:
            user_status = f"⚠️ Error: {str(e)}"
    
    @bot_client.on(events.NewMessage(pattern='/start'))
    async def start_handler(event):
        welcome_text = (
            "👋 **Halo! Selamat datang di Global Search Bot.**\n\n"
            "Bot ini memungkinkan Anda mencari Channel, Grup, Bot, serta Pesan dan Media secara global di Telegram.\n\n"
            "📖 **Cara Penggunaan:**\n"
            "1. Langsung ketik kata kunci yang ingin dicari (min. 3 karakter).\n"
            "2. Gunakan tombol di bawah hasil pencarian untuk memfilter kategori (Video, Musik, File, dll).\n"
            "3. Gunakan tombol navigasi untuk melihat hasil lainnya.\n\n"
            "💡 *Tips: Pastikan kata kunci spesifik untuk hasil terbaik.*"
        )
        await event.respond(welcome_text)

    @bot_client.on(events.NewMessage(pattern='/status'))
    async def status_handler(event):
        if event.sender_id != ADMIN_ID:
            return # Hanya admin yang bisa cek status
        
        status_text = (
            "📊 **Status Sistem (Admin Only)**\n\n"
            f"🔹 **Bot Client:** ✅ Aktif\n"
            f"🔹 **User Session:** {user_status}\n\n"
            "💡 *Guna Session String:* Digunakan untuk melakukan pencarian global terhadap pesan, media (video/musik), dan bot yang tidak bisa diakses oleh bot biasa."
        )
        await event.respond(status_text)

    @bot_client.on(events.NewMessage(pattern='^(?!/).*'))
    async def handler(event):
        query = event.text
        if len(query) < 3:
            return await event.respond("Keyword terlalu pendek (min 3 karakter).")
        
        msg = await event.respond(f"🔍 Mencari '{query}'...")
        results = await perform_search(query)
        
        if not results:
            return await msg.edit(f"❌ Tidak ditemukan hasil untuk '{query}'.\n\n"
                                 "Mungkin karena:\n"
                                 "1. Kata kunci terlalu umum.\n"
                                 "2. SESSION_STRING tidak aktif (pencarian pesan/media butuh session).")
        
        search_cache[query] = results
        total_pages = (len(results) + 9) // 10
        display_results = results[0:10]
        
        text = f"🔎 Hasil Pencarian: **{query}**\n\n"
        for i, res in enumerate(display_results, 1):
            emoji = TYPE_EMOJIS.get(res['type'], "🔹")
            text += f"{i}. {emoji} [{res['title']}]({res['link']}) ({res['type']})\n"
        
        await msg.edit(text, buttons=create_pagination_keyboard(query, 'all', 0, total_pages), link_preview=False)

    @bot_client.on(events.CallbackQuery(data=lambda d: d.startswith(b'nav_') or d.startswith(b'cat_')))
    async def callback_handler(event):
        data = event.data.decode().split('_')
        action, query, category, page = data[0], data[1], data[2], int(data[3])
        
        if action == 'cat':
            await event.answer(f"Kategori: {CATEGORIES.get(category)}")
            results = await perform_search(query, category)
            search_cache[f"{query}_{category}"] = results
            current_results = results
        else:
            current_results = search_cache.get(f"{query}_{category}") or search_cache.get(query)
            if not current_results:
                current_results = await perform_search(query, category)
                search_cache[f"{query}_{category}"] = current_results

        if not current_results:
            return await event.edit("Data tidak ditemukan atau sesi berakhir.")

        total_pages = (len(current_results) + 9) // 10
        start, end = page * 10, (page * 10) + 10
        display_results = current_results[start:end]
        
        text = f"🔎 Hasil Pencarian: **{query}** ({CATEGORIES.get(category, 'Semua')})\n\n"
        for i, res in enumerate(display_results, start + 1):
            emoji = TYPE_EMOJIS.get(res['type'], "🔹")
            text += f"{i}. {emoji} [{res['title']}]({res['link']}) ({res['type']})\n"
        
        await event.edit(text, buttons=create_pagination_keyboard(query, category, page, total_pages), link_preview=False)

    print("Bot sedang berjalan...")
    await asyncio.gather(
        bot_client.run_until_disconnected(),
        user_client.run_until_disconnected() if user_client else asyncio.sleep(0)
    )

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
