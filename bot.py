# bot.py
import os, django, httpx, secrets, random, asyncio
from decouple import config
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from asgiref.sync import sync_to_async
import logging
import pytz
from datetime import time as dt_time

logger = logging.getLogger(__name__)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')
django.setup()
from django.core.cache import cache
from main.models import UserProfile

BOT_TOKEN = config('TELEGRAM_BOT_TOKEN')
API_URL = config('DJANGO_API_URL', default='http://127.0.0.1:8000')

@sync_to_async
def get_profile(tg_id):
    try: return UserProfile.objects.select_related('user').get(telegram_id=tg_id)
    except UserProfile.DoesNotExist: return None

@sync_to_async
def get_all_telegram_users():
    """Получает всех пользователей с привязанным Telegram"""
    return list(UserProfile.objects.filter(
        telegram_id__isnull=False
    ).select_related('user'))

async def send_daily_quiz_to_all(context: ContextTypes.DEFAULT_TYPE):
    """Отправляет квиз всем пользователям (вызывается в 12:00 МСК)"""
    print(f"\n⏰ Ежедневная рассылка в {context.job.data['time']}")
    
    profiles = await get_all_telegram_users()
    print(f"📨 Отправляем квизы {len(profiles)} пользователям")
    
    for profile in profiles:
        try:
            await send_quiz_to_user(profile.telegram_id, profile.user.id, context.bot)
        except Exception as e:
            logger.error(f"Ошибка отправки пользователю {profile.telegram_id}: {e}")

async def send_quiz_to_user(tg_id, user_id, bot):
    """Отправляет квиз конкретному пользователю"""
    async with httpx.AsyncClient(timeout=5) as client:
        try:
            r = await client.post(f"{API_URL}/api/daily-quiz/", json={'user_id': user_id})
            data = r.json()
        except Exception as e:
            print(f"❌ Ошибка загрузки для {tg_id}: {e}")
            return
    
    if 'error' in data:
        print(f"❌ Нет вопросов для {tg_id}: {data['error']}")
        return
    
    # Сохраняем в кэш
    example_id = data.get('example_id')
    user_word_id = data.get('user_word_id')
    
    if example_id:
        cache.set(f"quiz_word_{tg_id}", example_id, 300)
    if user_word_id:
        cache.set(f"quiz_user_word_{tg_id}", user_word_id, 300)
    
    cache.set(f"quiz_exp_{tg_id}", data.get('explanation', ''), 300)
    
    # Отправляем вопрос
    question = data['question']
    options = data['options']
    random.shuffle(options)
    
    icons = ['🔹', '🔸', '▫️', '▪️', '🔘']
    kb = []
    for i, o in enumerate(options):
        text = o.get('text', '')
        is_correct = 1 if o.get('is_correct') else 0
        kb.append([InlineKeyboardButton(
            f"{icons[i % len(icons)]} {text}",
            callback_data=f"ans_{i}_{is_correct}"
        )])
    
    await bot.send_message(
        chat_id=tg_id,
        text=f"⚡ <b>ВОПРОС ДНЯ</b>\n\n{question}",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="HTML"
    )
    print(f"✅ Отправлено пользователю {tg_id}")


async def _do_quiz(tg_id, message):
    profile = await get_profile(tg_id)
    if not profile:
        return await message.reply_text("❌ /start для привязки")
    
    async with httpx.AsyncClient(timeout=5) as client:
        try:
            r = await client.post(f"{API_URL}/api/daily-quiz/", json={'user_id': profile.user.id})
            data = r.json()
        except Exception as e:
            print(f"❌ Ошибка загрузки: {e}")
            return await message.reply_text("⚠️ Ошибка загрузки")
    
    if 'error' in data:
        return await message.reply_text("🎉 Вопросы закончились")
    
    # Сохраняем только ID слова в кэш
    example_id = data.get('example_id')
    if example_id:
        cache.set(f"quiz_word_{tg_id}", example_id, 300)
    
    cache.set(f"quiz_exp_{tg_id}", data.get('explanation', ''), 300)
    
    # Отправляем вопрос
    question = data['question']
    options = data.get('options', [])
    random.shuffle(options)
    
    icons = ['🔹', '🔸', '▫️', '▪️', '🔘']
    kb = []
    for i, o in enumerate(options):
        text = o.get('text', '')
        is_correct = 1 if o.get('is_correct') else 0
        kb.append([InlineKeyboardButton(
            f"{icons[i % len(icons)]} {text}",
            callback_data=f"ans_{i}_{is_correct}_{example_id}"  # передаём ID в callback
        )])
    
    await message.reply_text(
        f"⚡ <b>ВОПРОС</b>\n\n{question}",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="HTML"
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    profile = await get_profile(tg_id)
    menu_kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("⚡ Вопрос дня", callback_data="cmd_quiz"),
        InlineKeyboardButton("📊 Статистика", callback_data="cmd_report")
    ]]) if profile else None
    if profile:
        return await update.message.reply_text(f"✅ Привет, {profile.user.username}!", reply_markup=menu_kb)
    token = secrets.token_urlsafe(16)
    cache.set(f"tg_link_{token}", tg_id, 300)
    link_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔗 Привязать", url=f"{API_URL}/profile/link-telegram/?token={token}")]])
    await update.message.reply_text("👋 Привяжи аккаунт:", reply_markup=link_kb)

