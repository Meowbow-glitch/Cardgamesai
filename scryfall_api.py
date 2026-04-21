"""
Scryfall API wrapper with rate limiting
"""

import asyncio
import aiohttp
from typing import Optional, Dict, Any, List
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RateLimiter:
    """Token bucket rate limiter for Scryfall API (10 req/s)"""
    def __init__(self, rate: int = 10, per: float = 1.0):
        self.rate = rate
        self.per = per
        self.tokens = rate
        self.updated_at = time.monotonic()
        self._lock = asyncio.Lock()
        
    async def acquire(self):
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.updated_at
            self.tokens = min(self.rate, self.tokens + elapsed * (self.rate / self.per))
            self.updated_at = now
            
            if self.tokens < 1:
                wait_time = (1 - self.tokens) * (self.per / self.rate)
                await asyncio.sleep(wait_time)
                self.tokens = 0
            else:
                self.tokens -= 1

class ScryfallAPI:
    """Scryfall API client with rate limiting and caching"""
    BASE_URL = 'https://api.scryfall.com'
    
    def __init__(self):
        self.rate_limiter = RateLimiter(rate=10, per=1.0)
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
        
    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
            
    async def _request(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Make a rate-limited request to Scryfall API"""
        await self.rate_limiter.acquire()
        
        session = await self._get_session()
        url = f"{self.BASE_URL}{endpoint}"
        
        async with session.get(url, params=params) as response:
            if response.status == 429:
                # Rate limited - wait and retry
                retry_after = int(response.headers.get('Retry-After', 1))
                await asyncio.sleep(retry_after)
                return await self._request(endpoint, params)
                
            response.raise_for_status()
            return await response.json()
    
    async def search_cards(self, query: str, page: int = 1) -> Dict[str, Any]:
        """Search for cards on Scryfall"""
        return await self._request('/cards/search', {
            'q': query,
            'page': page,
            'unique': 'cards'
        })
        
    async def autocomplete_cards(self, query: str) -> List[str]:
        """Get card name autocomplete suggestions"""
        if len(query) < 2:
            return []
        data = await self._request('/cards/autocomplete', {'q': query})
        return data.get('data', [])
        
    async def get_card(self, scryfall_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific card by ID"""
        try:
            return await self._request(f'/cards/{scryfall_id}')
        except aiohttp.ClientResponseError:
            return None
            
    async def get_migrations(self) -> List[Dict[str, Any]]:
        """Get card migrations from Scryfall"""
        data = await self._request('/migrations')
        return data.get('data', [])

# Global API instance
scryfall_api = ScryfallAPI()