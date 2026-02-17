// ===========================================================================
// МОДУЛЬ ДЛЯ ТЕКСТОВЫХ ЗАДАНИЙ 23–26
// ===========================================================================

// --- Вспомогательная функция для получения CSRF-токена ---
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// --- Функция для загрузки текстового анализа (задания 1-3) ---
async function loadTextAnalysis() {
    const csrfToken = getCookie('csrftoken');
    const answerSection = document.querySelector('.block-answer');
    
    if (!answerSection) {
        console.error('Не найден блок .block-answer');
        return;
    }
    
    answerSection.innerHTML = '<p>Загружаем текст для анализа...</p>';
    
    try {
        const response = await fetch('/api/generate-text-analysis/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({})
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || `HTTP ${response.status}`);
        }
        
        const data = await response.json();
        answerSection.innerHTML = `<h2 class="title-practice">Задания 1-3 (анализ текста)</h2>${data.html}`;
        
        // Навешиваем обработчик проверки для 1-3
        setupTextAnalysisCheck();
        
    } catch (err) {
        console.error('Ошибка загрузки текста:', err);
        answerSection.innerHTML = '<p class="error">Не удалось загрузить текст</p>';
    }
}

// --- Настройка проверки текста (задания 1-3) ---
function setupTextAnalysisCheck() {
    const answerSection = document.querySelector('.block-answer');
    const container = answerSection ? answerSection.querySelector('.text-analysis-exercise') : null;
    if (!container) {
        console.error('Контейнер .text-analysis-exercise не найден');
        return;
    }
    const checkBtn = container.querySelector('.check-text-analysis');
    const resultDiv = container.querySelector('.result');
    if (!checkBtn || !resultDiv) {
        console.error('Не найдены элементы для проверки (checkBtn или resultDiv)');
        return;
    }

    // Обработчик кнопки проверки
    checkBtn.addEventListener('click', async function () {
        const answers = {};
        // Вопрос 1 — текстовое поле
        const q1Input = container.querySelector('input[data-question="1"]');
        if (q1Input) answers['1'] = q1Input.value.trim();

        // Вопросы 2 и 3 — чекбоксы
        [2, 3].forEach(qNum => {
            const checkboxes = container.querySelectorAll(`input[data-question="${qNum}"]:checked`);
            const selected = Array.from(checkboxes).map(cb => cb.value).join('');
            answers[qNum.toString()] = selected;
        });

        try {
            const csrfToken = getCookie('csrftoken');
            const response = await fetch('/api/check-text-analysis/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({ answers })
            });
            const data = await response.json();
            if (data.error) {
                resultDiv.innerHTML = `<p class="error">${data.error}</p>`;
                resultDiv.style.display = 'block';
                return;
            }
            if (data.results) {
                // Подсветка чекбоксов и текстовых полей
                container.querySelectorAll('[data-question]').forEach(el => {
                    const q = el.dataset.question;
                    if (data.results[q]) {
                        const isCorrect = data.results[q].is_correct;
                        
                        // Убираем старые классы
                        el.classList.remove('task-match-correct', 'task-match-incorrect');
                        
                        // Подсвечиваем только если элемент выбран или имеет текст
                        const shouldHighlight = el.type === 'checkbox' ? el.checked : el.value.trim() !== '';
                        
                        if (shouldHighlight) {
                            if (isCorrect) {
                                el.classList.add('task-match-correct');
                            } else {
                                el.classList.add('task-match-incorrect');
                            }
                        }
                    }
                });
            }

            let html = `<h4>Результаты:</h4>`;
            html += `<p>Правильных ответов: ${data.total_correct} из ${data.total_questions}</p>`;
            for (const [qNum, result] of Object.entries(data.results)) {
                const icon = result.is_correct ? '✅' : '❌';
                html += `<p>${icon} Вопрос ${qNum}: Ваш ответ "${result.user_answer}"`;
                if (!result.is_correct) {
                    html += `, правильный: "${result.correct_answer}"`;
                }
                html += `</p>`;
            }
            resultDiv.innerHTML = html;
            resultDiv.style.display = 'block';
        } catch (err) {
            console.error('Ошибка проверки 1–3:', err);
            resultDiv.innerHTML = '<p class="error">Ошибка при проверке</p>';
            resultDiv.style.display = 'block';
        }
    });
}

// --- Загрузка заданий 23–26 ---
async function loadTextAnalysis23_26() {
    const csrfToken = getCookie('csrftoken');
    const answerSection = document.querySelector('.block-answer');
    if (!answerSection) {
        console.error('Не найден блок .block-answer');
        return;
    }
    answerSection.innerHTML = '<p>Загружаем текст для анализа (задания 23–26)...</p>';
    try {
        const response = await fetch('/api/generate-text-analysis-23-26/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({})
        });
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || `HTTP ${response.status}`);
        }
        const data = await response.json();
        answerSection.innerHTML = `<h2 class="title-practice">Задания 23–26 (анализ текста)</h2>${data.html}`;
        setupTextAnalysisCheck23_26();
    } catch (err) {
        console.error('Ошибка загрузки текста 23–26:', err);
        answerSection.innerHTML = '<p class="error">Не удалось загрузить текст</p>';
    }
}