async def quiz_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _do_quiz(update.effective_user.id, update.message)

async def report_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    profile = await get_profile(tg_id)
    if not profile:
        return await update.message.reply_text("❌ Аккаунт не привязан")
    
    async with httpx.AsyncClient(timeout=5) as client:
        try:
            r = await client.post(
                f"{API_URL}/api/weekly-report/", 
                json={'user_id': profile.user.id}
            )
            
            # Проверяем статус
            if r.status_code != 200:
                print(f"❌ Статус ошибки: {r.status_code}")
                print(f"Текст ответа: {r.text[:200]}")
                return await update.message.reply_text("⚠️ Ошибка получения статистики")
            
            # Пробуем получить JSON
            try:
                data = r.json()
            except Exception as e:
                print(f"❌ Ошибка парсинга JSON: {e}")
                print(f"Ответ сервера: {r.text[:200]}")
                return await update.message.reply_text("⚠️ Ошибка формата данных")
            
        except Exception as e:
            print(f"❌ Ошибка отчёта: {e}")
            return await update.message.reply_text("⚠️ Ошибка загрузки")
    
    # Формируем отчет
    msg = f"📊 **Ваша статистика**\n\n"
    msg += f"📚 **Слов в планинге:** {data.get('total_words', 0)}\n\n"
    msg += f"🎯 **Квизы за неделю:**\n"
    msg += f"• Всего попыток: {data.get('total_attempts', 0)}\n"
    msg += f"• Правильно: {data.get('correct_answers', 0)}\n"
    msg += f"• Успешность: {data.get('success_rate', 0)}%\n\n"
    
    weak = data.get('weak_orthograms', [])
    if weak:
        msg += f"⚠️ **Сложные темы:**\n"
        for o in weak:
            msg += f"• {o['name']}: {o['errors']} ошибок\n"
    else:
        msg += f"✅ Нет частых ошибок! Так держать!\n"
    
    await update.message.reply_text(msg, parse_mode="Markdown")


