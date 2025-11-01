import streamlit as st
from supabase import create_client
import os

# Загружаем ключи из Streamlit Secrets
SUPABASE_URL = os.getenv("SUPABASE_URL") or st.secrets["SUPABASE_URL"]
SUPABASE_KEY = os.getenv("SUPABASE_KEY") or st.secrets["SUPABASE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def login_or_register():
    st.sidebar.header("🔐 Авторизация")
    choice = st.sidebar.radio("Выберите действие:", ["Вход", "Регистрация"])

    email = st.sidebar.text_input("Email")
    password = st.sidebar.text_input("Пароль", type="password")

    if choice == "Регистрация":
        if st.sidebar.button("Создать аккаунт"):
            try:
                res = supabase.auth.sign_up({"email": email, "password": password})
                if res.user:
                    st.success("✅ Аккаунт создан! Проверь почту для подтверждения.")
                else:
                    st.warning(res)
            except Exception as e:
                st.error(f"Ошибка регистрации: {e}")

    elif choice == "Вход":
        if st.sidebar.button("Войти"):
            try:
                res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                if res.user:
                    st.session_state["user"] = res.user
                    st.success(f"Добро пожаловать, {email}!")
                else:
                    st.warning("Неверный логин или пароль.")
            except Exception as e:
                st.error(f"Ошибка входа: {e}")

    # Кнопка выхода
    if "user" in st.session_state:
        if st.sidebar.button("Выйти"):
            st.session_state.pop("user")
            st.rerun()

    return st.session_state.get("user")
