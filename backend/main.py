"""FastAPI приложение для генерации списка покупок"""

from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(env_path)

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
from typing import Dict

from .models import ShoppingListRequest, ShoppingListResponse, HealthResponse
from .llm import OpenRouterClient

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Глобальный клиент
llm_client: OpenRouterClient = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    global llm_client

    logger.info("🔄 Инициализация OpenRouter клиента...")
    llm_client = OpenRouterClient()

    if llm_client.mock_mode:
        logger.info("🔧 Работа в MOCK режиме")
    elif llm_client.api_key and llm_client.api_key != "your_api_key_here":
        logger.info("✅ API ключ OpenRouter настроен, загрузка списка моделей...")
        await llm_client.initialize()
        if llm_client.available_models:
            logger.info(f"✅ Загружено {len(llm_client.available_models)} бесплатных моделей")
        else:
            logger.warning("⚠️ Не удалось загрузить модели из OpenRouter")
    else:
        logger.warning("⚠️ API ключ OpenRouter не настроен, используется MOCK режим")

    yield

    logger.info("👋 Завершение работы приложения")


# Создание FastAPI приложения
app = FastAPI(
    title="Shopping List API",
    description="API для генерации списка покупок через OpenRouter с автоматическим переключением между моделями",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Настройка CORS для Streamlit
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8501",
        "http://localhost:8502",
        "http://127.0.0.1:8501",
        "http://127.0.0.1:8502"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_model=Dict)
async def root():
    """Корневой эндпоинт"""
    return {
        "message": "Shopping List API",
        "version": "2.0.0",
        "status": "running",
        "docs": "/docs"
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Проверка здоровья сервиса"""
    return HealthResponse(
        status="healthy",
        api_configured=bool(
            llm_client.api_key and
            llm_client.api_key != "your_api_key_here" and
            not llm_client.mock_mode
        )
    )


@app.post(
    "/generate",
    response_model=ShoppingListResponse,
    status_code=status.HTTP_200_OK,
    summary="Генерация списка покупок",
    description="Создаёт список продуктов и (опционально) шаги приготовления на основе названия блюда"
)
async def generate_shopping_list(request: ShoppingListRequest):
    """
    Генерация списка покупок

    - **dish**: Название блюда (от 1 до 500 символов)
    - **people**: Количество персон (1, 2, 4 или 6)
    - **output_format**: Формат вывода ("Список продуктов" или "Список + шаги")
    """
    try:
        logger.info(
            f"📝 Запрос: блюдо='{request.dish[:50]}...', персоны={request.people}, формат={request.output_format}")

        # Вызов LLM клиента
        result, model_or_error = await llm_client.generate_shopping_list(
            dish=request.dish,
            people=request.people,
            output_format=request.output_format
        )

        if result:
            logger.info(f"✅ Успешная генерация через {model_or_error}")
            return ShoppingListResponse(
                success=True,
                result=result,
                model_used=model_or_error
            )
        else:
            logger.error(f"❌ Ошибка генерации: {model_or_error}")

            # Определяем статус код в зависимости от ошибки
            if "временно недоступны" in model_or_error:
                status_code = status.HTTP_503_SERVICE_UNAVAILABLE
                error_detail = model_or_error
            else:
                status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
                error_detail = model_or_error

            raise HTTPException(
                status_code=status_code,
                detail=error_detail
            )

    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"❌ Ошибка валидации: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"❌ Непредвиденная ошибка: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера"
        )


# Обработчики ошибок
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Обработка HTTP исключений"""
    return {
        "success": False,
        "result": "",
        "error": exc.detail,
        "model_used": None
    }


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Обработка всех непредвиденных исключений"""
    logger.error(f"Unhandled exception: {str(exc)}")
    return {
        "success": False,
        "result": "",
        "error": "Произошла непредвиденная ошибка. Попробуйте позже.",
        "model_used": None
    }