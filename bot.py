import asyncio
import sqlite3
import logging
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ===== НАСТРОЙКИ =====
TOKEN = "ТВОЙ_ТОКЕН_ОТ_BOTFATHER"  # Замени на свой токен
SCHOOL_URL = "https://sch1554.mskobr.ru/#news"  # Ссылка на раздел с новостями
CHAT_ID = -1001234567890  # ID твоего классного чата (можно временно твой ID)
# =====================

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота
bot = Bot(token=TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('news.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sent_news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            news_title TEXT UNIQUE,
            news_link TEXT,
            sent_date TEXT
        )
    ''')
    conn.commit()
    conn.close()

# Функция парсинга новостей
def parse_news():
    """Парсит новости с сайта школы"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(SCHOOL_URL, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        
        if response.status_code != 200:
            logging.error(f"Ошибка загрузки сайта: {response.status_code}")
            return []
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # ПРИМЕР: ищем новости (теги нужно подобрать под реальный сайт)
        # Это примерная структура — нужно заменить на реальные теги сайта 1554
        news_items = []
        
        # Ищем блоки новостей (замени на реальные классы с сайта)
        for item in soup.find_all('div', class_='news-item')[:5]:  # 5 последних новостей
            title_tag = item.find('a', class_='news-title')
            if title_tag:
                title = title_tag.get_text(strip=True)
                link = title_tag.get('href', '')
                if not link.startswith('http'):
                    link = 'https://sch1554.mskobr.ru' + link
                news_items.append({
                    'title': title,
                    'link': link
                })
        
        # Если ничего не нашли по первой логике — попробуй другие селекторы
        if not news_items:
            # Альтернативный поиск (пример)
            for item in soup.find_all('div', class_='news'):
                title_elem = item.find('h3')
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    link_elem = item.find('a')
                    link = link_elem.get('href', '') if link_elem else ''
                    if link and not link.startswith('http'):
                        link = 'https://sch1554.mskobr.ru' + link
                    news_items.append({'title': title, 'link': link})
        
        return news_items
        
    except Exception as e:
        logging.error(f"Ошибка при парсинге: {e}")
        return []

# Функция проверки новых новостей
def check_new_news():
    """Проверяет, есть ли новые новости"""
    news_list = parse_news()
    if not news_list:
        return []
    
    conn = sqlite3.connect('news.db')
    cursor = conn.cursor()
    
    new_news = []
    for news in news_list:
        # Проверяем, не отправляли ли уже такую новость
        cursor.execute('SELECT * FROM sent_news WHERE news_title = ?', (news['title'],))
        if not cursor.fetchone():
            new_news.append(news)
            # Сохраняем в БД
            cursor.execute('''
                INSERT INTO sent_news (news_title, news_link, sent_date)
                VALUES (?, ?, ?)
            ''', (news['title'], news['link'], datetime.now().isoformat()))
    
    conn.commit()
    conn.close()
    return new_news

# Асинхронная отправка новостей в Telegram
async def send_news_to_telegram():
    """Отправляет новые новости в чат"""
    new_news = check_new_news()
    if new_news:
        for news in new_news:
            message = f"📢 **Новая новость школы!**\n\n"
            message += f"**{news['title']}**\n"
            message += f"[Читать подробнее]({news['link']})"
            
            try:
                await bot.send_message(
                    chat_id=CHAT_ID,
                    text=message,
                    parse_mode="Markdown",
                    disable_web_page_preview=False
                )
                logging.info(f"Отправлена новость: {news['title']}")
            except Exception as e:
                logging.error(f"Ошибка отправки: {e}")
        
        # Отправляем сводку в лог
        await bot.send_message(
            chat_id=CHAT_ID,
            text=f"✅ Бот проверил новости в {datetime.now().strftime('%H:%M')}\nНайдено новых: {len(new_news)}"
        )
    else:
        logging.info("Новых новостей нет")

# ===== КОМАНДЫ БОТА =====
@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "🤖 **Бот-помощник школы 1554**\n\n"
        "Я автоматически отслеживаю новости на сайте школы "
        "и присылаю их в этот чат.\n\n"
        "**Доступные команды:**\n"
        "/start - Показать это сообщение\n"
        "/last - Показать последнюю новость\n"
        "/check - Принудительно проверить новости сейчас"
    )

@dp.message(Command("last"))
async def cmd_last(message: Message):
    conn = sqlite3.connect('news.db')
    cursor = conn.cursor()
    cursor.execute('SELECT news_title, news_link FROM sent_news ORDER BY id DESC LIMIT 1')
    last = cursor.fetchone()
    conn.close()
    
    if last:
        await message.answer(
            f"📰 **Последняя новость:**\n\n{last[0]}\n\n[Ссылка]({last[1]})",
            parse_mode="Markdown"
        )
    else:
        await message.answer("Новостей ещё не было. Попробуй /check")

@dp.message(Command("check"))
async def cmd_check(message: Message):
    await message.answer("🔍 Проверяю новости...")
    await send_news_to_telegram()
    await message.answer("✅ Проверка завершена")

# Запуск планировщика и бота
async def main():
    # Инициализация БД
    init_db()
    
    # Запускаем планировщик (каждые 30 минут)
    scheduler.add_job(send_news_to_telegram, "interval", minutes=30)
    scheduler.start()
    
    # Первая проверка при запуске
    await send_news_to_telegram()
    
    # Запуск бота
    logging.info("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
