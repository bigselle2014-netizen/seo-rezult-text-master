import streamlit as st
import requests, re, os, numpy as np
from datetime import datetime
from docx import Document
from urllib.parse import quote
from supabase import create_client
from dotenv import load_dotenv
from auth import login_or_register  # импорт авторизации

# === Настройки ===
st.set_page_config(page_title="SEO Rezult Text Master v6.0", layout="wide")

load_dotenv()
PPLX_API_KEY = os.getenv("PPLX_API_KEY") or st.secrets["PPLX_API_KEY"]
TEXT_RU_KEY = os.getenv("TEXT_RU_KEY") or st.secrets["TEXT_RU_KEY"]
SUPABASE_URL = os.getenv("SUPABASE_URL") or st.secrets["SUPABASE_URL"]
SUPABASE_KEY = os.getenv("SUPABASE_KEY") or st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# === Авторизация ===
user = login_or_register()
if not user:
    st.stop()

st.title("🚀 SEO Rezult Text Master v6.0")
st.caption("Генератор SEO-текстов с LSI-анализом, уникальностью и естественностью")

# --- Форма ---
with st.form("input_form"):
    topic = st.text_input("Тематика текста")
    site = st.text_input("Сайт клиента")
    competitors = st.text_area("Ссылки на конкурентов (по одной в строке)")
    lsi_words = st.text_area("Список LSI-слов (через запятую)")
    banned = st.text_area("Запрещённые слова (через запятую)")
    keywords = st.text_area("Ключевые слова (через запятую)")
    symbols = st.number_input("Количество символов", value=8000, step=500)
    submitted = st.form_submit_button("Сгенерировать текст")

# --- Вспомогательные функции ---
def perplexity_generate(prompt: str):
    headers = {"Authorization": f"Bearer {PPLX_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": "sonar-pro", "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}]}
    r = requests.post("https://api.perplexity.ai/chat/completions", json=payload, headers=headers)
    return r.json()["choices"][0]["message"]["content"]

def build_prompt(topic, site, competitors, lsi, banned, keys, symbols):
    return f"""
Ты опытный SEO-копирайтер.
Напиши экспертный SEO-текст на тему: {topic}.
Сайт клиента: {site}.
Конкуренты: {competitors}.
Ключевые слова: {keys}.
LSI-фразы: {lsi}.
Не используй слова: {banned}.
Объём ≈ {symbols} символов.
Пиши живым языком, без шаблонов, максимально естественно.
"""

def clean_text(text): return re.sub(r"[#*_>`]+", "", text).strip()
def check_missing_lsi(text, lsi_list): return [w for w in lsi_list if w.lower() not in text.lower()]

def seo_score(text, keywords):
    words = re.findall(r"\w+", text.lower())
    word_count = len(words)
    avg_len = np.mean([len(w) for w in words])
    key_density = sum(text.lower().count(k.lower()) for k in keywords.split(",")) / max(word_count, 1) * 100
    return {"Количество слов": word_count, "Средняя длина слова": round(avg_len, 2), "Плотность ключей (%)": round(key_density, 2)}

def analyze_humanness(text):
    words = re.findall(r"\w+", text.lower())
    unique_words = len(set(words))
    perplexity = round(np.exp(len(words) / max(unique_words, 1)), 2)
    human_score = max(0, min(100, round(100 - (perplexity / 50) * 20, 1)))
    return {"Перплексия": perplexity, "Естественность (%)": human_score}

def export_docx(text, report, filename="seo_text.docx"):
    doc = Document()
    doc.add_heading("SEO Rezult Text Master — Отчёт", level=1)
    doc.add_paragraph(text)
    doc.add_page_break()
    for k, v in report.items():
        doc.add_paragraph(f"{k}: {v}")
    doc.save(filename)
    with open(filename, "rb") as f:
        st.download_button("📥 Скачать DOCX", f, file_name=filename)

# --- Основной процесс ---
if submitted:
    st.info("⚙️ Генерация текста...")
    lsi_list = [w.strip() for w in lsi_words.split(",") if w.strip()]
    text = clean_text(perplexity_generate(build_prompt(topic, site, competitors, lsi_words, banned, keywords, symbols)))

    st.text_area("📝 Результат", text, height=400)

    # Сохраняем в Supabase
    supabase.table("history").insert({
        "user_id": user.id,
        "topic": topic,
        "symbols": symbols,
        "lsi_count": len(lsi_list),
        "text": text,
        "date": datetime.now().isoformat()
    }).execute()

    report = seo_score(text, keywords)
    st.table(report.items())
    human = analyze_humanness(text)
    st.table(human.items())

    export_docx(text, report)
