import os
import sqlite3
import secrets
import requests
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


def join_keyboard(code):
    buttons = [
        [InlineKeyboardButton(name, url=url)]
        for name, _, url in FORCE_CHANNELS
    ]
    buttons.append([
        InlineKeyboardButton("I Joined ✅", callback_data=f"check:{code}")
    ])
    return InlineKeyboardMarkup(buttons)


async def send_pdf(update, file_id, name):
    await update.message.reply_document(document=file_id, caption=name)


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
        joined = all(
            await is_member(context.bot, user_id, channel_username)
            for _, channel_username, _ in FORCE_CHANNELS
        )

        if joined:
            file_id, name = result
            await send_pdf(update, file_id, name)
        else:
            await update.message.reply_text(
                "🔒 PDF is locked.\n\n"
                "Pehle dono channels join karein, phir neeche "
                '"I Joined ✅" button dabayein.',
                reply_markup=join_keyboard(code),
            )
    else:
        await update.message.reply_text("Welcome! Send me your PDF code.")


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
    joined = all(
        await is_member(context.bot, user_id, channel_username)
        for _, channel_username, _ in FORCE_CHANNELS
    )

    if joined:
        file_id, name = result
        await query.message.reply_document(document=file_id, caption=name)
    else:
        await query.message.reply_text(
            "❌ Abhi dono channels join nahi hue hain.\n"
            'Dono ko join karke phir "I Joined ✅" dabayein.',
            reply_markup=join_keyboard(code),
        )


async def save_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    doc = update.message.document
    if not doc:
        return

    code = secrets.token_urlsafe(6)
    name = doc.file_name or "PDF"
    db.execute(
        "INSERT INTO files (code, file_id, name) VALUES (?, ?, ?)",
        (code, doc.file_id, name),
    )
    db.commit()

    direct_link = f"https://t.me/Free_books_study_material_bot?start={code}"

    try:
        short_link = make_vplink(direct_link)
        await update.message.reply_text(
            f"PDF saved successfully!\n\n"
            f"VPLINK:\n{short_link}\n\n"
            f"Direct link:\n{direct_link}"
        )
    except Exception as e:
        await update.message.reply_text(
            f"PDF saved successfully!\n\n"
            f"VPLINK error: {e}\n\n"
            f"Direct link:\n{direct_link}"
        )


def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN is not set")

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(check_join, pattern=r"^check:"))
    app.add_handler(MessageHandler(filters.Document.PDF, save_pdf))

    print("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
