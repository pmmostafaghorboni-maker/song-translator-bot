import os
from datetime import datetime, timedelta
from telegram import Update, LabeledPrice, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, MessageHandler, filters, ContextTypes,
    CommandHandler, PreCheckoutQueryHandler, CallbackQueryHandler
)
from openai import OpenAI

# ==========================================
# ⚠️ این سه خط را با اطلاعات خودت پر کن
# ==========================================
BOT_TOKEN = "9029644547:AAEgCSzhllezoV6jiJtXk4YlCG2U-OxrT5U"
OPENAI_API_KEY = "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"
ADMIN_ID = 6600182795  # آیدی عددی خودت (با ربات @userinfobot بگیر)

# اطلاعات کارت برای پرداخت دستی
CARD_NUMBER = "5859-8318-0259-8994" # شماره کارت خودت
CARD_HOLDER = " مصطفی قربانی"               # نام و نام خانوادگی صاحب کارت
# ==========================================

client = OpenAI(api_key=OPENAI_API_KEY)

user_subscriptions = {}
user_free_usage = {}

def check_subscription(user_id):
    exp_date = user_subscriptions.get(user_id)
    if exp_date and exp_date > datetime.now():
        return True
    return False

async def show_payment_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("⭐ پرداخت با ستاره تلگرام", callback_data="pay_stars"),
            InlineKeyboardButton("💳 پرداخت با کارت (کارت به کارت)", callback_data="pay_gateway")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "شما به سقف استفاده رایگان (۲ آهنگ) رسیده‌اید.\nبرای ادامه، یکی از روش‌های پرداخت را انتخاب کنید:"
    
    if update.callback_query:
        await update.callback_query.message.reply_text(text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "pay_stars":
        await query.message.reply_invoice(
            title="اشتراک ماهانه",
            description="دسترسی نامحدود به ترجمه آهنگ",
            payload="monthly_sub",
            provider_token="", 
            currency="XTR",      
            prices=[LabeledPrice(label="اشتراک ماهانه", amount=100)]
        )
        
    elif query.data == "pay_gateway":
        payment_text = (
            f"💳 **پرداخت کارت به کارت**\n\n"
            f"مبلغ: **۵۰,۰۰۰ تومان**\n"
            f"5859 8318 0259 8994: `{CARD_NUMBER}`\n"
            f" مصطفی قربانی: **{CARD_HOLDER}**\n\n"
            f"پس از واریز، **عکس رسید** یا **۴ رقم آخر کارت خود** را همینجا بفرستید تا ادمین تأیید کند."
        )
        await query.message.reply_text(payment_text, parse_mode='Markdown')
        context.user_data['awaiting_receipt'] = True

    # بخش تایید یا رد کردن توسط ادمین
    elif query.data.startswith("approve_") or query.data.startswith("reject_"):
        if query.from_user.id != ADMIN_ID:
            await query.answer("شما اجازه این کار را ندارید.", show_alert=True)
            return

        action, target_user_id = query.data.split("_")
        target_user_id = int(target_user_id)

        if action == "approve":
            user_subscriptions[target_user_id] = datetime.now() + timedelta(days=30)
            await context.bot.send_message(chat_id=target_user_id, text="✅ پرداخت شما تأیید شد! اشتراک فعال شد.")
            await query.edit_message_text("✅ تأیید شد. اشتراک کاربر فعال گردید.")
        else:
            await context.bot.send_message(chat_id=target_user_id, text="❌ پرداخت شما تأیید نشد. لطفاً با پشتیبانی تماس بگیرید.")
            await query.edit_message_text("❌ رد شد.")

async def handle_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not context.user_data.get('awaiting_receipt'):
        return

    if update.message.photo:
        photo_file = await update.message.photo[-1].get_file()
        await context.bot.send_photo(
            chat_id=ADMIN_ID,
            photo=photo_file.file_id,
            caption=f"📸 رسید جدید از کاربر:\nنام: {update.effective_user.full_name}\nآیدی: `{user_id}`\n\nآیا پرداخت را تأیید می‌کنید؟",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ تأیید", callback_data=f"approve_{user_id}"),
                 InlineKeyboardButton("❌ رد", callback_data=f"reject_{user_id}")]
            ]),
            parse_mode='Markdown'
        )
    elif update.message.text:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"📝 پیام جدید از کاربر:\nنام: {update.effective_user.full_name}\nآیدی: `{user_id}`\nمتن: {update.message.text}\n\nآیا پرداخت را تأیید می‌کنید؟",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ تأیید", callback_data=f"approve_{user_id}"),
                 InlineKeyboardButton("❌ رد", callback_data=f"reject_{user_id}")]
            ]),
            parse_mode='Markdown'
        )
    
    context.user_data['awaiting_receipt'] = False
    await update.message.reply_text("رسید شما برای بررسی به ادمین ارسال شد. لطفاً منتظر بمانید.")

