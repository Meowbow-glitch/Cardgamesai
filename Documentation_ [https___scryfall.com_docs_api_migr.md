<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# Documentation: [https://scryfall.com/docs/api/migrations](https://scryfall.com/docs/api/migrations)

[https://docs.discord.com/developers/reference](https://docs.discord.com/developers/reference)
Create a plan for the creation of an app which allows users to import "cards" from Scryfall.com.
This app should:

1) Allow users to search for cards from Scryfall and import them into a collection
2) Be made in python
3) interact with discord

The plan should be made in the following manner:

- Break into clearly defined Hard, Medium, and Easy chunks.
- Clearly list any potential problems for review.
- Uses the provided documentation.

Here is a comprehensive development plan for a Python-based Discord bot that integrates with the Scryfall API.

***

# Scryfall Discord Bot — Development Plan

## Architecture Overview

The app will be a Python Discord bot (`discord.py` v2.0+) using slash commands  to let users search for Magic: The Gathering cards via the Scryfall REST API (`https://api.scryfall.com`)  and import them into a per-user collection stored in a local database.[^1][^2]

***

## ⚙️ Tech Stack

| Component | Tool |
| :-- | :-- |
| Discord integration | `discord.py` v2.0+ (slash commands via `app_commands`) [^3] |
| Scryfall API | `requests` or the `scrython` wrapper library [^4] |
| Local storage | `SQLite` via `aiosqlite` for async support |
| Auth | Discord Bot Token (via `Authorization: Bot <TOKEN>` header) |
| Rate limiting | Scryfall: max 10 req/s; enforced via `asyncio.sleep` [^4] |


***

## 🟢 Easy Tasks

These are well-documented, low-risk, and can be completed quickly.

- **Project scaffolding** — Set up the Python project with a `requirements.txt` (discord.py, requests/scrython, aiosqlite), `.env` for secrets, and a basic `main.py` bot entrypoint[^3]
- **Bot registration** — Create a Discord application and Bot user via the Developer Portal; set up `Authorization: Bot <TOKEN>` header usage
- **`/ping` health-check command** — A basic slash command (`@bot.tree.command`) as a connectivity smoke test[^2]
- **Scryfall card search wrapper** — A simple `GET https://api.scryfall.com/cards/search?q=<query>` call returning a paginated list of up to 175 cards[^5]
- **Discord Rich Embed card display** — Format a card's name, mana cost, type line, oracle text, and image as a Discord Embed object with `attachment://` image support
- **Read-only collection view** — A `/collection` slash command that fetches and displays a user's saved cards from the SQLite DB

***

## 🟡 Medium Tasks

These require integration between systems or moderately complex logic.

- **`/search` slash command** — Accept a query string, call the Scryfall `cards/search` endpoint, paginate results, and present the first page as an embed with "Next / Prev" Discord UI buttons[^5]
- **`/import` command with card selection** — Allow users to pick a card from search results (via a Discord Select Menu component) and write it to their personal collection table in SQLite
- **Collection schema design** — Create a DB schema with `users`, `collections`, and `cards` tables; cards store the Scryfall `id` (UUID), name, set code, and collector number as canonical identifiers[^6]
- **Migration reconciliation** — Periodically query `https://api.scryfall.com/migrations` and apply `merge` or `delete` strategies against stored Scryfall IDs: update old UUIDs on `merge`, soft-delete records on `delete`[^1]
- **Rate-limit handling** — Respect Scryfall's 10 req/s tiered rate limits  using an `asyncio.Semaphore` or token bucket pattern; handle Discord's own rate-limit headers from the API[^4]
- **Per-user collection isolation** — Use Discord Snowflake IDs (returned as strings)  as the user identifier in the DB to ensure collections are scoped correctly per user

***

## 🔴 Hard Tasks

These involve the most complexity, edge cases, and architectural decisions.

