import asyncio
import sys
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    first_name = update.effective_user.first_name if update.effective_user else "Usuário"
    print(f"\nSUCCESS: Seu Chat ID é {chat_id} (Remetente: {first_name})")
    try:
        await update.message.reply_text(f"Olá {first_name}! Seu Chat ID foi identificado com sucesso: {chat_id}.\nCopie este número e configure no campo TELEGRAM_CHAT_ID no seu arquivo .env!")
    except Exception as e:
        print("Erro ao responder no Telegram:", e)
    # Finaliza o loop
    sys.exit(0)

async def main():
    token = "8831893690:AAFk_OFe0x15U9_cBUw-5JDnVIoVDd-cPA8"
    app = Application.builder().token(token).build()
    app.add_handler(MessageHandler(filters.ALL, handle_message))
    
    print("\n[UTILITY] Escutando mensagens... Por favor, envie QUALQUER mensagem no Telegram para o bot agora!")
    
    await app.initialize()
    await app.start()
    
    offset = 0
    while True:
        try:
            updates = await app.bot.get_updates(offset=offset, timeout=2)
            for update in updates:
                await app.process_update(update)
                offset = update.update_id + 1
        except (KeyboardInterrupt, SystemExit):
            break
        except Exception as e:
            await asyncio.sleep(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("\nIdentificação finalizada.")
