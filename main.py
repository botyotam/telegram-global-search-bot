import os
import asyncio
from telethon import TelegramClient, events, Button
from telethon.tl.types import InputMessagesFilterPhotos, InputMessagesFilterVideo, InputMessagesFilterDocument, InputMessagesFilterMusic, InputMessagesFilterUrl

# Konfigurasi dari Environment Variables
API_ID = int(os.getenv('API_ID', 0))
API_HASH = os.getenv('API_HASH', '')
BOT_TOKEN = os.getenv('BOT_TOKEN', '')

if not API_ID or not API_HASH:
    raise ValueError("API_ID and API_HASH must be set as environment variables.")

client = TelegramClient('bot_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# Cache sederhana untuk menyimpan hasil pencarian (untuk paginasi)
search_cache = {}

CATEGORIES = {
    'all': 'Semua',
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
    
    # Karena SearchGlobalRequest tidak diizinkan untuk BOT, 
    # kita menggunakan pendekatan alternatif. 
    # Bot hanya bisa mencari di chat di mana ia menjadi anggota.
    # Untuk pencarian global yang sesungguhnya, diperlukan akun USER (bukan BOT).
    
    msg_filter = get_filter(category)
    
    try:
        # Mencari pesan di semua chat yang diikuti bot
        async for msg in client.iter_messages(None, search=query, filter=msg_filter, limit=50):
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
        print(f"Error during search: {e}")

    return results

def create_pagination_keyboard(query, category, page, total_pages):
    buttons = []
    # Baris 1: Filter Kategori
    row1 = [
        Button.inline("All", data=f"cat_{query}_all_{page}"),
        Button.inline("Video", data=f"cat_{query}_video_{page}"),
        Button.inline("Gambar", data=f"cat_{query}_photo_{page}")
    ]
    row2 = [
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
    
    return [row1, row2, nav_row]

@client.on(events.NewMessage(pattern='^(?!/).*'))
async def handler(event):
    query = event.text
    if len(query) < 3:
        return await event.respond("Keyword terlalu pendek (min 3 karakter).")
    
    msg = await event.respond(f"🔍 Mencari '{query}'...\n(Catatan: Bot hanya bisa mencari di grup/channel tempat ia bergabung)")
    results = await perform_search(query)
    
    if not results:
        return await msg.edit(f"❌ Tidak ditemukan hasil untuk '{query}'.\nBot tidak dapat melakukan pencarian global Telegram secara luas karena batasan API untuk akun Bot.")
    
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
        return await event.edit("Data tidak ditemukan atau bot tidak memiliki akses ke pesan tersebut.")

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
