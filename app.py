import os
import threading
from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

@app.route('/health')
def health():
    return "OK"

def run_bot():
    try:
        import bot
        print(">>> BOT IMPORT SUCCESSFUL. STARTING POLLING...")
        bot.application.run_polling()
    except Exception as e:
        print(f">>> FATAL ERROR IN BOT: {e}")

if __name__ == '__main__':
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
