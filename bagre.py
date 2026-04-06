import asyncio
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from config import TELEGRAM_TOKEN
from src.funcs import start, handle_message, button_callback, worker_download

async def post_init(application):
    # Inicia Workers em Background nativos do asyncio, atrelados ao event loop principal do bot
    for _ in range(4):
        asyncio.create_task(worker_download())

def main() -> None:
    application = (
        ApplicationBuilder()
        .token(TELEGRAM_TOKEN)
        .post_init(post_init)
        .read_timeout(10)
        .connect_timeout(10)
        .job_queue(None)
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    application.run_polling(poll_interval=0, timeout=30)

if __name__ == '__main__':
    main()