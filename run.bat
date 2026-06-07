@echo off
echo 🚀 Запуск Shopping List App
echo ================================

if not exist ".env" (
    echo ⚠️ .env файл не найден, создаю из .env.example
    copy .env.example .env
    echo ✏️ Отредактируйте .env и добавьте OPENROUTER_API_KEY
)

if exist "venv\" (
    echo 📦 Активация виртуального окружения...
    call venv\Scripts\activate.bat
) else (
    echo ❌ Виртуальное окружение не найдено
    echo Создайте его: python -m venv venv
    exit /b 1
)

echo 📡 Запуск FastAPI бэкенда на http://localhost:8000
start /B uvicorn backend.main:app --reload --port 8000

timeout /t 3 /nobreak >nul

echo 🎨 Запуск Streamlit UI на http://localhost:8501
streamlit run frontend/streamlit_app.py --server.port 8501

echo 🛑 Остановка API...
taskkill /F /IM uvicorn.exe