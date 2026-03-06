// backend/app/api/templates/widget.js
(function() {
    'use strict';

    const config = {{CONFIG}};

    console.log('AI Chat Widget loaded for tenant:', config.tenant_id);

    class ChatWidget {
        constructor() {
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
        }

        getClientId() {
            const STORAGE_KEY = 'chat_client_id';
            let clientId = localStorage.getItem(STORAGE_KEY);

            if (!clientId) {
                clientId = 'client_' + Date.now() + '_' +
                          Math.random().toString(36).substr(2, 9) +
                          Math.random().toString(36).substr(2, 9);
                localStorage.setItem(STORAGE_KEY, clientId);
            }

            return clientId;
        }

        init() {
            this.createButton();
            this.createChatWindow();
            this.bindEvents();
        }

        createButton() {
            this.button = document.createElement('div');

            this.button.innerHTML = `
                <svg width="30" height="30" viewBox="0 0 24 24" fill="white">
                    <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"/>
                </svg>
            `;

            const position = this.getPosition();
            this.button.style.cssText = `
                position: fixed;
                ${position.style};
                width: 60px;
                height: 60px;
                background: ${config.button_color};
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
        }

        getPosition() {
            const pos = config.widget_position || 'bottom-right';
            let style = '';

            switch(pos) {
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
                    style = 'bottom: 20px; right: 20px;';
            }

            return { style: style, position: pos };
        }

        createChatWindow() {
            this.chatWindow = document.createElement('div');

            const position = this.getPosition();
            let windowStyle = '';

            if (position.position.includes('bottom')) {
                windowStyle = 'bottom: 90px;';
            } else {
                windowStyle = 'top: 90px;';
            }

            if (position.position.includes('right')) {
                windowStyle += ' right: 20px;';
            } else {
                windowStyle += ' left: 20px;';
            }

            this.chatWindow.style.cssText = `
                position: fixed;
                ${windowStyle}
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
                `<img src="${config.consultant_avatar}" style="width: 40px; height: 40px; border-radius: 50%; object-fit: cover; margin-right: 10px; border: 2px solid white;">` :
                `<div style="width: 40px; height: 40px; border-radius: 50%; background: rgba(255,255,255,0.2); margin-right: 10px; display: flex; align-items: center; justify-content: center; font-size: 20px; border: 2px solid white;">👤</div>`;

            this.chatWindow.innerHTML = `
                <div style="
                    background: ${config.button_color};
                    color: white;
                    padding: 15px;
                    border-radius: 12px 12px 0 0;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                ">
                    <div style="display: flex; align-items: center;">
                        ${avatarHtml}
                        <div>
                            <strong style="font-size: 16px;">${config.consultant_name}</strong>
                            <div style="font-size: 12px; opacity: 0.8;">Онлайн Консультант</div>
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
                            background: ${config.button_color};
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
        }

        bindEvents() {
            this.button.addEventListener('click', () => this.toggleChat());
            this.chatWindow.querySelector('#close-chat').addEventListener('click', () => this.closeChat());
            this.chatWindow.querySelector('#send-btn').addEventListener('click', () => this.sendMessage());
            this.chatWindow.querySelector('#chat-input').addEventListener('keypress', (e) => {
                if (e.key === 'Enter') this.sendMessage();
            });
        }

        async toggleChat() {
            if (this.isToggling) return;

            this.isToggling = true;
            this.isOpen = !this.isOpen;

            if (this.isOpen) {
                this.chatWindow.style.display = 'flex';
                if (!this.chatStarted) {
                    await this.startChat();
                }
            } else {
                this.chatWindow.style.display = 'none';
            }

            setTimeout(() => {
                this.isToggling = false;
            }, 300);
        }

        closeChat() {
            this.isOpen = false;
            this.chatWindow.style.display = 'none';
        }

        async startChat() {
            if (this.chatStarted) return;

            try {
                const response = await fetch(`${config.api_url}/${config.tenant_id}/start`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        client_id: this.clientId
                    })
                });

                if (!response.ok) {
                    const error = await response.json();
                    this.addMessage(error.detail || 'Ошибка при начале чата', false);
                    return;
                }

                const data = await response.json();
                this.sessionId = data.session_id;
                this.messageCount = 0;
                this.chatStarted = true;

                this.addMessage(config.welcome_message, false);

            } catch (error) {
                console.error('Error starting chat:', error);
                this.addMessage('Извините, произошла ошибка при начале чата.', false);
            }
        }

        async sendMessage() {
            const input = this.chatWindow.querySelector('#chat-input');
            const message = input.value.trim();

            if (!message || !this.sessionId) return;

            this.addMessage(message, true);
            input.value = '';
            this.messageCount++;

            this.showTypingIndicator();

            try {
                const response = await fetch(`${config.api_url}/${config.tenant_id}/message`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        session_id: this.sessionId,
                        message: message,
                        client_id: this.clientId
                    })
                });

                this.removeTypingIndicator();

                if (!response.ok) {
                    const error = await response.json();
                    this.addMessage(error.detail || 'Ошибка отправки', false);
                    return;
                }

                const data = await response.json();

                setTimeout(() => {
                    // Проверяем, есть ли маркер для показа формы
                    if (data.response.includes('||SHOW_CONTACT_FORM||')) {
                        const cleanResponse = data.response.replace('||SHOW_CONTACT_FORM||', '');
                        this.addMessage(cleanResponse, false);
                        if (!this.contactsSubmitted && !this.contactFormShown) {
                            setTimeout(() => {
                                this.showContactForm();
                            }, 500);
                        }
                    } else {
                        this.addMessage(data.response, false);
                    }
                }, config.response_delay);

                // Проверяем контакты в сообщении
                await this.checkForContacts(message);

            } catch (error) {
                console.error('Error sending message:', error);
                this.removeTypingIndicator();
                this.addMessage('Произошла ошибка. Пожалуйста, попробуйте еще раз.', false);
            }
        }

        async checkForContacts(message) {
            if (this.contactsSubmitted) return;

            // Улучшенные регулярные выражения для поиска контактов
            const phoneRegex = /(?:\+7|8)?[\s-]?\(?\d{3}\)?[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}/g;
            const cleanPhoneRegex = /(?:\+7|8)?\d{10}/g;

            let phone = null;

            // Ищем форматированный телефон
            const phoneMatch = message.match(phoneRegex);
            if (phoneMatch) {
                phone = phoneMatch[0];
            } else {
                // Ищем телефон без форматирования (10 цифр подряд)
                const cleanMatch = message.replace(/[\s\-\(\)]/g, '').match(cleanPhoneRegex);
                if (cleanMatch) {
                    phone = cleanMatch[0];
                }
            }

            // Ищем email
            const emailRegex = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g;
            const emailMatch = message.match(emailRegex);
            const email = emailMatch ? emailMatch[0] : null;

            if (phone || email) {
                await this.saveContacts(phone, email);
            }
        }

        async saveContacts(phone, email) {
            if (this.contactsSubmitted) return;

            try {
                const response = await fetch(`${config.api_url}/${config.tenant_id}/save-contact`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        session_id: this.sessionId,
                        lead_name: '',
                        lead_phone: phone || '',
                        lead_email: email || '',
                        client_id: this.clientId
                    })
                });

                if (response.ok) {
                    this.contactsSubmitted = true;
                    this.addMessage('✅ Спасибо! Ваши контакты сохранены.', false);

                    const contactForm = this.chatWindow.querySelector('#contact-form');
                    if (contactForm) contactForm.remove();
                } else {
                    const error = await response.json();
                    console.error('Failed to save contacts:', error);
                }
            } catch (error) {
                console.error('Error saving contacts:', error);
            }
        }

        showContactForm() {
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
            document.getElementById('close-contact').addEventListener('click', () => {
                contactForm.remove();
                this.contactFormShown = false;
            });

            // Автофокус на имя
            setTimeout(() => {
                const nameInput = document.getElementById('contact-name');
                if (nameInput) nameInput.focus();
            }, 100);
        }

        async submitContactForm() {
            const nameInput = document.getElementById('contact-name');
            const phoneInput = document.getElementById('contact-phone');
            const emailInput = document.getElementById('contact-email');

            const name = nameInput ? nameInput.value.trim() : '';
            const phone = phoneInput ? phoneInput.value.trim() : '';
            const email = emailInput ? emailInput.value.trim() : '';

            if (!phone && !email) {
                alert('Пожалуйста, заполните хотя бы телефон или email');
                return;
            }

            try {
                const response = await fetch(`${config.api_url}/${config.tenant_id}/save-contact`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        session_id: this.sessionId,
                        lead_name: name,
                        lead_phone: phone,
                        lead_email: email,
                        client_id: this.clientId
                    })
                });

                if (response.ok) {
                    const contactForm = this.chatWindow.querySelector('#contact-form');
                    if (contactForm) contactForm.remove();
                    this.addMessage('✅ Спасибо! Мы свяжемся с вами в ближайшее время.', false);
                    this.contactsSubmitted = true;
                } else {
                    const error = await response.json();
                    alert(error.detail || 'Ошибка при сохранении контактов');
                }
            } catch (error) {
                console.error('Error submitting contact form:', error);
                alert('Ошибка соединения. Пожалуйста, попробуйте позже.');
            }
        }

        addMessage(text, isUser) {
            const messagesDiv = this.chatWindow.querySelector('#chat-messages');
            const messageDiv = document.createElement('div');

            messageDiv.style.cssText = `
                max-width: 80%;
                padding: 12px 16px;
                border-radius: 18px;
                align-self: ${isUser ? 'flex-end' : 'flex-start'};
                background: ${isUser ? config.button_color : '#f0f0f0'};
                color: ${isUser ? 'white' : 'black'};
                word-wrap: break-word;
                font-size: 14px;
                line-height: 1.4;
                margin-bottom: 8px;
            `;

            messageDiv.textContent = text;
            messagesDiv.appendChild(messageDiv);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }

        showTypingIndicator() {
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
                    @keyframes typing {
                        0%, 60%, 100% { transform: translateY(0); }
                        30% { transform: translateY(-5px); }
                    }
                </style>
            `;

            messagesDiv.appendChild(typingDiv);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }

        removeTypingIndicator() {
            const typingDiv = this.chatWindow.querySelector('#typing-indicator');
            if (typingDiv) typingDiv.remove();
        }
    }

    // Добавляем стили для анимаций
    const style = document.createElement('style');
    style.textContent = `
        @keyframes slideIn {
            from {
                opacity: 0;
                transform: translateY(20px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
    `;
    document.head.appendChild(style);

    if (!window.chatWidget) {
        window.chatWidget = new ChatWidget();
        console.log('✅ AI Chat Widget инициализирован');
    }
})();