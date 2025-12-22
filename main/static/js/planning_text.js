// ===========================================================================
// МОДУЛЬ ДЛЯ ТЕКСТОВЫХ ЗАДАНИЙ 1-3 и 23-24
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

// --- Функция для загрузки текстового анализа (задания 23-24) ---
async function loadTextAnalysis23_24() {
    const csrfToken = getCookie('csrftoken');
    const answerSection = document.querySelector('.block-answer');
    
    if (!answerSection) {
        console.error('Не найден блок .block-answer');
        return;
    }
    
    answerSection.innerHTML = '<p>Загружаем текст для анализа (задания 23-24)...</p>';
    
    try {
        const response = await fetch('/api/generate-text-analysis-23-24/', {
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
        answerSection.innerHTML = `<h2 class="title-practice">Задания 23-24 (анализ текста)</h2>${data.html}`;
        
        // Используем ОТДЕЛЬНУЮ функцию для 23-24
        setupTextAnalysisCheck23_24();
        
    } catch (err) {
        console.error('Ошибка загрузки текста 23-24:', err);
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
    
    // ФИКС СТИЛЕЙ
    function applyCorrectStyles() {
        console.log('=== ФИКС СТИЛЕЙ ДЛЯ ТЕКСТОВЫХ ЗАДАНИЙ ===');
        
        // 1. Удаляем старые стили если есть
        const oldStyle = document.getElementById('nuclear-text-analysis-styles');
        if (oldStyle) oldStyle.remove();
        
        // 2. Добавляем ПРАВИЛЬНЫЕ стили
        const styleId = 'correct-text-analysis-styles';
        if (!document.getElementById(styleId)) {
            const style = document.createElement('style');
            style.id = styleId;
            style.textContent = `
                /* ПРАВИЛЬНЫЕ СТИЛИ - только нужные свойства */
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
                
                /* Компенсируем padding родительского .block-answer */
                .block-answer .text-analysis-exercise {
                    margin-left: -5px !important;
                    padding-left: 0 !important;
                }
            `;
            document.head.appendChild(style);
            console.log('✅ Правильные стили добавлены');
        }
        
        // 3. Применяем инлайн стили КОНТРОЛИРОВАННО
        const labels = container.querySelectorAll('label');
        console.log(`Найдено labels: ${labels.length}`);
        
        labels.forEach(label => {
            label.style.display = 'block';
            label.style.marginLeft = '0';
            label.style.paddingLeft = '0';
            label.style.marginBottom = '8px';
        });
        
        const checkboxes = container.querySelectorAll('input[type="checkbox"]');
        console.log(`Найдено чекбоксов: ${checkboxes.length}`);
        
        checkboxes.forEach(cb => {
            cb.style.marginRight = '12px';
            cb.style.marginLeft = '0';
            cb.style.marginBottom = '0';
            cb.style.verticalAlign = 'top';
            cb.style.position = 'relative';
            cb.style.top = '1px';
            
            // Гарантируем видимость
            cb.style.opacity = '1';
            cb.style.visibility = 'visible';
            cb.style.display = 'inline-block';
            cb.style.width = '';
            cb.style.height = '';
        });
        
        // 4. Фиксим контейнеры
        const containers = container.querySelectorAll('.option, .options, .question');
        containers.forEach(el => {
            el.style.marginLeft = '0';
            el.style.paddingLeft = '0';
        });
        
        // 5. Компенсируем padding родителя
        container.style.marginLeft = '-5px';
        container.style.paddingLeft = '0';
        
        console.log('✅ Стили применены');
    }
    
    // ПРИМЕНЯЕМ ФИКС
    applyCorrectStyles();
    setTimeout(applyCorrectStyles, 300);
    
    // Обработчик кнопки проверки
    checkBtn.addEventListener('click', async function() {
        // Собираем ответы для 1-3
        const answers = {};
        
        // Ответ на вопрос 1 (текстовое поле)
        const q1Input = container.querySelector('input[data-question="1"]');
        if (q1Input) answers['1'] = q1Input.value.trim();
        
        // Ответы на вопросы 2 и 3 (чеки)
        [2, 3].forEach(qNum => {
            const checkboxes = container.querySelectorAll(`input[data-question="${qNum}"]:checked`);
            const selected = Array.from(checkboxes).map(cb => cb.value).join('');
            answers[qNum.toString()] = selected;
        });
        
        // Проверяем API для 1-3
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
            
            // Показываем результаты
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
            console.error('Ошибка проверки:', err);
            resultDiv.innerHTML = '<p class="error">Ошибка проверки</p>';
            resultDiv.style.display = 'block';
        }
    });
}

// --- Функция проверки для 23-24 (полный аналог функции для 1-3) ---
function setupTextAnalysisCheck23_24() {
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
    
    // ТОЧНО ТАКОЙ ЖЕ ФИКС СТИЛЕЙ КАК ДЛЯ 1-3
    function applyCorrectStyles() {
        console.log('=== ФИКС СТИЛЕЙ ДЛЯ 23-24 ===');
        
        // 1. Удаляем старые стили если есть
        const oldStyle = document.getElementById('correct-text-analysis-styles-23-24');
        if (oldStyle) oldStyle.remove();
        
        // 2. Добавляем ПРАВИЛЬНЫЕ стили (ТОЧНО ТАКИЕ ЖЕ)
        const styleId = 'correct-text-analysis-styles-23-24';
        if (!document.getElementById(styleId)) {
            const style = document.createElement('style');
            style.id = styleId;
            style.textContent = `
                /* ТОЧНО ТЕ ЖЕ СТИЛИ ЧТО ДЛЯ 1-3 */
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
                
                /* Компенсируем padding родительского .block-answer */
                .block-answer .text-analysis-exercise {
                    margin-left: -5px !important;
                    padding-left: 0 !important;
                }
            `;
            document.head.appendChild(style);
            console.log('✅ Стили для 23-24 добавлены');
        }
        
        // 3. Применяем инлайн стили (ТОЧНО ТАК ЖЕ)
        const labels = container.querySelectorAll('label');
        console.log(`Найдено labels для 23-24: ${labels.length}`);
        
        labels.forEach(label => {
            label.style.display = 'block';
            label.style.marginLeft = '0';
            label.style.paddingLeft = '0';
            label.style.marginBottom = '8px';
        });
        
        const checkboxes = container.querySelectorAll('input[type="checkbox"]');
        console.log(`Найдено чекбоксов для 23-24: ${checkboxes.length}`);
        
        checkboxes.forEach(cb => {
            cb.style.marginRight = '12px';
            cb.style.marginLeft = '0';
            cb.style.marginBottom = '0';
            cb.style.verticalAlign = 'top';
            cb.style.position = 'relative';
            cb.style.top = '1px';
            
            // Гарантируем видимость (ТОЧНО ТАК ЖЕ)
            cb.style.opacity = '1';
            cb.style.visibility = 'visible';
            cb.style.display = 'inline-block';
            cb.style.width = '';
            cb.style.height = '';
        });
        
        // 4. Фиксим контейнеры (ТОЧНО ТАК ЖЕ)
        const containers = container.querySelectorAll('.option, .options, .question');
        containers.forEach(el => {
            el.style.marginLeft = '0';
            el.style.paddingLeft = '0';
        });
        
        // 5. Компенсируем padding родителя (ТОЧНО ТАК ЖЕ)
        container.style.marginLeft = '-5px';
        container.style.paddingLeft = '0';
        
        console.log('✅ Стили для 23-24 применены');
    }
    
    // ПРИМЕНЯЕМ ФИКС (ТОЧНО ТАК ЖЕ)
    applyCorrectStyles();
    setTimeout(applyCorrectStyles, 300);
    
    // Обработчик кнопки проверки ДЛЯ 23-24
    checkBtn.addEventListener('click', async function() {
        // Собираем ответы для 23-24 (вопросы 23 и 24)
        const answers = {};
        
        // Ответы на вопросы 23 и 24 (чеки)
        [23, 24].forEach(qNum => {
            const checkboxes = container.querySelectorAll(`input[data-question="${qNum}"]:checked`);
            const selected = Array.from(checkboxes).map(cb => cb.value).join('');
            answers[qNum.toString()] = selected;
        });
        
        // Проверяем через API для 23-24 (другой endpoint)
        try {
            const csrfToken = getCookie('csrftoken');
            const response = await fetch('/api/check-text-analysis-23-24/', {
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
            
            // Показываем результаты для 23-24
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
            console.error('Ошибка проверки 23-24:', err);
            resultDiv.innerHTML = '<p class="error">Ошибка проверки</p>';
            resultDiv.style.display = 'block';
        }
    });
}

// --- Экспорт функций для использования в planning.js ---
window.TextAnalysisModule = {
    loadTextAnalysis,
    loadTextAnalysis23_24,
    setupTextAnalysisCheck,
    setupTextAnalysisCheck23_24
};