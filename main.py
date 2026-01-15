from aiogram import Bot, Dispatcher, types, filters, exceptions
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from cachetools import TTLCache
from math import ceil
from itertools import batched
import asyncio, requests, os, datetime

ACTIVE_KEYBOARDS: TTLCache[int, tuple[int, str, dict]] = TTLCache(maxsize=2048, ttl=60)
API = "https://qobuz.squid.wtf/api"
PAGE_LIMIT = 10

if not os.path.exists("tracks"):
    os.mkdir("tracks")

#session = AiohttpSession(
#    proxy="http://localhost:10808"
#)

bot = Bot(
    open("token", "r").readline(),
#    session,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()

def search(query: str, page: int = 0) -> dict | requests.Response:
    offset = page * PAGE_LIMIT
    req = requests.get(f"{API}/get-music?q={query}&offset={offset}")
    
    if not req.ok:
        return req
    
    return req.json()["data"]["tracks"]

def parse_result(result: dict, page: int = 0) -> tuple[str, types.InlineKeyboardMarkup]:
    track_format = "<b>%i</b>. <code>%s</code> - <code>%s</code>\n⏱️ %s"
    
    texts = []
    buttons = []

    for i, v in enumerate(result["items"]):
        i += 1
        texts.append(track_format % (
            i,
            v["title"],
            v["performer"]["name"],
            datetime.timedelta(seconds=float(v["duration"])))
        )
        buttons.append(types.InlineKeyboardButton(
            text=str(i),
            callback_data=f"d{v["id"]}"
        ))

    total_pages = ceil(result["total"] / PAGE_LIMIT)

    texts = "\n".join(texts)
    buttons = [list(i) for i in batched(buttons, 3)]

    arrows = []
    if page > 0:
        arrows.append(types.InlineKeyboardButton(
            text="⬅️",
            callback_data=f"p{page - 1}"
        ))

    if page + 1 < total_pages:
        arrows.append(types.InlineKeyboardButton(
            text="➡️",
            callback_data=f"p{page + 1}"
        ))
    
    if len(arrows) > 0: buttons.append(arrows)

    keyboard = types.InlineKeyboardMarkup(inline_keyboard=buttons)

    return f"📃 Page {page + 1}/{total_pages}\n{texts}", keyboard

@dp.message(filters.Command("search"))
async def search_command(msg: types.Message, command: filters.CommandObject):
    if msg.from_user == None:
        return
    
    query = command.args
    if not query:
        return await msg.reply("❌ <b>No query provided!</b>\nUsage: <code>/search </code>query")

    botmsg = await msg.reply(f"🔍 Searching for <code>{query}</code>...")
    result = search(query)
    if isinstance(result, requests.Response):
        return await botmsg.edit_text(f"❌ <b>API Error</b> ({result.status_code}): {result.text}")
    
    parsed = parse_result(result)
    await botmsg.edit_text(parsed[0], reply_markup=parsed[1])
    ACTIVE_KEYBOARDS[botmsg.message_id] = (msg.from_user.id, query, result)

@dp.callback_query()
async def on_callback_query(query: types.CallbackQuery):
    if query.message == None or query.data == None:
        return
    
    if query.message.message_id not in ACTIVE_KEYBOARDS:
        return await query.answer("❌ Keyboard is inactive, send command!", True)
    
    query_data = ACTIVE_KEYBOARDS[query.message.message_id]
    if query_data[0] != query.from_user.id:
        return await query.answer("❌ This isn't your keyboard!", True)
    
    if query.data.startswith("p"):
        if isinstance(query.message, types.InaccessibleMessage):
            return await query.answer("❌ Message isn't accessible, send command!", True)

        page = int(query.data[1:])
        track_query: str = query_data[1]
        result = search(track_query, page)
        if isinstance(result, requests.Response):
            return await query.message.edit_text(f"❌ <b>API Error</b> ({result.status_code}): {result.text}")
        
        parsed = parse_result(result, page)
        await query.message.edit_text(parsed[0], reply_markup=parsed[1])

        ACTIVE_KEYBOARDS[query.message.message_id] = (query.from_user.id, track_query, result)
    elif query.data.startswith("d"):
        track_id = query.data[1:]
        track_data = query_data[2]["items"]
        
        track_data = next((track for track in track_data if str(track["id"]) == track_id), None)
        if track_data == None:
            return await query.answer("❌ Track not found, send command!", True)

        botmsg = await query.message.reply(f"📩 Downloading <code>{track_data["title"]}</code>...")
        path = f"tracks/{track_id}.flac"

        result = requests.get(f"{API}/download-music?track_id={track_id}&quality=27")
        if not result.ok:
            return await botmsg.edit_text(f"❌ <b>API Error</b> ({result.status_code}): {result.text}")
            
        trackurl = result.json()["data"]["url"]
        
        if not os.path.exists(path):
            track = requests.get(trackurl)
            if not track.ok:
                return await botmsg.edit_text(f"❌ <b>Download Error</b> ({track.status_code}): {track.text}")
            
            with open(path, "wb") as f:
                f.write(track.content)

        await botmsg.edit_text("📨 Uploading...")

        try:
            await botmsg.edit_media(types.InputMediaAudio(
                media=types.FSInputFile(path),
                thumbnail=types.URLInputFile(track_data["album"]["image"]["small"]),
                duration=int(track_data["duration"]),
                performer=track_data["performer"]["name"],
                title=track_data["title"]
            ))
        except exceptions.TelegramEntityTooLarge:
            await botmsg.edit_text(
                f"❌ Telegram error: file is too large!",
                reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[
                    types.InlineKeyboardButton(
                        text="Download",
                        url=trackurl
                    )
                ]])
            )

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
