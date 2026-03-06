# app/api/endpoints/widget.py
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import json
import logging
from pathlib import Path
import uuid
import re
import traceback

from app.crud import crud_chat_session, crud_message, crud_tenant
from app.database import get_db
from app.services.ai_service import ai_service
from app.core.ratelimit.memory import check_suspicious_activity
from app.core.ratelimit import widget_limiter
from app.core.config import settings
from app.core.storage import storage_manager
from app.models.tenant import Tenant
from app.api.dependencies import get_tenant_with_balance, get_tenant_for_widget
from app.schemas.chat import (
    ChatSessionCreate,
    MessageCreate,
    WidgetMessageRequest,
    WidgetMessageResponse,
    WidgetStartResponse,
    SaveContactRequest
)

router = APIRouter(tags=["widget"])
logger = logging.getLogger(__name__)


def _cors_headers(request: Request) -> dict:
    """
    Формирует CORS‑заголовки для ответов виджета.
    В продакшене возвращаем конкретный Origin (если он есть),
    в разработке оставляем '*'.
    """
    origin = request.headers.get("origin")

    # В разработке проще использовать '*'
    if settings.DEBUG or not origin:
        return {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Credentials": "true",
        }

    # В production/staging явно возвращаем Origin клиента
    return {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Credentials": "true",
    }


def generate_widget_js(config: dict) -> str:
    """Генерирует JavaScript код виджета из шаблона"""
    template_path = Path(__file__).parent.parent / "templates" / "widget.js"

    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            template = f.read()

        # Заменяем плейсхолдер на конфиг
        js_code = template.replace('{{CONFIG}}', json.dumps(config, ensure_ascii=False))
        return js_code

    except FileNotFoundError:
        logger.error(f"❌ Шаблон виджета не найден: {template_path}")
        # Возвращаем полную версию виджета (как fallback)
        return generate_full_widget_js(config)
    except Exception as e:
        logger.error(f"❌ Ошибка генерации виджета: {e}")
        return f"console.error('Widget generation error');"


