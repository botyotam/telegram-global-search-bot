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

def get_filter(category):
    if category == 'video': return InputMessagesFilterVideo()
    if category == 'photo': return InputMessagesFilterPhotos()
    if category == 'file': return InputMessagesFilterDocument()
    if category == 'music': return InputMessagesFilterMusic()
    if category == 'link': return InputMessagesFilterUrl()
    return None

async def perform_search(query, category='all'):
    results = []
    if not user_client:
        print("User client tidak aktif. Tidak dapat melakukan pencarian global.")
        return results

    # 1. Cari Channel, Grup, dan Bot (Global Search)
    if category in ['all', 'channel', 'group', 'bot']:
        try:
            search_res = await user_client(SearchRequest(q=query, limit=50))
            for chat in search_res.chats:
                is_bot = getattr(chat, 'bot', False)
                is_channel = getattr(chat, 'broadcast', False)
                is_group = not is_channel and not is_bot
                
                if category == 'channel' and not is_channel: continue
                if category == 'group' and not is_group: continue
                if category == 'bot' and not is_bot: continue
                
                type_str = "Channel" if is_channel else ("Bot" if is_bot else "Grup")
                username = f"@{chat.username}" if chat.username else "Private"
                results.append({
                    'title': chat.title,
                    'link': f"https://t.me/{chat.username}" if chat.username else "N/A",
                    'type': type_str
                })
        except Exception as e:
            print(f"Error during entity search: {e}")

    # 2. Cari Pesan/Media (Global Message Search)
    if category in ['all', 'video', 'photo', 'file', 'music', 'link']:
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
                limit=50
            ))
            
            for msg in msg_res.messages:
                try:
                    chat = await msg.get_chat()
                    title = getattr(chat, 'title', 'Pesan')
                    username = getattr(chat, 'username', None)
                    link = f"https://t.me/{username}/{msg.id}" if username else "N/A"
                    
                    results.append({
                        'title': f"{title} (Pesan)",
                        'link': link,
                        'type': category.capitalize() if category != 'all' else "Pesan"
                    })
                except:
                    continue
        except Exception as e:
            print(f"Error during global message search: {e}")

    return results

def create_pagination_keyboard(query, category, page, total_pages):
    buttons = []
    # Baris 1: Filter Kategori
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
    
    # Baris Navigasi
    nav_row = []
    if page > 0:
        nav_row.append(Button.inline("⬅️ Back", data=f"nav_{query}_{category}_{page-1}"))
    nav_row.append(Button.inline(f"{page+1}/{total_pages}", data="ignore"))
    if page < total_pages - 1:
        nav_row.append(Button.inline("Next ➡️", data=f"nav_{query}_{category}_{page+1}"))
    
    return [row1, row2, row3, nav_row]

async def main():
    global bot_client, user_client
    
    # Inisialisasi Bot Client di dalam event loop
    bot_client = TelegramClient("bot_session", API_ID, API_HASH)
    await bot_client.start(bot_token=BOT_TOKEN)
    
    # Inisialisasi User Client di dalam event loop
    if SESSION_STRING:
        user_client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
        await user_client.start()
    else:
        print("Peringatan: SESSION_STRING tidak ditemukan. Pencarian global mungkin tidak berfungsi.")

    @bot_client.on(events.NewMessage(pattern='^(?!/).*'))
    async def handler(event):
        query = event.text
        if len(query) < 3:
            return await event.respond("Keyword terlalu pendek (min 3 karakter).")
        
        msg = await event.respond(f"🔍 Mencari '{query}'...")
        results = await perform_search(query)
        
        if not results:
            return await msg.edit(f"❌ Tidak ditemukan hasil untuk '{query}'.\nPastikan SESSION_STRING sudah diatur dengan benar dan akun user aktif.")
        
        search_cache[query] = results
        total_pages = (len(results) + 9) // 10
        
        display_results = results[0:10]
        text = f"🔎 Hasil Pencarian: **{query}**\n\n"
        for i, res in enumerate(display_results, 1):
            text += f"{i}. [{res['title']}]({res['link']}) ({res['type']})\n"
        
        await msg.edit(text, buttons=create_pagination_keyboard(query, 'all', 0, total_pages), link_preview=False)

    @bot_client.on(events.CallbackQuery(data=lambda d: d.startswith(b'nav_') or d.startswith(b'cat_')))
    async def callback_handler(event):
        data = event.data.decode().split('_')
        action = data[0] # nav atau cat
        query = data[1]
        category = data[2]
        page = int(data[3])
        
        if action == 'cat':
            await event.answer("Mengubah kategori...")
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
        start = page * 10
        end = start + 10
        display_results = current_results[start:end]
        
        text = f"🔎 Hasil Pencarian: **{query}** ({CATEGORIES.get(category, 'Semua')})\n\n"
        for i, res in enumerate(display_results, start + 1):
            text += f"{i}. [{res['title']}]({res['link']}) ({res['type']})\n"
        
        await event.edit(text, buttons=create_pagination_keyboard(query, category, page, total_pages), link_preview=False)

    print("Bot sedang berjalan...")
    # Run both clients until disconnected
    await asyncio.gather(
        bot_client.run_until_disconnected(),
        user_client.run_until_disconnected() if user_client else asyncio.sleep(0)
    )

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
