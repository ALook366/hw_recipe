from pydantic import BaseModel, Field, validator
from typing import Optional


class ShoppingListRequest(BaseModel):
    """Модель запроса для генерации списка покупок"""
    dish: str = Field(..., min_length=1, max_length=500, description="Название блюда")
    people: str = Field(..., description="Количество персон")
    output_format: str = Field(..., description="Формат вывода")

    @validator('people')
    def validate_people(cls, v):
        if v not in ["1", "2", "4", "6"]:
            raise ValueError('people must be 1, 2, 4, or 6')
        return v

    @validator('output_format')
    def validate_format(cls, v):
        if v not in ["Список продуктов", "Список + шаги"]:
            raise ValueError('output_format must be "Список продуктов" or "Список + шаги"')
        return v

    @validator('dish')
    def validate_dish(cls, v):
        if not v or not v.strip():
            raise ValueError('Dish cannot be empty')
        if len(v.strip()) > 500:
            raise ValueError('Dish too long (max 500 characters)')
        return v.strip()


class ShoppingListResponse(BaseModel):
    """Модель ответа API"""
    success: bool
    result: str
    error: Optional[str] = None
    model_used: Optional[str] = None


class HealthResponse(BaseModel):
    """Модель проверки здоровья"""
    status: str
    api_configured: bool