def generate_full_widget_js(config: dict) -> str:
    """Полная версия виджета (fallback если шаблон не найден)"""
    return f"""
(function() {{
    'use strict';

    const config = {json.dumps(config, ensure_ascii=False)};

    console.log('AI Chat Widget loaded for tenant:', config.tenant_id);

    class ChatWidget {{
        constructor() {{
            this.config = config;
            this.isOpen = false;
            this.sessionId = null;
            this.messageCount = 0;
            this.chatStarted = false;
            this.isToggling = false;
            this.clientId = this.getClientId();
            this.contactsSubmitted = false;
            this.contactFormShown = false;
            this.init();
        }}

        getClientId() {{
            const STORAGE_KEY = 'chat_client_id';
            let clientId = localStorage.getItem(STORAGE_KEY);

            if (!clientId) {{
                clientId = 'client_' + Date.now() + '_' + 
                          Math.random().toString(36).substr(2, 9) + 
                          Math.random().toString(36).substr(2, 9);
                localStorage.setItem(STORAGE_KEY, clientId);
            }}

            return clientId;
        }}

        init() {{
            this.createButton();
            this.createChatWindow();
            this.bindEvents();
        }}

        createButton() {{
            this.button = document.createElement('div');

            this.button.innerHTML = `
                <svg width="30" height="30" viewBox="0 0 24 24" fill="white">
                    <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"/>
                </svg>
            `;

            const position = this.getPosition();
            this.button.style.cssText = `
                position: fixed;
                ${{position.style}};
                width: 60px;
                height: 60px;
                background: ${{config.button_color}};
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                cursor: pointer;
                z-index: 10000;
                box-shadow: 0 4px 12px rgba(0,0,0,0.2);
                transition: all 0.3s ease;
                overflow: hidden;
                border: 2px solid white;
            `;
            document.body.appendChild(this.button);
        }}

        getPosition() {{
            const pos = config.widget_position || 'bottom-right';
            let style = '';

            switch(pos) {{
                case 'bottom-left':
                    style = 'bottom: 20px; left: 20px;';
                    break;
                case 'top-right':
                    style = 'top: 20px; right: 20px;';
                    break;
                case 'top-left':
                    style = 'top: 20px; left: 20px;';
                    break;
                default:
                    style = 'bottom: 20px; right: 20px';
            }}

            return {{ style: style, position: pos }};
        }}

        createChatWindow() {{
            this.chatWindow = document.createElement('div');

            const position = this.getPosition();
            let windowStyle = '';

            if (position.position.includes('bottom')) {{
                windowStyle = 'bottom: 90px;';
            }} else {{
                windowStyle = 'top: 90px;';
            }}

            if (position.position.includes('right')) {{
                windowStyle += ' right: 20px;';
            }} else {{
                windowStyle += ' left: 20px;';
            }}

            this.chatWindow.style.cssText = `
                position: fixed;
                ${{windowStyle}}
                width: 350px;
                height: 500px;
                background: white;
                border-radius: 12px;
                box-shadow: 0 8px 30px rgba(0,0,0,0.2);
                z-index: 9999;
                display: none;
                flex-direction: column;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            `;

            const avatarHtml = config.consultant_avatar ? 
                `<img src="${{config.consultant_avatar}}" style="width: 40px; height: 40px; border-radius: 50%; object-fit: cover; margin-right: 10px; border: 2px solid white;">` :
                `<div style="width: 40px; height: 40px; border-radius: 50%; background: rgba(255,255,255,0.2); margin-right: 10px; display: flex; align-items: center; justify-content: center; font-size: 20px; border: 2px solid white;">👤</div>`;

            this.chatWindow.innerHTML = `
                <div style="
                    background: ${{config.button_color}};
                    color: white;
                    padding: 15px;
                    border-radius: 12px 12px 0 0;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                ">
                    <div style="display: flex; align-items: center;">
                        ${{avatarHtml}}
                        <div>
                            <strong style="font-size: 16px;">${{config.consultant_name}}</strong>
                            <div style="font-size: 12px; opacity: 0.8;">Онлайн • Консультант</div>
                        </div>
                    </div>
                    <button id="close-chat" style="background: none; border: none; color: white; cursor: pointer; font-size: 20px;">×</button>
                </div>
                <div id="chat-messages" style="flex: 1; padding: 15px; overflow-y: auto; display: flex; flex-direction: column; gap: 10px;"></div>
                <div style="border-top: 1px solid #eee; padding: 15px;">
                    <div style="display: flex;">
                        <input type="text" id="chat-input" placeholder="Введите сообщение..." style="
                            flex: 1;
                            padding: 12px;
                            border: 1px solid #ddd;
                            border-radius: 25px;
                            outline: none;
                            font-size: 14px;
                        ">
                        <button id="send-btn" style="
                            background: ${{config.button_color}};
                            color: white;
                            border: none;
                            border-radius: 50%;
                            width: 40px;
                            height: 40px;
                            margin-left: 10px;
                            cursor: pointer;
                            display: flex;
                            align-items: center;
                            justify-content: center;
                        ">
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="white">
                                <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
                            </svg>
                        </button>
                    </div>
                </div>
            `;
            document.body.appendChild(this.chatWindow);
        }}

        bindEvents() {{
            this.button.addEventListener('click', () => this.toggleChat());
            this.chatWindow.querySelector('#close-chat').addEventListener('click', () => this.closeChat());
            this.chatWindow.querySelector('#send-btn').addEventListener('click', () => this.sendMessage());
            this.chatWindow.querySelector('#chat-input').addEventListener('keypress', (e) => {{
                if (e.key === 'Enter') this.sendMessage();
            }});
        }}

        async toggleChat() {{
            if (this.isToggling) return;

            this.isToggling = true;
            this.isOpen = !this.isOpen;

            if (this.isOpen) {{
                this.chatWindow.style.display = 'flex';
                if (!this.chatStarted) {{
                    await this.startChat();
                }}
            }} else {{
                this.chatWindow.style.display = 'none';
            }}

            setTimeout(() => {{
                this.isToggling = false;
            }}, 300);
        }}

        closeChat() {{
            this.isOpen = false;
            this.chatWindow.style.display = 'none';
        }}

        async startChat() {{
            if (this.chatStarted) return;

            try {{
                const response = await fetch(`${{config.api_url}}/${{config.tenant_id}}/start`, {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{
                        client_id: this.clientId
                    }})
                }});

                if (!response.ok) {{
                    const error = await response.json();
                    this.addMessage(error.detail || 'Ошибка при начале чата', false);
                    return;
                }}

                const data = await response.json();
                this.sessionId = data.session_id;
                this.messageCount = 0;
                this.chatStarted = true;

                this.addMessage(config.welcome_message, false);

            }} catch (error) {{
                console.error('Error starting chat:', error);
                this.addMessage('Извините, произошла ошибка при начале чата.', false);
            }}
        }}

        async sendMessage() {{
            const input = this.chatWindow.querySelector('#chat-input');
            const message = input.value.trim();

            if (!message || !this.sessionId) return;

            this.addMessage(message, true);
            input.value = '';
            this.messageCount++;

            this.showTypingIndicator();

            try {{
                const response = await fetch(`${{config.api_url}}/${{config.tenant_id}}/message`, {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{
                        session_id: this.sessionId,
                        message: message,
                        client_id: this.clientId
                    }})
                }});

                this.removeTypingIndicator();

                if (!response.ok) {{
                    const error = await response.json();
                    this.addMessage(error.detail || 'Ошибка отправки', false);
                    return;
                }}

                const data = await response.json();

                setTimeout(() => {{
                    // Проверяем, есть ли маркер для показа формы
                    if (data.response.includes('||SHOW_CONTACT_FORM||')) {{
                        const cleanResponse = data.response.replace('||SHOW_CONTACT_FORM||', '');
                        this.addMessage(cleanResponse, false);
                        if (!this.contactsSubmitted && !this.contactFormShown) {{
                            setTimeout(() => {{
                                this.showContactForm();
                            }}, 500);
                        }}
                    }} else {{
                        this.addMessage(data.response, false);
                    }}
                }}, config.response_delay);

                // Проверяем контакты в сообщении
                await this.checkForContacts(message);

            }} catch (error) {{
                console.error('Error sending message:', error);
                this.removeTypingIndicator();
                this.addMessage('Произошла ошибка. Пожалуйста, попробуйте еще раз.', false);
            }}
        }}

        async checkForContacts(message) {{
            if (this.contactsSubmitted) return;

            // Улучшенные регулярные выражения для поиска контактов
            const phoneRegex = /(?:\\+7|8)?[\\s-]?\\(?\\d{{3}}\\)?[\\s-]?\\d{{3}}[\\s-]?\\d{{2}}[\\s-]?\\d{{2}}/g;
            const cleanPhoneRegex = /(?:\\+7|8)?\\d{{10}}/g;

            let phone = null;

            // Ищем форматированный телефон
            const phoneMatch = message.match(phoneRegex);
            if (phoneMatch) {{
                phone = phoneMatch[0];
            }} else {{
                // Ищем телефон без форматирования (10 цифр подряд)
                const cleanMatch = message.replace(/[\\s\\-\\(\\)]/g, '').match(cleanPhoneRegex);
                if (cleanMatch) {{
                    phone = cleanMatch[0];
                }}
            }}

            // Ищем email
            const emailRegex = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{{2,}}/g;
            const emailMatch = message.match(emailRegex);
            const email = emailMatch ? emailMatch[0] : null;

            if (phone || email) {{
                await this.saveContacts(phone, email);
            }}
        }}

        async saveContacts(phone, email) {{
            if (this.contactsSubmitted) return;

            try {{
                const response = await fetch(`${{config.api_url}}/${{config.tenant_id}}/save-contact`, {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{
                        session_id: this.sessionId,
                        lead_name: '',
                        lead_phone: phone || '',
                        lead_email: email || '',
                        client_id: this.clientId
                    }})
                }});

                if (response.ok) {{
                    this.contactsSubmitted = true;
                    this.addMessage('Спасибо! Ваши контакты сохранены.', false);

                    const contactForm = this.chatWindow.querySelector('#contact-form');
                    if (contactForm) contactForm.remove();
                }} else {{
                    const error = await response.json();
                    console.error('Failed to save contacts:', error);
                }}
            }} catch (error) {{
                console.error('Error saving contacts:', error);
            }}
        }}

        showContactForm() {{
            if (this.contactsSubmitted || this.contactFormShown) return;

            this.contactFormShown = true;
            const messagesDiv = this.chatWindow.querySelector('#chat-messages');

            const contactForm = document.createElement('div');
            contactForm.id = 'contact-form';
            contactForm.style.cssText = `
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                border-radius: 12px;
                padding: 20px;
                margin: 10px 0;
                color: white;
                animation: slideIn 0.3s ease;
            `;

            contactForm.innerHTML = `
                <div style="font-size: 16px; font-weight: 600; margin-bottom: 15px; text-align: center;">
                    📞 Оставьте контакты
                </div>
                <div style="margin-bottom: 10px;">
                    <input type="text" id="contact-name" placeholder="Ваше имя" style="
                        width: 100%;
                        padding: 12px;
                        border: none;
                        border-radius: 8px;
                        font-size: 14px;
                        box-sizing: border-box;
                        margin-bottom: 10px;
                    ">
                </div>
                <div style="margin-bottom: 10px;">
                    <input type="tel" id="contact-phone" placeholder="Телефон" style="
                        width: 100%;
                        padding: 12px;
                        border: none;
                        border-radius: 8px;
                        font-size: 14px;
                        box-sizing: border-box;
                        margin-bottom: 10px;
                    ">
                </div>
                <div style="margin-bottom: 15px;">
                    <input type="email" id="contact-email" placeholder="Email" style="
                        width: 100%;
                        padding: 12px;
                        border: none;
                        border-radius: 8px;
                        font-size: 14px;
                        box-sizing: border-box;
                    ">
                </div>
                <div style="display: flex; gap: 10px;">
                    <button id="submit-contact" style="
                        flex: 2;
                        padding: 12px;
                        background: #28a745;
                        color: white;
                        border: none;
                        border-radius: 8px;
                        cursor: pointer;
                        font-weight: 600;
                        font-size: 14px;
                    ">Отправить</button>
                    <button id="close-contact" style="
                        flex: 1;
                        padding: 12px;
                        background: rgba(255,255,255,0.2);
                        color: white;
                        border: 1px solid white;
                        border-radius: 8px;
                        cursor: pointer;
                        font-size: 14px;
                    ">Закрыть</button>
                </div>
            `;

            messagesDiv.appendChild(contactForm);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;

            document.getElementById('submit-contact').addEventListener('click', () => this.submitContactForm());
            document.getElementById('close-contact').addEventListener('click', () => {{
                contactForm.remove();
                this.contactFormShown = false;
            }});

            // Автофокус на имя
            setTimeout(() => {{
                const nameInput = document.getElementById('contact-name');
                if (nameInput) nameInput.focus();
            }}, 100);
        }}

        async submitContactForm() {{
            const nameInput = document.getElementById('contact-name');
            const phoneInput = document.getElementById('contact-phone');
            const emailInput = document.getElementById('contact-email');

            const name = nameInput ? nameInput.value.trim() : '';
            const phone = phoneInput ? phoneInput.value.trim() : '';
            const email = emailInput ? emailInput.value.trim() : '';

            if (!phone && !email) {{
                alert('Пожалуйста, заполните хотя бы телефон или email');
                return;
            }}

            try {{
                const response = await fetch(`${{config.api_url}}/${{config.tenant_id}}/save-contact`, {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{
                        session_id: this.sessionId,
                        lead_name: name,
                        lead_phone: phone,
                        lead_email: email,
                        client_id: this.clientId
                    }})
                }});

                if (response.ok) {{
                    const contactForm = this.chatWindow.querySelector('#contact-form');
                    if (contactForm) contactForm.remove();
                    this.addMessage('Спасибо! Мы свяжемся с вами в ближайшее время.', false);
                    this.contactsSubmitted = true;
                }} else {{
                    const error = await response.json();
                    alert(error.detail || 'Ошибка при сохранении контактов');
                }}
            }} catch (error) {{
                console.error('Error submitting contact form:', error);
                alert('Ошибка соединения. Пожалуйста, попробуйте позже.');
            }}
        }}

        addMessage(text, isUser) {{
            const messagesDiv = this.chatWindow.querySelector('#chat-messages');
            const messageDiv = document.createElement('div');

            messageDiv.style.cssText = `
                max-width: 80%;
                padding: 12px 16px;
                border-radius: 18px;
                align-self: ${{isUser ? 'flex-end' : 'flex-start'}};
                background: ${{isUser ? config.button_color : '#f0f0f0'}};
                color: ${{isUser ? 'white' : 'black'}};
                word-wrap: break-word;
                font-size: 14px;
                line-height: 1.4;
                margin-bottom: 8px;
            `;

            messageDiv.textContent = text;
            messagesDiv.appendChild(messageDiv);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }}

        showTypingIndicator() {{
            const messagesDiv = this.chatWindow.querySelector('#chat-messages');
            const typingDiv = document.createElement('div');
            typingDiv.id = 'typing-indicator';
            typingDiv.style.cssText = `
                align-self: flex-start;
                background: #f0f0f0;
                padding: 12px 16px;
                border-radius: 18px;
                display: flex;
                gap: 5px;
                margin-bottom: 8px;
            `;

            typingDiv.innerHTML = `
                <div style="width: 8px; height: 8px; background: #999; border-radius: 50%; animation: typing 1.4s infinite;"></div>
                <div style="width: 8px; height: 8px; background: #999; border-radius: 50%; animation: typing 1.4s infinite 0.2s;"></div>
                <div style="width: 8px; height: 8px; background: #999; border-radius: 50%; animation: typing 1.4s infinite 0.4s;"></div>
                <style>
                    @keyframes typing {{
                        0%, 60%, 100% {{ transform: translateY(0); }}
                        30% {{ transform: translateY(-5px); }}
                    }}
                </style>
            `;

            messagesDiv.appendChild(typingDiv);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }}

        removeTypingIndicator() {{
            const typingDiv = this.chatWindow.querySelector('#typing-indicator');
            if (typingDiv) typingDiv.remove();
        }}
    }}

    // Добавляем стили для анимаций
    const style = document.createElement('style');
    style.textContent = `
        @keyframes slideIn {{
            from {{
                opacity: 0;
                transform: translateY(20px);
            }}
            to {{
                opacity: 1;
                transform: translateY(0);
            }}
        }}
    `;
    document.head.appendChild(style);

    if (!window.chatWidget) {{
        window.chatWidget = new ChatWidget();
        console.log('AI Chat Widget инициализирован');
    }}
}})();
    """


