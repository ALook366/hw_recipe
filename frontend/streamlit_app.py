"""Streamlit фронтенд для Shopping List App"""

import streamlit as st
import requests
import os
from dotenv import load_dotenv
import time

# Загрузка переменных окружения
load_dotenv()

API_URL = os.getenv("API_URL", "http://localhost:8000")

# Настройка страницы
st.set_page_config(
    page_title="Список покупок",
    page_icon="🛒",
    layout="wide"
)


def check_api_health():
    """Проверка доступности API"""
    try:
        response = requests.get(f"{API_URL}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            return True, data.get("api_configured", False)
        return False, False
    except:
        return False, False


def main():
    st.title("🛒 Генератор списка покупок")
    st.markdown("Напишите блюдо — получите список продуктов с учётом количества персон")

    # Проверка API
    api_available, api_configured = check_api_health()

    col1, col2 = st.columns([3, 1])
    with col1:
        if not api_available:
            st.error("❌ API сервер недоступен")
            st.info("📡 Запустите API командой:\n```bash\nuvicorn backend.main:app --reload --port 8000\n```")
        elif not api_configured:
            st.warning("⚠️ API ключ OpenRouter не настроен, используется МОК-режим")
        else:
            st.success("✅ API сервер готов к работе")

    with col2:
        if st.button("🔄 Проверить API"):
            st.rerun()

    st.divider()

    # Форма ввода
    with st.form("shopping_form"):
        dish = st.text_area(
            "🍳 Что приготовить?",
            placeholder="Примеры: Борщ, Оливье, Пицца Маргарита, Омлет с сыром, Паста Карбонара...",
            height=100,
            help="Напишите название блюда или его основные ингредиенты"
        )

        col1, col2 = st.columns(2)
        with col1:
            people = st.selectbox(
                "👥 На сколько человек?",
                options=["1", "2", "4", "6"],
                help="Количество персон влияет на количество продуктов"
            )
        with col2:
            output_format = st.selectbox(
                "📄 Формат вывода",
                options=["Список продуктов", "Список + шаги"],
                help="Только список продуктов или с шагами приготовления"
            )

        submitted = st.form_submit_button(
            "✨ Сгенерировать список покупок",
            type="primary",
            use_container_width=True
        )

    if submitted:
        # Валидация на клиенте
        if not dish or not dish.strip():
            st.error("❌ Напишите, что хотите приготовить.")
            return

        if len(dish.strip()) > 500:
            st.error("❌ Слишком длинный текст — сократите или разбейте на части.")
            return

        # Проверка API доступности перед запросом
        if not api_available:
            st.error("❌ API сервер недоступен. Запустите бэкенд командой: uvicorn backend.main:app --reload")
            return

        # Прогресс бар
        progress_bar = st.progress(0, text="Подготовка запроса...")

        try:
            progress_bar.progress(30, text="Отправка запроса к API...")

            response = requests.post(
                f"{API_URL}/generate",
                json={
                    "dish": dish.strip(),
                    "people": people,
                    "output_format": output_format
                },
                timeout=60
            )

            progress_bar.progress(80, text="Обработка ответа...")

            if response.status_code == 200:
                data = response.json()

                if data["success"]:
                    progress_bar.progress(100, text="Готово!")
                    st.success("✅ Список продуктов сгенерирован!")

                    # Информация о модели
                    if data.get("model_used"):
                        st.caption(f"🔧 Использована модель: {data['model_used']}")

                    # Результат
                    st.text_area(
                        "📋 Результат:",
                        value=data["result"],
                        height=400,
                        key="result_output",
                        label_visibility="collapsed"
                    )
                else:
                    st.error(f"❌ {data.get('error', 'Неизвестная ошибка')}")

            elif response.status_code == 503:
                st.error("❌ Сервис временно недоступен. Попробуйте позже.")
            elif response.status_code == 422:
                st.error("❌ Неверный формат запроса. Проверьте введённые данные.")
            else:
                st.error(f"❌ Ошибка API (код {response.status_code}). Попробуйте позже.")

        except requests.exceptions.Timeout:
            st.error("❌ Не удалось получить ответ. Попробуйте ещё раз.")
        except requests.exceptions.ConnectionError:
            st.error("❌ Не удалось подключиться к API. Убедитесь, что сервер запущен.")
        except Exception as e:
            st.error(f"❌ Пустой ответ модели. Попробуйте переформулировать вопрос.")
        finally:
            time.sleep(0.5)
            progress_bar.empty()


if __name__ == "__main__":
    main()