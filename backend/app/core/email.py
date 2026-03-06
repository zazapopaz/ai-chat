# app/core/email.py
import os
import logging
from datetime import datetime
from typing import Optional
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from jinja2 import Template
import asyncio

from app.core.config import settings

logger = logging.getLogger(__name__)


def _mask_code(code: str) -> str:
  """
  Маскирует проверочный/2FA код для безопасного логирования.
  Показываем только последние 2 цифры, остальное заменяем звёздочками.
  """
  if not code:
      return "***"
  visible = code[-2:]
  return "***" + visible

# HTML шаблон для подтверждения email при регистрации
VERIFICATION_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            text-align: center;
            border-radius: 10px 10px 0 0;
        }
        .content {
            background: #f9f9f9;
            padding: 30px;
            border-radius: 0 0 10px 10px;
            border: 1px solid #ddd;
        }
        .code {
            font-size: 36px;
            font-weight: bold;
            color: #667eea;
            text-align: center;
            padding: 20px;
            background: white;
            border-radius: 10px;
            margin: 20px 0;
            letter-spacing: 5px;
        }
        .footer {
            text-align: center;
            margin-top: 20px;
            color: #999;
            font-size: 12px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h2>Подтверждение email</h2>
    </div>
    <div class="content">
        <p>Здравствуйте, <strong>{{ full_name or email }}</strong>!</p>
        <p>Для завершения регистрации в сервисе <strong>Агелар</strong> введите следующий код подтверждения:</p>

        <div class="code">{{ code }}</div>

        <p>Код действителен в течение <strong>15 минут</strong>.</p>
        <p>Если вы не регистрировались на нашем сайте, просто проигнорируйте это письмо.</p>
    </div>
    <div class="footer">
        <p>© {{ year }} Агелар. Все права защищены.</p>
        <p>Это автоматическое письмо, пожалуйста, не отвечайте на него.</p>
    </div>
</body>
</html>
"""

# HTML шаблон для 2FA кода при входе
TWO_FACTOR_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }
        .header {
            background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
            color: white;
            padding: 20px;
            text-align: center;
            border-radius: 10px 10px 0 0;
        }
        .content {
            background: #f9f9f9;
            padding: 30px;
            border-radius: 0 0 10px 10px;
            border: 1px solid #ddd;
        }
        .code {
            font-size: 36px;
            font-weight: bold;
            color: #f59e0b;
            text-align: center;
            padding: 20px;
            background: white;
            border-radius: 10px;
            margin: 20px 0;
            letter-spacing: 5px;
        }
        .warning {
            background: #fff3cd;
            border: 1px solid #ffeeba;
            color: #856404;
            padding: 15px;
            border-radius: 5px;
            margin: 20px 0;
            font-size: 14px;
        }
        .footer {
            text-align: center;
            margin-top: 20px;
            color: #999;
            font-size: 12px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h2>Код подтверждения входа</h2>
    </div>
    <div class="content">
        <p>Здравствуйте, <strong>{{ full_name or email }}</strong>!</p>
        <p>Для входа в ваш аккаунт введите следующий код подтверждения:</p>

        <div class="code">{{ code }}</div>

        <p>Код действителен в течение <strong>10 минут</strong>.</p>

        <div class="warning">
            <strong>Важно!</strong> Если вы не пытались войти в аккаунт, 
            немедленно смените пароль и свяжитесь с поддержкой.
        </div>
    </div>
    <div class="footer">
        <p>© {{ year }} Агелар. Все права защищены.</p>
        <p>Это автоматическое письмо, пожалуйста, не отвечайте на него.</p>
    </div>
</body>
</html>
"""

# HTML шаблон для уведомления о включении 2FA
TWO_FACTOR_ENABLED_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }
        .header {
            background: linear-gradient(135deg, #10b981 0%, #059669 100%);
            color: white;
            padding: 20px;
            text-align: center;
            border-radius: 10px 10px 0 0;
        }
        .content {
            background: #f9f9f9;
            padding: 30px;
            border-radius: 0 0 10px 10px;
            border: 1px solid #ddd;
        }
        .info {
            background: #d4edda;
            border: 1px solid #c3e6cb;
            color: #155724;
            padding: 15px;
            border-radius: 5px;
            margin: 20px 0;
        }
        .footer {
            text-align: center;
            margin-top: 20px;
            color: #999;
            font-size: 12px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h2>Двухфакторная аутентификация включена</h2>
    </div>
    <div class="content">
        <p>Здравствуйте, <strong>{{ full_name or email }}</strong>!</p>

        <div class="info">
            <strong>Двухфакторная аутентификация успешно включена</strong>
        </div>

        <p>Теперь при каждом входе в аккаунт вам будет приходить код подтверждения на этот email.</p>
        <p>Это значительно повышает безопасность вашего аккаунта.</p>

        <p>Если вы не включали двухфакторную аутентификацию, немедленно свяжитесь с поддержкой.</p>
    </div>
    <div class="footer">
        <p>© {{ year }} Агелар. Все права защищены.</p>
        <p>Это автоматическое письмо, пожалуйста, не отвечайте на него.</p>
    </div>
</body>
</html>
"""

# HTML шаблон для уведомления об отключении 2FA
TWO_FACTOR_DISABLED_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }
        .header {
            background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
            color: white;
            padding: 20px;
            text-align: center;
            border-radius: 10px 10px 0 0;
        }
        .content {
            background: #f9f9f9;
            padding: 30px;
            border-radius: 0 0 10px 10px;
            border: 1px solid #ddd;
        }
        .warning {
            background: #fff3cd;
            border: 1px solid #ffeeba;
            color: #856404;
            padding: 15px;
            border-radius: 5px;
            margin: 20px 0;
        }
        .footer {
            text-align: center;
            margin-top: 20px;
            color: #999;
            font-size: 12px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h2>Двухфакторная аутентификация отключена</h2>
    </div>
    <div class="content">
        <p>Здравствуйте, <strong>{{ full_name or email }}</strong>!</p>

        <div class="warning">
            <strong>⚠Двухфакторная аутентификация была отключена</strong>
        </div>

        <p>Ваш аккаунт теперь менее защищен. Рекомендуем снова включить двухфакторную аутентификацию.</p>

        <p>Если вы не отключали двухфакторную аутентификацию, немедленно свяжитесь с поддержкой.</p>
    </div>
    <div class="footer">
        <p>© {{ year }} Агелар. Все права защищены.</p>
        <p>Это автоматическое письмо, пожалуйста, не отвечайте на него.</p>
    </div>
</body>
</html>
"""


class EmailService:
    """Сервис для отправки email уведомлений"""

    def __init__(self):
        self.smtp_host = settings.SMTP_HOST
        self.smtp_port = settings.SMTP_PORT
        self.smtp_user = settings.SMTP_USER
        self.smtp_password = settings.SMTP_PASSWORD
        self.from_email = settings.FROM_EMAIL
        self.use_smtp = all([self.smtp_host, self.smtp_port, self.smtp_user, self.smtp_password])

        # Добавляем таймаут для SMTP
        self.timeout = 30

        if not self.use_smtp and settings.ENVIRONMENT == "production":
            logger.error("SMTP настройки не заданы! Email рассылка не будет работать в production.")
        elif not self.use_smtp:
            logger.warning("⚠SMTP настройки не заданы. Email будут логироваться в консоль.")
        else:
            # Маскируем пароль в логах
            masked_password = self.smtp_password[:4] + "..." + self.smtp_password[-4:] if self.smtp_password and len(
                self.smtp_password) > 8 else "***"
            logger.info(f"SMTP настроен: {self.smtp_host}:{self.smtp_port} ({self.smtp_user})")
            logger.info(f"From: {self.from_email}")

    async def send_email(self, to_email: str, subject: str, html_content: str) -> bool:
        """Отправка email через SMTP с повторными попытками"""

        if not self.use_smtp:
            # В режиме разработки просто логируем
            logger.info(f"[DEV MODE] Email to: {to_email}")
            logger.info(f"Subject: {subject}")
            logger.info(f"Content preview: {html_content[:200]}...")
            return True

        # Пробуем отправить до 3 раз
        for attempt in range(3):
            try:
                message = MIMEMultipart("alternative")
                message["Subject"] = subject
                message["From"] = self.from_email
                message["To"] = to_email

                # Добавляем HTML версию
                message.attach(MIMEText(html_content, "html"))

                # Определяем параметры подключения в зависимости от порта
                if self.smtp_port == 465:
                    # Для порта 465 используем SSL/TLS сразу
                    await aiosmtplib.send(
                        message,
                        hostname=self.smtp_host,
                        port=self.smtp_port,
                        username=self.smtp_user,
                        password=self.smtp_password,
                        use_tls=True,
                        timeout=self.timeout
                    )
                else:
                    # Для портов 25, 587 используем STARTTLS
                    await aiosmtplib.send(
                        message,
                        hostname=self.smtp_host,
                        port=self.smtp_port,
                        username=self.smtp_user,
                        password=self.smtp_password,
                        use_tls=False,
                        start_tls=True,
                        timeout=self.timeout
                    )

                logger.info(f"Email успешно отправлен на {to_email}")
                return True

            except aiosmtplib.SMTPAuthenticationError as e:
                logger.error(f"Ошибка аутентификации SMTP (попытка {attempt + 1}/3): {e}")
                logger.error("   Проверьте логин и пароль приложения")
                if attempt == 2:
                    return False
                await asyncio.sleep(2)

            except aiosmtplib.SMTPException as e:
                logger.error(f"SMTP ошибка (попытка {attempt + 1}/3): {e}")
                if attempt == 2:
                    return False
                await asyncio.sleep(2 ** attempt)  # Экспоненциальная задержка

            except asyncio.TimeoutError:
                logger.error(f"Таймаут SMTP (попытка {attempt + 1}/3)")
                if attempt == 2:
                    return False
                await asyncio.sleep(2 ** attempt)

            except ConnectionRefusedError:
                logger.error(f"Соединение отклонено (попытка {attempt + 1}/3). Проверьте хост и порт.")
                if attempt == 2:
                    return False
                await asyncio.sleep(2)

            except Exception as e:
                logger.error(f"Неожиданная ошибка отправки email: {e}")
                if attempt == 2:
                    return False
                await asyncio.sleep(1)

        return False

    async def send_verification_email(self, to_email: str, code: str, full_name: Optional[str] = None):
        """Отправка кода подтверждения при регистрации"""
        try:
            template = Template(VERIFICATION_TEMPLATE)
            html_content = template.render(
                full_name=full_name,
                email=to_email,
                code=code,
                year=datetime.utcnow().year
            )

            subject = "Подтверждение email для регистрации в Агелар"

            if self.use_smtp:
                logger.info(
                    f"Отправка подтверждения на {to_email} с кодом {_mask_code(code)}"
                )

            result = await self.send_email(to_email, subject, html_content)

            if result:
                logger.info(f"Письмо с подтверждением отправлено на {to_email}")
            else:
                logger.error(f"Не удалось отправить письмо с подтверждением на {to_email}")

            return result

        except Exception as e:
            logger.error(f"Ошибка подготовки email подтверждения: {e}")
            return False

    async def send_2fa_email(self, to_email: str, code: str, full_name: Optional[str] = None):
        """Отправка 2FA кода при входе"""
        try:
            template = Template(TWO_FACTOR_TEMPLATE)
            html_content = template.render(
                full_name=full_name,
                email=to_email,
                code=code,
                year=datetime.utcnow().year
            )

            subject = "Код подтверждения для входа в Агелар"

            if self.use_smtp:
                logger.info(f"Отправка 2FA кода на {to_email}")

            result = await self.send_email(to_email, subject, html_content)

            if result:
                logger.info(f"2FA код отправлен на {to_email}")
            else:
                logger.error(f"Не удалось отправить 2FA код на {to_email}")

            return result

        except Exception as e:
            logger.error(f"Ошибка подготовки 2FA email: {e}")
            return False

    async def send_2fa_enabled_notification(self, to_email: str, full_name: Optional[str] = None):
        """Уведомление о включении 2FA"""
        try:
            template = Template(TWO_FACTOR_ENABLED_TEMPLATE)
            html_content = template.render(
                full_name=full_name,
                email=to_email,
                year=datetime.utcnow().year
            )

            subject = "Двухфакторная аутентификация включена"
            result = await self.send_email(to_email, subject, html_content)

            if result:
                logger.info(f"Уведомление о включении 2FA отправлено на {to_email}")

            return result

        except Exception as e:
            logger.error(f"Ошибка подготовки уведомления о включении 2FA: {e}")
            return False

    async def send_2fa_disabled_notification(self, to_email: str, full_name: Optional[str] = None):
        """Уведомление об отключении 2FA"""
        try:
            template = Template(TWO_FACTOR_DISABLED_TEMPLATE)
            html_content = template.render(
                full_name=full_name,
                email=to_email,
                year=datetime.utcnow().year
            )

            subject = "Двухфакторная аутентификация отключена"
            result = await self.send_email(to_email, subject, html_content)

            if result:
                logger.info(f"Уведомление об отключении 2FA отправлено на {to_email}")

            return result

        except Exception as e:
            logger.error(f"Ошибка подготовки уведомления об отключении 2FA: {e}")
            return False


# Создаем глобальный экземпляр
email_service = EmailService()