# OPTIONS обработчики для CORS
@router.options("/{tenant_id}/start")
async def options_start_chat_session(tenant_id: str, request: Request):
    """OPTIONS запрос для CORS"""
    return Response(
        content="",
        media_type="application/json",
        headers={
            "Access-Control-Allow-Origin": request.headers.get("origin", "*"),
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Max-Age": "600",
        }
    )


@router.options("/{tenant_id}/message")
async def options_widget_message(tenant_id: str, request: Request):
    """OPTIONS запрос для CORS"""
    return Response(
        content="",
        media_type="application/json",
        headers={
            "Access-Control-Allow-Origin": request.headers.get("origin", "*"),
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Max-Age": "600",
        }
    )


@router.options("/{tenant_id}/save-contact")
async def options_save_contact(tenant_id: str, request: Request):
    """OPTIONS запрос для CORS"""
    return Response(
        content="",
        media_type="application/json",
        headers={
            "Access-Control-Allow-Origin": request.headers.get("origin", "*"),
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Max-Age": "600",
        }
    )


@router.post("/{tenant_id}/start")
async def start_chat_session(
        request: Request,
        db: AsyncSession = Depends(get_db),
        tenant: Tenant = Depends(get_tenant_with_balance)
):
    """Начать новую сессию чата (создаёт временную сессию)"""
    logger.info(f"🚀 Старт чата для tenant: {tenant.id}")

    try:
        # Получаем client_id из тела запроса
        try:
            body = await request.json()
            client_id = body.get('client_id')
            logger.info(f"📦 Получен client_id: {client_id}")
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга JSON: {e}")
            client_id = None

        # Rate limiting
        client_ip = request.client.host
        logger.info(f"🌐 Client IP: {client_ip}")

        allowed, msg = await widget_limiter.check_limit(
            tenant_id=tenant.id,
            action='start',
            client_id=client_id,
            client_ip=client_ip
        )
        if not allowed:
            logger.warning(f"⏱️ Rate limit exceeded: {msg}")
            return JSONResponse(
                status_code=429,
                content={"detail": msg},
                headers=_cors_headers(request),
            )

        # СОЗДАЁМ ВРЕМЕННУЮ СЕССИЮ
        temp_session_id = f"temp_{uuid.uuid4()}"

        # Сохраняем временные данные в StorageManager
        session_data = {
            "tenant_id": tenant.id,
            "client_id": client_id,
            "client_ip": client_ip,
            "user_agent": request.headers.get("user-agent", ""),
            "page_url": request.headers.get("referer", ""),
            "created_at": datetime.utcnow().isoformat(),
            "is_active": True
        }

        # Сохраняем с правильным ключом
        storage_key = f"temp_session:{temp_session_id}"
        await storage_manager.set(storage_key, session_data, 3600)  # 1 час

        # Проверяем, что сохранилось
        check_data = await storage_manager.get(storage_key)
        if check_data:
            logger.info(f"✅ Временная сессия сохранена: {temp_session_id}")
        else:
            logger.error(f"❌ Не удалось сохранить временную сессию: {temp_session_id}")

        response_data = {
            "session_id": temp_session_id,
            "welcome_message": tenant.widget_config.get("welcome_message", "Здравствуйте! Чем могу помочь?")
        }

        return JSONResponse(
            status_code=200,
            content=response_data,
            headers=_cors_headers(request),
        )

    except HTTPException as he:
        logger.error(f"❌ HTTP Exception: {he.detail}")
        return JSONResponse(
            status_code=he.status_code,
            content={"detail": he.detail},
            headers=_cors_headers(request),
        )
    except Exception as e:
        logger.error(f"❌ Ошибка в start_chat_session: {str(e)}")
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"detail": "Внутренняя ошибка сервера"},
            headers=_cors_headers(request),
        )


