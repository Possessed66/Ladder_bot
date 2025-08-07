import os
import asyncio
import logging
import math
from typing import Dict, Tuple, Optional, Union
from dataclasses import dataclass
from aiogram import Router, F, Bot, Dispatcher
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import StateFilter
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv


# --- Настройка логирования ---
logging.basicConfig(level=logging.DEBUG) # Или level=logging.INFO для менее подробного лога
logger = logging.getLogger(__name__)

load_dotenv('secret.env')

# --- ИНТЕГРАЦИЯ LADDERCALCULATOR ---
class LadderCalculator:
    """Класс для расчета параметров лестницы с фиксированными элементами 30x20 см"""
    def __init__(self):
        self.min_angle = 30
        self.max_angle = 45
        # --- СТАНДАРТНЫЕ ЭЛЕМЕНТЫ ---
        self.standard_step_width = 30  # см (ширина ступени)
        self.standard_step_height = 20  # см (высота подступенка)
        # -----------------------------
        # Диапазоны для проверок (можно расширить при необходимости)
        self.min_step_width = 25  # см
        self.min_step_height = 15  # см
        self.max_step_height = 25  # см (увеличен для 20 см стандартной)
        self.min_ladder_width = 80  # см
        # Устаревшие параметры, оставлены для совместимости частично
        # self.standard_step = 50  # см (30 + 20)
        # self.min_step = 45  # см
        # self.max_step = 55  # см

    def calculate_angle(self, height: float, length: float, angle: Optional[float] = None) -> Tuple[
        Optional[float], str]:
        """
        Рассчитывает угол наклона лестницы.
        """
        if angle is not None:
            return angle, "Угол задан вручную"
        if length == 0:
            return None, "Ошибка: длина проема не может быть 0"
        try:
            angle_rad = math.atan(height / length)
            angle_deg = math.degrees(angle_rad)
            return round(angle_deg, 2), "Угол рассчитан"
        except Exception:
            return None, "Ошибка при расчете угла"

    def check_angle(self, angle: Optional[float]) -> str:
        """
        Проверяет, попадает ли угол в допустимый диапазон.
        """
        if angle is None:
            return "Ошибка: угол не определен"
        if self.min_angle <= angle <= self.max_angle:
            return "Угол подходит"
        else:
            return f"Угол не подходит (должен быть от {self.min_angle}° до {self.max_angle}°)"

    def calculate_steps(self, height: float, length: float, step_height: Optional[float] = None,
                        step_width: Optional[float] = None) -> Tuple[
        Optional[int], str, Optional[float], Optional[float]]:
        """
        Рассчитывает количество ступеней и параметры шага, ориентируясь на стандарт 30x20 см.
        """
        # 1. Если ничего не задано, используем стандарты
        if step_height is None and step_width is None:
            # Используем стандартную высоту подступенка для расчета количества
            default_height = self.standard_step_height
            # Проверка стандартной высоты (на всякий случай)
            if not (self.min_step_height <= default_height <= self.max_step_height):
                default_height = max(self.min_step_height,
                                     min(self.max_step_height, default_height))
            steps = round(height / default_height)
            actual_height = height / steps
            actual_width = self.standard_step_width
            return steps, "Количество ступеней рассчитано (стандартные элементы 30x20 см)", actual_height, actual_width
        # 2. Если задана только высота подступенка
        elif step_height is not None and step_width is None:
            if step_height <= 0:
                return None, "Ошибка: высота подступенка должна быть положительной", None, None
            # Проверяем, попадает ли заданная высота в допустимый диапазон
            if step_height < self.min_step_height or step_height > self.max_step_height:
                return None, f"Ошибка: высота подступенка должна быть от {self.min_step_height} до {self.max_step_height} см", None, None
            steps = height / step_height
            # Используем стандартную ширину ступени
            actual_width = self.standard_step_width
            return round(steps), "Количество ступеней рассчитано (высота задана)", step_height, actual_width
        # 3. Если задана только ширина ступени
        elif step_width is not None and step_height is None:
            if step_width <= 0:
                return None, "Ошибка: ширина ступени должна быть положительной", None, None
            # Проверяем ширину
            if step_width < self.min_step_width:
                return None, f"Ошибка: ширина ступени должна быть не менее {self.min_step_width} см", None, None
            # Рассчитываем высоту, используя стандартную "сумму шага" или напрямую?
            # Вариант: Используем стандартную высоту подступенка
            standard_height = self.standard_step_height
            if self.min_step_height <= standard_height <= self.max_step_height:
                steps = height / standard_height
                return round(steps), "Количество ступеней рассчитано (ширина задана, высота стандартная)", standard_height, step_width
            else:
                # Если стандартная высота недопустима, рассчитываем
                # Это маловероятно при стандартных 20 см и диапазоне 15-25
                steps = height / standard_height
                return round(steps), "Количество ступеней рассчитано (ширина задана)", standard_height, step_width
        # 4. Если заданы и ширина, и высота
        else:
            # Оба параметра заданы
            if step_height <= 0 or step_width <= 0:
                return None, "Ошибка: параметры должны быть положительными", None, None
            # Проверка высоты
            if step_height < self.min_step_height or step_height > self.max_step_height:
                return None, f"Ошибка: высота подступенка должна быть от {self.min_step_height} до {self.max_step_height} см", None, None
            # Проверка ширины
            if step_width < self.min_step_width:
                return None, f"Ошибка: ширина ступени должна быть не менее {self.min_step_width} см", None, None
            # Расчет количества ступеней
            steps = height / step_height
            return round(steps), "Количество ступеней рассчитано (ширина и высота заданы)", step_height, step_width

    def calculate_length(self, height: float, length: float,
                         angle: Optional[float] = None) -> Tuple[Optional[float], str]:
        """
        Рассчитывает длину лестницы.
        """
        if angle is not None:
            try:
                length_ladder = length / math.cos(math.radians(angle))
                return round(length_ladder, 2), "Длина лестницы рассчитана по углу"
            except:
                return None, "Ошибка: неверный угол"
        else:
            try:
                length_ladder = math.sqrt(height ** 2 + length ** 2)
                return round(length_ladder, 2), "Длина лестницы рассчитана по теореме Пифагора"
            except:
                return None, "Ошибка: неверные параметры"

    def calculate_parts(self, steps: int, ladder_type: int = 1) -> Dict[str, Union[int, str]]:
        """
        Рассчитывает количество деталей лестницы.
        """
        if ladder_type not in [1, 2, 3]:
            ladder_type = 1
        parts = {
            "ступени": steps,
            "подступенки": steps,
            "косоуры": 2 if ladder_type == 1 else 1,
            "балясины": steps + 2,
            "поручни": 2,
            "площадки": 1 if ladder_type in [2, 3] else 0,
            "поворотные ступени": 2 if ladder_type in [2, 3] else 0
        }
        return parts

    def validate_inputs(self, height: float, length: float, width: Optional[float] = None) -> str:
        """
        Проверяет входные параметры на корректность.
        """
        errors = []
        if height <= 0:
            errors.append("Высота должна быть положительной")
        if length <= 0:
            errors.append("Длина проема должна быть положительной")
        if height > 500:
            errors.append("Высота слишком большая (максимум 500 см)")
        if length > 1000:
            errors.append("Длина проема слишком большая (максимум 1000 см)")
        if width is not None and width < self.min_ladder_width:
            errors.append(f"Ширина проема должна быть не менее {self.min_ladder_width} см")
        return "; ".join(errors) if errors else ""

    def check_installation_feasibility(self, height: float, length: float, width: Optional[float],
                                       angle: float, steps: int, step_width: float,
                                       step_height: float, horizontal_projection: float) -> Dict[
        str, Union[bool, str, list]]:
        """
        Проверяет возможность установки лестницы (включая габариты).
        """
        feasibility = {
            "possible": True,
            "issues": [],
            "warnings": []
        }
        # Проверка наличия необходимых параметров
        if steps is None or steps == 0:
            feasibility["possible"] = False
            feasibility["issues"].append("Не удалось рассчитать количество ступеней")
            return feasibility
        if step_width is None or step_height is None or step_width <= 0 or step_height <= 0:
            feasibility["possible"] = False
            feasibility["issues"].append("Не удалось рассчитать параметры ступеней")
            return feasibility
        # Проверка угла
        if angle is None:
            feasibility["possible"] = False
            feasibility["issues"].append("Угол наклона не определен")
        elif not (self.min_angle <= angle <= self.max_angle):
            feasibility["possible"] = False
            feasibility["issues"].append(
                f"Угол наклона {angle}° вне допустимого диапазона ({self.min_angle}°-{self.max_angle}°)")
        # --- УДАЛЕНА ПРОВЕРКА СУММЫ ШАГА (step_sum) ---
        # Она больше не актуальна при фиксированных элементах
        # ---------------------------------------------
        # Проверка высоты подступенка
        if step_height < self.min_step_height:
            feasibility["possible"] = False
            feasibility["issues"].append(f"Слишком низкие подступенки ({step_height} см < {self.min_step_height} см)")
        elif step_height > self.max_step_height:
            feasibility["possible"] = False
            feasibility["issues"].append(f"Слишком высокие подступенки ({step_height} см > {self.max_step_height} см)")
        # Проверка ширины ступени
        if step_width < self.min_step_width:
            feasibility["possible"] = False
            feasibility["issues"].append(f"Слишком узкие ступени ({step_width} см < {self.min_step_width} см)")
        # Проверка минимального количества ступеней
        if steps < 3:
            feasibility["possible"] = False
            feasibility["issues"].append("Слишком мало ступеней (минимум 3)")
        # Проверка максимального количества ступеней
        if steps > 25:  # Увеличен лимит
            feasibility["possible"] = False
            feasibility["issues"].append("Слишком много ступеней (максимум 25)")
        # Проверка ширины проема
        if width is not None and width < self.min_ladder_width:
            feasibility["possible"] = False
            feasibility["issues"].append(f"Ширина проема недостаточна ({width} см < {self.min_ladder_width} см)")
        # Проверка габаритов (самая важная!)
        if horizontal_projection > length:
            feasibility["possible"] = False
            feasibility["issues"].append(
                f"Лестница не поместится по длине: требуется {horizontal_projection} см, доступно {length} см")
        # Предупреждения
        # Уточнены для новых стандартов
        if step_height < 17:
            feasibility["warnings"].append("Высота подступенка на нижней границе комфортного диапазона")
        elif step_height > 23:
            feasibility["warnings"].append("Высота подступенка на верхней границе комфортного диапазона (стандарт 20 см)")
        if step_width < 28:
            feasibility["warnings"].append("Ширина ступени близка к минимальной (стандарт 30 см)")
        elif step_width > 35:
             feasibility["warnings"].append("Ширина ступени больше стандартной (стандарт 30 см)")
        return feasibility

    def calculate_ladder_footprint(self, steps: int, step_width: float,
                                   ladder_type: int) -> Dict[str, Union[float, str]]:
        """
        Рассчитывает фактические габариты лестницы.
        """
        if steps <= 0 or step_width <= 0:
            return {"error": "Неверные параметры для расчета габаритов"}
        footprint = {
            "message": "Габариты рассчитаны"
        }
        if ladder_type == 1:  # Прямая
            # Горизонтальная проекция прямой лестницы
            footprint["horizontal_projection"] = round((steps - 1) * step_width, 2)
            footprint["width_required"] = 80
            footprint["description"] = "Прямая лестница"
        elif ladder_type == 2:  # П-образная
            # Для П-образной: две секции + площадка
            section_steps = max(1, steps // 2)
            footprint["horizontal_projection"] = round(2 * ((section_steps - 1) * step_width) + 100, 2)
            footprint["width_required"] = 120
            footprint["description"] = "П-образная лестница"
        elif ladder_type == 3:  # Г-образная
            # Для Г-образной: одна секция + поворот
            footprint["horizontal_projection"] = round((steps - 1) * step_width + 80, 2)
            footprint["width_required"] = 100
            footprint["description"] = "Г-образная лестница"
        else:
            footprint["horizontal_projection"] = round((steps - 1) * step_width, 2)
            footprint["width_required"] = 80
            footprint["description"] = "Прямая лестница (по умолчанию)"
        return footprint

    def suggest_optimal_parameters(self, height: float, available_length: float,
                                   available_width: Optional[float] = None) -> Dict[str, any]:
        """
        Предлагает оптимальные параметры лестницы для заданных габаритов, ориентируясь на стандарт 30x20 см.
        """
        suggestions = {
            "message": "Предложения по оптимизации под стандарт 30x20 см"
        }
        # 1. Попробуем использовать стандартные элементы
        # Рассчитаем количество ступеней с высотой 20 см
        std_steps = round(height / self.standard_step_height)
        std_actual_height = height / std_steps
        std_width = self.standard_step_width
        std_projection = (std_steps - 1) * std_width
        if std_projection <= available_length and \
                self.min_step_height <= std_actual_height <= self.max_step_height:
            suggestions["standard_option"] = {
                "note": "Рекомендуемый стандартный вариант",
                "steps": std_steps,
                "height": round(std_actual_height, 2),
                "width": std_width,
                "projection": round(std_projection, 2),
                "will_fit": True
            }
            suggestions["message"] = "Найдено решение с использованием стандартных элементов 30x20 см"
        # 2. Если стандарт не подходит, ищем альтернативы
        # Находим максимальное количество ступеней, которое поместится
        max_steps = 0
        best_params = None
        # Пробуем от 3 до 25 ступеней
        for steps in range(3, 26):
            step_height = height / steps
            # Проверяем, попадает ли высота в допустимый диапазон
            if self.min_step_height <= step_height <= self.max_step_height:
                step_width = self.standard_step_width  # Пробуем с фиксированной шириной 30 см
                horizontal_projection = (steps - 1) * step_width
                if horizontal_projection <= available_length:
                    if steps > max_steps:
                        max_steps = steps
                        best_params = {
                            "steps": steps,
                            "height": round(step_height, 2),
                            "width": step_width,
                            "projection": round(horizontal_projection, 2)
                        }
        if best_params and (max_steps != std_steps or not suggestions.get("standard_option")):
            suggestions["best_option"] = best_params
            if "message" not in suggestions or "стандарт" not in suggestions["message"]:
                suggestions["message"] = "Найдены подходящие параметры (ширина ступени фиксирована 30 см)"
        # 3. Если ничего не нашли, предлагаем минимальные параметры
        if not suggestions.get("standard_option") and not suggestions.get("best_option"):
            # Предлагаем минимальные параметры
            min_steps = max(3, round(height / self.max_step_height))
            min_height = height / min_steps
            min_width = self.standard_step_width  # Фиксируем ширину
            min_projection = (min_steps - 1) * min_width
            suggestions["minimum_option"] = {
                "steps": min_steps,
                "height": round(min_height, 2),
                "width": min_width,
                "projection": round(min_projection, 2)
            }
            suggestions["message"] = "Рекомендуемые минимальные параметры (ширина ступени 30 см)"
        return suggestions

    def calculate_all(self, height: float, length: float, width: Optional[float] = None,
                      angle: Optional[float] = None, step_height: Optional[float] = None,
                      step_width: Optional[float] = None, ladder_type: int = 1) -> Dict[str, any]:
        """
        Полный расчет всех параметров лестницы с проверкой возможности установки.
        """
        logger.debug(f"calculate_all called with: height={height}, length={length}, width={width}, "
                     f"ladder_type={ladder_type}")
                          
        # Валидация входных данных
        validation_error = self.validate_inputs(height, length, width)
        if validation_error:
            logger.debug(f"Validation error: {validation_error}")
            return {"error": validation_error}
        result = {
            "inputs": {
                "height": height,
                "length": length,
                "width": width,
                "angle": angle,
                "step_height": step_height,
                "step_width": step_width,
                "ladder_type": ladder_type
            },
            "warnings": []
        }
        # Расчет угла
        calculated_angle, angle_msg = self.calculate_angle(height, length, angle)
        result["angle"] = {
            "value": calculated_angle,
            "message": angle_msg,
            "status": self.check_angle(calculated_angle)
        }
        logger.debug(f"Calculated angle: {calculated_angle}, status: {result['angle']['status']}")
        
        # Расчет количества ступеней и параметров
        steps, steps_msg, actual_height, actual_width = self.calculate_steps(
            height, length, step_height, step_width
        )
        logger.debug(f"Steps calculation: steps={steps}, msg={steps_msg}, "
                     f"actual_height={actual_height}, actual_width={actual_width}")

        if steps is None:
            result["error"] = steps_msg
            logger.debug("Steps is None, generating suggestions...")
            # Добавляем предложения по исправлению
            suggestions = self.suggest_optimal_parameters(height, length, width)
            result["suggestions"] = suggestions
            logger.debug(f"Suggestions generated: {suggestions}")
            return result
            
        result["steps"] = {
            "count": steps,
            "message": steps_msg,
            "actual_height": round(actual_height, 2) if actual_height else None,
            "actual_width": round(actual_width, 2) if actual_width else None,
            # "step_sum": round(actual_height + actual_width, 2) if actual_height and actual_width else None # Удалено
        }
        # Расчет длины лестницы
        ladder_length, length_msg = self.calculate_length(height, length, calculated_angle)
        result["ladder_length"] = {
            "value": ladder_length,
            "message": length_msg
        }
        logger.debug(f"Ladder length: {ladder_length}")
                          
        # Расчет габаритов
        footprint = None
        horizontal_projection = 0
        if steps and actual_width:
            footprint = self.calculate_ladder_footprint(steps, actual_width, ladder_type)
            result["footprint"] = footprint
            horizontal_projection = footprint.get("horizontal_projection", 0)
        # Проверка возможности установки (включая габариты)
        feasibility = self.check_installation_feasibility(
            height, length, width, calculated_angle or 0, steps or 0,
            actual_width or 0, actual_height or 0, horizontal_projection
        )
        result["feasibility"] = feasibility
        logger.debug(f"Feasibility check result: {feasibility}")
                          
        if not feasibility["possible"]:
            # Добавляем предложения по исправлению
            suggestions = self.suggest_optimal_parameters(height, length, width)
            result["suggestions"] = suggestions
            logger.debug(f"Suggestions generated: {suggestions}")
                          
        # Расчет деталей
        if steps is not None:
            parts = self.calculate_parts(steps, ladder_type)
            result["parts"] = parts
        return result

    def format_result(self, result: Dict[str, any]) -> str:
        """
        Форматирует результат для вывода в Telegram.
        """
        # logger.debug(f"format_result called with result keys: {result.keys()}") # Для отладки
        if "error" in result:
            text = f"❌ Ошибка: {result['error']}\n"
            # Добавляем рекомендации, если есть
            if "suggestions" in result and result["suggestions"]:
                suggestions = result["suggestions"]
                text += f"\n💡 РЕКОМЕНДАЦИИ:\n"
                if "standard_option" in suggestions:
                    std = suggestions["standard_option"]
                    text += f"✅ {std['note']}\n"
                    text += f"  {std['steps']} ступеней\n"
                    text += f"  Высота: {std['height']} см, Ширина: {std['width']} см\n"
                    text += f"  Займет: {std['projection']} см из доступных {result['inputs']['length']} см\n"
                if "best_option" in suggestions:
                    best = suggestions["best_option"]
                    text += f"🔧 Альтернативный вариант:\n"
                    text += f"  {best['steps']} ступеней\n"
                    text += f"  Высота: {best['height']} см, Ширина: {best['width']} см\n"
                    text += f"  Займет: {best['projection']} см\n"
                elif "minimum_option" in suggestions:
                    min_opt = suggestions["minimum_option"]
                    text += f"🔻 Минимальные параметры:\n"
                    text += f"  {min_opt['steps']} ступеней\n"
                    text += f"  Высота: {min_opt['height']} см, Ширина: {min_opt['width']} см\n"
                    text += f"  Займет: {min_opt['projection']} см\n"
            return text
            
        text = "📊 РАСЧЕТ ЛЕСТНИЦЫ\n" + "=" * 30 + "\n"
        # Входные данные
        inputs = result["inputs"]
        text += f"📈 ВХОДНЫЕ ДАННЫЕ:\n"
        text += f"Высота подъема: {inputs['height']} см\n"
        text += f"Длина проема: {inputs['length']} см\n"
        if inputs['width']:
            text += f"Ширина проема: {inputs['width']} см\n"
        if inputs['angle']:
            text += f"Угол наклона: {inputs['angle']}°\n"
        text += "\n"
        # Угол
        angle_data = result["angle"]
        text += f"📐 УГОЛ НАКЛОНА:\n"
        text += f"Рассчитанный угол: {angle_data['value']}°\n"
        text += f"Статус: {angle_data['status']}\n"
        text += "\n"
        # Ступени
        steps_data = result["steps"]
        text += f"🪜 СТУПЕНИ:\n"
        text += f"Количество ступеней: {steps_data['count']}\n"
        if steps_data['actual_height']:
            text += f"Высота подступенка: {steps_data['actual_height']} см\n"
        if steps_data['actual_width']:
            text += f"Ширина ступени: {steps_data['actual_width']} см\n"
        text += f"{steps_data['message']}\n"
        text += "\n"
        # Проверка возможности установки
        feasibility = result["feasibility"]
        text += f"✅ ВОЗМОЖНОСТЬ УСТАНОВКИ:\n"
        if feasibility["possible"]:
            text += "✅ Лестница может быть установлена\n"
        else:
            text += "❌ Лестница не может быть установлена\n"
            if feasibility["issues"]:
                text += "Проблемы:\n"
                for issue in feasibility["issues"]:
                    text += f"  • {issue}\n"
        if feasibility["warnings"]:
            text += "Предупреждения:\n"
            for warning in feasibility["warnings"]:
                text += f"  • {warning}\n"
        # --- ИСПРАВЛЕНИЕ: Всегда проверяем и отображаем suggestions ---
        # Это ключевое изменение: отображаем рекомендации независимо от того,
        # где они были сгенерированы (в ошибке или в основном результате)
        if "suggestions" in result and result["suggestions"]:
            # logger.debug("Found suggestions in main result, adding to output") # Для отладки
            suggestions = result["suggestions"]
            text += f"\n💡 РЕКОМЕНДАЦИИ:\n"
            # Отображаем message из suggestions
            text += f"{suggestions['message']}\n" 
            if "standard_option" in suggestions:
                std = suggestions["standard_option"]
                text += f"✅ {std['note']}\n"
                text += f"  {std['steps']} ступеней\n"
                text += f"  Высота: {std['height']} см, Ширина: {std['width']} см\n"
                text += f"  Займет: {std['projection']} см из доступных {result['inputs']['length']} см\n"
            if "best_option" in suggestions:
                best = suggestions["best_option"]
                text += f"🔧 Альтернативный вариант:\n"
                text += f"  {best['steps']} ступеней\n"
                text += f"  Высота: {best['height']} см, Ширина: {best['width']} см\n"
                text += f"  Займет: {best['projection']} см\n"
            elif "minimum_option" in suggestions: # elif, потому что это взаимоисключающие варианты
                min_opt = suggestions["minimum_option"]
                text += f"🔻 Минимальные параметры:\n"
                text += f"  {min_opt['steps']} ступеней\n"
                text += f"  Высота: {min_opt['height']} см, Ширина: {min_opt['width']} см\n"
                text += f"  Займет: {min_opt['projection']} см\n"
        # ---------------------------------------------------------------
        text += "\n"
        # Длина лестницы
        if "ladder_length" in result:
            length_data = result["ladder_length"]
            text += f"📏 ДЛИНА ЛЕСТНИЦЫ:\n"
            text += f"{length_data['value']} см\n"
            text += f"{length_data['message']}\n"
            text += "\n"
        # Детали
        if "parts" in result:
            text += f"🔨 НЕОБХОДИМЫЕ ДЕТАЛИ:\n"
            parts = result["parts"]
            for part, count in parts.items():
                if count > 0:
                    text += f"- {part.capitalize()}: {count} шт.\n"
        return text

# Создаем экземпляр калькулятора
calculator = LadderCalculator()
# --- КОНЕЦ ИНТЕГРАЦИИ LADDERCALCULATOR ---

# --- AIogram SETUP ---
router = Router()

class StairCalculationStates(StatesGroup):
    choosing_stair_type = State()  # Выбор типа лестницы
    entering_height = State()      # Ввод высоты подъема
    entering_length = State()      # Ввод длины проема
    entering_width = State()       # Ввод ширины проема

# --- UI/UX ---
# Кнопки для выбора типа лестницы (сопоставление с типами из LadderCalculator)
TYPE_MAPPING = {
    "Прямая": 1,
    "П-образная": 2,
    "Г-образная": 3
}

stair_type_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Прямая")],
        [KeyboardButton(text="П-образная")],
        [KeyboardButton(text="Г-образная")]
    ],
    resize_keyboard=True
)

