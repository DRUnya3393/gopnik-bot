import telebot
import google.generativeai as genai
from telebot import types
import edge_tts
import asyncio
import os
import time
from flask import Flask
from threading import Thread

# --- ВСТАВЬ КЛЮЧИ ---
GOOGLE_API_KEY = 'AIzaSyDOtHrHLYXl6RRSIfpkMDIy4DfGAmBRtP0'
BOT_TOKEN = '8550077194:AAFqNRmHAUzb86nUGNBleGRqJ9FCCQ3aR6c'

# --- ВЕБ-СЕРВЕР (ЧТОБЫ RENDER НЕ УСЫПЛЯЛ БОТА) ---
app = Flask('')

@app.route('/')
def home():
    return "I'm alive! Gopnik AI is working."

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- НАСТРОЙКИ БОТА ---
genai.configure(api_key=GOOGLE_API_KEY)
bot = telebot.TeleBot(BOT_TOKEN)
chat_sessions = {}
user_voice_mode = {}
VOICE = "ru-RU-DmitryNeural" # Голос Дмитрия

SYSTEM_PROMPT = (
    "Ты — Четкий Пацанчик. "
    "Общайся дерзко, но справедливо. Сленг: 'братан', 'короче', 'в натуре'. "
    "Отвечай емко, по делу."
)

MODEL_NAME = 'gemini-1.5-flash'
try:
    all_models = [m.name for m in genai.list_models()]
    good_models = [m for m in all_models if 'gemini' in m and 'vision' not in m]
    if good_models:
        flash = next((m for m in good_models if 'flash' in m and 'latest' in m), None)
        MODEL_NAME = flash if flash else good_models[0]
except:
    pass

# --- ФУНКЦИИ ---
async def _generate_voice(text, filename):
    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(filename)

def send_answer(chat_id, text):
    if user_voice_mode.get(chat_id):
        filename = f"voice_{chat_id}_{int(time.time())}.mp3"
        try:
            clean_text = text.replace("*", "").replace("#", "")
            asyncio.run(_generate_voice(clean_text, filename))
            with open(filename, 'rb') as audio:
                bot.send_voice(chat_id, audio)
            os.remove(filename)
        except Exception as e:
            bot.send_message(chat_id, text)
    else:
        bot.send_message(chat_id, text)

def get_chat(chat_id):
    if chat_id not in chat_sessions or chat_sessions[chat_id] is None:
        try:
            model = genai.GenerativeModel(MODEL_NAME, system_instruction=SYSTEM_PROMPT)
            chat_sessions[chat_id] = model.start_chat(history=[])
        except:
            return None
    return chat_sessions[chat_id]

# --- ОБРАБОТЧИКИ ---
@bot.message_handler(commands=['start'])
def start(message):
    chat_sessions[message.chat.id] = None
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(types.KeyboardButton("🗣 Голос ВКЛ"), types.KeyboardButton("🔇 Голос ВЫКЛ"))
    markup.row(types.KeyboardButton("🔄 Забыть всё"))
    bot.send_message(message.chat.id, "Здарова! Я на сервере Render. Голос Дмитрия работает! 🎤", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "🗣 Голос ВКЛ")
def v_on(message):
    user_voice_mode[message.chat.id] = True
    send_answer(message.chat.id, "Базар, включил мужской голос.")

@bot.message_handler(func=lambda m: m.text == "🔇 Голос ВЫКЛ")
def v_off(message):
    user_voice_mode[message.chat.id] = False
    bot.send_message(message.chat.id, "Окей, пишу буквами.")

@bot.message_handler(func=lambda m: m.text == "🔄 Забыть всё")
def reset(message):
    chat_sessions[message.chat.id] = None
    bot.send_message(message.chat.id, "Память стерта.")

@bot.message_handler(content_types=['text'])
def handle_text(message):
    txt = message.text.strip()
    chat_id = message.chat.id
    bot.send_chat_action(chat_id, 'record_audio' if user_voice_mode.get(chat_id) else 'typing')
    try:
        chat = get_chat(chat_id)
        if not chat: return
        response = chat.send_message(txt)
        send_answer(chat_id, response.text)
    except:
        chat_sessions[chat_id] = None
        bot.send_message(chat_id, "Сбой.")

# --- ЗАПУСК ---
keep_alive() # Запускаем веб-сервер
print("🚀 Bot Started on Render")
bot.infinity_polling()