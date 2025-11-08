# bot.py
import os
import requests
import secrets
from decouple import config
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# Настройки
BOT_TOKEN = config('TELEGRAM_BOT_TOKEN')
DJANGO_API_URL = config('DJANGO_API_URL')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    username = update.effective_user.username or "no_username"

    # Генерация ссылки для привязки аккаунта
    token = secrets.token_urlsafe(16)
    link = f"http://127.0.0.1:8000/telegram-link/?token={token}&telegram_id={telegram_id}"
    
    await update.message.reply_text(
        f"Привет! Чтобы привязать Telegram к твоему аккаунту на сайте, перейди по ссылке:\n{link}"
    )

    # Отправка вопроса дня
    try:
        response = requests.post(f"{DJANGO_API_URL}/api/daily-quiz/", json={'user_id': 1})  # временно user_id=1
        data = response.json()

        if 'error' in data:
            await update.message.reply_text("Сегодня нет вопроса дня. Попробуй завтра!")
            return

        options = data['options']
        keyboard = [
            [InlineKeyboardButton(options[0]['text'], callback_data='correct')],
            [InlineKeyboardButton(options[1]['text'], callback_data='incorrect')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "⚡ ВОПРОС ДНЯ:\n\nКак правильно пишется (нажми):\n\n" + data['question'],
            reply_markup=reply_markup
        )

        context.user_data['explanation'] = data['explanation']

    except Exception as e:
        await update.message.reply_text("Произошла ошибка при загрузке вопроса.")
        print(f"Ошибка бота: {e}")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатия на кнопку"""
    query = update.callback_query
    await query.answer()

    is_correct = (query.data == 'correct')
    explanation = context.user_data.get('explanation', 'Правило: после предлогов на согласную пишется Е/Ё.')

    if is_correct:
        await query.edit_message_text("✅ Правильно! Молодец!\n\n" + explanation)
    else:
        await query.edit_message_text("❌ Неправильно.\n\n" + explanation)

# Запуск бота
if __name__ == '__main__':
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.run_polling()