cancel_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Отмена")]],
    resize_keyboard=True
)

@router.message(F.text == "/start")
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "📐 Добро пожаловать в калькулятор лестниц!\n\n"
        "Выберите тип лестницы:",
        reply_markup=stair_type_keyboard
    )
    await state.set_state(StairCalculationStates.choosing_stair_type)

@router.message(StateFilter(StairCalculationStates.choosing_stair_type))
async def stair_type_chosen(message: Message, state: FSMContext):
    if message.text not in TYPE_MAPPING:
        await message.answer(
            "Пожалуйста, выберите тип лестницы из предложенных вариантов:",
            reply_markup=stair_type_keyboard
        )
        return
    
    await state.update_data(ladder_type=TYPE_MAPPING[message.text])
    await message.answer(
        "Введите высоту подъема (в см):",
        reply_markup=cancel_keyboard
    )
    await state.set_state(StairCalculationStates.entering_height)

@router.message(StateFilter(StairCalculationStates.entering_height))
async def height_entered(message: Message, state: FSMContext):
    try:
        height = float(message.text.replace(',', '.'))
        if height <= 0:
            await message.answer("Высота должна быть положительным числом. Попробуйте еще раз:")
            return
        if height > 500:  # Ограничение из LadderCalculator
            await message.answer("Высота слишком большая. Введите значение до 500 см:")
            return
            
        await state.update_data(height=height)
        await message.answer("Введите длину проема (в см):", reply_markup=cancel_keyboard)
        await state.set_state(StairCalculationStates.entering_length)
    except ValueError:
        await message.answer("Пожалуйста, введите число (например: 270 или 270.5):")

