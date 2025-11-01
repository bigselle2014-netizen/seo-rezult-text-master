import streamlit as st
import requests, sqlite3, os, time, re
from dotenv import load_dotenv
from datetime import datetime
from docx import Document
from collections import Counter

# === ЗАГРУЗКА КЛЮЧЕЙ ===
load_dotenv()
API_KEY = os.getenv("PPLX_API_KEY")
TEXT_RU_KEY = os.getenv("TEXT_RU_KEY")

# === БАЗА ДАННЫХ ===
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

# === НАСТРОЙКИ СТРАНИЦЫ ===
st.set_page_config(page_title="SEO Rezult Text Master", layout="wide")
st.title("🚀 SEO Rezult Text Master v4.0")
st.caption("Генератор SEO-текстов с LSI-анализом, проверкой уникальности, естественности и SEO-оценкой")

# === ФОРМА ВВОДА ===
with st.form("input_form"):
    topic = st.text_input("Тематика текста")
    site = st.text_input("Сайт клиента")
    competitors = st.text_area("Ссылки на конкурентов (по одной в строке)")
    lsi_words = st.text_area("Список LSI-слов (через запятую)")
    ngrams = st.text_area("Список n-грамм (необязательно)")
    banned = st.text_area("Запрещённые слова (через запятую)")
    keywords = st.text_area("Ключевые слова (через запятую)")
    symbols = st.number_input("Количество символов", value=10000, step=500)
    submitted = st.form_submit_button("Сгенерировать текст")

# === ФУНКЦИИ ===
def perplexity_generate(prompt: str):
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "sonar-pro",
        "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}],
        "max_output_tokens": 2500,
    }
    r = requests.post("https://api.perplexity.ai/chat/completions", json=payload, headers=headers)
    if not r.ok:
        st.error(f"Ошибка Perplexity ({r.status_code}): {r.text}")
        r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

def build_prompt(topic, site, competitors, lsi, ngrams, banned, keys, symbols):
    return f"""
Ты опытный SEO-копирайтер и журналист.
Напиши экспертный и естественный SEO-текст на тему: {topic}.
Сайт клиента: {site}.
Конкуренты: {competitors}.
Используй ключевые слова: {keys}.
Используй LSI-фразы: {lsi}.
Избегай слов: {banned}.
Добавь фразы: {ngrams}.
Длина ≈ {symbols} символов.
Пиши живым языком, без шаблонов и «ИИ-тона».
"""

def check_missing_lsi(text, lsi_list):
    return [w for w in lsi_list if w.lower() not in text.lower()]

def save_history(topic, symbols, lsi_count, text):
    conn.execute(
        "INSERT INTO history (date,topic,symbols,lsi_count,text) VALUES (?,?,?,?,?)",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), topic, symbols, lsi_count, text),
    )
    conn.commit()

def export_docx(text, filename="seo_text.docx"):
    doc = Document(); doc.add_paragraph(text); doc.save(filename)
    with open(filename, "rb") as f:
        st.download_button("📥 Скачать DOCX", f, file_name=filename)

# === ПРОВЕРКА УНИКАЛЬНОСТИ ===
def check_text_unique(text):
    if not TEXT_RU_KEY:
        st.warning("🔑 Ключ TEXT_RU_KEY не найден в .env")
        return None
    st.info("🧾 Проверка уникальности через Text.ru…")
    payload = {"userkey": TEXT_RU_KEY, "text": text, "jsonvisible": "detail"}
    resp = requests.post("https://api.text.ru/post", data=payload).json()
    uid = resp.get("text_uid")
    if not uid:
        st.error("Ошибка запроса к Text.ru")
        return None
    for _ in range(20):
        time.sleep(5)
        check = requests.post("https://api.text.ru/post", data={"userkey": TEXT_RU_KEY, "uid": uid}).json()
        if "text_unique" in check:
            return check["text_unique"]
    return None

# === АНАЛИЗ ЕСТЕСТВЕННОСТИ ===
def analyze_naturalness(text):
    sentences = re.split(r'[.!?]', text)
    avg_len = sum(len(s.split()) for s in sentences if s.strip()) / max(1, len(sentences))
    words = re.findall(r'\w+', text.lower())
    common = Counter(words).most_common(10)
    repeat_score = sum(c for _, c in common[:10]) / max(1, len(words))
    return {
        "avg_sentence_len": round(avg_len, 1),
        "top_words": common[:10],
        "repeat_score": round(repeat_score * 100, 2)
    }

