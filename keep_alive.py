import os
import requests
import time

RENDER_API_KEY = os.getenv("RENDER_API_KEY")
SERVICE_ID = "srv-d43f4kpr0fns73evb16g"  # <-- твой ID сервиса в Render
CHECK_URL = "https://text-master.seo-rezult.ru"
CHECK_INTERVAL = 600  # каждые 10 минут

def check_site():
    try:
        r = requests.get(CHECK_URL, timeout=10)
        return r.status_code == 200
    except Exception as e:
        print(f"[ERROR] Не удалось проверить сайт: {e}")
        return False

def restart_render_service():
    url = f"https://api.render.com/v1/services/{SERVICE_ID}/deploys"
    headers = {"Authorization": f"Bearer {RENDER_API_KEY}", "Content-Type": "application/json"}
    data = {"clearCache": True}
    r = requests.post(url, headers=headers, json=data)
    if r.status_code == 201:
        print("✅ Render-сервис успешно перезапущен.")
    else:
        print(f"⚠️ Ошибка перезапуска: {r.status_code} — {r.text}")

def main():
    print("🚀 Мониторинг Render запущен...")
    while True:
        if check_site():
            print("✅ Сайт работает нормально.")
        else:
            print("❌ Сайт недоступен — выполняю перезапуск Render.")
            restart_render_service()
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
