import os
import logging
import sys
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CommandHandler
from twilio.rest import Client

# Logging setup
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables check
required_vars = ['TWILIO_ACCOUNT_SID', 'TWILIO_AUTH_TOKEN', 'TWILIO_PHONE_NUMBER', 'BOT_TOKEN', 'ADMIN_CHAT_ID']
missing_vars = [var for var in required_vars if not os.environ.get(var)]

if missing_vars:
    logger.error(f"Missing environment variables: {', '.join(missing_vars)}")
    sys.exit(1)

TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER')
BOT_TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_CHAT_ID = os.environ.get('ADMIN_CHAT_ID')

# Initialize Twilio client
try:
    twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
except Exception as e:
    logger.error(f"Failed to initialize Twilio client: {e}")
    sys.exit(1)

# Initialize Telegram bot
application = Application.builder().token(BOT_TOKEN).build()
telegram_to_twilio_map = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('Hi! I am your SMS forwarding bot.')

async def forward_telegram_message_to_twilio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if str(update.effective_chat.id) != ADMIN_CHAT_ID:
        await update.message.reply_text("You are not authorized.")
        return

    reply_to_message = update.message.reply_to_message
    if reply_to_message and reply_to_message.message_id in telegram_to_twilio_map:
        to_number = telegram_to_twilio_map[reply_to_message.message_id]
        try:
            twilio_client.messages.create(to=to_number, from_=TWILIO_PHONE_NUMBER, body=update.message.text)
            await update.message.reply_text(f"SMS sent to {to_number}")
        except Exception as e:
            logger.error(f"Twilio error: {e}")
            await update.message.reply_text(f"Failed: {e}")
    else:
        await update.message.reply_text("Please reply to an SMS message.")

if __name__ == '__main__':
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, forward_telegram_message_to_twilio))
    logger.info("Starting Telegram bot polling...")
    application.run_polling()