@router.post("/{tenant_id}/message")
async def handle_widget_message(
        message_request: WidgetMessageRequest,
        request: Request,
        db: AsyncSession = Depends(get_db),
        tenant: Tenant = Depends(get_tenant_with_balance)
):
    """Обработать сообщение от пользователя и вернуть ответ AI"""
    logger.info(f"💬 Обработка сообщения для сессии: {message_request.session_id}")

    try:
        # Rate limiting
        client_ip = request.client.host
        allowed, msg = await widget_limiter.check_limit(
            tenant_id=tenant.id,
            action='message',
            client_id=message_request.client_id,
            session_id=message_request.session_id,
            client_ip=client_ip
        )
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": msg},
                headers=_cors_headers(request),
            )

        # Проверка на спам
        if check_suspicious_activity(message_request.message):
            logger.warning(f"🚫 Обнаружен спам от {client_ip}: {message_request.message[:50]}")
            return JSONResponse(
                status_code=400,
                content={"detail": "Сообщение заблокировано как подозрительное"},
                headers=_cors_headers(request),
            )

        # Проверяем, является ли session_id временным
        real_session_id = message_request.session_id
        is_temp_session = message_request.session_id.startswith("temp_")

        if is_temp_session:
            # Получаем временные данные
            storage_key = f"temp_session:{message_request.session_id}"
            logger.info(f"🔍 Ищем временную сессию по ключу: {storage_key}")

            temp_data = await storage_manager.get(storage_key)

            if not temp_data:
                logger.error(f"❌ Временная сессия не найдена: {message_request.session_id}")
                return JSONResponse(
                    status_code=404,
                    content={"detail": "Сессия истекла или не найдена. Пожалуйста, обновите страницу."},
                    headers=_cors_headers(request),
                )

            logger.info(f"✅ Временные данные найдены: {temp_data}")

            # Создаём реальную сессию в БД
            session_in = ChatSessionCreate(
                tenant_id=tenant.id,
                client_id=message_request.client_id or temp_data.get('client_id'),
                session_metadata={
                    "page_url": temp_data.get('page_url', ''),
                    "user_agent": temp_data.get('user_agent', ''),
                    "ip_address": temp_data.get('client_ip', client_ip),
                    "client_id": message_request.client_id or temp_data.get('client_id'),
                    "temp_session_id": message_request.session_id
                }
            )

            chat_session = await crud_chat_session.create(db, session_in=session_in)
            real_session_id = chat_session.id

            # Удаляем временные данные
            await storage_manager.delete(storage_key)

            logger.info(f"✅ Создана реальная сессия {real_session_id} из временной {message_request.session_id}")
        else:
            # Проверяем существование реальной сессии
            session = await crud_chat_session.get(db, message_request.session_id)
            if not session or session.tenant_id != tenant.id:
                return JSONResponse(
                    status_code=404,
                    content={"detail": "Сессия не найдена"},
                    headers=_cors_headers(request),
                )
            real_session_id = message_request.session_id

        # Сохраняем сообщение от пользователя
        user_message = MessageCreate(
            chat_session_id=real_session_id,
            content=message_request.message,
            is_from_lead=True
        )
        await crud_message.create(db, message_in=user_message)

        # Получаем историю сообщений
        message_history = await crud_message.get_by_session(db, real_session_id)

        # Генерируем ответ через AI
        ai_response = await ai_service.generate_response(
            tenant=tenant,
            message_history=message_history,
            user_message=message_request.message
        )

        # Сохраняем ответ AI
        ai_message = MessageCreate(
            chat_session_id=real_session_id,
            content=ai_response,
            is_from_lead=False
        )
        await crud_message.create(db, message_in=ai_message)

        # Обновляем баланс
        tenant.message_balance -= 1
        db.add(tenant)
        await db.commit()
        await db.refresh(tenant)

        logger.info(f"✅ Ответ AI сгенерирован. Новый баланс: {tenant.message_balance}")

        response_data = {
            "response": ai_response,
            "session_id": real_session_id,
            "message_balance": tenant.message_balance
        }

        return JSONResponse(
            status_code=200,
            content=response_data,
            headers=_cors_headers(request),
        )

    except HTTPException as he:
        logger.error(f"❌ HTTP Exception: {he.detail}")
        return JSONResponse(
            status_code=he.status_code,
            content={"detail": he.detail},
            headers=_cors_headers(request),
        )
    except Exception as e:
        logger.error(f"❌ Ошибка в handle_widget_message: {str(e)}")
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"detail": "Внутренняя ошибка сервера"},
            headers=_cors_headers(request),
        )