# === SEO-ОЦЕНКА ===
def seo_score(unique, coverage, avg_len, repeat_score):
    score = 0
    if unique and unique >= 90: score += 3
    elif unique and unique >= 80: score += 2
    elif unique: score += 1

    if coverage >= 95: score += 3
    elif coverage >= 80: score += 2
    else: score += 1

    if 10 <= avg_len <= 20: score += 2
    else: score += 1

    if repeat_score <= 3: score += 2
    elif repeat_score <= 5: score += 1

    return round(score, 1)

def seo_feedback(unique, coverage, avg_len, repeat_score):
    tips = []
    if unique < 90:
        tips.append("🔁 Повышай уникальность (используй синонимы).")
    if coverage < 95:
        tips.append("🧩 Добавь недостающие LSI-фразы.")
    if avg_len > 20:
        tips.append("✂️ Разбей длинные предложения (до 20 слов).")
    if repeat_score > 3:
        tips.append("🧠 Разнообразь лексику, снизь повторы.")
    if not tips:
        tips.append("🎯 Отличный SEO-текст! Можно публиковать.")
    return tips

# === ОСНОВНОЙ ПРОЦЕСС ===
if submitted:
    lsi_list = [w.strip() for w in lsi_words.split(",") if w.strip()]
    total_lsi = len(lsi_list)
    progress_bar = st.progress(0)
    status_text = st.empty()

    with st.spinner("Генерация первичного текста…"):
        text = perplexity_generate(build_prompt(topic, site, competitors, lsi_words, ngrams, banned, keywords, symbols))

    iteration = 1
    MAX_LSI_PER_ITER = 30

    while True:
        missing = check_missing_lsi(text, lsi_list)
        done = total_lsi - len(missing)
        coverage = int(done / total_lsi * 100) if total_lsi else 100
        progress_bar.progress(min(coverage, 100))
        status_text.text(f"🧩 Покрытие LSI: {done}/{total_lsi} ({coverage}%) | Итерация {iteration}")

        if not missing:
            break

        batch = missing[:MAX_LSI_PER_ITER]
        st.info(f"Итерация {iteration}: отсутствует {len(batch)} LSI-слов → дорабатываю…")

        fix_prompt = (
            f"Спасибо за текст, но ты не учёл {len(batch)} LSI-слов. "
            f"Прошу добавить абзацы с этими словами: {', '.join(batch)}"
        )

        try:
            addition = perplexity_generate(fix_prompt + "\n\nИсходный текст:\n" + text)
            text += "\n" + addition
            iteration += 1
            time.sleep(1)
        except Exception as e:
            st.error(f"⚠️ Ошибка при доработке: {e}")
            break

    progress_bar.progress(100)
    status_text.text("✅ Все LSI-слова учтены. Текст готов!")

    st.success("✅ Текст успешно создан!")
    st.text_area("Результат", text, height=400)
    export_docx(text)
    save_history(topic, symbols, total_lsi, text)

    # --- Проверка уникальности
    unique = check_text_unique(text)
    if unique:
        st.success(f"🧾 Уникальность текста: {unique}%")

    # --- Анализ естественности
    stats = analyze_naturalness(text)
    st.subheader("🧠 Анализ естественности")
    st.write(f"Средняя длина предложения: {stats['avg_sentence_len']} слов")
    st.write(f"Повторяемость топ-слов: {stats['repeat_score']}%")
    st.write("Наиболее часто встречающиеся слова:")
    st.json(stats['top_words'])

    # --- SEO-Оценка
    st.subheader("📊 SEO-Оценка текста")
    coverage = 100
    final_score = seo_score(unique or 100, coverage, stats['avg_sentence_len'], stats['repeat_score'])
    st.metric("Общая SEO-оценка", f"{final_score} / 10")
    st.metric("Уникальность", f"{unique}%")
    st.metric("LSI-покрытие", f"{coverage}%")
    st.metric("Средняя длина предложения", f"{stats['avg_sentence_len']} слов")
    st.metric("Повторяемость топ-слов", f"{stats['repeat_score']}%")

    st.subheader("💡 Рекомендации")
    for tip in seo_feedback(unique or 100, coverage, stats['avg_sentence_len'], stats['repeat_score']):
        st.write(tip)

# === ИСТОРИЯ ===
st.subheader("📚 История генераций")
rows = conn.execute("SELECT id,date,topic,symbols,lsi_count FROM history ORDER BY id DESC").fetchall()
if rows:
    for row in rows:
        with st.expander(f"{row[1]} — {row[2]}"):
            st.write(f"Объём: {row[3]} символов, LSI: {row[4]}")
            txt = conn.execute("SELECT text FROM history WHERE id=?", (row[0],)).fetchone()[0]
            st.text_area("Текст", txt, height=200)
else:
    st.info("История пока пуста.")
