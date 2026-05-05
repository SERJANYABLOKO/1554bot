import sqlite3
import time
import threading
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ===== НАСТРОЙКИ =====
TOKEN = "ТВОЙ_ТОКЕН"  # Замени на свой токен от BotFather
CHAT_ID = -1001234567890  # ID твоего чата (можно пока свой ID)
SCHOOL_URL = "https://sch1554.mskobr.ru/#news"
# =====================

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
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(SCHOOL_URL, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        
        if response.status_code != 200:
            return []
        
        soup = BeautifulSoup(response.text, 'html.parser')
        news_items = []
        
        # Пример поиска (замени на реальные теги сайта 1554)
        for item in soup.find_all('div', class_='news-item')[:5]:
            title_tag = item.find('a', class_='news-title')
            if title_tag:
                title = title_tag.get_text(strip=True)
                link = title_tag.get('href', '')
                if link and not link.startswith('http'):
                    link = 'https://sch1554.mskobr.ru' + link
                news_items.append({'title': title, 'link': link})
        
        return news_items
    except Exception as e:
        print(f"Ошибка парсинга: {e}")
        return []

# Проверка новых новостей
def check_new_news():
    news_list = parse_news()
    if not news_list:
        return []
    
    conn = sqlite3.connect('news.db')
    cursor = conn.cursor()
    
    new_news = []
    for news in news_list:
        cursor.execute('SELECT * FROM sent_news WHERE news_title = ?', (news['title'],))
        if not cursor.fetchone():
            new_news.append(news)
            cursor.execute('INSERT INTO sent_news (news_title, news_link, sent_date) VALUES (?, ?, ?)',
                         (news['title'], news['link'], datetime.now().isoformat()))
    
    conn.commit()
    conn.close()
    return new_news

# Отправка новостей в Telegram
async def send_news(context: ContextTypes.DEFAULT_TYPE):
    new_news = check_new_news()
    if new_news:
        for news in new_news:
            message = f"📢 **Новая новость школы!**\n\n**{news['title']}**\n[Читать]({news['link']})"
            await context.bot.send_message(chat_id=CHAT_ID, text=message, parse_mode='Markdown')

# Команды бота
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Бот-помощник школы 1554\n"
        "Доступные команды:\n"
        "/start - Показать это сообщение\n"
        "/last - Последняя новость\n"
        "/check - Проверить новости сейчас"
    )

async def last(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect('news.db')
    cursor = conn.cursor()
    cursor.execute('SELECT news_title, news_link FROM sent_news ORDER BY id DESC LIMIT 1')
    last_news = cursor.fetchone()
    conn.close()
    
    if last_news:
        await update.message.reply_text(f"📰 **Последняя новость:**\n\n{last_news[0]}\n[Ссылка]({last_news[1]})", parse_mode='Markdown')
    else:
        await update.message.reply_text("Новостей пока нет. Попробуй /check")

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Проверяю новости...")
    await send_news(context)
    await update.message.reply_text("✅ Готово!")

# Функция для фоновой проверки (без планировщика)
def background_checker(app: Application):
    while True:
        time.sleep(1800)  # 30 минут
        import asyncio
        asyncio.run(send_news(app.context))

def main():
    init_db()
    
    # Создаём приложение
    app = Application.builder().token(TOKEN).build()
    
    # Добавляем команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("last", last))
    app.add_handler(CommandHandler("check", check))
    
    # Запускаем фоновую проверку в отдельном потоке
    thread = threading.Thread(target=background_checker, args=(app,), daemon=True)
    thread.start()
    
    # Запускаем бота
    print("Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()