- **Full pagination UX for search results** — Implementing stateful "Next/Prev" navigation using Discord's Button interactions requires persisting ephemeral session state (in-memory dict keyed to interaction ID since `localStorage` is unavailable), handling interaction token expiry (15 min TTL), and re-querying Scryfall's `has_more` + `next_page` fields[^5]
- **Autocomplete for card names** — Using Discord's `app_commands.autocomplete` to call `https://api.scryfall.com/cards/autocomplete?q=<partial>` in real-time as users type; must handle debouncing and the 10 req/s Scryfall limit[^4]
- **Cog-based modular architecture** — Splitting commands into `discord.ext.commands.Cog` classes (SearchCog, CollectionCog, MigrationCog) with proper dependency injection for the DB and API clients[^3]
- **Automated migration sync** — A background `asyncio` task using `discord.ext.tasks` that polls the migrations endpoint, compares `performed_at` timestamps, and updates the DB without user intervention[^1]
- **Deployment \& persistence** — Containerizing with Docker, managing environment secrets, and ensuring SQLite is on a persistent volume (or migrating to PostgreSQL for multi-server scalability)

***

## ⚠️ Potential Problems for Review

These are the highest-risk issues to address before or during development.

- **Scryfall ID instability** — Scryfall UUIDs can be invalidated via the migrations system. If the bot stores card UUIDs without a migration sync routine, user collections can silently reference deleted or replaced cards. A migration check must be built early, not retrofitted.[^1]
- **Discord interaction token expiry** — Slash command interaction tokens expire after **3 seconds** for initial response and **15 minutes** for follow-up edits . Long Scryfall API calls (especially bulk fetches) risk missing this window; use `interaction.response.defer()` immediately before any API call.
- **Scryfall rate limits** — At 10 req/s, a burst of users simultaneously searching will hit the ceiling quickly. A shared async rate limiter (not per-user) is essential and should be designed upfront.[^4]
- **Discord ID serialization** — Discord Snowflake IDs must always be stored as strings (not integers), as they exceed JavaScript's safe integer range and are serialized as strings by Discord's API . Using Python `int` in the DB for user IDs will cause lookup failures.
- **Dual-print card handling** — Cards with two faces (e.g., MDFCs, transform cards) have split image URIs in the Scryfall response (`card_faces` array). The embed builder must handle this case explicitly or it will error on roughly 10–15% of cards.[^6]
- **Discord API versioning** — Only API versions 9 and 10 are currently active ; v8 is deprecated and v7 and below are discontinued. Ensure `discord.py` v2.0+ targets v10 by default and that no library code pins an older version.
- **`discord.py` vs `nextcord`/`py-cord` fragmentation** — The Python Discord library ecosystem is fragmented. Commit to one library (`discord.py` 2.0+) and document this clearly to avoid dependency conflicts during team onboarding.
<span style="display:none">[^10][^11][^12][^13][^14][^15][^7][^8][^9]</span>

<div align="center">⁂</div>

[^1]: https://scryfall.com/docs/api

[^2]: https://stackoverflow.com/questions/71165431/how-do-i-make-a-working-slash-command-in-discord-py

[^3]: https://www.pythondiscord.com/pages/guides/python-guides/app-commands/

[^4]: https://github.com/NandaScott/Scrython

[^5]: https://scryfall.com/docs/api/cards/search

[^6]: https://scryfall.com/docs/api/cards

[^7]: https://www.reddit.com/r/magicTCG/comments/rg0v4p/scryfall_api_question/

[^8]: https://stackoverflow.com/questions/78328743/recieve-json-data-from-an-api-and-extract-the-information-for-later-use

[^9]: http://goldieanalytics.com/articles/scryfall1.html

[^10]: https://pypi.org/project/discord-py-slash-command/

[^11]: https://apify.com/parseforge/scryfall-mtg-scraper/api/python

[^12]: https://github.com/dolfies/discord.py-self/discussions/705

[^13]: https://pypi.org/project/scrython/

[^14]: https://discordpy.readthedocs.io/en/stable/ext/commands/commands.html

[^15]: https://scryfall.com/blog/api-all-cards-and-mana-parsing-endpoints-128

