"""
Collection Cog - User card collection management
"""

import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import io

import sys
sys.path.append('..')
from scryfall_api import scryfall_api

class CollectionCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        
    async def _ensure_user(self, discord_id: str):
        """Ensure user exists in database"""
        await self.bot.db.execute(
            'INSERT OR IGNORE INTO users (discord_id) VALUES (?)',
            (discord_id,)
        )
        await self.bot.db.commit()
    
    @app_commands.command(name="import", description="Import a card to your collection")
    @app_commands.describe(card_name="Name of the card to import")
    async def import_card(self, interaction: discord.Interaction, card_name: str):
        """Import a card from Scryfall to user's collection"""
        await interaction.response.defer()
        
        try:
            # Search for the card
            data = await scryfall_api.search_cards(f'!"{card_name}"')
            cards = data.get('data', [])
            
            if not cards:
                await interaction.followup.send(f"Card '{card_name}' not found.")
                return
            
            card = cards[0]
            scryfall_id = card['id']
            user_id = str(interaction.user.id)
            
            # Ensure user exists
            await self._ensure_user(user_id)
            
            # Check if already in collection
            async with self.bot.db.execute(
                'SELECT id FROM collections WHERE user_id = ? AND scryfall_id = ?',
                (user_id, scryfall_id)
            ) as cursor:
                existing = await cursor.fetchone()
                if existing:
                    await interaction.followup.send(f"'{card['name']}' is already in your collection!")
                    return
            
            # Add to collection
            await self.bot.db.execute(
                '''INSERT INTO collections 
                   (user_id, scryfall_id, name, set_code, collector_number) 
                   VALUES (?, ?, ?, ?, ?)''',
                (user_id, scryfall_id, card['name'], card.get('set', ''), card.get('collector_number', ''))
            )
            await self.bot.db.commit()
            
            await interaction.followup.send(f"✅ Added **{card['name']}** to your collection!")
            
        except Exception as e:
            await interaction.followup.send(f"Error importing card: {str(e)}", ephemeral=True)
    
    @app_commands.command(name="collection", description="View your card collection")
    async def view_collection(self, interaction: discord.Interaction):
        """Display user's collection"""
        await interaction.response.defer()
        
        try:
            user_id = str(interaction.user.id)
            
            async with self.bot.db.execute(
                '''SELECT scryfall_id, name, set_code, collector_number 
                   FROM collections WHERE user_id = ? ORDER BY added_at DESC''',
                (user_id,)
            ) as cursor:
                cards = await cursor.fetchall()
            
            if not cards:
                await interaction.followup.send("Your collection is empty. Use `/import` to add cards!")
                return
            
            # Create embed
            embed = discord.Embed(
                title=f"{interaction.user.display_name}'s Collection",
                description=f"Total cards: {len(cards)}",
                color=0x2ecc71
            )
            
            # Show first 10 cards
            for scryfall_id, name, set_code, collector_num in cards[:10]:
                embed.add_field(
                    name=name,
                    value=f"{set_code.upper()} #{collector_num}",
                    inline=True
                )
            
            if len(cards) > 10:
                embed.set_footer(text=f"...and {len(cards) - 10} more cards")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(f"Error loading collection: {str(e)}", ephemeral=True)
    
    @app_commands.command(name="remove", description="Remove a card from your collection")
    @app_commands.describe(card_name="Name of the card to remove")
    async def remove_card(self, interaction: discord.Interaction, card_name: str):
        """Remove a card from user's collection"""
        await interaction.response.defer()
        
        try:
            user_id = str(interaction.user.id)
            
            # Find card by name (case-insensitive)
            async with self.bot.db.execute(
                'SELECT id, name FROM collections WHERE user_id = ? AND LOWER(name) = LOWER(?)',
                (user_id, card_name)
            ) as cursor:
                card = await cursor.fetchone()
            
            if not card:
                await interaction.followup.send(f"'{card_name}' is not in your collection.")
                return
            
            # Remove from collection
            await self.bot.db.execute(
                'DELETE FROM collections WHERE id = ?',
                (card[0],)
            )
            await self.bot.db.commit()
            
            await interaction.followup.send(f"✅ Removed **{card[1]}** from your collection.")
            
        except Exception as e:
            await interaction.followup.send(f"Error removing card: {str(e)}", ephemeral=True)
    
    @import_card.autocomplete('card_name')
    async def import_autocomplete(self, interaction: discord.Interaction, current: str) -> list:
        """Autocomplete for card import"""
        if len(current) < 2:
            return []
        
        try:
            suggestions = await scryfall_api.autocomplete_cards(current)
            return [
                app_commands.Choice(name=name[:100], value=name[:100])
                for name in suggestions[:25]
            ]
        except Exception:
            return []
    
    @app_commands.command(name="export", description="Export your collection to a file for importing to Moxfield or other sites")
    @app_commands.describe(format="Export format")
    @app_commands.choices(format=[
        app_commands.Choice(name="Moxfield (Bulk Edit)", value="moxfield"),
        app_commands.Choice(name="Plain Text (Card Names)", value="plaintext"),
        app_commands.Choice(name="CSV", value="csv")
    ])
    async def export_collection(self, interaction: discord.Interaction, format: str = "moxfield"):
        """Export user's collection to a file format suitable for import to deck building sites"""
        await interaction.response.defer()
        
        try:
            user_id = str(interaction.user.id)
            
            async with self.bot.db.execute(
                '''SELECT name, set_code, collector_number 
                   FROM collections WHERE user_id = ? ORDER BY name''',
                (user_id,)
            ) as cursor:
                cards = await cursor.fetchall()
            
            if not cards:
                await interaction.followup.send("Your collection is empty. Use `/import` to add cards first!")
                return
            
            # Generate export content based on format
            if format == "moxfield":
                # Moxfield Bulk Edit format: "1 Card Name (SET) CollectorNumber"
                lines = []
                for name, set_code, collector_num in cards:
                    # Format: "1 Card Name (SET) CollectorNumber"
                    line = f"1 {name}"
                    if set_code:
                        line += f" ({set_code.upper()})"
                    if collector_num:
                        line += f" {collector_num}"
                    lines.append(line)
                content = "\n".join(lines)
                filename = f"{interaction.user.display_name}_collection_moxfield.txt"
                description = "Moxfield format"
                
            elif format == "plaintext":
                # Simple text list
                lines = [name for name, _, _ in cards]
                content = "\n".join(lines)
                filename = f"{interaction.user.display_name}_collection.txt"
                description = "Plain text list"
                
            else:  # csv
                import csv
                output = io.StringIO()
                writer = csv.writer(output)
                writer.writerow(["Name", "Set Code", "Collector Number"])
                for name, set_code, collector_num in cards:
                    writer.writerow([name, set_code.upper() if set_code else "", collector_num])
                content = output.getvalue()
                filename = f"{interaction.user.display_name}_collection.csv"
                description = "CSV format"
            
            # Create file attachment
            file = discord.File(
                fp=io.BytesIO(content.encode('utf-8')),
                filename=filename
            )
            
            embed = discord.Embed(
                title="📤 Collection Exported",
                description=f"Exported **{len(cards)}** cards in {description}",
                color=0x2ecc71
            )
            embed.add_field(
                name="Import Instructions",
                value="**Moxfield:** Go to your Collection → Click 'Edit' → 'Bulk Edit' → Paste the contents",
                inline=False
            )
            embed.set_footer(text=f"Export generated for {interaction.user.display_name}")
            
            await interaction.followup.send(embed=embed, file=file)
            
        except Exception as e:
            await interaction.followup.send(f"Error exporting collection: {str(e)}", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(CollectionCog(bot))