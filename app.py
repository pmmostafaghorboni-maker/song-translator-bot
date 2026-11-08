import os
import threading
from flask import Flask

app = Flask(__name__)

# در اینجا ما ربات را به تعویق می‌اندازیم تا Flask اول بالا بیاید
bot_app = None

@app.route('/')
def home():
    return "Song Bot is running!"

@app.route('/health')
def health():
    return "OK"

def run_bot():
    global bot_app
    try:
        # ایمپورت کردن داخل تابع تا اگر خطا داد، Flask کرش نکند
        import bot
        bot_app = bot.application
        # اجرای ربات تلگرام
        bot_app.run_polling()
    except Exception as e:
        print(f"Error starting bot: {e}")

if __name__ == '__main__':
    # ربات را در یک نخ جداگانه اجرا می‌کنیم
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    # اجرای وب‌سرور برای Render
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