@router.post("/{tenant_id}/save-contact")
async def save_lead_contact(
        tenant_id: str,
        contact_data: SaveContactRequest,
        request: Request,
        db: AsyncSession = Depends(get_db)
):
    """Сохранить контактные данные лида (публичный эндпоинт для виджета)"""
    logger.info(f"📝 Сохранение контактов для сессии: {contact_data.session_id}")

    try:
        # Валидация tenant_id
        try:
            uuid.UUID(tenant_id)
        except ValueError:
            return JSONResponse(
                status_code=400,
                content={
                    "error": True,
                    "message": "Неверный формат ID компании"
                },
                headers=_cors_headers(request),
            )

        # Проверяем существование тенанта
        tenant = await crud_tenant.get(db, tenant_id)
        if not tenant:
            return JSONResponse(
                status_code=404,
                content={
                    "error": True,
                    "message": "Тенант не найден"
                },
                headers=_cors_headers(request),
            )

        # Rate limiting
        client_ip = request.client.host
        allowed, msg = await widget_limiter.check_limit(
            tenant_id=tenant_id,
            action='contact',
            client_id=contact_data.client_id,
            session_id=contact_data.session_id,
            client_ip=client_ip
        )
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "error": True,
                    "message": msg
                },
                headers=_cors_headers(request),
            )

        # Проверяем, не временная ли сессия
        if contact_data.session_id.startswith("temp_"):
            return JSONResponse(
                status_code=400,
                content={
                    "error": True,
                    "message": "Нельзя сохранить контакты до отправки первого сообщения"
                },
                headers=_cors_headers(request),
            )

        # Проверяем сессию
        session = await crud_chat_session.get(db, contact_data.session_id)
        if not session:
            return JSONResponse(
                status_code=404,
                content={
                    "error": True,
                    "message": "Сессия не найдена"
                },
                headers=_cors_headers(request),
            )

        if session.tenant_id != tenant_id:
            return JSONResponse(
                status_code=403,
                content={
                    "error": True,
                    "message": "Сессия не принадлежит этому тенанту"
                },
                headers=_cors_headers(request),
            )

        # Если контактов нет, но это вызов из функции saveContacts с пустыми значениями
        if not contact_data.lead_phone and not contact_data.lead_email:
            logger.info(f"⚠️ Попытка сохранения пустых контактов для сессии: {contact_data.session_id}")
            return JSONResponse(
                status_code=200,
                content={
                    "status": "success",
                    "message": "Нет контактов для сохранения",
                    "session_id": contact_data.session_id
                },
                headers=_cors_headers(request),
            )

        # Обновляем информацию о лиде
        updated_session = await crud_chat_session.update_lead_info(
            db,
            session=session,
            lead_name=contact_data.lead_name,
            lead_phone=contact_data.lead_phone,
            lead_email=contact_data.lead_email
        )

        logger.info(f"✅ Контакты сохранены для сессии: {contact_data.session_id}")

        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "message": "Контакты сохранены",
                "session_id": contact_data.session_id
            },
            headers=_cors_headers(request),
        )

    except Exception as e:
        logger.error(f"❌ Ошибка сохранения контактов: {e}")
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={
                "error": True,
                "message": "Ошибка при сохранении контактов"
            },
            headers=_cors_headers(request),
        )


