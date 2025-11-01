import streamlit as st
import requests, sqlite3, os, re
from dotenv import load_dotenv
from datetime import datetime
from docx import Document
from urllib.parse import quote

load_dotenv()
PPLX_API_KEY = os.getenv("PPLX_API_KEY")
TEXT_RU_KEY = os.getenv("TEXT_RU_KEY")

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

st.set_page_config(page_title="SEO Rezult Text Master v5.0", layout="wide")

st.title("🚀 SEO Rezult Text Master v5.0")
st.caption("Генератор SEO-текстов с LSI-анализом, проверкой уникальности, естественности и SEO-оценкой")

# =================== Ввод данных ===================
with st.form("input_form"):
    topic = st.text_input("Тематика текста")
    site = st.text_input("Сайт клиента")
    competitors = st.text_area("Ссылки на конкурентов (по одной в строке)")
    lsi_words = st.text_area("Список LSI-слов (через запятую)")
    banned = st.text_area("Запрещённые слова (через запятую)")
    keywords = st.text_area("Ключевые слова (через запятую)")
    symbols = st.number_input("Количество символов", value=8000, step=500)
    submitted = st.form_submit_button("Сгенерировать текст")

# =================== Генерация ===================
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
Длина ≈ {symbols} символов.
Пиши естественно, без шаблонов и с фактами.
"""

def clean_text(text):
    return re.sub(r"[#*_>`]+", "", text).strip()

def check_missing_lsi(text, lsi_list):
    return [w for w in lsi_list if w.lower() not in text.lower()]

def save_history(topic, symbols, lsi_count, text):
    conn.execute("INSERT INTO history (date,topic,symbols,lsi_count,text) VALUES (?,?,?, ?, ?)",
                 (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), topic, symbols, lsi_count, text))
    conn.commit()

def export_docx(text, report, filename="seo_text.docx"):
    doc = Document()
    doc.add_heading("SEO Rezult Text Master", level=1)
    doc.add_paragraph(text)
    doc.add_page_break()
    doc.add_heading("SEO-оценка", level=2)
    for k, v in report.items():
        doc.add_paragraph(f"{k}: {v}")
    doc.save(filename)
    with open(filename, "rb") as f:
        st.download_button("📥 Скачать DOCX", f, file_name=filename)

# =================== SEO-анализ ===================
def seo_score(text, keywords):
    words = re.findall(r"\w+", text.lower())
    word_count = len(words)
    avg_len = sum(len(w) for w in words) / len(words)
    key_density = sum(text.lower().count(k.lower()) for k in keywords.split(",")) / max(word_count, 1) * 100
    sentences = re.split(r"[.!?]", text)
    avg_sentence_len = sum(len(s.split()) for s in sentences if s.strip()) / max(len(sentences), 1)
    water = len(re.findall(r"\b(очень|это|также|поэтому|например)\b", text.lower())) / max(word_count, 1) * 100
    return {
        "Общее кол-во слов": word_count,
        "Средняя длина слова": round(avg_len, 2),
        "Средняя длина предложения": round(avg_sentence_len, 2),
        "Плотность ключей (%)": round(key_density, 2),
        "Водность (%)": round(water, 2)
    }

# =================== Основной процесс ===================
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
    st.info("📊 Анализ SEO-показателей...")
    report = seo_score(text, keywords)
    st.table(report.items())

    # === Кнопка проверки на ИИ ===
    st.markdown(f"[🧠 Проверить на ИИ и человечность](https://aidetectorwriter.com/ru/?text={quote(text)})")

    export_docx(text, report)
    save_history(topic, symbols, len(lsi_list), text)
