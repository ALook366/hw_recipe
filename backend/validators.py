"""Валидаторы для входных данных"""

MAX_INPUT_LENGTH = 500


def validate_dish_input(text: str) -> tuple[bool, str]:
    """
    Валидация ввода блюда

    Returns:
        tuple[bool, str]: (валидность, сообщение_об_ошибке)
    """
    if not text or text.strip() == "":
        return False, "Напишите, что хотите приготовить."

    if len(text.strip()) > MAX_INPUT_LENGTH:
        return False, "Слишком длинный текст — сократите или разбейте на части."

    return True, ""


def validate_people_count(people: str) -> tuple[bool, str]:
    """Валидация количества персон"""
    if people not in ["1", "2", "4", "6"]:
        return False, "Выберите корректное количество персон (1, 2, 4 или 6)"
    return True, ""


def validate_output_format(format_type: str) -> tuple[bool, str]:
    """Валидация формата вывода"""
    if format_type not in ["Список продуктов", "Список + шаги"]:
        return False, "Выберите корректный формат вывода"
    return True, ""