async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"🤖 Button pressed: {update.callback_query.data}")
    
    q = update.callback_query
    await q.answer()
    cb = q.data
    tg_id = q.from_user.id
    
    profile = await get_profile(tg_id)
    if not profile:
        return await q.edit_message_text("❌ Ошибка: аккаунт не найден")
    
    # Обработка кнопок меню
    if cb == "cmd_quiz":
        await q.message.reply_text("⏳ Загружаю вопрос...")
        await q.edit_message_reply_markup(reply_markup=None)
        return await _do_quiz(tg_id, q.message)
    
    if cb == "cmd_report":
        await q.message.reply_text("⏳ Готовлю статистику...")
        await q.edit_message_reply_markup(reply_markup=None)
        
        async with httpx.AsyncClient(timeout=5) as client:
            try:
                r = await client.post(
                    f"{API_URL}/api/weekly-report/", 
                    json={'user_id': profile.user.id}
                )
                data = r.json()
            except Exception as e:
                print(f"❌ Ошибка отчёта: {e}")
                return await q.message.reply_text("⚠️ Ошибка загрузки статистики")
        
        msg = f"📊 **Ваша статистика**\n\n"
        msg += f"📚 **Слов в планинге:** {data.get('total_words', 0)}\n\n"
        msg += f"🎯 **Квизы за неделю:**\n"
        msg += f"• Всего попыток: {data.get('total_attempts', 0)}\n"
        msg += f"• Правильно: {data.get('correct_answers', 0)}\n"
        msg += f"• Успешность: {data.get('success_rate', 0)}%\n\n"
        
        weak = data.get('weak_orthograms', [])
        if weak:
            msg += f"⚠️ **Сложные темы:**\n"
            for o in weak:
                msg += f"• {o['name']}: {o['errors']} ош. (№ {o['orthogram_id']})\n"
        
        await q.message.reply_text(msg, parse_mode="Markdown")
        return
    
    # Обработка ответа на вопрос
    try:
        # Парсим callback_data: ans_0_1_123
        parts = cb.split('_')
        if len(parts) == 4 and parts[0] == 'ans':
            _, selected_idx, ok, word_id = parts
            is_correct = bool(int(ok))
        else:
            await q.edit_message_text("⚠️ Неизвестный формат ответа")
            return
        
        # 🔥 ИСПРАВЛЕНИЕ: используем sync_to_async для запроса к БД
        from main.models import OrthogramExample
        
        @sync_to_async
        def get_word(word_id):
            return OrthogramExample.objects.select_related('orthogram').get(id=word_id)
        
        word = await get_word(word_id)
        
        # Определяем, какой текст показать
        if is_correct:
            selected_text = word.text
        else:
            selected_text = word.incorrect_variant or word.text
        
        exp = cache.get(f"quiz_exp_{tg_id}", word.orthogram.rule if word.orthogram else "Правило")
        
        # Логируем ответ
        async with httpx.AsyncClient(timeout=3.0) as client:
            await client.post(
                f"{API_URL}/api/log-quiz-answer/",
                json={
                    'user_id': profile.user.id,
                    'word_id': word_id,
                    'was_correct': is_correct
                }
            )
        
        # Формируем ответ
        emoji = "✅ Верно!" if is_correct else "❌ Ошибка!"
        response = f"{emoji}\n{selected_text}\n\n📚 {exp}"
        
        # Очищаем кэш
        cache.delete(f"quiz_exp_{tg_id}")
        
        await q.edit_message_text(response, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Ошибка обработки ответа: {e}")
        await q.edit_message_text("⚠️ Ошибка обработки ответа")

async def log_answer(user_id, word_id, user_word_id, was_correct):
    """Фоновая отправка лога"""
    async with httpx.AsyncClient(timeout=3.0) as client:
        try:
            await client.post(
                f"{API_URL}/api/log-quiz-answer/",
                json={
                    'user_id': user_id,
                    'word_id': word_id,
                    'user_word_id': user_word_id,
                    'was_correct': was_correct
                }
            )
        except:
            pass

async def praise_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает, какие слова выучены лучше всего"""
    tg_id = update.effective_user.id
    profile = await get_profile(tg_id)
    if not profile:
        return await update.message.reply_text("❌ Аккаунт не привязан")
    
    async with httpx.AsyncClient(timeout=5) as client:
        try:
            r = await client.post(
                f"{API_URL}/api/user-praise/",
                json={'user_id': profile.user.id}
            )
            data = r.json()
        except Exception as e:
            print(f"❌ Ошибка похвалы: {e}")
            return await update.message.reply_text("⚠️ Ошибка загрузки")
    
    mastered = data.get('mastered_words', [])
    if not mastered:
        msg = "🌟 **Твои успехи**\n\n"
        msg += "Пока нет слов с отличным результатом.\n"
        msg += "Продолжай тренироваться! 💪"
    else:
        msg = f"🌟 **Твои успехи!**\n\n"
        msg += f"✅ Отлично выучено {data.get('total_mastered', 0)} слов:\n\n"
        for word in mastered:
            msg += f"• **{word['text']}** – {word['success_rate']}% правильных\n"
    
    await update.message.reply_text(msg, parse_mode="Markdown")


async def repeat_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает слова для повторения"""
    tg_id = update.effective_user.id
    profile = await get_profile(tg_id)
    if not profile:
        return await update.message.reply_text("❌ Аккаунт не привязан")
    
    async with httpx.AsyncClient(timeout=5) as client:
        try:
            r = await client.post(
                f"{API_URL}/api/weak-words/",
                json={'user_id': profile.user.id}
            )
            data = r.json()
        except Exception as e:
            print(f"❌ Ошибка загрузки слов: {e}")
            return await update.message.reply_text("⚠️ Ошибка загрузки")
    
    weak_words = data.get('weak_words', [])
    if not weak_words:
        msg = "📚 **Слова для повторения**\n\n"
        msg += "🎉 Отлично! Сейчас нет слов, требующих повторения!"
    else:
        msg = f"📚 **Слова для повторения**\n\n"
        msg += f"Найдено {len(weak_words)} слов, в которых чаще всего ошибаешься:\n\n"
        for i, word in enumerate(weak_words, 1):
            msg += f"{i}. **{word['text']}** – {word['errors']} ошибок\n"
            msg += f"   (орф. {word['orthogram_id']})\n"
    
    await update.message.reply_text(msg, parse_mode="Markdown")

async def praise_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await praise_cmd(update, context)  # используем функцию выше

async def repeat_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await repeat_cmd(update, context)  # используем функцию выше


if __name__ == '__main__':
    # Убираем asyncio.run() и используем простой запуск
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Добавляем обработчики команд
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("quiz", quiz_cmd))
    app.add_handler(CommandHandler("report", report_cmd))
    app.add_handler(CommandHandler("praise", praise_cmd))
    app.add_handler(CommandHandler("repeat", repeat_cmd))
    app.add_handler(CallbackQueryHandler(on_button))
    
    # Настраиваем ежедневную рассылку
    try:
        import pytz
        from datetime import time as dt_time
        
        job_queue = app.job_queue
        if job_queue:
            moscow_tz = pytz.timezone('Europe/Moscow')
            job_queue.run_daily(
                send_daily_quiz_to_all,
                time=dt_time(hour=12, minute=0, tzinfo=moscow_tz),
                days=tuple(range(7)),
                data={'time': '12:00 MSK'}
            )
            print("🤖 Бот запущен и будет отправлять вопросы ежедневно в 12:00 МСК")
        else:
            print("⚠️ JobQueue не доступен, рассылка не будет работать")
    except Exception as e:
        print(f"⚠️ Ошибка настройки рассылки: {e}")
    
    # Запускаем бота (без asyncio.run)
    app.run_polling(drop_pending_updates=True)