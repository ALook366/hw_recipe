#!/bin/bash

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Запуск Shopping List App${NC}"
echo "================================"

# Проверка наличия .env
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠️  .env файл не найден, создаю из .env.example${NC}"
    cp .env.example .env
    echo -e "${YELLOW}✏️  Отредактируйте .env и добавьте OPENROUTER_API_KEY${NC}"
fi

# Активация виртуального окружения
if [ -d "venv" ]; then
    echo -e "${GREEN}📦 Активация виртуального окружения...${NC}"
    source venv/bin/activate
else
    echo -e "${RED}❌ Виртуальное окружение не найдено${NC}"
    echo "Создайте его: python3 -m venv venv"
    exit 1
fi

# Запуск FastAPI в фоне
echo -e "${GREEN}📡 Запуск FastAPI бэкенда на http://localhost:8000${NC}"
uvicorn backend.main:app --reload --port 8000 &
API_PID=$!

# Ожидание запуска API
sleep 3

# Проверка запуска API
if ! kill -0 $API_PID 2>/dev/null; then
    echo -e "${RED}❌ Не удалось запустить API${NC}"
    exit 1
fi

echo -e "${GREEN}✅ API запущен (PID: $API_PID)${NC}"

# Запуск Streamlit
echo -e "${GREEN}🎨 Запуск Streamlit UI на http://localhost:8501${NC}"
streamlit run frontend/streamlit_app.py --server.port 8501

# Остановка API при завершении работы Streamlit
echo -e "${YELLOW}🛑 Остановка API...${NC}"
kill $API_PID