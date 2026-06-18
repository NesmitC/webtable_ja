// main/static/js/chatbot.js
/**
 * Нейроассистент — чат-бот для платформы "Нейростат"
 */

(function() {
    // 🔹 Ждём загрузки DOM
    document.addEventListener('DOMContentLoaded', function() {
        initChatWidget();
    });

    // 🔹 Инициализация виджета
    function initChatWidget() {
        const toggle = document.getElementById('chat-toggle');
        const chatWindow = document.getElementById('chat-window');
        const close = document.getElementById('chat-close');
        const input = document.getElementById('chat-input');
        const send = document.getElementById('chat-send');
        const messagesDiv = document.getElementById('chat-messages');

        if (!toggle || !chatWindow || !input || !send || !messagesDiv) {
            console.warn('⚠️ Chat widget elements not found');
            return;
        }

        let isWaiting = false;  // Блокировка во время ожидания ответа

        // Открыть/закрыть окно
        toggle.addEventListener('click', function() {
            chatWindow.style.display = chatWindow.style.display === 'flex' ? 'none' : 'flex';
            if (chatWindow.style.display === 'flex') {
                input.focus();
            }
        });

        // Закрыть по крестику
        if (close) {
            close.addEventListener('click', function() {
                chatWindow.style.display = 'none';
            });
        }

        // Отправка по кнопке
        send.addEventListener('click', function() {
            sendMessage();
        });

        // Отправка по Enter
        input.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                sendMessage();
            }
        });

        // 🔹 Функция отправки сообщения
        function sendMessage() {
            if (isWaiting) return;  // Блокируем повторную отправку

            const message = input.value.trim();
            if (!message) return;

            // Сообщение пользователя
            appendUserMessage(message);
            input.value = '';
            scrollToBottom();

            // Показываем индикатор "Работаю..."
            showTypingIndicator();
            isWaiting = true;
            input.disabled = true;
            send.disabled = true;
            send.style.opacity = '0.5';
            send.style.cursor = 'not-allowed';

            // Запрос к API
            fetch('/api/chat/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken')
                },
                body: JSON.stringify({ message: message })
            })
            .then(function(response) {
                return response.json();
            })
            .then(function(data) {
                // Скрываем индикатор
                hideTypingIndicator();

                // Показываем ответ
                appendBotMessage(data.reply);
                scrollToBottom();
            })
            .catch(function(error) {
                console.error('Chat error:', error);
                hideTypingIndicator();
                appendErrorMessage();
                scrollToBottom();
            })
            .finally(function() {
                // Разблокируем ввод
                isWaiting = false;
                input.disabled = false;
                send.disabled = false;
                send.style.opacity = '1';
                send.style.cursor = 'pointer';
                input.focus();
            });
        }

        // 🔹 Добавить сообщение пользователя
        function appendUserMessage(text) {
            const msgDiv = document.createElement('div');
            msgDiv.style.cssText = 'margin: 8px 0; text-align: right;';
            msgDiv.innerHTML = '<strong style="color: #0d6efd;">Ты:</strong> ' + escapeHtml(text);
            messagesDiv.appendChild(msgDiv);
        }

        // 🔹 Добавить сообщение бота
        function appendBotMessage(text) {
            const msgDiv = document.createElement('div');
            msgDiv.style.cssText = 'margin: 8px 0;';
            msgDiv.innerHTML = 
                '<strong style="color: #2e7d32;">Нейроассистент:</strong> ' +
                '<div style="background: #f0f8ff; padding: 8px; border-radius: 4px; margin-top: 4px;">' +
                escapeHtml(text).replace(/\n/g, '<br>') +
                '</div>';
            messagesDiv.appendChild(msgDiv);
        }

        // 🔹 Добавить сообщение об ошибке
        function appendErrorMessage() {
            const msgDiv = document.createElement('div');
            msgDiv.style.cssText = 'margin: 8px 0; color: red;';
            msgDiv.textContent = '⚠️ Ошибка соединения. Попробуй позже.';
            messagesDiv.appendChild(msgDiv);
        }

        // 🔹 Показать индикатор набора
        function showTypingIndicator() {
            const indicator = document.createElement('div');
            indicator.id = 'typing-indicator';
            indicator.className = 'typing-indicator';
            indicator.innerHTML = 
                'Работаю над ответом' +
                '<span class="dot">.</span>' +
                '<span class="dot">.</span>' +
                '<span class="dot">.</span>';
            messagesDiv.appendChild(indicator);
            scrollToBottom();
        }

        // 🔹 Скрыть индикатор набора
        function hideTypingIndicator() {
            const indicator = document.getElementById('typing-indicator');
            if (indicator) {
                indicator.remove();
            }
        }

        // 🔹 Прокрутка вниз
        function scrollToBottom() {
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }

        // 🔹 CSRF токен
        function getCookie(name) {
            const match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
            return match ? match[2] : null;
        }

        // 🔹 Экранирование HTML (безопасность)
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
    }
})();


