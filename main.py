import asyncio
import random
import aiohttp

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.exceptions import TelegramBadRequest


# =========================
# НАСТРОЙКИ
# =========================

TOKEN = "8205786674:AAF0JYnQBU7F6-hXQ0eqjYoJZyxAFhlxKsA"
SEARCH_LIMIT = 5
JSON_TIMEOUT = 10

bot = Bot(token="8205786674:AAF0JYnQBU7F6-hXQ0eqjYoJZyxAFhlxKsA")
dp = Dispatcher()

session: aiohttp.ClientSession | None = None

# кеш и сессии пользователей
cache = {}
user_sessions = {}


# =========================
# HTTP
# =========================

async def fetch_json(url: str, params: dict | None = None):
    try:
        async with session.get(
            url,
            params=params,
            timeout=aiohttp.ClientTimeout(total=JSON_TIMEOUT)
        ) as resp:

            if resp.status != 200:
                return None

            return await resp.json(content_type=None)

    except Exception as e:
        print("Fetch error:", e)
        return None


# =========================
# ПОИСК
# =========================

async def search_music(query: str, limit=SEARCH_LIMIT):
    if query in cache:
        return cache[query]

    url = "https://itunes.apple.com/search"
    params = {
        "term": query,
        "entity": "song",
        "limit": limit,
        "country": "US"
    }

    data = await fetch_json(url, params)
    if not data:
        return []

    results = [r for r in data.get("results", []) if r.get("previewUrl")]

    if len(cache) > 100:
        cache.clear()

    cache[query] = results
    return results


async def get_random_tracks(limit=SEARCH_LIMIT):
    terms = ["billboard", "viral hits", "top charts", "trending music"]
    results = await search_music(random.choice(terms), limit=20)

    return random.sample(results, min(limit, len(results))) if results else []


async def get_top_tracks(limit=SEARCH_LIMIT):
    results = await search_music("billboard hot 100", limit=20)
    return results[:limit] if results else []


# =========================
# КНОПКИ ПАГИНАЦИИ
# =========================

def get_pagination_keyboard(user_id: int, index: int, total: int):
    buttons = []

    if index > 0:
        buttons.append(
            InlineKeyboardButton(
                text="⬅️",
                callback_data=f"prev:{user_id}:{index}"
            )
        )

    if index < total - 1:
        buttons.append(
            InlineKeyboardButton(
                text="➡️",
                callback_data=f"next:{user_id}:{index}"
            )
        )

    return InlineKeyboardMarkup(inline_keyboard=[buttons])


# =========================
# ОТПРАВКА ТРЕКА
# =========================

async def send_track_page(message: Message, user_id: int, index: int):
    session_data = user_sessions.get(user_id)
    if not session_data:
        return

    tracks = session_data["tracks"]

    if index < 0 or index >= len(tracks):
        return

    track = tracks[index]

    track_name = track.get("trackName", "Unknown")
    artist_name = track.get("artistName", "Unknown")
    preview_url = track.get("previewUrl")
    artwork = track.get("artworkUrl100")

    caption = f"{track_name}\n{artist_name}"

    try:
        if artwork:
            artwork = artwork.replace("100x100", "600x600")

            await message.answer_photo(
                photo=artwork,
                caption=caption
            )

        if preview_url:
            await message.answer_audio(
                audio=preview_url,
                caption="Preview",
                reply_markup=get_pagination_keyboard(user_id, index, len(tracks))
            )

    except TelegramBadRequest:
        print("Invalid media")
    except Exception as e:
        print("Send error:", e)


# =========================
# CALLBACK ПАГИНАЦИИ
# =========================

@dp.callback_query()
async def pagination_handler(callback: CallbackQuery):
    try:
        action, user_id, index = callback.data.split(":")
        user_id = int(user_id)
        index = int(index)

        if callback.from_user.id != user_id:
            await callback.answer("Это не ваши кнопки (Not your buttons)", show_alert=True)
            return

        if action == "next":
            index += 1
        elif action == "prev":
            index -= 1

        session_data = user_sessions.get(user_id)
        if not session_data:
            return

        tracks = session_data["tracks"]

        if index < 0 or index >= len(tracks):
            return

        try:
            await callback.message.delete()
        except:
            pass

        await send_track_page(callback.message, user_id, index)
        await callback.answer()

    except Exception as e:
        print("Pagination error:", e)


# =========================
# КОМАНДЫ
# =========================

@dp.message(Command("start"))
async def start(message: Message):
    await message.answer(
        "Музыкальный бот (Music Bot)\n\n"
        "Отправь название трека или исполнителя\n"
        "(Send track or artist name)\n\n"
        "Команды (Commands):\n"
        "/track - поиск трека (search track)\n"
        "/artist - поиск исполнителя (search artist)\n"
        "/random - случайные треки (random tracks)\n"
        "/top - топ треков (top tracks)"
    )


@dp.message(Command("track"))
async def track_cmd(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Введите название трека (Enter track name)")
        return

    tracks = await search_music(args[1])

    if not tracks:
        await message.answer("Ничего не найдено (Nothing found)")
        return

    user_sessions[message.from_user.id] = {"tracks": tracks}
    await send_track_page(message, message.from_user.id, 0)


@dp.message(Command("artist"))
async def artist_cmd(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Введите имя исполнителя (Enter artist name)")
        return

    tracks = await search_music(args[1])

    if not tracks:
        await message.answer("Ничего не найдено (Nothing found)")
        return

    user_sessions[message.from_user.id] = {"tracks": tracks}
    await send_track_page(message, message.from_user.id, 0)


@dp.message(Command("random"))
async def random_cmd(message: Message):
    tracks = await get_random_tracks()

    if not tracks:
        await message.answer("Ошибка загрузки треков (Error loading tracks)")
        return

    user_sessions[message.from_user.id] = {"tracks": tracks}
    await send_track_page(message, message.from_user.id, 0)


@dp.message(Command("top"))
async def top_cmd(message: Message):
    tracks = await get_top_tracks()

    if not tracks:
        await message.answer("Топ временно недоступен (Top unavailable)")
        return

    user_sessions[message.from_user.id] = {"tracks": tracks}
    await send_track_page(message, message.from_user.id, 0)


@dp.message()
async def text_search(message: Message):
    if not message.text:
        return

    query = message.text.strip()

    if query.startswith('/'):
        return

    tracks = await search_music(query)

    if not tracks:
        await message.answer("Ничего не найдено (Nothing found)")
        return

    user_sessions[message.from_user.id] = {"tracks": tracks}
    await send_track_page(message, message.from_user.id, 0)


# =========================
# ЗАПУСК
# =========================

async def main():
    global session
    session = aiohttp.ClientSession()

    print("Bot started")

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await session.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())