@router.post("/{tenant_id}/extract-contacts")
async def extract_contacts_from_message(
        tenant_id: str,
        request: Request,
        db: AsyncSession = Depends(get_db)
):
    """Извлечь контакты из сообщения и сохранить их"""
    try:
        body = await request.json()
        session_id = body.get('session_id')
        message = body.get('message', '')
        client_id = body.get('client_id')

        if not session_id or not message:
            return JSONResponse(
                status_code=400,
                content={"extracted": False},
                headers=_cors_headers(request),
            )

        # Валидация tenant_id
        try:
            uuid.UUID(tenant_id)
        except ValueError:
            return JSONResponse(
                status_code=400,
                content={"extracted": False},
                headers=_cors_headers(request),
            )

        # Проверяем существование тенанта
        tenant = await crud_tenant.get(db, tenant_id)
        if not tenant:
            return JSONResponse(
                status_code=404,
                content={"extracted": False},
                headers=_cors_headers(request),
            )

        # Не обрабатываем временные сессии
        if session_id.startswith("temp_"):
            return JSONResponse(
                status_code=200,
                content={"extracted": False},
                headers=_cors_headers(request),
            )

        # Ищем телефон
        phone_patterns = [
            r'(\+7|8)[\s-]?\(?\d{3}\)?[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}',
            r'(\+7|8)[\s-]?\d{3}[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}',
            r'(\+7|8)\d{10}',
        ]

        phone = None
        for pattern in phone_patterns:
            match = re.search(pattern, message)
            if match:
                phone = match.group(0)
                break

        # Ищем email
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        email_match = re.search(email_pattern, message)
        email = email_match.group(0) if email_match else None

        if phone or email:
            # Сохраняем контакты
            session = await crud_chat_session.get(db, session_id)
            if session and session.tenant_id == tenant_id:
                await crud_chat_session.update_lead_info(
                    db,
                    session=session,
                    lead_phone=phone,
                    lead_email=email
                )
                return JSONResponse(
                    status_code=200,
                    content={
                        "extracted": True,
                        "phone": phone,
                        "email": email
                    },
                    headers=_cors_headers(request),
                )

        return JSONResponse(
            status_code=200,
            content={"extracted": False},
            headers=_cors_headers(request),
        )

    except Exception as e:
        logger.error(f"❌ Error extracting contacts: {e}")
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"extracted": False},
            headers=_cors_headers(request),
        )


