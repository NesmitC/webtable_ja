// main/static/js/chatbot.js
/**
 * Нейроассистент — чат-бот для платформы "Нейростат"
 */

(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', initChatWidget);

    function initChatWidget() {
        const chatbot = document.getElementById('chatbot');
        const toggle = chatbot?.querySelector('.chatbot__button');
        const chatWindow = document.getElementById('chatbot-window');
        const close = chatbot?.querySelector('.chatbot__close');
        const input = document.getElementById('chatbot-input');
        const send = document.getElementById('chatbot-send');
        const messagesDiv = document.getElementById('chatbot-messages');

        if (!toggle || !chatWindow || !input || !send || !messagesDiv) {
            console.warn('⚠️ Chat widget elements not found');
            return;
        }

        let isWaiting = false;
        let lastUserMessage = '';

        // Открытие/закрытие чата
        toggle.addEventListener('click', () => {
            chatbot.classList.toggle('chatbot--open');
            chatbot.classList.remove('chatbot--hidden');
            if (chatbot.classList.contains('chatbot--open')) {
                setTimeout(() => input.focus(), 100);
                maybeShowProactive();
            }
        });

        // Проактивная рекомендация: один раз за сессию
        function maybeShowProactive() {
            if (sessionStorage.getItem('ns_proactive_shown')) return;
            sessionStorage.setItem('ns_proactive_shown', '1');
            fetch('/api/chat/proactive/')
                .then(r => r.ok ? r.json() : null)
                .then(data => {
                    if (!data || !data.tip) return;
                    appendMessage(data.tip, 'bot');
                    if (data.url) {
                        const a = document.createElement('a');
                        a.href = data.url;
                        a.className = 'chatbot__message chatbot__message--bot';
                        a.style.cssText = 'display:inline-block;text-decoration:none;font-weight:600;';
                        a.textContent = (data.button || '🎯 Открыть тренажёры') + ' →';
                        messagesDiv.appendChild(a);
                        scrollToBottom();
                    }
                })
                .catch(() => {});
        }

        if (close) {
            close.addEventListener('click', () => {
                chatbot.classList.remove('chatbot--open');
            });
        }

        // Прячем кнопку чата, пока футер в кадре:
        // внизу страницы — зона контактов, кнопка не должна перекрывать её
        const footer = document.querySelector('.footer');
        if (footer && 'IntersectionObserver' in window) {
            const io = new IntersectionObserver((entries) => {
                entries.forEach((entry) => {
                    const open = chatbot.classList.contains('chatbot--open');
                    chatbot.classList.toggle('chatbot--hidden', entry.isIntersecting && !open);
                });
            }, { threshold: 0.05 });
            io.observe(footer);
        }

        // Отправка сообщений
        send.addEventListener('click', sendMessage);
        input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });

        function sendMessage() {
            if (isWaiting) return;

            const message = input.value.trim();
            if (!message) return;
            input.value = '';
            lastUserMessage = message;

            // Показываем сообщение пользователя
            appendMessage(message, 'user');
            scrollToBottom();
            sendToServer(message, false);
        }

        // «Объясни проще» — тот же вопрос в упрощённом режиме
        function sendSimplify() {
            if (isWaiting || !lastUserMessage) return;
            appendMessage('🧒 Простыми словами', 'user');
            scrollToBottom();
            sendToServer(lastUserMessage, true);
        }

        function sendToServer(message, simplify) {
            setWaitingState(true);
            showTypingIndicator();

            fetch('/api/chat/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken')
                },
                body: JSON.stringify({ message, simplify })
            })
                .then(response => response.json().then(data => ({ status: response.status, data })))
                .then(({ status, data }) => {
                    hideTypingIndicator();
                    // Гость или исчерпан лимит — вежливая плашка вместо ошибки
                    if (status === 403 && data && data.paywall) {
                        appendPaywall(data.error);
                        scrollToBottom();
                        return;
                    }
                    if (status !== 200 || !data) {
                        throw new Error('HTTP ' + status);
                    }
                    appendMessage(data.reply, 'bot', data.message_id);
                    if (data.simplifiable) addSimplifyButton();
                    scrollToBottom();
                })
                .catch(error => {
                    console.error('Chat error:', error);
                    hideTypingIndicator();
                    appendErrorMessage();
                    scrollToBottom();
                })
                .finally(() => {
                    setWaitingState(false);
                    input.focus();
                });
        }

        // Добавление сообщения в чат
        function appendMessage(text, type, messageId) {
            const msgDiv = document.createElement('div');
            msgDiv.className = `chatbot__message chatbot__message--${type}`;

            const textDiv = document.createElement('div');
            textDiv.className = 'chatbot__message-text';

            if (type === 'bot') {
                textDiv.innerHTML = escapeHtml(text).replace(/\n/g, '<br>');
            } else {
                textDiv.textContent = text;
            }

            msgDiv.appendChild(textDiv);

            // 👍/👎 под ответом ассистента
            if (type === 'bot' && messageId) {
                const fbRow = document.createElement('div');
                fbRow.style.cssText = 'margin-top:4px;display:flex;gap:8px;opacity:0.7;';

                const mkBtn = (emoji) => {
                    const b = document.createElement('button');
                    b.textContent = emoji;
                    b.style.cssText = 'background:none;border:none;cursor:pointer;font-size:13px;padding:2px;';
                    return b;
                };
                const up = mkBtn('👍');
                const down = mkBtn('👎');

                function sendFeedback(value) {
                    fetch('/api/chat-feedback/', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': getCookie('csrftoken')
                        },
                        body: JSON.stringify({ message_id: messageId, feedback: value })
                    }).then(() => {
                        fbRow.style.opacity = '1';
                        up.style.opacity = value === 1 ? '1' : '0.35';
                        down.style.opacity = value === -1 ? '1' : '0.35';
                        up.disabled = true;
                        down.disabled = true;
                    }).catch(() => {});
                }

                up.addEventListener('click', () => sendFeedback(1));
                down.addEventListener('click', () => sendFeedback(-1));
                fbRow.appendChild(up);
                fbRow.appendChild(down);
                msgDiv.appendChild(fbRow);
            }

            messagesDiv.appendChild(msgDiv);
        }

        // Кнопка «Объясни проще» под ответом ИИ
        function addSimplifyButton() {
            const b = document.createElement('button');
            b.style.cssText = 'cursor:pointer;border:1px solid #c9b28c;background:#fff8ec;' +
                'border-radius:14px;padding:6px 12px;font-size:13px;margin:2px 0 2px 8px;';
            b.textContent = '🧒 Простыми словами';
            b.addEventListener('click', () => { b.remove(); sendSimplify(); });
            messagesDiv.appendChild(b);
        }

        function appendErrorMessage() {
            const msgDiv = document.createElement('div');
            msgDiv.className = 'chatbot__message chatbot__message--error';
            msgDiv.textContent = '⚠️ Ошибка соединения. Попробуй позже.';
            messagesDiv.appendChild(msgDiv);
        }

        // Гость: вежливое приглашение войти вместо ошибки
        function appendPaywall(text) {
            const msgDiv = document.createElement('div');
            msgDiv.className = 'chatbot__message chatbot__message--bot';
            const textDiv = document.createElement('div');
            textDiv.className = 'chatbot__message-text';
            textDiv.textContent = '🔐 ' + (text || 'Войди, чтобы общаться с Алексом.');
            msgDiv.appendChild(textDiv);
            const row = document.createElement('div');
            row.style.cssText = 'margin-top:6px;display:flex;gap:8px;';
            const mk = (href, label) => {
                const a = document.createElement('a');
                a.href = href;
                a.textContent = label;
                a.style.cssText = 'text-decoration:none;font-weight:600;border:1px solid #c9b28c;' +
                    'background:#fff8ec;border-radius:14px;padding:6px 12px;font-size:13px;color:#4A3520;';
                return a;
            };
            row.appendChild(mk('/accounts/login/', 'Войти'));
            row.appendChild(mk('/accounts/register/', 'Зарегистрироваться'));
            msgDiv.appendChild(row);
            messagesDiv.appendChild(msgDiv);
        }

        // Индикатор набора
        function showTypingIndicator() {
            const indicator = document.createElement('div');
            indicator.id = 'typing-indicator';
            indicator.className = 'chatbot__typing';
            indicator.innerHTML = `
                <span class="chatbot__typing-dot"></span>
                <span class="chatbot__typing-dot"></span>
                <span class="chatbot__typing-dot"></span>
            `;
            messagesDiv.appendChild(indicator);
            scrollToBottom();
        }

        function hideTypingIndicator() {
            const indicator = document.getElementById('typing-indicator');
            if (indicator) indicator.remove();
        }

        // Управление состоянием ожидания
        function setWaitingState(waiting) {
            isWaiting = waiting;
            input.disabled = waiting;
            send.disabled = waiting;
        }

        // Прокрутка к последнему сообщению
        function scrollToBottom() {
            messagesDiv.scrollTo({
                top: messagesDiv.scrollHeight,
                behavior: 'smooth'
            });
        }

        // Получение CSRF токена
        function getCookie(name) {
            const match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
            return match ? match[2] : null;
        }

        // Экранирование HTML для безопасности
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
    }
})();