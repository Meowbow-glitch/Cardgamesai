"""
Scryfall Discord Bot - Main Entry Point
A bot for searching and collecting Magic: The Gathering cards
"""

import os
import asyncio
import aiosqlite
from dotenv import load_dotenv
import discord
from discord.ext import commands

# Load environment variables
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

# Bot setup
intents = discord.Intents.default()

class ScryfallBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix='!',
            intents=intents,
            application_id=int(os.getenv('APPLICATION_ID', '0'))
        )
        self.db = None
        
    async def setup_hook(self):
        # Initialize database
        self.db = await aiosqlite.connect('scryfall.db')
        await self._init_db()
        
        # Load cogs
        await self.load_extension('cogs.search')
        await self.load_extension('cogs.collection')
        await self.load_extension('cogs.migration')
        
        # Sync slash commands
        await self.tree.sync()
        
    async def _init_db(self):
        """Initialize database tables"""
        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                discord_id TEXT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS collections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                scryfall_id TEXT,
                name TEXT,
                set_code TEXT,
                collector_number TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(discord_id)
            )
        ''')
        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS migrations_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                migration_id TEXT,
                performed_at TIMESTAMP,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await self.db.commit()
        
    async def close(self):
        if self.db:
            await self.db.close()
        await super().close()

bot = ScryfallBot()

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')

# Health check command
@bot.tree.command(name="ping", description="Check bot latency")
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f'Pong! {latency}ms')

if __name__ == '__main__':
    bot.run(DISCORD_TOKEN)