@router.get("/{tenant_id}/widget.js")
async def get_widget_js(
        tenant_id: str,
        request: Request,
        db: AsyncSession = Depends(get_db)
):
    """Получить JavaScript код виджета с настройками"""
    logger.info(f"🔍 Запрос виджета для tenant_id: {tenant_id}")

    try:
        # Используем специальную зависимость для виджета
        tenant = await get_tenant_for_widget(tenant_id, db)

        if not tenant:
            return Response(
                content="console.log('Widget not available');",
                media_type="application/javascript",
                headers=_cors_headers(request),
            )

        if not tenant.is_active or tenant.message_balance <= 0:
            return Response(
                content="console.log('Widget temporarily unavailable');",
                media_type="application/javascript",
                headers=_cors_headers(request),
            )

        logger.info(f"✅ Тенант найден: {tenant.company_name} (ID: {tenant.id})")

        # Получаем настройки виджета
        widget_config = tenant.widget_config or {}

        config = {
            "tenant_id": tenant_id,
            "api_url": "http://localhost:8000/api/v1/widget",
            "consultant_name": widget_config.get("consultant_name", "Консультант"),
            "consultant_avatar": widget_config.get("consultant_avatar"),
            "button_color": widget_config.get("button_color", "#007bff"),
            "welcome_message": widget_config.get("welcome_message", "Здравствуйте! Чем могу помочь?"),
            "typing_delay": widget_config.get("typing_delay", 1000),
            "response_delay": widget_config.get("response_delay", 500),
            "widget_position": widget_config.get("widget_position", "bottom-right")
        }

        widget_js = generate_widget_js(config)
        return Response(
            content=widget_js,
            media_type="application/javascript",
            headers=_cors_headers(request),
        )

    except Exception as e:
        logger.error(f"❌ Ошибка в get_widget_js: {e}")
        logger.error(traceback.format_exc())
        return Response(
            content="console.error('Widget generation error');",
            media_type="application/javascript",
            headers=_cors_headers(request),
        )


