import os
import asyncio
from telethon import TelegramClient, events, Button
from telethon.tl.functions.contacts import SearchRequest
from telethon.tl.functions.messages import SearchGlobalRequest
from telethon.tl.types import InputMessagesFilterPhotos, InputMessagesFilterVideo, InputMessagesFilterDocument, InputMessagesFilterMusic, InputMessagesFilterUrl

# Konfigurasi dari Environment Variables
API_ID = int(os.getenv('API_ID', 0))
API_HASH = os.getenv('API_HASH', '')
BOT_TOKEN = os.getenv('BOT_TOKEN', '')

if not API_ID or not API_HASH:
    raise ValueError("API_ID and API_HASH must be set as environment variables.")

client = TelegramClient('bot_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# Cache sederhana untuk menyimpan hasil pencarian (untuk paginasi)
# Dalam produksi, sebaiknya gunakan database atau cache yang lebih persisten
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
    
    # 1. Cari Channel, Grup, dan Bot (Global Search)
    # Temporarily disable this block as SearchRequest is not suitable for global entity search.
    # The previous error was due to SearchRequest being called without a peer, which is required for contact search.
    # If global entity search is needed, a different Telethon API should be used.
    # if category in ['all', 'channel', 'group', 'bot']:
    if False:
        # SearchRequest is for contacts, not global entities. Removing this part or replacing with a more appropriate global search if available.
        # For now, we will rely on SearchGlobalRequest for messages and media.
        # If the intent was to search for public channels/groups/bots, a different Telethon API call is needed.
        # For example, client.iter_entities() or client.get_entity() with a username.
        pass # No direct global search for entities with SearchRequest

    # 2. Cari Pesan/Media (Global Message Search)
    if category in ['all', 'video', 'photo', 'file', 'music', 'link']:
        msg_filter = get_filter(category)
        # SearchGlobalRequest mencari pesan di seluruh Telegram (yang bisa diakses user/bot)
        msg_res = await client(SearchGlobalRequest(
            q=query,
            filter=msg_filter or None,
            min_date=None,
            max_date=None,
            offset_id=0,
            offset_peer=None,
            limit=50
        ))
        
        for msg in msg_res.messages:
            # Mengambil info chat dari pesan
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
        Button.inline("Video", data=f"cat_{query}_video_{page}"),
        Button.inline("Gambar", data=f"cat_{query}_photo_{page}"),
        Button.inline("File", data=f"cat_{query}_file_{page}")
    ]
    
    # Baris Navigasi
    nav_row = []
    if page > 0:
        nav_row.append(Button.inline("⬅️ Back", data=f"nav_{query}_{category}_{page-1}"))
    nav_row.append(Button.inline(f"{page+1}/{total_pages}", data="ignore"))
    if page < total_pages - 1:
        nav_row.append(Button.inline("Next ➡️", data=f"nav_{query}_{category}_{page+1}"))
    
    return [row1, row2, nav_row]

@client.on(events.NewMessage(pattern='^(?!/).*'))
async def handler(event):
    query = event.text
    if len(query) < 3:
        return await event.respond("Keyword terlalu pendek (min 3 karakter).")
    
    msg = await event.respond(f"🔍 Mencari '{query}'...")
    results = await perform_search(query)
    
    if not results:
        return await msg.edit(f"❌ Tidak ditemukan hasil untuk '{query}'.")
    
    search_cache[query] = results
    total_pages = (len(results) + 9) // 10
    
    display_results = results[0:10]
    text = f"🔎 Hasil Pencarian: **{query}**\n\n"
    for i, res in enumerate(display_results, 1):
        text += f"{i}. [{res['title']}]({res['link']}) ({res['type']})\n"
    
    await msg.edit(text, buttons=create_pagination_keyboard(query, 'all', 0, total_pages), link_preview=False)

@client.on(events.CallbackQuery(data=lambda d: d.startswith(b'nav_') or d.startswith(b'cat_')))
async def callback_handler(event):
    data = event.data.decode().split('_')
    action = data[0] # nav atau cat
    query = data[1]
    category = data[2]
    page = int(data[3])
    
    if action == 'cat':
        # Jika ganti kategori, lakukan pencarian ulang untuk kategori tersebut
        await event.answer("Mengubah kategori...")
        results = await perform_search(query, category)
        search_cache[f"{query}_{category}"] = results
        current_results = results
    else:
        # Jika navigasi, ambil dari cache jika ada
        current_results = search_cache.get(f"{query}_{category}") or search_cache.get(query)
        if not current_results:
            # Re-search jika cache hilang
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
client.run_until_disconnected()
