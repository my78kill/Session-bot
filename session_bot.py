import os
import threading
from flask import Flask
from telethon import TelegramClient, errors
from telethon.sessions import StringSession
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ================= CONFIG =================
BOT_TOKEN = os.environ.get("BOT_TOKEN")  # Render ENV
PORT = int(os.environ.get("PORT", 10000))
# =========================================

# Flask app (Render port bind)
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running"

# States
ASK_API_ID = 1
ASK_API_HASH = 2
ASK_PHONE = 3
ASK_OTP = 4
ASK_2FA = 5

USER_STATE = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return

    USER_STATE[update.effective_user.id] = {
        "state": ASK_API_ID
    }

    await update.message.reply_text(
        "👋 *Session String Generator*\n\n"
        "Step 1️⃣ Send your **API ID**\n\n"
        "/cancel to stop",
        parse_mode="Markdown"
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = USER_STATE.pop(update.effective_user.id, None)

    if data and "client" in data:
        try:
            await data["client"].disconnect()
        except:
            pass

    await update.message.reply_text("❌ Process cancelled.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if user_id not in USER_STATE:
        return

    data = USER_STATE[user_id]
    state = data["state"]

    # API ID
    if state == ASK_API_ID:
        if not text.isdigit():
            await update.message.reply_text("❌ API ID number hota hai.")
            return
        data["api_id"] = int(text)
        data["state"] = ASK_API_HASH
        await update.message.reply_text("Step 2️⃣ Send your **API HASH**")

    # API HASH
    elif state == ASK_API_HASH:
        data["api_hash"] = text
        data["state"] = ASK_PHONE
        await update.message.reply_text(
            "Step 3️⃣ Send your **phone number**\nExample: `+919xxxxxxxxx`",
            parse_mode="Markdown"
        )

    # PHONE
    elif state == ASK_PHONE:
        data["phone"] = text
        data["state"] = ASK_OTP
        await update.message.reply_text("📩 Sending OTP...")
        await send_otp(update, data)

    # OTP
    elif state == ASK_OTP:
        try:
            await update.message.delete()
        except:
            pass

        data["otp"] = text.replace(" ", "")
        await try_signin(update, data)

    # 2FA PASSWORD
    elif state == ASK_2FA:
        try:
            await update.message.delete()
        except:
            pass

        data["password"] = text
        await signin_with_2fa(update, data)


async def send_otp(update, data):
    client = TelegramClient(
        StringSession(),
        data["api_id"],
        data["api_hash"]
    )
    await client.connect()
    await client.send_code_request(data["phone"])
    data["client"] = client

    await update.message.reply_text(
        "✅ OTP sent\n\nStep 4️⃣ Send OTP",
        parse_mode="Markdown"
    )


async def try_signin(update, data):
    client = data["client"]
    try:
        await client.sign_in(data["phone"], data["otp"])
        await send_session(update, data)

    except errors.SessionPasswordNeededError:
        data["state"] = ASK_2FA
        await update.message.reply_text(
            "🔐 *2FA Enabled*\nSend your **2FA password**",
            parse_mode="Markdown"
        )

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")
        await cleanup(update, data)


async def signin_with_2fa(update, data):
    try:
        await data["client"].sign_in(password=data["password"])
        await send_session(update, data)
    except Exception as e:
        await update.message.reply_text(f"❌ 2FA Error: {e}")
        await cleanup(update, data)


async def send_session(update, data):
    session_string = data["client"].session.save()

    await update.message.reply_text(
        "🎉 *Session Generated Successfully!*\n\n"
        f"`{session_string}`\n\n"
        "⚠️ **Never share this session**",
        parse_mode="Markdown"
    )
    await cleanup(update, data)


async def cleanup(update, data):
    try:
        await data["client"].disconnect()
    except:
        pass
    USER_STATE.pop(update.effective_user.id, None)


def run_bot():
    tg_app = ApplicationBuilder().token(BOT_TOKEN).build()

    tg_app.add_handler(CommandHandler("start", start))
    tg_app.add_handler(CommandHandler("cancel", cancel))
    tg_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Telegram bot started...")
    tg_app.run_polling()


if __name__ == "__main__":
    # Direct run bot first in main thread
    run_bot()  # now polling runs in main thread, no thread freeze

    # Flask optional for Render port (can comment out if not needed)
    # app.run(host="0.0.0.0", port=PORT)
