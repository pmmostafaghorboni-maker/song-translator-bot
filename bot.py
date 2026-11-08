import os
import threading
from flask import Flask
import psycopg2
from datetime import datetime, timedelta
from telegram import Update, LabeledPrice, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, MessageHandler, filters, ContextTypes,
    CommandHandler, PreCheckoutQueryHandler, CallbackQueryHandler
)
from google import genai

# ==========================================
# تنظیمات و متغیرها
# ==========================================
app = Flask(__name__)

BOT_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))
DATABASE_URL = os.environ.get("DATABASE_URL")

CARD_NUMBER = "5859-8318-0259-8994"
CARD_HOLDER = "مصطفی قربانی"

client_ai = genai.Client(api_key=GEMINI_API_KEY)

# ==========================================
# توابع دیتابیس
# ==========================================
def get_db_connection():
    return psycopg2.connect(DATABASE_URL, sslmode='require')

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS subscriptions (user_id BIGINT PRIMARY KEY, expiry_date TIMESTAMP NOT NULL)")
    cur.execute("CREATE TABLE IF NOT EXISTS free_usage (user_id BIGINT PRIMARY KEY, usage_count INTEGER NOT NULL DEFAULT 0)")
    conn.commit()
    cur.close()
    conn.close()

def check_subscription(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT expiry_date FROM subscriptions WHERE user_id = %s", (user_id,))
    result = cur.fetchone()
    cur.close()
    conn.close()
    return result and result[0] > datetime.now()

def get_free_usage(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT usage_count FROM free_usage WHERE user_id = %s", (user_id,))
    result = cur.fetchone()
    cur.close()
    conn.close()
    return result[0] if result else 0

def increment_free_usage(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO free_usage (user_id, usage_count) VALUES (%s, 1) ON CONFLICT (user_id) DO UPDATE SET usage_count = free_usage.usage_count + 1", (user_id,))
    conn.commit()
    cur.close()
    conn.close()

def activate_subscription(user_id, days=30):
    expiry = datetime.now() + timedelta(days=days)
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO subscriptions (user_id, expiry_date) VALUES (%s, %s) ON CONFLICT (user_id) DO UPDATE SET expiry_date = %s", (user_id, expiry, expiry))
    conn.commit()
    cur.close()
    conn.close()

# ==========================================
# منطق ربات تلگرام
# ==========================================
async def show_payment_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("⭐ پرداخت با ستاره", callback_data="pay_stars"), InlineKeyboardButton("💳 کارت به کارت", callback_data="pay_gateway")]]
    text = "شما به سقف استفاده رایگان (۲ آهنگ) رسیده‌اید.\nبرای ادامه، یکی از روش‌های پرداخت را انتخاب کنید:"
    if update.callback_query:
        await update.callback_query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "pay_stars":
        await query.message.reply_invoice(title="اشتراک", description="دسترسی نامحدود", payload="sub", provider_token="", currency="XTR", prices=[LabeledPrice(label="اشتراک", amount=100)])
    elif query.data == "pay_gateway":
        await query.message.reply_text(f"💳 **پرداخت کارت به کارت**\n\nمبلغ: **۵۰,۰۰۰ تومان**\nشماره کارت: `{CARD_NUMBER}`\nبه نام: **{CARD_HOLDER}**\n\nعکس رسید را بفرستید.", parse_mode='Markdown')
        context.user_data['awaiting_receipt'] = True
    elif query.data.startswith("approve_") or query.data.startswith("reject_"):
        if query.from_user.id != ADMIN_ID: return
        action, target = query.data.split("_")
        target = int(target)
        if action == "approve":
            activate_subscription(target)
            await context.bot.send_message(chat_id=target, text="✅ اشتراک فعال شد.")
            await query.edit_message_text("✅ تایید شد.")
        else:
            await context.bot.send_message(chat_id=target, text="❌ پرداخت تایید نشد.")
            await query.edit_message_text("❌ رد شد.")

async def handle_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('awaiting_receipt'): return
    user_id = update.effective_user.id
    if update.message.photo:
        await context.bot.send_photo(chat_id=ADMIN_ID, photo=update.message.photo[-1].file_id, caption=f"رسید از: {user_id}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ تایید", callback_data=f"approve_{user_id}"), InlineKeyboardButton("❌ رد", callback_data=f"reject_{user_id}")]]))
    context.user_data['awaiting_receipt'] = False
    await update.message.reply_text("رسید ارسال شد.")

async def subscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_payment_options(update, context)

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    activate_subscription(update.effective_user.id)
    await update.message.reply_text("✅ اشتراک فعال شد.")

async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not check_subscription(user_id):
        usage = get_free_usage(user_id)
        if usage >= 2:
            await show_payment_options(update, context)
            return
        increment_free_usage(user_id)
        await update.message.reply_text(f"{2 - (usage + 1)} آهنگ رایگان باقی مانده.")
    
    audio = update.message.audio or update.message.voice
    if not audio: return
    file = await context.bot.get_file(audio.file_id)
    path = f"temp_{update.message.message_id}.mp3"
    await file.download_to_drive(path)
    await update.message.reply_text("در حال پردازش...")
    try:
        uploaded = client_ai.files.upload(file=path)
        res = client_ai.models.generate_content(model='gemini-2.5-flash', contents=["متن انگلیسی را بنویس و به فارسی ترجمه کن.", uploaded])
        await update.message.reply_text(res.text)
    except Exception as e:
        await update.message.reply_text(f"خطا: {e}")
    finally:
        if os.path.exists(path): os.remove(path)

# ==========================================
# راه‌اندازی ربات و وب‌سرور
# ==========================================
def start_bot():
    print(">>> BOT STARTING...")
    init_db()
    app_bot = ApplicationBuilder().token(BOT_TOKEN).build()
    app_bot.add_handler(CommandHandler("subscribe", subscribe_command))
    app_bot.add_handler(CallbackQueryHandler(button_callback))
    app_bot.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    app_bot.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
    app_bot.add_handler(MessageHandler(filters.AUDIO | filters.VOICE, handle_audio))
    app_bot.add_handler(MessageHandler(filters.PHOTO | (filters.TEXT & ~filters.COMMAND), handle_receipt))
    print(">>> BOT STARTED.")
    app_bot.run_polling()

@app.route('/')
def home(): return "Bot is running!"
@app.route('/health')
def health(): return "OK"

if __name__ == '__main__':
    threading.Thread(target=start_bot, daemon=True).start()
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
