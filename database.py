import aiosqlite
import time

class Database:
    def __init__(self, db_path="bot_data.db"):
        self.db_path = db_path

    async def init(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS tokens (
                    ca TEXT PRIMARY KEY,
                    platform TEXT,
                    first_price REAL,
                    ath_mc REAL,
                    ath_timestamp INTEGER,
                    first_sharer_id INTEGER,
                    first_sharer_name TEXT,
                    first_share_time INTEGER,
                    chat_id INTEGER
                )
            """)
            await db.commit()

    async def get_token(self, ca, chat_id):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT * FROM tokens WHERE ca = ? AND chat_id = ?", (ca, chat_id)
            ) as cursor:
                return await cursor.fetchone()

    async def save_token(self, ca, platform, first_price, mc, sharer_id, sharer_name, chat_id):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT OR IGNORE INTO tokens 
                   (ca, platform, first_price, ath_mc, ath_timestamp, first_sharer_id, first_sharer_name, first_share_time, chat_id) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (ca, platform, first_price, mc, int(time.time()), sharer_id, sharer_name, int(time.time()), chat_id)
            )
            await db.commit()

    async def update_ath(self, ca, mc):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE tokens SET ath_mc = ?, ath_timestamp = ? WHERE ca = ? AND ath_mc < ?",
                (mc, int(time.time()), ca, mc)
            )
            await db.commit()