async def subscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_payment_options(update, context)

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_subscriptions[user_id] = datetime.now() + timedelta(days=30)
    await update.message.reply_text("✅ اشتراک شما فعال شد! حالا می‌توانید آهنگ بفرستید.")

async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if check_subscription(user_id):
        pass 
    else:
        usage_count = user_free_usage.get(user_id, 0)
        if usage_count >= 2:
            await show_payment_options(update, context)
            return
        else:
            user_free_usage[user_id] = usage_count + 1
            remaining = 2 - user_free_usage[user_id]
            await update.message.reply_text(f"شما {remaining} آهنگ رایگان دیگر دارید.")

    audio_file = update.message.audio or update.message.voice
    if not audio_file:
        await update.message.reply_text("لطفاً یک فایل صوتی یا آهنگ بفرستید.")
        return

    await update.message.reply_text("فایل دریافت شد. در حال پردازش...")
    file = await context.bot.get_file(audio_file.file_id)
    file_path = f"temp_{update.message.message_id}.mp3"
    await file.download_to_drive(file_path)

    await update.message.reply_text("در حال تبدیل صدا به متن...")
    try:
        with open(file_path, "rb") as audio:
            transcript = client.audio.transcriptions.create(model="whisper-1", file=audio)
        english_text = transcript.text

        if len(english_text) < 20:
            await update.message.reply_text("متن قابل تشخیصی پیدا نشد. لطفاً فایل واضح‌تری بفرستید.")
            os.remove(file_path)
            return

        await update.message.reply_text("در حال ترجمه به فارسی...")
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a professional translator. Translate the following English song lyrics into natural, poetic Persian (Farsi)."},
                {"role": "user", "content": english_text}
            ]
        )
        persian_text = response.choices[0].message.content

        final_message = f"🎵 **متن انگلیسی:**\n\n{english_text}\n\n🇮🇷 **ترجمه فارسی:**\n\n{persian_text}"
        
        if len(final_message) > 4000:
            await update.message.reply_text(f"🎵 متن انگلیسی:\n\n{english_text[:2000]}...")
            await update.message.reply_text(f"🇮🇷 ترجمه فارسی:\n\n{persian_text[:2000]}...")
        else:
            await update.message.reply_text(final_message, parse_mode='Markdown')

    except Exception as e:
        await update.message.reply_text(f"خطا: {e}")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

# ==========================================
# اینجا اپلیکیشن ساخته می‌شود و هندلرها اضافه می‌شوند
# ==========================================
application = ApplicationBuilder().token(BOT_TOKEN).build()
    
application.add_handler(CommandHandler("subscribe", subscribe_command))
application.add_handler(CallbackQueryHandler(button_callback))
application.add_handler(PreCheckoutQueryHandler(precheckout_callback))
application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
application.add_handler(MessageHandler(filters.AUDIO | filters.VOICE, handle_audio))
application.add_handler(MessageHandler(filters.PHOTO | (filters.TEXT & ~filters.COMMAND), handle_receipt))

# این خط فقط وقتی اجرا میشه که خود فایل bot.py مستقیم اجرا بشه (مثلاً روی لپ‌تاپ)
if __name__ == '__main__':
    print("ربات در حال اجراست...")
    application.run_polling()