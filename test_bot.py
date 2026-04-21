"""
Test script to verify Scryfall bot functionality
Tests: API search, database operations, card insertion
"""

import asyncio
import aiosqlite
import aiohttp
from datetime import datetime

# Test adding "Darkness" card to a test collection

SCRYFALL_BASE_URL = 'https://api.scryfall.com'

class TestScryfallAPI:
    def __init__(self):
        self.session = None
        
    async def _get_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def search_cards(self, query: str):
        session = await self._get_session()
        async with session.get(f"{SCRYFALL_BASE_URL}/cards/search", params={'q': query}) as resp:
            return await resp.json()
    
    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

async def test_database():
    """Test database operations"""
    print("🧪 Testing database...")
    
    # Create test database
    db = await aiosqlite.connect('test_scryfall.db')
    
    # Create tables
    await db.execute('''
        CREATE TABLE IF NOT EXISTS users (
            discord_id TEXT PRIMARY KEY,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    await db.execute('''
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
    await db.commit()
    print("  ✅ Tables created")
    
    return db

async def test_add_darkness():
    """Test adding the 'Darkness' card"""
    print("\n🎴 Testing card 'Darkness' addition...")
    
    api = TestScryfallAPI()
    db = await test_database()
    
    try:
        # Search for Darkness
        print("  🔍 Searching Scryfall API...")
        data = await api.search_cards('!"Darkness"')
        cards = data.get('data', [])
        
        if not cards:
            print("  ❌ Card not found")
            return False
        
        card = cards[0]
        print(f"  ✅ Found: {card['name']} ({card['set'].upper()}) #{card.get('collector_number', 'N/A')}")
        print(f"     Scryfall ID: {card['id']}")
        print(f"     Type: {card.get('type_line', 'N/A')}")
        
        # Simulate adding to collection
        test_user_id = "123456789012345678"  # Fake Discord ID
        
        # Ensure user exists
        await db.execute(
            'INSERT OR IGNORE INTO users (discord_id) VALUES (?)',
            (test_user_id,)
        )
        
        # Check if already in collection
        async with db.execute(
            'SELECT id FROM collections WHERE user_id = ? AND scryfall_id = ?',
            (test_user_id, card['id'])
        ) as cursor:
            existing = await cursor.fetchone()
            if existing:
                print(f"  ⚠️  Card already in collection")
            else:
                # Add to collection
                await db.execute(
                    '''INSERT INTO collections 
                       (user_id, scryfall_id, name, set_code, collector_number) 
                       VALUES (?, ?, ?, ?, ?)''',
                    (test_user_id, card['id'], card['name'], 
                     card.get('set', ''), card.get('collector_number', ''))
                )
                await db.commit()
                print(f"  ✅ Added '{card['name']}' to test collection!")
        
        # Verify collection
        async with db.execute(
            'SELECT name, set_code, collector_number FROM collections WHERE user_id = ?',
            (test_user_id,)
        ) as cursor:
            collection = await cursor.fetchall()
            print(f"\n  📚 Collection now has {len(collection)} card(s):")
            for name, set_code, num in collection:
                print(f"     - {name} ({set_code.upper()}) #{num}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        await api.close()
        await db.close()
        # Clean up test database
        import os
        if os.path.exists('test_scryfall.db'):
            os.remove('test_scryfall.db')
            print("\n  🗑️  Cleaned up test database")

async def main():
    print("=" * 60)
    print("SCRYFALL BOT TEST SUITE")
    print("=" * 60)
    
    success = await test_add_darkness()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ ALL TESTS PASSED")
    else:
        print("❌ TESTS FAILED")
    print("=" * 60)

if __name__ == '__main__':
    asyncio.run(main())
