# app/services/yandex_gpt.py
import logging
from typing import List, Optional
import aiohttp
import asyncio
import json

from app.models.tenant import Tenant
from app.models.message import Message
from app.core.config import settings

logger = logging.getLogger(__name__)


class YandexGPTClient:
    """Клиент для работы с Yandex GPT API"""

    def __init__(self):
        # Берем ключи из настроек (которые загрузились из .env)
        self.api_key = settings.YANDEX_API_KEY
        self.folder_id = settings.YANDEX_FOLDER_ID
        self.model = settings.YANDEX_MODEL
        self.base_url = "https://llm.api.cloud.yandex.net"

        # Проверяем наличие ключей
        if not self.api_key or not self.folder_id:
            if settings.ENVIRONMENT == "production":
                logger.error("Yandex GPT API ключи не настроены в production!")
                self.available = False
            else:
                logger.warning("Yandex GPT API ключи не настроены. Будет использован тестовый режим!")
                self.available = False
        else:
            self.available = True
            # Маскируем ключ в логах для безопасности
            masked_key = self.api_key[:4] + "..." + self.api_key[-4:] if len(self.api_key) > 8 else "***"
            logger.info(f"Yandex GPT клиент инициализирован (key: {masked_key})")

    def _count_user_messages(self, message_history: List[Message]) -> int:
        """Подсчитывает количество сообщений от пользователя"""
        return len([m for m in message_history if m.is_from_lead])

    def _has_contact_info(self, message_history: List[Message]) -> bool:
        """Проверяет, есть ли уже контактная информация в истории"""
        for msg in message_history:
            if not msg.is_from_lead:
                continue

            content = msg.content.lower()
            # Проверяем наличие телефона
            if any(phone in content for phone in ['+7', '8(', '8 ', '89', '79']):
                digits = ''.join(filter(str.isdigit, content))
                if len(digits) >= 10:
                    return True

            # Проверяем наличие email
            if '@' in content and '.' in content:
                parts = content.split('@')
                if len(parts) == 2 and '.' in parts[1]:
                    return True

        return False

    def _should_show_contact_form(self, message_history: List[Message]) -> bool:
        """Определяет, нужно ли показать форму для контактов"""
        user_messages = self._count_user_messages(message_history)

        # Не показываем если уже есть контакты
        if self._has_contact_info(message_history):
            return False

        # Показываем после 3 сообщений от пользователя
        return user_messages >= 3

    async def generate_response(
            self,
            tenant: Tenant,
            message_history: List[Message],
            user_message: str
    ) -> str:
        """Генерация ответа с использованием Yandex GPT"""

        # Если ключи не настроены, возвращаем тестовый ответ
        if not self.available:
            return self._get_test_response(user_message, tenant)

        try:
            # Формируем системный промпт ИЗ НАСТРОЕК КЛИЕНТА
            system_prompt = self._build_system_prompt(tenant)

            # Форматируем историю сообщений (берем последние 10 для контекста)
            recent_history = message_history[-10:] if len(message_history) > 10 else message_history
            messages = self._format_messages(
                system_prompt=system_prompt,
                message_history=recent_history,
                user_message=user_message
            )

            # Генерируем ответ
            logger.debug(f"Отправка запроса к Yandex GPT")
            response_text = await self._call_yandex_gpt(messages)

            # Проверяем, нужно ли показать форму для контактов
            if self._should_show_contact_form(message_history):
                response_text = response_text + "||SHOW_CONTACT_FORM||"

            return self._format_response(response_text)

        except aiohttp.ClientError as e:
            logger.error(f"Ошибка сети при обращении к Yandex GPT: {str(e)}")
            return "Извините, возникли проблемы с подключением к AI. Пожалуйста, попробуйте позже."
        except asyncio.TimeoutError:
            logger.error("Таймаут при обращении к Yandex GPT")
            return "Извините, AI сервис не отвечает. Пожалуйста, попробуйте позже."
        except Exception as e:
            logger.error(f"Неожиданная ошибка Yandex GPT: {str(e)}", exc_info=True)
            return "Извините, произошла техническая ошибка. Наш менеджер скоро свяжется с вами."

    def _get_test_response(self, user_message: str, tenant: Tenant) -> str:
        """Тестовый режим (когда нет API ключей) - используем ТОЛЬКО если нет API ключей"""
        import random

        # Берем название компании из настроек клиента
        company_name = tenant.company_name or "нашей компании"

        test_responses = [
            f"Спасибо за вопрос! (тестовый режим - AI не подключен)",
            f"Наш менеджер скоро ответит вам. (тестовый режим)",
            f"Оставьте телефон, и мы перезвоним. (тестовый режим)",
            f"Интересный вопрос! (тестовый режим - для работы AI нужен API ключ)"
        ]

        response = random.choice(test_responses)
        return response

    def _build_system_prompt(self, tenant: Tenant) -> str:
        """
        Строим системный промпт ИСКЛЮЧИТЕЛЬНО из настроек клиента.
        Никакого хардкода!
        """
        main_prompt = tenant.ai_prompt or "Ты - дружелюбный консультант. Отвечай на вопросы клиентов кратко и по делу."
        knowledge_base = tenant.company_knowledge_base or ""

        # Добавляем только общие инструкции по поведению, НЕ тему
        behavior_instruction = """
Общие инструкции:
- Отвечай вежливо и по делу, кратко (2-3 предложения максимум)
- Используй информацию из базы знаний компании
- Если не знаешь ответа, предложи оставить контакты для связи с менеджером
- Не придумывай информацию, которой нет в базе знаний
- Если пользователь прощается - просто попрощайся
- Отвечай на русском языке
"""

        # Формируем промпт ТОЛЬКО из данных клиента
        return f"""{main_prompt}

Информация о компании:
{knowledge_base}

{behavior_instruction}"""

    def _format_messages(
            self,
            system_prompt: str,
            message_history: List[Message],
            user_message: str
    ) -> List[dict]:
        """Форматируем сообщения для API"""
        messages = [{"role": "system", "text": system_prompt}]

        # Добавляем последние сообщения из истории для контекста
        for msg in message_history:
            role = "user" if msg.is_from_lead else "assistant"
            messages.append({"role": role, "text": msg.content})

        # Добавляем текущее сообщение
        messages.append({"role": "user", "text": user_message})

        return messages

    async def _call_yandex_gpt(self, messages: List[dict]) -> str:
        """Реальный вызов API Yandex GPT с retry логикой"""
        url = f"{self.base_url}/foundationModels/v1/completion"

        headers = {
            "Authorization": f"Api-Key {self.api_key}",
            "Content-Type": "application/json",
            "x-folder-id": self.folder_id
        }

        data = {
            "modelUri": f"gpt://{self.folder_id}/{self.model}",
            "completionOptions": {
                "stream": False,
                "temperature": 0.6,
                "maxTokens": 250,
                "topP": 0.8
            },
            "messages": messages
        }

        # Retry логика (3 попытки)
        max_retries = 3
        timeout = aiohttp.ClientTimeout(total=15)

        for attempt in range(max_retries):
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(url, headers=headers, json=data) as response:
                        if response.status == 200:
                            result = await response.json()
                            return result["result"]["alternatives"][0]["message"]["text"]
                        elif response.status == 429:
                            wait_time = 2 ** attempt
                            logger.warning(f"Rate limit exceeded, waiting {wait_time}s...")
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            error_text = await response.text()
                            logger.error(f"Yandex GPT API ошибка: {response.status} - {error_text}")

                            if attempt < max_retries - 1:
                                wait_time = 2 ** attempt
                                await asyncio.sleep(wait_time)
                                continue
                            else:
                                raise Exception(f"API вернул ошибку {response.status}")

            except asyncio.TimeoutError:
                logger.error(f"Таймаут при вызове API (попытка {attempt + 1})")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                else:
                    raise
            except aiohttp.ClientError as e:
                logger.error(f"Ошибка соединения (попытка {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                else:
                    raise

        raise Exception("Все попытки вызова API исчерпаны")

    def _format_response(self, response_text: str) -> str:
        """Очищаем и форматируем ответ"""
        if not response_text:
            return "Извините, не удалось получить ответ."

        response_text = " ".join(response_text.split())

        import re
        response_text = re.sub(r'([.!?])\1+', r'\1', response_text)

        response_text = response_text.replace('||SHOW_CONTACT_FORM||', '')

        return response_text

yandex_gpt_client = YandexGPTClient()