@router.message(StateFilter(StairCalculationStates.entering_length))
async def length_entered(message: Message, state: FSMContext):
    try:
        length = float(message.text.replace(',', '.'))
        if length <= 0:
            await message.answer("Длина должна быть положительным числом. Попробуйте еще раз:")
            return
        if length > 1000:  # Ограничение из LadderCalculator
            await message.answer("Длина слишком большая. Введите значение до 1000 см:")
            return
            
        await state.update_data(length=length)
        await message.answer("Введите ширину проема (в см):", reply_markup=cancel_keyboard)
        await state.set_state(StairCalculationStates.entering_width)
    except ValueError:
        await message.answer("Пожалуйста, введите число (например: 450 или 450.5):")

@router.message(StateFilter(StairCalculationStates.entering_width))
async def width_entered(message: Message, state: FSMContext):
    try:
        width = float(message.text.replace(',', '.'))
        if width <= 0:
            await message.answer("Ширина должна быть положительным числом. Попробуйте еще раз:")
            return
        if width > 1000:  # Ограничение (можно настроить)
            await message.answer("Ширина слишком большая. Введите значение до 1000 см:")
            return
            
        # Получаем все данные
        user_data = await state.get_data()
        
        # Вызываем мощный расчетный движок
        result = calculator.calculate_all(
            height=user_data['height'],
            length=user_data['length'],
            width=width,
            ladder_type=user_data['ladder_type']
        )
        
        # Форматируем результат
        formatted_result = calculator.format_result(result)
        
        # Отправляем результат
        await message.answer(formatted_result, reply_markup=stair_type_keyboard)
        await state.clear()
        await state.set_state(StairCalculationStates.choosing_stair_type)
        
    except ValueError:
        await message.answer("Пожалуйста, введите число (например: 100 или 100.5):")
    except Exception as e:
        await message.answer(f"Произошла ошибка при расчете: {str(e)}")
        await state.clear()
        await message.answer("Начните сначала:", reply_markup=stair_type_keyboard)
        await state.set_state(StairCalculationStates.choosing_stair_type)

@router.message(F.text == "Отмена")
async def cancel_handler(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Расчет отменен. Начните сначала:",
        reply_markup=stair_type_keyboard
    )
    await state.set_state(StairCalculationStates.choosing_stair_type)

# --- ЗАПУСК В РЕЖИМЕ ПОЛЛИНГА ---
async def main():
    # Получаем токен из переменных окружения
    token = os.getenv('BOT_TOKEN')
    if not token:
        raise ValueError("BOT_TOKEN не найден в переменных окружения. Проверьте файл .env")
    
    bot = Bot(token=token)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    # Удаление вебхуков и запуск поллинга
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    # Запуск бота
    asyncio.run(main())
