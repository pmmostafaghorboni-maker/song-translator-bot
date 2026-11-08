import os
import threading
from flask import Flask
from bot import application  # ایمپورت کردن اپلیکیشن ربات از فایل bot.py

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

@app.route('/health')
def health():
    return "OK"

def run_bot():
    # اجرای ربات تلگرام در پس‌زمینه
    application.run_polling()

if __name__ == '__main__':
    # شروع ربات در یک نخ جداگانه
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    # اجرای وب‌سرور روی پورتی که Render مشخص می‌کنه
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)