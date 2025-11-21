import telebot
import google.generativeai as genai
from telebot import types
import edge_tts
import asyncio
import os
import time
import random
import requests
from flask import Flask
from threading import Thread

# --- ВСТАВЬ СВОИ КЛЮЧИ ---
GOOGLE_API_KEY = 'AIzaSyDOtHrHLYXl6RRSIfpkMDIy4DfGAmBRtP0'
BOT_TOKEN = '8550077194:AAFqNRmHAUzb86nUGNBleGRqJ9FCCQ3aR6c'

# --- ВЕБ-СЕРВЕР (Чтобы Render не спал) ---
app = Flask('')
@app.route('/')
def home(): return "Gopnik AI is Alive!"
def run(): app.run(host='0.0.0.0', port=8080)
def keep_alive():
    t = Thread(target=run)
    t.start()

# --- НАСТРОЙКИ ---
genai.configure(api_key=GOOGLE_API_KEY)
bot = telebot.TeleBot(BOT_TOKEN)
chat_sessions = {}
user_voice_mode = {}

# Голос Дмитрия
VOICE = "ru-RU-DmitryNeural"

# Характер
SYSTEM_PROMPT = (
    "Ты — Четкий Пацанчик. "
    "Общайся дерзко, но справедливо. Сленг: 'братан', 'короче', 'фарту', 'базар'. "
    "Если просят перевести — переводи художественно. "
    "Если просят мудрость — выдавай пацанские цитаты в стиле Джейсона Стэтхема или Волка."
)

# Поиск модели
MODEL_NAME = 'gemini-1.5-flash'
try:
    all_models = [m.name for m in genai.list_models()]
    good = [m for m in all_models if 'gemini' in m and 'vision' not in m]
    if good: MODEL_NAME = next((m for m in good if 'flash' in m), good[0])
except: pass

# --- ФУНКЦИИ ---

async def _gen_voice(text, filename):
    comm = edge_tts.Communicate(text, VOICE)
    await comm.save(filename)

def send_answer(chat_id, text):
    if user_voice_mode.get(chat_id):
        filename = f"v_{chat_id}_{int(time.time())}.mp3"
        try:
            clean_text = text.replace("*", "").replace("#", "")
            asyncio.run(_gen_voice(clean_text, filename))
            with open(filename, 'rb') as audio:
                bot.send_voice(chat_id, audio)
            os.remove(filename)
        except Exception as e:
            print(f"Voice Error: {e}")
            bot.send_message(chat_id, f"(Без звука): {text}")
    else:
        bot.send_message(chat_id, text)

def get_chat(chat_id):
    if chat_id not in chat_sessions or chat_sessions[chat_id] is None:
        try:
            model = genai.GenerativeModel(MODEL_NAME, system_instruction=SYSTEM_PROMPT)
            chat_sessions[chat_id] = model.start_chat(history=[])
        except: return None
    return chat_sessions[chat_id]

def ask_gemini(prompt, chat_id):
    chat = get_chat(chat_id)
    if chat:
        resp = chat.send_message(prompt)
        send_answer(chat_id, resp.text)
    else:
        bot.send_message(chat_id, "Мозг отключился, жми /start")

# --- КОМАНДЫ ---

@bot.message_handler(commands=['start'])
def start(message):
    chat_sessions[message.chat.id] = None
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    
    # Меню кнопок
    markup.row(types.KeyboardButton("🗣 Голос ВКЛ"), types.KeyboardButton("🔇 Голос ВЫКЛ"))
    markup.row(types.KeyboardButton("🐺 Мудрость"), types.KeyboardButton("👊 Наезд"))
    markup.row(types.KeyboardButton("🇺🇸 Перевод"), types.KeyboardButton("🎰 Казик"))
    markup.row(types.KeyboardButton("🎲 Кубик"), types.KeyboardButton("🔄 Забыть всё"))

    bot.send_message(message.chat.id, "Здарова! Я обновился. Теперь функций — вагон. 😎", reply_markup=markup)

# --- ОБРАБОТЧИКИ КНОПОК ---

@bot.message_handler(func=lambda m: m.text == "🗣 Голос ВКЛ")
def v_on(message):
    user_voice_mode[message.chat.id] = True
    send_answer(message.chat.id, "Базар, врубаю микрофон. 🎤")

@bot.message_handler(func=lambda m: m.text == "🔇 Голос ВЫКЛ")
def v_off(message):
    user_voice_mode[message.chat.id] = False
    bot.send_message(message.chat.id, "Окей, пишу буквами.")

@bot.message_handler(func=lambda m: m.text == "🔄 Забыть всё")
def reset(message):
    chat_sessions[message.chat.id] = None
    bot.send_message(message.chat.id, "Память стерта.")

@bot.message_handler(func=lambda m: m.text == "🐺 Мудрость")
def wisdom(message):
    ask_gemini("Придумай смешную пацанскую цитату про жизнь (в стиле волка или Стэтхема). Коротко.", message.chat.id)

@bot.message_handler(func=lambda m: m.text == "👊 Наезд")
def roast(message):
    ask_gemini("Придумай смешной, но не обидный 'наезд' на собеседника, типа 'Ты че такой дерзкий?'.", message.chat.id)

@bot.message_handler(func=lambda m: m.text == "🇺🇸 Перевод")
def translate_mode(message):
    bot.send_message(message.chat.id, "Напиши фразу, а я переведу её на английский, но с пацанским акцентом. 👇")
    bot.register_next_step_handler(message, lambda m: ask_gemini(f"Переведи эту фразу на английский сленг: '{m.text}'", m.chat.id))

@bot.message_handler(func=lambda m: m.text == "🎰 Казик")
def casino(message):
    res = bot.send_dice(message.chat.id, emoji='🎰')
    time.sleep(3) # Интрига
    val = res.dice.value
    if val in [1, 22, 43, 64]: # Выигрышные комбинации (примерно)
        send_answer(message.chat.id, "ДЖЕКПОТ! 🤑 С тебя пиво!")
    else:
        send_answer(message.chat.id, "Не фартануло, братан. Казино всегда в плюсе.")

@bot.message_handler(func=lambda m: m.text == "🎲 Кубик")
def dice(message):
    bot.send_dice(message.chat.id, emoji='🎲')

# --- ОСНОВНОЙ ЧАТ ---

@bot.message_handler(content_types=['text'])
def handle_text(message):
    txt = message.text.strip()
    chat_id = message.chat.id
    
    # Рисование
    if txt.lower().startswith("нарисуй"):
        bot.send_message(chat_id, "Рисую... 🖌")
        try:
            seed = int(time.time())
            url = f"https://image.pollinations.ai/prompt/{txt}?width=1024&height=1024&seed={seed}&model=flux"
            bot.send_photo(chat_id, requests.get(url).content)
        except:
            bot.send_message(chat_id, "Кисть сломалась (ошибка сервера).")
        return

    # Обычный разговор
    bot.send_chat_action(chat_id, 'record_audio' if user_voice_mode.get(chat_id) else 'typing')
    try:
        chat = get_chat(chat_id)
        if not chat:
            bot.send_message(chat_id, "/start")
            return
        resp = chat.send_message(txt)
        send_answer(chat_id, resp.text)
    except:
        chat_sessions[chat_id] = None
        bot.send_message(chat_id, "Сбой связи.")

# --- ЗАПУСК ---
keep_alive()
print("🚀 Mega-Gopnik Started on Render...")
bot.infinity_polling()
