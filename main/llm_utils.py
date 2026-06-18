# main/llm_utils.py
"""
Утилиты для работы с LLM (DeepSeek API)
Без зависимостей от оркестратора и ассистентов
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')
DEEPSEEK_MODEL = os.getenv('DEEPSEEK_MODEL', 'deepseek-chat')
DEEPSEEK_URL = 'https://api.deepseek.com/chat/completions'


def call_deepseek(messages):
    """Отправляет запрос в DeepSeek API"""
    
    if not DEEPSEEK_API_KEY:
        raise Exception("DEEPSEEK_API_KEY not configured")
    
    response = requests.post(
        DEEPSEEK_URL,
        headers={
            'Authorization': f'Bearer {DEEPSEEK_API_KEY}',
            'Content-Type': 'application/json'
        },
        json={
            'model': DEEPSEEK_MODEL,
            'messages': messages,
            'temperature': 0.3,
            'max_tokens': 300,
            'stream': False
        },
        timeout=10
    )
    
    if response.status_code != 200:
        raise Exception(f"DeepSeek API error: {response.status_code} - {response.text}")
    
    result = response.json()
    return result['choices'][0]['message']['content']


def get_fallback_response(message):
    """Ответ без LLM (если API недоступно)"""
    
    message_lower = message.lower()
    
    if 'привет' in message_lower:
        return "Привет! 👋 Я Нейро-ассистент платформы."
    
    if 'помощ' in message_lower:
        return """💡 Я могу помочь:
• Спроси про правило (например: "почему подростковый с О?")
• Узнай статистику ("моя статистика")
• Узнай про тарифы ("тарифы")"""
    
    return "🤔 Не совсем понял вопрос. Попробуй перефразировать."