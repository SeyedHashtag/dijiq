import threading
from utils.command import bot
from tbot import monitoring_thread, version_monitoring
from utils.purchase_plan import app as flask_app

def run_flask_app():
    flask_app.run(port=5000)

if __name__ == '__main__':
    # Start monitoring threads
    monitor_thread = threading.Thread(target=monitoring_thread, daemon=True)
    monitor_thread.start()
    version_thread = threading.Thread(target=version_monitoring, daemon=True)
    version_thread.start()

    # Start Flask app in a separate thread
    flask_thread = threading.Thread(target=run_flask_app, daemon=True)
    flask_thread.start()

    # Start bot polling
    bot.polling(none_stop=True)
