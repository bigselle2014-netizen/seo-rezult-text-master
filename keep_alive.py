import os
import requests
import time
import threading

RENDER_API_KEY = os.getenv("RENDER_API_KEY")
SERVICE_ID = "srv-d43f4kpr0fns73evb16g"
CHECK_URL = "https://text-master.seo-rezult.ru"
CHECK_INTERVAL = 600  # каждые 10 минут

def check_site():
    try:
        r = requests.get(CHECK_URL, timeout=10)
        return r.status_code == 200
    except Exception as e:
        print(f"[ERROR] Проверка сайта: {e}")
        return False

def restart_render_service():
    if not RENDER_API_KEY:
        print("⚠️ Пропущено: RENDER_API_KEY не задан.")
        return
    url = f"https://api.render.com/v1/services/{SERVICE_ID}/deploys"
    headers = {"Authorization": f"Bearer {RENDER_API_KEY}", "Content-Type": "application/json"}
    data = {"clearCache": True}
    r = requests.post(url, headers=headers, json=data)
    if r.status_code == 201:
        print("✅ Render-сервис перезапущен.")
    else:
        print(f"⚠️ Ошибка перезапуска: {r.status_code} — {r.text}")

def monitor():
    print("🚀 Мониторинг Render запущен...")
    while True:
        if check_site():
            print("✅ Сайт работает.")
        else:
            print("❌ Сайт недоступен — выполняется перезапуск.")
            restart_render_service()
        time.sleep(CHECK_INTERVAL)

def keep_alive():
    def run():
        while True:
            try:
                r = requests.get(CHECK_URL, timeout=10)
                print(f"[KeepAlive] Пинг {r.status_code}")
            except Exception as e:
                print("[KeepAlive] Ошибка:", e)
            time.sleep(300)
    threading.Thread(target=run, daemon=True).start()
    threading.Thread(target=monitor, daemon=True).start()
