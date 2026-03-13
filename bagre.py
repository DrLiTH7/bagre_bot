import threading
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler
from config import TELEGRAM_TOKEN
from src.funcs import start, handle_message, button_callback, worker_download

def main() -> None:
    # 1. Inicia Workers em Background (Pool de Threads) para consumir a PriorityQueue simultaneamente
    for _ in range(4):
        worker_thread = threading.Thread(target=worker_download, daemon=True)
        worker_thread.start()

    updater = Updater(TELEGRAM_TOKEN, request_kwargs={'read_timeout': 10, 'connect_timeout': 10})
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start, run_async=True))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message, run_async=True))
    dp.add_handler(CallbackQueryHandler(button_callback, run_async=True))
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()