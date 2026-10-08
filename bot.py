import os
import sqlite3
import secrets
import requests
from urllib.parse import quote
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

TOKEN = os.getenv("BOT_TOKEN")
VPLINK_API_TOKEN = os.getenv("VPLINK_API_TOKEN")
ADMIN_ID = 8491323757

FORCE_CHANNELS = [
    ("Freee Movies Club", "@Freee_Movies_Club", "https://t.me/Freee_Movies_Club"),
    ("Free Books PDF Hub", "@Free_books_pdf_hub", "https://t.me/Free_books_pdf_hub"),
]

# GitHub Pages URL for the FILEHUB landing page.
FILEHUB_URL = "https://pravaltiwari8-hub.github.io/dpbooks/"

DB_PATH = "/data/files.db" if os.path.isdir("/data") else "files.db"
db = sqlite3.connect(DB_PATH, check_same_thread=False)
db.execute("""CREATE TABLE IF NOT EXISTS files (
    code TEXT PRIMARY KEY,
    file_id TEXT NOT NULL,
    name TEXT
)""")
db.commit()


def make_vplink(url):
    response = requests.get(
        "https://vplink.in/api",
        params={"api": VPLINK_API_TOKEN, "url": url, "format": "json"},
        timeout=20,
    )
    data = response.json()
    if data.get("status") == "success":
        return data["shortenedUrl"]
    raise Exception(data.get("message", "VPLINK error"))


async def is_member(bot, user_id, channel_username):
    try:
        member = await bot.get_chat_member(
            chat_id=channel_username,
            user_id=user_id,
        )
        if member.status in ("member", "administrator", "creator"):
            return True
        if member.status == "restricted" and getattr(member, "is_member", False):
            return True
        return False
    except TelegramError:
        return False


async def all_channels_joined(bot, user_id):
    for _, channel_username, _ in FORCE_CHANNELS:
        if not await is_member(bot, user_id, channel_username):
            return False
    return True


def join_keyboard(code):
    buttons = [
        [InlineKeyboardButton(name, url=url)]
        for name, _, url in FORCE_CHANNELS
    ]
    buttons.append([
        InlineKeyboardButton("I Joined ✅", callback_data=f"check:{code}")
    ])
    return InlineKeyboardMarkup(buttons)


async def send_file(message, file_id, name):
    await message.reply_document(document=file_id, caption=name)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        code = context.args[0]
        result = db.execute(
            "SELECT file_id, name FROM files WHERE code = ?", (code,)
        ).fetchone()

        if not result:
            await update.message.reply_text("Invalid or expired code.")
            return

        user_id = update.effective_user.id
        joined = await all_channels_joined(context.bot, user_id)

        if joined:
            file_id, name = result
            await send_file(update.message, file_id, name)
        else:
            await update.message.reply_text(
                "🔒 File is locked.\n\n"
                "Pehle dono channels join karein, phir neeche "
                '"I Joined ✅" button dabayein.',
                reply_markup=join_keyboard(code),
            )
    else:
        await update.message.reply_text("Welcome! Send me your file.")


async def check_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not query.data or not query.data.startswith("check:"):
        return

    code = query.data.split(":", 1)[1]
    result = db.execute(
        "SELECT file_id, name FROM files WHERE code = ?", (code,)
    ).fetchone()

    if not result:
        await query.message.reply_text("Invalid or expired code.")
        return

    user_id = query.from_user.id
    joined = await all_channels_joined(context.bot, user_id)

    if joined:
        file_id, name = result
        await send_file(query.message, file_id, name)
    else:
        await query.message.reply_text(
            "❌ Abhi dono channels join nahi hue hain.\n"
            'Dono ko join karke phir "I Joined ✅" dabayein.',
            reply_markup=join_keyboard(code),
        )


async def save_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    message = update.message
    if not message:
        return

    file_id = None
    name = None

    if message.document:
        file_id = message.document.file_id
        name = message.document.file_name or "File"
    elif message.video:
        file_id = message.video.file_id
        name = message.video.file_name or "Video"
    else:
        return

    code = secrets.token_urlsafe(6)
    db.execute(
        "INSERT INTO files (code, file_id, name) VALUES (?, ?, ?)",
        (code, file_id, name),
    )
    db.commit()

    direct_link = f"https://t.me/Free_books_study_material_bot?start={code}"

    try:
        short_link = make_vplink(direct_link)
        filehub_link = FILEHUB_URL + "?url=" + quote(short_link, safe="")

        await message.reply_text(
            f"File saved successfully!\n\n"
            f"FILEHUB:\n{filehub_link}\n\n"
            f"VPLINK:\n{short_link}\n\n"
            f"Direct link:\n{direct_link}"
        )
    except Exception as e:
        await message.reply_text(
            f"File saved successfully!\n\n"
            f"VPLINK error: {e}\n\n"
            f"Direct link:\n{direct_link}"
        )


def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN is not set")

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(check_join, pattern=r"^check:"))
    app.add_handler(
        MessageHandler(
            filters.Document.ALL | filters.VIDEO,
            save_file,
        )
    )

    print("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
