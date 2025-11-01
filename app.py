import streamlit as st
import requests, sqlite3, os, re, numpy as np
from dotenv import load_dotenv
from datetime import datetime
from docx import Document
from urllib.parse import quote

# --- Настройки окружения ---
load_dotenv()
PPLX_API_KEY = os.getenv("PPLX_API_KEY")
TEXT_RU_KEY = os.getenv("TEXT_RU_KEY")

# --- Инициализация базы ---
DB_PATH = "database.db"
conn = sqlite3.connect(DB_PATH)
conn.execute("""CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT,
    topic TEXT,
    symbols INTEGER,
    lsi_count INTEGER,
    text TEXT
)""")
conn.commit()

st.set_page_config(page_title="SEO Rezult Text Master v6.0", layout="wide")
st.title("🚀 SEO Rezult Text Master v6.0")
st.caption("Генератор SEO-текстов с LSI-анализом, проверкой уникальности, SEO-оценкой и анализом естественности")

# --- Форма ввода ---
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
    payload = {
        "model": "sonar-pro",
        "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}],
        "max_output_tokens": 2000
    }
    r = requests.post("https://api.perplexity.ai/chat/completions", json=payload, headers=headers)
    if not r.ok:
        st.error(f"Perplexity API вернул ошибку {r.status_code}: {r.text}")
        r.raise_for_status()
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

def clean_text(text):
    return re.sub(r"[#*_>`]+", "", text).strip()

def check_missing_lsi(text, lsi_list):
    return [w for w in lsi_list if w.lower() not in text.lower()]

def save_history(topic, symbols, lsi_count, text):
    conn.execute("INSERT INTO history (date,topic,symbols,lsi_count,text) VALUES (?,?,?,?,?)",
                 (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), topic, symbols, lsi_count, text))
    conn.commit()

def export_docx(text, report, human_report, filename="seo_text.docx"):
    doc = Document()
    doc.add_heading("SEO Rezult Text Master — Отчёт", level=1)
    doc.add_paragraph(text)
    doc.add_page_break()
    doc.add_heading("📊 SEO-анализ", level=2)
    for k, v in report.items():
        doc.add_paragraph(f"{k}: {v}")
    doc.add_heading("🧠 Анализ естественности", level=2)
    for k, v in human_report.items():
        doc.add_paragraph(f"{k}: {v}")
    doc.save(filename)
    with open(filename, "rb") as f:
        st.download_button("📥 Скачать DOCX-отчёт", f, file_name=filename)

# --- SEO-анализ ---
def seo_score(text, keywords):
    words = re.findall(r"\w+", text.lower())
    word_count = len(words)
    avg_len = sum(len(w) for w in words) / len(words)
    key_density = sum(text.lower().count(k.lower()) for k in keywords.split(",")) / max(word_count, 1) * 100
    sentences = re.split(r"[.!?]", text)
    avg_sentence_len = sum(len(s.split()) for s in sentences if s.strip()) / max(len(sentences), 1)
    water = len(re.findall(r"\b(очень|это|также|поэтому|например|в целом|следовательно)\b", text.lower())) / max(word_count, 1) * 100
    return {
        "Количество слов": word_count,
        "Средняя длина слова": round(avg_len, 2),
        "Средняя длина предложения": round(avg_sentence_len, 2),
        "Плотность ключей (%)": round(key_density, 2),
        "Водность (%)": round(water, 2)
    }

# --- Анализ естественности ---
def analyze_humanness(text):
    sentences = [s.strip() for s in re.split(r'[.!?]', text) if s.strip()]
    words = re.findall(r'\w+', text.lower())

    unique_words = len(set(words))
    perplexity = round(np.exp(len(words) / max(unique_words, 1)), 2)

    sentence_lengths = [len(s.split()) for s in sentences]
    burstiness = round(np.std(sentence_lengths) / (np.mean(sentence_lengths) + 1e-5), 2)

    bigrams = [f"{words[i]} {words[i+1]}" for i in range(len(words)-1)]
    repeats = len(bigrams) - len(set(bigrams))
    repeat_ratio = round(repeats / max(len(bigrams), 1) * 100, 2)

    human_score = 100 - ((perplexity / 50) * 20 + (repeat_ratio / 2) - (burstiness * 10))
    human_score = max(0, min(100, round(human_score, 1)))

    return {
        "Перплексия (предсказуемость)": perplexity,
        "Разнообразие предложений (Burstiness)": burstiness,
        "Повторяемость фраз (%)": repeat_ratio,
        "Оценка естественности (%)": human_score
    }

# --- Основной процесс ---
if submitted:
    st.info("⚙️ Этап 1: Генерация текста через Perplexity...")
    lsi_list = [w.strip() for w in lsi_words.split(",") if w.strip()]
    text = perplexity_generate(build_prompt(topic, site, competitors, lsi_words, banned, keywords, symbols))
    text = clean_text(text)
    iteration = 1

    progress = st.progress(0)
    while True:
        missing = check_missing_lsi(text, lsi_list)
        if not missing: break
        st.warning(f"Этап 2: доработка LSI ({len(missing)} слов)...")
        addition = perplexity_generate(f"Добавь абзац со словами: {', '.join(missing)}.\n\n{text}")
        text += "\n" + clean_text(addition)
        iteration += 1
        progress.progress(min(90, iteration * 20))

    progress.progress(100)
    st.success("✅ Текст готов!")
    st.text_area("Результат", text, height=400)

    # === Проверка уникальности ===
    st.info("🔎 Проверка уникальности через Text.ru API...")
    r = requests.post("https://api.text.ru/post", data={"text": text, "userkey": TEXT_RU_KEY})
    if r.ok:
        res = requests.get("https://api.text.ru/post", params={"uid": r.json()["text_uid"], "userkey": TEXT_RU_KEY}).json()
        uniq = res.get("text_unique", "?")
        st.write(f"**Уникальность:** {uniq}%")
    else:
        st.warning("Ошибка при проверке уникальности.")

    # === SEO-оценка ===
    st.info("📊 SEO-анализ текста...")
    report = seo_score(text, keywords)
    st.table(report.items())

    # === Анализ естественности ===
    st.info("🧠 Анализ естественности текста...")
    human_report = analyze_humanness(text)
    st.table(human_report.items())
    score = human_report["Оценка естественности (%)"]

    if score >= 85:
        st.success(f"✅ Текст выглядит полностью естественным ({score}%) — написан живо и по-человечески.")
    elif score >= 70:
        st.info(f"🟢 Текст преимущественно естественный ({score}%) — небольшие признаки шаблонности.")
    elif score >= 50:
        st.warning(f"🟠 Текст выглядит отчасти машинным ({score}%) — желательно переработать стиль.")
    else:
        st.error(f"🔴 Текст похож на ИИ ({score}%) — рекомендуется сильная редактура.")

    # === Проверка на ИИ (внешняя кнопка) ===
    st.markdown(f"[🧩 Проверить на сайте AI Detector](https://aidetectorwriter.com/ru/?text={quote(text)})")

    export_docx(text, report, human_report)
    save_history(topic, symbols, len(lsi_list), text)
