"""
Migration Cog - Automated card migration sync
"""

import asyncio
from datetime import datetime, timedelta
from discord.ext import commands, tasks
import aiosqlite

import sys
sys.path.append('..')
from scryfall_api import scryfall_api

class MigrationCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.migration_check.start()
        
    def cog_unload(self):
        self.migration_check.cancel()
    
    async def _get_last_migration_time(self) -> datetime:
        """Get the timestamp of the last processed migration"""
        async with self.bot.db.execute(
            'SELECT performed_at FROM migrations_log ORDER BY performed_at DESC LIMIT 1'
        ) as cursor:
            row = await cursor.fetchone()
            if row and row[0]:
                return datetime.fromisoformat(row[0])
        return datetime.min
    
    async def _log_migration(self, migration_id: str, performed_at: str):
        """Log a processed migration"""
        await self.bot.db.execute(
            'INSERT INTO migrations_log (migration_id, performed_at) VALUES (?, ?)',
            (migration_id, performed_at)
        )
        await self.bot.db.commit()
    
    @tasks.loop(hours=1)
    async def migration_check(self):
        """Background task to check for card migrations every hour"""
        try:
            last_check = await self._get_last_migration_time()
            migrations = await scryfall_api.get_migrations()
            
            for migration in migrations:
                performed_at = datetime.fromisoformat(migration['performed_at'].replace('Z', '+00:00'))
                
                # Skip if already processed
                if performed_at <= last_check:
                    continue
                
                migration_id = migration['id']
                migration_type = migration['migration_strategy']
                
                if migration_type == 'merge':
                    # Update old card IDs to new ones
                    old_id = migration['old_scryfall_id']
                    new_id = migration['new_scryfall_id']
                    
                    await self.bot.db.execute(
                        'UPDATE collections SET scryfall_id = ? WHERE scryfall_id = ?',
                        (new_id, old_id)
                    )
                    print(f"Migration: Merged {old_id} -> {new_id}")
                    
                elif migration_type == 'delete':
                    # Remove deleted cards from collections
                    card_id = migration['old_scryfall_id']
                    
                    await self.bot.db.execute(
                        'DELETE FROM collections WHERE scryfall_id = ?',
                        (card_id,)
                    )
                    print(f"Migration: Deleted {card_id}")
                
                # Log this migration
                await self._log_migration(migration_id, migration['performed_at'])
            
            await self.bot.db.commit()
            print(f"[{datetime.now()}] Migration check completed")
            
        except Exception as e:
            print(f"Migration check error: {e}")
    
    @migration_check.before_loop
    async def before_migration_check(self):
        """Wait for bot to be ready before starting migration task"""
        await self.bot.wait_until_ready()
    
    @commands.command(name="force_migration")
    @commands.is_owner()
    async def force_migration(self, ctx):
        """Manually trigger migration check (owner only)"""
        await ctx.send("Running migration check...")
        self.migration_check.restart()
        
    @commands.command(name="migration_status")
    @commands.is_owner()
    async def migration_status(self, ctx):
        """Check migration processing status (owner only)"""
        try:
            async with self.bot.db.execute(
                'SELECT COUNT(*), MAX(performed_at) FROM migrations_log'
            ) as cursor:
                count, last = await cursor.fetchone()
            
            await ctx.send(f"Processed {count} migrations. Last: {last or 'Never'}")
        except Exception as e:
            await ctx.send(f"Error: {e}")

async def setup(bot: commands.Bot):
    await bot.add_cog(MigrationCog(bot))