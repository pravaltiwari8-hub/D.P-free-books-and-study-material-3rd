import os
import sqlite3
import secrets
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

TOKEN = os.getenv("BOT_TOKEN")
VPLINK_API_TOKEN = os.getenv("VPLINK_API_TOKEN")
ADMIN_ID = 8491323757

DB_PATH = "/data/files.db" if os.path.isdir("/data") else "files.db"
db = sqlite3.connect(DB_PATH, check_same_thread=False)
db.execute("""CREATE TABLE IF NOT EXISTS files (
    code TEXT PRIMARY KEY,
    file_id TEXT NOT NULL,
    name TEXT
)""")
db.commit()

def make_vplink(url):
    response = requests.get("https://vplink.in/api",
        params={"api": VPLINK_API_TOKEN, "url": url, "format": "json"}, timeout=20)
    data = response.json()
    if data.get("status") == "success":
        return data["shortenedUrl"]
    raise Exception(data.get("message", "VPLINK error"))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        code = context.args[0]
        result = db.execute("SELECT file_id, name FROM files WHERE code = ?", (code,)).fetchone()
        if result:
            file_id, name = result
            await update.message.reply_document(document=file_id, caption=name)
        else:
            await update.message.reply_text("Invalid or expired code.")
    else:
        await update.message.reply_text("Welcome! Send me your PDF code.")

async def save_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    doc = update.message.document
    if not doc:
        return
    code = secrets.token_urlsafe(6)
    name = doc.file_name or "PDF"
    db.execute("INSERT INTO files (code, file_id, name) VALUES (?, ?, ?)", (code, doc.file_id, name))
    db.commit()
    direct_link = f"https://t.me/Free_books_study_material_bot?start={code}"
    try:
        short_link = make_vplink(direct_link)
        await update.message.reply_text(f"PDF saved successfully!\n\nVPLINK:\n{short_link}\n\nDirect link:\n{direct_link}")
    except Exception as e:
        await update.message.reply_text(f"PDF saved successfully!\n\nVPLINK error: {e}\n\nDirect link:\n{direct_link}")

def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN is not set")
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.PDF, save_pdf))
    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
