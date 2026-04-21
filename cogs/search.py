"""
Search Cog - Card search with pagination and autocomplete
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button

import sys
sys.path.append('..')
from scryfall_api import scryfall_api

# Session storage for pagination
class PaginationSession:
    """Stores pagination state for search results"""
    def __init__(self, query: str, results: list, has_more: bool, next_page: Optional[str]):
        self.query = query
        self.results = results
        self.has_more = has_more
        self.next_page_url = next_page
        self.current_page = 1
        self.created_at = datetime.now()
        
    def is_expired(self) -> bool:
        return datetime.now() - self.created_at > timedelta(minutes=15)

# In-memory session storage
pagination_sessions: Dict[str, PaginationSession] = {}

class PaginationView(View):
    """Discord view with Next/Prev buttons for search results"""
    def __init__(self, session_id: str):
        super().__init__(timeout=900)  # 15 minute timeout
        self.session_id = session_id
        
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return True
        
    @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.secondary, disabled=True)
    async def prev_button(self, interaction: discord.Interaction, button: Button):
        await self._handle_page_change(interaction, -1)
        
    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.primary)
    async def next_button(self, interaction: discord.Interaction, button: Button):
        await self._handle_page_change(interaction, 1)
        
    async def _handle_page_change(self, interaction: discord.Interaction, direction: int):
        session = pagination_sessions.get(self.session_id)
        if not session or session.is_expired():
            await interaction.response.send_message("Session expired. Please search again.", ephemeral=True)
            return
            
        # Defer response since API call may take time
        await interaction.response.defer()
        
        new_page = session.current_page + direction
        
        try:
            data = await scryfall_api.search_cards(session.query, page=new_page)
            session.results = data.get('data', [])
            session.has_more = data.get('has_more', False)
            session.current_page = new_page
            
            embed = create_search_embed(session.query, session.results, new_page)
            
            # Update button states
            self.prev_button.disabled = (new_page == 1)
            self.next_button.disabled = not session.has_more
            
            await interaction.edit_original_response(embed=embed, view=self)
            
        except Exception as e:
            await interaction.followup.send(f"Error loading page: {str(e)}", ephemeral=True)
            
    async def on_timeout(self):
        # Clean up expired session
        if self.session_id in pagination_sessions:
            del pagination_sessions[self.session_id]

def create_search_embed(query: str, cards: list, page: int) -> discord.Embed:
    """Create an embed for search results"""
    embed = discord.Embed(
        title=f"Search: {query}",
        description=f"Page {page}",
        color=0x3498db
    )
    
    for card in cards[:5]:  # Show first 5 cards
        name = card.get('name', 'Unknown')
        mana_cost = card.get('mana_cost', '')
        type_line = card.get('type_line', 'Unknown')
        oracle_text = card.get('oracle_text', 'No text')[:100] + '...' if len(card.get('oracle_text', '')) > 100 else card.get('oracle_text', 'No text')
        
        value = f"{mana_cost}\n*{type_line}*\n{oracle_text}"
        embed.add_field(name=name, value=value, inline=False)
        
    return embed

def create_card_embed(card: Dict[str, Any]) -> discord.Embed:
    """Create a rich embed for a single card"""
    embed = discord.Embed(
        title=card.get('name', 'Unknown'),
        description=f"{card.get('mana_cost', '')}\n*{card.get('type_line', 'Unknown')}*",
        color=0x9b59b6
    )
    
    # Handle dual-faced cards
    if 'card_faces' in card:
        for i, face in enumerate(card['card_faces']):
            face_text = face.get('oracle_text', 'No text')
            if len(face_text) > 500:
                face_text = face_text[:500] + '...'
            embed.add_field(
                name=f"Face {i+1}: {face.get('name', 'Unknown')}",
                value=f"{face.get('mana_cost', '')}\n{face_text}",
                inline=False
            )
    else:
        oracle_text = card.get('oracle_text', 'No text')
        if len(oracle_text) > 1000:
            oracle_text = oracle_text[:1000] + '...'
        embed.add_field(name="Text", value=oracle_text, inline=False)
    
    # Add image if available
    image_url = card.get('image_uris', {}).get('normal')
    if image_url:
        embed.set_image(url=image_url)
    elif 'card_faces' in card and card['card_faces']:
        image_url = card['card_faces'][0].get('image_uris', {}).get('normal')
        if image_url:
            embed.set_image(url=image_url)
    
    embed.set_footer(text=f"Set: {card.get('set_name', 'Unknown')} | ID: {card.get('id', 'N/A')}")
    return embed

class SearchCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        
    async def cog_unload(self):
        await scryfall_api.close()
    
    @app_commands.command(name="search", description="Search for Magic cards on Scryfall")
    @app_commands.describe(query="Card name or search query")
    async def search(self, interaction: discord.Interaction, query: str):
        """Search for cards and display with pagination"""
        # Defer immediately to avoid 3-second timeout
        await interaction.response.defer()
        
        try:
            data = await scryfall_api.search_cards(query)
            cards = data.get('data', [])
            
            if not cards:
                await interaction.followup.send("No cards found for that query.")
                return
            
            # Create pagination session
            session_id = f"{interaction.user.id}:{interaction.id}"
            session = PaginationSession(
                query=query,
                results=cards,
                has_more=data.get('has_more', False),
                next_page=data.get('next_page')
            )
            pagination_sessions[session_id] = session
            
            # Create embed and view
            embed = create_search_embed(query, cards, 1)
            view = PaginationView(session_id)
            view.next_button.disabled = not session.has_more
            
            await interaction.followup.send(embed=embed, view=view)
            
        except Exception as e:
            await interaction.followup.send(f"Error searching cards: {str(e)}", ephemeral=True)
    
    @search.autocomplete('query')
    async def search_autocomplete(self, interaction: discord.Interaction, current: str) -> list:
        """Autocomplete card names from Scryfall"""
        if len(current) < 2:
            return []
        
        try:
            suggestions = await scryfall_api.autocomplete_cards(current)
            return [
                app_commands.Choice(name=name[:100], value=name[:100])
                for name in suggestions[:25]  # Discord limits to 25 choices
            ]
        except Exception:
            return []
    
    @app_commands.command(name="card", description="Get detailed info about a specific card")
    @app_commands.describe(name="Exact card name")
    async def card(self, interaction: discord.Interaction, name: str):
        """Get detailed card information"""
        await interaction.response.defer()
        
        try:
            data = await scryfall_api.search_cards(f'!"{name}"')  # Exact name match
            cards = data.get('data', [])
            
            if not cards:
                await interaction.followup.send(f"Card '{name}' not found.")
                return
            
            embed = create_card_embed(cards[0])
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(f"Error fetching card: {str(e)}", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(SearchCog(bot))