// --- Проверка заданий 23–26 ---
function setupTextAnalysisCheck23_26() {
    const answerSection = document.querySelector('.block-answer');
    const container = answerSection ? answerSection.querySelector('.text-analysis-exercise') : null;
    if (!container) {
        console.error('Контейнер .text-analysis-exercise не найден');
        return;
    }
    const checkBtn = container.querySelector('.check-text-analysis');
    const resultDiv = container.querySelector('.result');
    if (!checkBtn || !resultDiv) {
        console.error('Не найдены элементы для проверки (checkBtn или resultDiv)');
        return;
    }

    // Применяем стили (как в 23-24)
    function applyCorrectStyles() {
        const styleId = 'correct-text-analysis-styles-23-26';
        if (!document.getElementById(styleId)) {
            const style = document.createElement('style');
            style.id = styleId;
            style.textContent = `
                .text-analysis-exercise label {
                    display: block !important;
                    margin-left: 0 !important;
                    padding-left: 0 !important;
                    margin-bottom: 8px !important;
                }
                .text-analysis-exercise input[type="checkbox"] {
                    margin-right: 12px !important;
                    margin-left: 0 !important;
                    vertical-align: top !important;
                    margin-bottom: 0 !important;
                    position: relative !important;
                    top: 1px !important;
                    display: inline-block !important;
                    width: auto !important;
                    height: auto !important;
                }
                .text-analysis-exercise .option {
                    margin-left: 0 !important;
                    padding-left: 0 !important;
                    margin-bottom: 8px !important;
                }
                .block-answer .text-analysis-exercise {
                    margin-left: -5px !important;
                    padding-left: 0 !important;
                }
            `;
            document.head.appendChild(style);
        }

        // Инлайн-стили для надёжности
        container.querySelectorAll('label').forEach(label => {
            label.style.display = 'block';
            label.style.marginLeft = '0';
            label.style.paddingLeft = '0';
            label.style.marginBottom = '8px';
        });
        container.querySelectorAll('input[type="checkbox"]').forEach(cb => {
            cb.style.marginRight = '12px';
            cb.style.marginLeft = '0';
            cb.style.marginBottom = '0';
            cb.style.verticalAlign = 'top';
            cb.style.position = 'relative';
            cb.style.top = '1px';
            cb.style.opacity = '1';
            cb.style.visibility = 'visible';
            cb.style.display = 'inline-block';
            cb.style.width = '';
            cb.style.height = '';
        });
        container.querySelectorAll('.option, .options, .question').forEach(el => {
            el.style.marginLeft = '0';
            el.style.paddingLeft = '0';
        });
        container.style.marginLeft = '-5px';
        container.style.paddingLeft = '0';
    }

    applyCorrectStyles();
    setTimeout(applyCorrectStyles, 300);

    // Обработчик проверки
    checkBtn.addEventListener('click', async function () {
        const answers = {};

        // Сбор чекбоксов: 23, 24
        [23, 24].forEach(qNum => {
            const checkboxes = container.querySelectorAll(`input[data-question="${qNum}"]:checked`);
            const selected = Array.from(checkboxes).map(cb => cb.value).join('');
            answers[qNum.toString()] = selected;
        });

        // Сбор текстовых полей: 25, 26
        [25, 26].forEach(qNum => {
            const input = container.querySelector(`input[data-question="${qNum}"]`);
            answers[qNum.toString()] = input ? input.value.trim() : '';
        });

        // Отправка на сервер
        try {
            const csrfToken = getCookie('csrftoken');
            const response = await fetch('/api/check-text-analysis-23-26/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({ answers })
            });
            const data = await response.json();
            if (data.error) {
                resultDiv.innerHTML = `<p class="error">${data.error}</p>`;
                resultDiv.style.display = 'block';
                return;
            }
            if (data.results) {
                // Подсветка всех полей с data-question
                container.querySelectorAll('[data-question]').forEach(el => {
                    const q = el.dataset.question;
                    if (data.results[q]) {
                        const isCorrect = data.results[q].is_correct;
                        
                        el.classList.remove('task-match-correct', 'task-match-incorrect');
                        
                        const shouldHighlight = el.type === 'checkbox' ? el.checked : el.value.trim() !== '';
                        
                        if (shouldHighlight) {
                            if (isCorrect) {
                                el.classList.add('task-match-correct');
                            } else {
                                el.classList.add('task-match-incorrect');
                            }
                        }
                    }
                });
}

            // Отображение результата
            let html = `<h4>Результаты:</h4>`;
            html += `<p>Правильных ответов: ${data.total_correct} из ${data.total_questions}</p>`;
            for (const [qNum, result] of Object.entries(data.results)) {
                const icon = result.is_correct ? '✅' : '❌';
                html += `<p>${icon} Вопрос ${qNum}: Ваш ответ "${result.user_answer}"`;
                if (!result.is_correct) {
                    html += `, правильный: "${result.correct_answer}"`;
                }
                html += `</p>`;
            }
            resultDiv.innerHTML = html;
            resultDiv.style.display = 'block';
        } catch (err) {
            console.error('Ошибка проверки 23–26:', err);
            resultDiv.innerHTML = '<p class="error">Ошибка при проверке</p>';
            resultDiv.style.display = 'block';
        }
    });
}

// --- Экспорт модуля ---
window.TextAnalysisModule = {
    ...window.TextAnalysisModule,
    loadTextAnalysis,
    loadTextAnalysis23_26,
    setupTextAnalysisCheck,
    setupTextAnalysisCheck23_26
};