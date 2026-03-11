# bot.py
import os, django, httpx, secrets, random
from decouple import config
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from asgiref.sync import sync_to_async
import logging
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

# async def _do_quiz(tg_id, message):
#     profile = await get_profile(tg_id)
#     if not profile: return await message.reply_text("❌ /start для привязки")
    
#     async with httpx.AsyncClient(timeout=5) as client:
#         try:
#             r = await client.post(f"{API_URL}/api/daily-quiz/", json={'user_id': profile.user.id})
#             data = r.json()
#         except: return await message.reply_text("⚠️ Ошибка загрузки")
    
#     if 'error' in data: return await message.reply_text("🎉 Вопросы закончились")
    
#     # 🔧 Сохраняем example_id в кэш для логирования ответа
#     example_id = data.get('example_id')
#     if example_id:
#         cache.set(f"quiz_example_{tg_id}", example_id, 300)
    
#     # Убираем строку с плейсхолдером 😊
#     lines = data['question'].split('\n')
#     question = '\n'.join(line for line in lines if '😊' not in line).strip()
    
#     # Рандомизируем варианты
#     options = data.get('options', [])
#     random.shuffle(options)
    
#     # Добавляем эмодзи для оформления
#     icons = ['🔹', '🔸', '▫️', '▪️', '🔘']
#     kb = [[InlineKeyboardButton(f"{icons[i % len(icons)]} {o['text']}", 
#                                 callback_data=f"ans_{i}_{int(o['is_correct'])}")] 
#           for i, o in enumerate(options)]
    
#     cache.set(f"quiz_exp_{tg_id}", data.get('explanation',''), 300)
#     await message.reply_text(f"⚡ <b>ВОПРОС</b>\n\n{question}", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")



# bot.py - добавить в функцию _do_quiz после получения данных

async def _do_quiz(tg_id, message):
    profile = await get_profile(tg_id)
    if not profile: 
        return await message.reply_text("❌ /start для привязки")
    
    async with httpx.AsyncClient(timeout=5) as client:
        try:
            r = await client.post(f"{API_URL}/api/daily-quiz/", json={'user_id': profile.user.id})
            data = r.json()
            # Логируем полученные данные
            print(f"📦 Получены данные от API: {data}")
        except Exception as e:
            print(f"❌ Ошибка загрузки: {e}")
            return await message.reply_text("⚠️ Ошибка загрузки")
    
    if 'error' in data: 
        return await message.reply_text("🎉 Вопросы закончились")
    
    # Сохраняем example_id в кэш
    example_id = data.get('example_id')
    if example_id:
        cache.set(f"quiz_example_{tg_id}", example_id, 300)
    
    # Получаем вопрос и варианты
    question = data.get('question', '')
    options = data.get('options', [])
    
    print(f"📝 Вопрос: {question}")
    print(f"🔘 Варианты: {options}")
    
    # Рандомизируем варианты
    random.shuffle(options)
    
    # Создаём клавиатуру
    icons = ['🔹', '🔸', '▫️', '▪️', '🔘']
    kb = []
    for i, o in enumerate(options):
        text = o.get('text', '')
        is_correct = o.get('is_correct', False)
        kb.append([InlineKeyboardButton(
            f"{icons[i % len(icons)]} {text}", 
            callback_data=f"ans_{i}_{1 if is_correct else 0}"
        )])
    
    cache.set(f"quiz_exp_{tg_id}", data.get('explanation', ''), 300)
    
    await message.reply_text(
        f"⚡ <b>ВОПРОС</b>\n\n{question}", 
        reply_markup=InlineKeyboardMarkup(kb), 
        parse_mode="HTML"
    )



async def _do_report(tg_id, message):
    profile = await get_profile(tg_id)
    if not profile: return await message.reply_text("❌ Аккаунт не привязан")
    async with httpx.AsyncClient(timeout=5) as client:
        try:
            r = await client.post(f"{API_URL}/api/weekly-report/", json={'telegram_id': tg_id})
            data = r.json()
        except: return await message.reply_text("⚠️ Ошибка отчёта")
    if data.get('status') == 'inactive': return await message.reply_text(f"⚠️ {data['message']}")
    msg = f"📊 <b>Отчёт</b>\nЗаданий: {data['total']}\nПравильно: {data['correct']}\nУспешность: {data['success_rate']}%\n"
    for o in data.get('weak_orthograms',[]): msg += f"• {o.get('orthogram__name') or o.get('name','?')}: {o['errors']} ошибок\n"
    await message.reply_text(msg, parse_mode="HTML")

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
    await _do_report(update.effective_user.id, update.message)

async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"🤖 Button pressed: {update.callback_query.data}")  # ← Добавь это
    q = update.callback_query
    await q.answer()
    cb = q.data
    tg_id = q.from_user.id
    
    # 🔧 Получаем профиль для логирования
    profile = await get_profile(tg_id)
    if not profile:
        return await q.edit_message_text("❌ Ошибка: аккаунт не найден")
    
    # Кнопки меню
    if cb == "cmd_quiz":
        await q.message.reply_text("⏳ Загружаю...")
        return await _do_quiz(tg_id, q.message)
    if cb == "cmd_report":
        await q.message.reply_text("⏳ Готовлю...")
        return await _do_report(tg_id, q.message)
    
    # Ответ на вопрос
    try:
        _, oid, ok = cb.split('_')
        ok = bool(int(ok))
        exp = cache.get(f"quiz_exp_{tg_id}", "Правило применено.")
        cache.delete(f"quiz_exp_{tg_id}")
        
        # 🔧 Достаём example_id из кэша
        example_id = cache.get(f"quiz_example_{tg_id}")
        
        # 🔧 Логируем ответ в Django
        async with httpx.AsyncClient(timeout=3.0) as client:
            await client.post(
                f"{API_URL}/api/log-quiz-answer/",
                json={
                    'user_id': profile.user.id,
                    'example_id': example_id,
                    'is_correct': ok
                }
            )
        
        await q.edit_message_text(f"{'✅ Верно!' if ok else '❌ Ошибка.'}\n\n📚 {exp}", parse_mode="HTML")
    except: 
        await q.edit_message_text("⚠️ Ошибка")

if __name__ == '__main__':
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("quiz", quiz_cmd))
    app.add_handler(CommandHandler("report", report_cmd))
    app.add_handler(CallbackQueryHandler(on_button))
    
    # Эта строка должна работать
    app.run_polling(drop_pending_updates=True)