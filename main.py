import os
import logging
from datetime import datetime

from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

# Set up logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER')
BOT_TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_CHAT_ID = os.environ.get('ADMIN_CHAT_ID') # This should be the user's Telegram chat ID

# Initialize Flask app
app = Flask(__name__)

# Initialize Twilio client
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Initialize Telegram bot application
application = Application.builder().token(BOT_TOKEN).build()

# Dictionary to store mapping of Telegram message_id to Twilio From number
# This is crucial for replying to specific SMS messages
telegram_to_twilio_map = {}

# --- Telegram Bot Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a message when the command /start is issued."""
    await update.message.reply_text('Hi! I am your SMS forwarding bot. I will forward SMS from your Twilio number to this chat.')

async def forward_telegram_message_to_twilio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Forwards a message from Telegram back to Twilio as an SMS."""
    if str(update.effective_chat.id) != ADMIN_CHAT_ID:
        await update.message.reply_text("You are not authorized to send SMS.")
        return

    reply_to_message = update.message.reply_to_message
    if reply_to_message and reply_to_message.message_id in telegram_to_twilio_map:
        to_number = telegram_to_twilio_map[reply_to_message.message_id]
        message_body = update.message.text

        try:
            twilio_client.messages.create(
                to=to_number,
                from_=TWILIO_PHONE_NUMBER,
                body=message_body
            )
            await update.message.reply_text(f"SMS sent to {to_number}: '{message_body}'")
            logger.info(f"SMS sent to {to_number} from Telegram chat {update.effective_chat.id}")
        except Exception as e:
            logger.error(f"Error sending SMS via Twilio: {e}")
            await update.message.reply_text(f"Failed to send SMS: {e}")
    else:
        await update.message.reply_text("Please reply to an SMS message to send a response.")

# --- Flask Webhook for Twilio ---

@app.route('/twilio-webhook', methods=['POST'])
def twilio_webhook():
    """Handles incoming SMS from Twilio."""
    from_number = request.form.get('From')
    message_body = request.form.get('Body')
    message_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    logger.info(f"Received SMS from {from_number}: {message_body}")

    # Forward to Telegram
    if ADMIN_CHAT_ID and BOT_TOKEN:
        try:
            # Send message to admin and store the message_id for replies
            message_text = f"*New SMS from {from_number} at {message_time}:*\n\n{message_body}"
            # Using application.bot.send_message directly as it's outside an async handler
            # This requires running the Flask app in a separate thread or using an async Flask setup
            # For simplicity in this example, we'll assume a way to run this async or handle it.
            # In a real-world scenario, you might use a queue or a dedicated async task runner.
            # For now, let's use a synchronous approach for demonstration, which might block.
            # A better approach would be to use a separate thread or an async library for Flask.
            
            # For demonstration, we'll use a blocking call, which is not ideal for production.
            # A proper solution would involve a background task or an async web framework.
            # For now, we'll use a simple workaround to make it work synchronously.
            import asyncio
            async def send_telegram_message_and_map():
                sent_message = await application.bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text=message_text,
                    parse_mode='Markdown'
                )
                telegram_to_twilio_map[sent_message.message_id] = from_number
                logger.info(f"SMS from {from_number} forwarded to Telegram chat {ADMIN_CHAT_ID}")
            
            # Run the async function synchronously
            asyncio.run(send_telegram_message_and_map())

        except Exception as e:
            logger.error(f"Error forwarding SMS to Telegram: {e}")
    else:
        logger.warning("ADMIN_CHAT_ID or BOT_TOKEN not set. Cannot forward SMS to Telegram.")

    # Twilio response (optional, can be empty)
    resp = MessagingResponse()
    return str(resp)

# --- Health Check Endpoint ---
@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for Render."""
    return 'OK', 200

# --- Main execution ---
if __name__ == '__main__':
    # Add Telegram handlers
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, forward_telegram_message_to_twilio))
    # For /start command
    # application.add_handler(CommandHandler("start", start)) # Not strictly needed for this bot's core function

    # Start the Telegram bot in a non-blocking way (e.g., in a separate thread or process)
    # For Render deployment, we'll run Flask and the bot in the same process.
    # The Telegram bot needs to be started in a way that doesn't block the Flask app.
    # A common pattern is to use webhook for Telegram bot as well, but for simplicity,
    # and since Twilio is the primary webhook, we'll run the Telegram bot polling in a thread.
    
    # This is a simplified approach. For production, consider a more robust async setup
    # or separate processes for Flask and Telegram polling.
    import threading
    def run_telegram_bot():
        logger.info("Starting Telegram bot polling...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)

    telegram_thread = threading.Thread(target=run_telegram_bot)
    telegram_thread.start()

    # Run Flask app
    logger.info("Starting Flask app...")
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

