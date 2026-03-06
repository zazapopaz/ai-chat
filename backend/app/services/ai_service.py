# app/services/ai_service.py
from typing import List, Optional
import logging
import re
from app.models.tenant import Tenant
from app.models.message import Message
from app.core.config import settings

logger = logging.getLogger(__name__)


class AIService:
    """Главный AI сервис для управления разными провайдерами"""

    def __init__(self):
        self.provider = settings.AI_PROVIDER
        self.is_available = False

        # Проверяем доступность AI в зависимости от провайдера
        if self.provider == "yandexgpt":
            from .yandex_gpt import yandex_gpt_client
            self.yandex_client = yandex_gpt_client
            self.is_available = yandex_gpt_client.available
        else:
            self.is_available = False

        if self.is_available:
            logger.info(f"AI сервис инициализирован с провайдером: {self.provider}")
        else:
            logger.warning(f"AI сервис недоступен (провайдер: {self.provider})")
            if settings.ENVIRONMENT == "production":
                logger.error("В production режиме AI сервис должен быть доступен!")

    def _extract_phone(self, text: str) -> Optional[str]:
        """Извлекает телефон из текста"""
        phone_patterns = [
            r'(?:\+7|8)?\d{10}',
            r'\+7\s?\d{3}\s?\d{3}\s?\d{2}\s?\d{2}',
            r'8\s?\(?\d{3}\)?\s?\d{3}\s?\d{2}\s?\d{2}',
        ]

        for pattern in phone_patterns:
            match = re.search(pattern, text)
            if match:
                phone = match.group(0)
                digits = re.sub(r'\D', '', phone)
                if len(digits) >= 10:
                    return phone
        return None

    def _extract_email(self, text: str) -> Optional[str]:
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        match = re.search(email_pattern, text)
        return match.group(0) if match else None

    def _has_contact_info(self, message: str) -> bool:
        return bool(self._extract_phone(message) or self._extract_email(message))

    def _has_contact_request(self, text: str) -> bool:
        contact_phrases = [
            "оставьте", "контакт", "телефон", "номер", "email", "почту",
            "свяжемся", "перезвоним", "позвоните", "свяжитесь", "ваши контакты",
            "записаться", "запишите", "форма"
        ]
        text_lower = text.lower()
        return any(phrase in text_lower for phrase in contact_phrases)

    def _is_asking_for_form(self, message: str) -> bool:
        """Проверяет, просит ли пользователь форму"""
        keywords = [
            'форма', 'форму', 'запись', 'записаться', 'контакт', 'контакты',
            'оставить', 'отправь', 'скинь', 'дай', 'покажи', 'где форма',
            'хочу оставить', 'оставлю', 'заполнить', 'формочку', 'запиши'
        ]
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in keywords)

    def _is_farewell(self, message: str) -> bool:
        farewells = ['пока', 'до свидания', 'всего доброго', 'до связи', 'удачи', 'спасибо', 'всего хорошего']
        message_lower = message.lower()
        return any(farewell in message_lower for farewell in farewells)

    def _should_show_contact_form(self, message_history: List[Message], current_message: str) -> bool:
        """Определяет, нужно ли показать форму для контактов"""
        user_messages = [m for m in message_history if m.is_from_lead]
        bot_messages = [m for m in message_history if not m.is_from_lead]

        # Проверяем, есть ли уже контакты
        for msg in user_messages:
            if self._has_contact_info(msg.content):
                return False

        if self._is_asking_for_form(current_message):
            return True

        # Проверяем, не показывали ли уже форму в последних 3 сообщениях бота
        for msg in bot_messages[-3:]:
            if '||SHOW_CONTACT_FORM||' in msg.content:
                return False

        # Проверяем, не запрашивал ли уже бот контакты в тексте
        for msg in bot_messages[-3:]:
            if self._has_contact_request(msg.content):
                return False

        # Показываем после 3 сообщений от пользователя
        return len(user_messages) >= 3

    async def generate_response(
            self,
            tenant: Tenant,
            message_history: List[Message],
            user_message: str
    ) -> str:
        """Генерация ответа AI"""

        # Проверяем баланс сообщений
        if tenant.message_balance <= 0:
            logger.warning(f"Лимит сообщений исчерпан для тенанта {tenant.id}")
            return "Извините, лимит сообщений исчерпан. Пожалуйста, свяжитесь с администратором сайта."

        # Проверяем доступность AI сервиса
        if not self.is_available:
            logger.error(f"AI сервис недоступен для тенанта {tenant.id}")
            if settings.ENVIRONMENT == "production":
                # В production возвращаем сообщение об ошибке
                return "Извините, сервис временно недоступен. Пожалуйста, попробуйте позже или свяжитесь с менеджером."
            else:
                # В разработке возвращаем информативное сообщение
                return (
                    "AI сервис не настроен.\n\n"
                    "Для работы AI необходимо:\n"
                    "1. Добавить YANDEX_API_KEY и YANDEX_FOLDER_ID в .env файл\n"
                    "2. Перезапустить сервер\n\n"
                    "Сейчас используется тестовый режим."
                )

        logger.info(f"Генерация ответа для {tenant.company_name} (ID: {tenant.id})")

        # Проверяем, не прощается ли пользователь
        if self._is_farewell(user_message):
            return "Всего доброго! Обращайтесь ещё. "

        # Проверяем, нужно ли показать форму для контактов
        show_contact_form = self._should_show_contact_form(message_history, user_message)

        try:
            if self.provider == "yandexgpt":
                response = await self.yandex_client.generate_response(
                    tenant=tenant,
                    message_history=message_history,
                    user_message=user_message
                )

                # Если нужно показать форму, добавляем маркер
                if show_contact_form:
                    if '||SHOW_CONTACT_FORM||' not in response:
                        response = response + "||SHOW_CONTACT_FORM||"

                return response
            else:
                # Если провайдер не поддерживается
                logger.error(f"Неподдерживаемый AI провайдер: {self.provider}")
                return "Извините, возникла техническая ошибка. Наш менеджер скоро свяжется с вами."

        except Exception as e:
            logger.error(f"Ошибка AI сервиса: {str(e)}", exc_info=True)
            return "Извините, произошла техническая ошибка. Наш менеджер скоро свяжется с вами."


# Создаем глобальный экземпляр
ai_service = AIService()