@router.get("/{tenant_id}/test-connection")
async def test_connection(
        tenant_id: str,
        request: Request,
        db: AsyncSession = Depends(get_db)
):
    """Тестовый endpoint для проверки соединения"""
    try:
        # В production/staging не раскрываем детали о тенанте через публичный endpoint
        if settings.ENVIRONMENT != "development":
            return JSONResponse(
                status_code=404,
                content={"detail": "Not found"},
                headers=_cors_headers(request),
            )

        logger.info(f"🔍 Тест соединения для tenant_id: {tenant_id}")

        # Валидация tenant_id
        try:
            uuid.UUID(tenant_id)
        except ValueError:
            return JSONResponse(
                status_code=400,
                content={"detail": "Неверный формат ID компании"},
                headers=_cors_headers(request),
            )

        tenant = await crud_tenant.get(db, tenant_id)
        if not tenant:
            return JSONResponse(
                status_code=404,
                content={"detail": "Тенант не найден"},
                headers=_cors_headers(request),
            )

        return JSONResponse(
            status_code=200,
            content={
                "status": "ok",
                "tenant_id": tenant_id,
                "company_name": tenant.company_name,
                "is_active": tenant.is_active,
                "message_balance": tenant.message_balance,
                "widget_configured": bool(tenant.widget_config),
                "ai_configured": bool(tenant.ai_prompt),
                "timestamp": datetime.utcnow().isoformat()
            },
            headers=_cors_headers(request),
        )

    except Exception as e:
        logger.error(f"❌ Ошибка в test-connection: {str(e)}")
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"detail": "Внутренняя ошибка сервера"},
            headers=_cors_headers(request),
        )