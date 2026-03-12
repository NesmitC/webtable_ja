// === ЛОКАЛЬНЫЕ ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ ДИАГНОСТИКИ ===
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

// Вспомогательная функция: получает mapping групп букв для задания 10
function getTask10LetterGroups() {
    const script = document.getElementById('task10-letter-groups');
    if (!script) return null;
    try {
        return JSON.parse(script.textContent);
    } catch (e) {
        console.warn("Не удалось распарсить task10-letter-groups");
        return null;
    }
}

// Вспомогательная функция для задания 11
function getTask11LetterGroups() {
    const script = document.getElementById('task11-letter-groups');
    if (!script) return null;
    try {
        return JSON.parse(script.textContent);
    } catch (e) {
        console.warn("Не удалось распарсить task11-letter-groups");
        return null;
    }
}

// Вспомогательная функция для задания 12
function getTask12LetterGroups() {
    const script = document.getElementById('task12-letter-groups');
    if (!script) {
        const container = document.querySelector('.block-answer, .article-practice');
        if (container) {
            const localScript = container.querySelector('#task12-letter-groups');
            if (localScript) {
                try {
                    return JSON.parse(localScript.textContent);
                } catch (e) {
                    console.warn("Не удалось распарсить локальный task12-letter-groups");
                }
            }
        }
        return null;
    }
    try {
        return JSON.parse(script.textContent);
    } catch (e) {
        console.warn("Не удалось распарсить task12-letter-groups");
        return null;
    }
}

// Вспомогательная функция для задания 13
function getTask13LetterGroups() {
    const script = document.getElementById('task13-letter-groups');
    if (!script) return null;
    try {
        return JSON.parse(script.textContent);
    } catch (e) {
        console.warn("Не удалось распарсить task13-letter-groups");
        return null;
    }
}

// Вспомогательная функция для задания 14
function getTask14LetterGroups() {
    const script = document.getElementById('task14-letter-groups');
    if (!script) return null;
    try {
        return JSON.parse(script.textContent);
    } catch (e) {
        console.warn("Не удалось распарсить task14-letter-groups");
        return null;
    }
}

// Вспомогательная функция для задания 15
function getTask15LetterGroups() {
    const script = document.getElementById('task15-letter-groups');
    if (!script) return null;
    try {
        return JSON.parse(script.textContent);
    } catch (e) {
        console.warn("Не удалось распарсить task15-letter-groups");
        return null;
    }
}

// ===========================================================================
// ФУНКЦИЯ ПОЛУЧЕНИЯ БУКВ ДЛЯ ОРФОГРАММЫ
// ===========================================================================
async function getLettersForOrthogram(orthId) {
    if (typeof orthId !== 'string') orthId = String(orthId);

    // === ЗАДАНИЕ 9 ===
    if (orthId.startsWith('9-')) {
        const index = parseInt(orthId.split('-')[1]) - 1;
        const groupIndex = Math.floor(index / 3);
        const groups = [
            ['о', 'а', 'е', 'и', 'я', 'у', 'ю'],
            ['о', 'а'],
            ['е', 'и', 'я'],
            ['ё', 'о'],
            ['и', 'ы']
        ];
        return groups[groupIndex] || groups[0];
    }

    // === ЗАДАНИЕ 10: маски вида *10_ORTHID-INDEX* ===
    if (orthId.startsWith('10_')) {
        try {
            const groupsScript = document.getElementById('task10-letter-groups');
            const lettersScript = document.getElementById('task10-subgroup-letters');
            
            if (groupsScript && lettersScript) {
                const groups = JSON.parse(groupsScript.textContent);
                const subgroupLetters = JSON.parse(lettersScript.textContent);
                
                const subgroupKey = groups[orthId];
                if (subgroupKey && subgroupLetters[subgroupKey]) {
                    return subgroupLetters[subgroupKey];
                }
            }
        } catch (e) {
            console.warn("Ошибка при получении подгруппы для задания 10:", e);
        }
        
        const parts = orthId.split('-')[0].split('_');
        const baseId = parts[1];
        const fallback = {
            "10": ["с", "з", "д", "т", "а", "о"],
            "11": ["з", "с"],
            "28": ["и", "ы"],
            "29": ["е", "и"],
            "6": ["ъ", "ь", "/"]
        };
        return fallback[baseId] || ['а','о','е','и','я'];
    }

    if (orthId.startsWith('11-')) {
        try {
            const groupsScript = document.getElementById('task11-letter-groups');
            const lettersScript = document.getElementById('task11-subgroup-letters');
            
            if (groupsScript && lettersScript) {
                const groups = JSON.parse(groupsScript.textContent);
                const subgroupLetters = JSON.parse(lettersScript.textContent);
                
                const subgroupKey = groups[orthId];
                if (subgroupKey && subgroupLetters[subgroupKey]) {
                    return subgroupLetters[subgroupKey];
                }
            }
        } catch (e) {
            console.warn("Ошибка получения подгруппы для задания 11:", e);
        }
        
        console.warn(`[11] Не найдена подгруппа для маски ${orthId}, использую полный набор`);
        return ['е', 'и', 'я', 'а', 'о', 'ё', 'ы', 'ч', 'щ', 'к', 'ск'];
    }

    // === ЗАДАНИЕ 12 ===
    if (orthId.startsWith('12-')) {
        const letterGroups = getTask12LetterGroups();
        if (letterGroups) {
            const groupKey = letterGroups[orthId];
            const subgroupLettersScript = document.getElementById('task12-subgroup-letters');
            if (subgroupLettersScript) {
                try {
                    const subgroupMap = JSON.parse(subgroupLettersScript.textContent);
                    if (subgroupMap[groupKey]) {
                        return subgroupMap[groupKey];
                    }
                } catch (e) {
                    console.warn("Не удалось распарсить task12-subgroup-letters");
                }
            }
        }
        return ['е', 'у', 'ю', 'и', 'а', 'я', 'ё', 'о', 'ы', 'ч', 'щ', 'к', 'ск'];
    }

    // === ЗАДАНИЕ 13 ===
    if (orthId.startsWith('13-')) {
        const letterGroups = getTask13LetterGroups();
        if (letterGroups) {
            const groupKey = letterGroups[orthId];
            const subgroupLettersScript = document.getElementById('task13-subgroup-letters');
            if (subgroupLettersScript) {
                try {
                    const subgroupMap = JSON.parse(subgroupLettersScript.textContent);
                    if (subgroupMap[groupKey]) {
                        return subgroupMap[groupKey];
                    }
                } catch (e) {
                    console.warn("Не удалось распарсить task13-subgroup-letters");
                }
            }
        }
        return ['|', '/'];
    }

    // === ЗАДАНИЕ 14 ===
    if (orthId.startsWith('14-')) {
        const letterGroups = getTask14LetterGroups();
        if (letterGroups) {
            const groupKey = letterGroups[orthId];
            const subgroupLettersScript = document.getElementById('task14-subgroup-letters');
            if (subgroupLettersScript) {
                try {
                    const subgroupMap = JSON.parse(subgroupLettersScript.textContent);
                    if (subgroupMap[groupKey]) {
                        return subgroupMap[groupKey];
                    }
                } catch (e) {
                    console.warn("Не удалось распарсить task14-subgroup-letters");
                }
            }
        }
        return ['|', '/', '-'];
    }

    // === ЗАДАНИЕ 15 ===
    if (orthId.startsWith('15-')) {
        const letterGroups = getTask15LetterGroups();
        if (letterGroups) {
            const groupKey = letterGroups[orthId];
            const subgroupLettersScript = document.getElementById('task15-subgroup-letters');
            if (subgroupLettersScript) {
                try {
                    const subgroupMap = JSON.parse(subgroupLettersScript.textContent);
                    if (subgroupMap[groupKey]) {
                        return subgroupMap[groupKey];
                    }
                } catch (e) {
                    console.warn("Не удалось распарсить task15-subgroup-letters");
                }
            }
        }
        return ['н', 'нн'];
    }

    // === ПУНКТОГРАММЫ 16–20 ===
    const PUNKTUM_TASKS = ['16', '17', '18', '19', '20'];
    if (PUNKTUM_TASKS.some(task => orthId.startsWith(task))) {
        return [',', 'х'];
    }

    // === ЗАДАНИЕ 21 ===
    if (orthId.startsWith('21-')) {
        
        const script = document.getElementById('task21-subgroup-letters');
        if (script) {
            try {
                const data = JSON.parse(script.textContent);
                if (data.punktum_21) {
                    return data.punktum_21;
                }
            } catch (e) {
                console.warn("Не удалось распарсить task21-subgroup-letters:", e);
            }
        }
        
        return ['5', '8', '9.1', '9.2', '10', '13', '16', '18', '19'];
    }

    // === Все остальные орфограммы ===
    let baseId = orthId.includes('-') ? orthId.split('-')[0] : orthId;
    try {
        const res = await fetch(`/api/orthogram/${baseId}/letters/`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        return Array.isArray(data.letters) ? data.letters : ['а','о','е','и','я'];
    } catch (err) {
        return ['а','о','е','и','я'];
    }
}

// ===========================================================================
// ОСНОВНАЯ ЛОГИКА ДИАГНОСТИКИ
// ===========================================================================
document.addEventListener('DOMContentLoaded', function () {
    const startBtn = document.getElementById('start-diagnostic-btn');
    if (!startBtn) return;
    
    const csrfToken = getCookie('csrftoken');
    if (!csrfToken) {
        console.error('CSRF токен не найден. Обновите страницу.');
        return;
    }
    
    startBtn.addEventListener('click', async () => {
        const contentDiv = document.getElementById('diagnostic-content');
        const resultSection = document.getElementById('result-section');
        const resultDetails = document.getElementById('result-details');
        
        startBtn.disabled = true;
        startBtn.textContent = 'Загрузка...';
        
        try {
            // 1. Загружаем диагностику
            const res = await fetch('/api/generate-starting-diagnostic/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                body: JSON.stringify({})
            });
            
            const data = await res.json();
            if (data.error) throw new Error(data.error);
            
            contentDiv.innerHTML = data.html;
            
            // 2. Ждем обновления DOM
            setTimeout(async () => {
                // === УНИВЕРСАЛЬНАЯ ОБРАБОТКА ВСЕХ ПРАКТИЧЕСКИХ СТРОК ===
                const practiceBlocks = contentDiv.querySelectorAll('[data-question-number]');

                for (const block of practiceBlocks) {
                    const practiceLines = block.querySelectorAll('.practice-line');
                    
                    for (const line of practiceLines) {
                        const originalText = line.textContent || line.innerText || '';
                        if (!originalText.trim()) continue;
                        
                        const regex = /\*([^*]+)\*/g;
                        let matches;
                        let result = originalText;
                        
                        while ((matches = regex.exec(originalText)) !== null) {
                            const fullMask = matches[0];
                            const orthId = matches[1];
                            
                            const letters = await getLettersForOrthogram(orthId);
                            
                            const liItems = letters.map(letter =>
                                `<li data-letter="${letter}">${letter}</li>`
                            ).join('');
                            
                            const smileyHtml = `
                                <span class="smiley-button" data-orth-id="${orthId}">
                                    <span class="smiley-icon">😊</span>
                                    <ul class="smiley-options">${liItems}</ul>
                                </span>
                            `;
                            
                            result = result.replace(fullMask, smileyHtml);
                        }
                        
                        line.innerHTML = result;
                    }
                }
                
                // === АКТИВАЦИЯ ИНТЕРАКТИВНЫХ СМАЙЛИКОВ ===
                document.querySelectorAll('.smiley-button').forEach(btn => {
                    const icon = btn.querySelector('.smiley-icon');
                    const options = btn.querySelector('.smiley-options');
                    
                    icon.addEventListener('click', (e) => {
                        e.stopPropagation();
                        document.querySelectorAll('.smiley-options').forEach(el => {
                            if (el !== options) el.style.display = 'none';
                        });
                        options.style.display = options.style.display === 'block' ? 'none' : 'block';
                    });
                    
                    options.querySelectorAll('li').forEach(li => {
                        li.addEventListener('click', (e) => {
                            e.stopPropagation();
                            const letter = li.dataset.letter;
                            icon.textContent = letter;
                            icon.classList.add('selected');
                            options.style.display = 'none';
                        });
                    });
                });
                
                document.addEventListener('click', () => {
                    document.querySelectorAll('.smiley-options').forEach(el => {
                        el.style.display = 'none';
                    });
                });
            }, 50);

            // === АКТИВАЦИЯ УНИКАЛЬНЫХ SELECT В ЗАДАНИЯХ 8 И 22 ===
            function setupUniqueSelectsForAll() {
                function setupUniqueSelects(containerSelector, selectClass) {
                    const container = document.querySelector(containerSelector);
                    if (!container) return;
                    
                    const selects = Array.from(container.querySelectorAll(selectClass));
                    
                    function updateSelects() {
                        const selectedValues = selects
                            .map(s => s.value)
                            .filter(v => v !== '-' && v !== '');
                        
                        selects.forEach(s => {
                            const currentValue = s.value;
                            
                            Array.from(s.options).forEach(option => {
                                const value = option.value;
                                if (value === '-') return;
                                
                                const isUsed = selectedValues.includes(value) && value !== currentValue;
                                option.disabled = isUsed;
                                
                                if (isUsed) {
                                    option.style.color = '#ccc';
                                    option.style.fontStyle = 'italic';
                                } else {
                                    option.style.color = '';
                                    option.style.fontStyle = '';
                                }
                            });
                        });
                    }
                    
                    selects.forEach(select => {
                        select.addEventListener('change', updateSelects);
                    });
                    
                    updateSelects();
                }
                
                setupUniqueSelects('[data-question-number="8"] .task-eight-exercise', '.task-eight-select');
                setupUniqueSelects('[data-question-number="22"] .task-twotwo-exercise', '.task-twotwo-select');
            }

            setTimeout(setupUniqueSelectsForAll, 100);

            setTimeout(() => {
                document.querySelectorAll('.check-task-eight, .check-task-twotwo').forEach(btn => btn.remove());
            }, 120);
            
            // 3. Добавляем кнопку проверки
            const checkBtn = document.createElement('button');
            checkBtn.className = 'check-task green';
            checkBtn.textContent = 'Проверить всю работу';
            checkBtn.style.cssText = 'margin-top: 30px; display: block; margin: 30px auto 0 auto;';
            contentDiv.appendChild(checkBtn);
            
            // 4. Обработчик проверки
            checkBtn.addEventListener('click', async () => {
                const answers = {};
                
                // === СБОР ОТВЕТОВ ===
                document.querySelectorAll('[data-question]').forEach(el => {
                    const q = el.dataset.question;
                    
                    if (el.type === 'checkbox') {
                        // Для чекбоксов (задания 1-3, 4, 23-26) собираем МАССИВ
                        if (el.checked) {
                            if (!answers[q]) answers[q] = [];
                            answers[q].push(el.value);
                        }
                    } else {
                        // Для текстовых полей и селектов — строка
                        answers[q] = (el.value || '').trim();
                    }
                });
                
                // 2. Смайлики (орфограммы)
                const smileyButtons = document.querySelectorAll('.smiley-button');
                
                smileyButtons.forEach(btn => {
                    const orthId = btn.dataset.orthId;
                    const icon = btn.querySelector('.smiley-icon');
                    let selectedLetter = icon ? icon.textContent : '😊';
                    
                    if (selectedLetter === ',') selectedLetter = '!';
                    else if (selectedLetter === 'х') selectedLetter = '?';
                    
                    // === НОРМАЛИЗАЦИЯ ДЛЯ ЗАДАНИЯ 13 ===
                    // Если это задание 13 и выбрана вертикальная черта, заменяем на обратный слеш
                    if (orthId && orthId.startsWith('13-') && selectedLetter === '|') {
                        selectedLetter = '\\';  // Заменяем | на \
                    }
                    
                    answers[orthId] = selectedLetter;
                });

                // Сбор ответов задания 8
                const task8Container = document.querySelector('.task-eight-exercise');
                if (task8Container) {
                    const task8Selects = task8Container.querySelectorAll('.task-eight-select');
                    task8Selects.forEach(select => {
                        const letter = select.dataset.errorLetter;
                        if (letter) {
                            answers[`8-${letter}`] = select.value;
                        }
                    });
                }

                // === СБОР ОТВЕТОВ ЗАДАНИЯ 22 ===
                const task22Container = document.querySelector('[data-question-number="22"] .task-twotwo-exercise');
                if (task22Container) {
                    const task22Selects = task22Container.querySelectorAll('.task-twotwo-select');
                    
                    task22Selects.forEach((select, index) => {
                        const letterFromData = select.dataset.errorLetter;
                        const letters = ['А', 'Б', 'В', 'Г', 'Д'];
                        const letter = letterFromData || (letters[index] ? letters[index] : null);
                        
                        if (letter) {
                            const key = `22-${letter}`;
                            const value = select.value;
                            answers[key] = value;
                        }
                    });
                }
                
                // Отправка на сервер
                const checkRes = await fetch('/api/check-starting-diagnostic/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                    body: JSON.stringify({ answers: answers })
                });
                
                const result = await checkRes.json();
                
                if (result.error) {
                    alert(`Ошибка: ${result.error}`);
                    return;
                }
                
                // ===== ПОДСВЕТКА РЕЗУЛЬТАТОВ =====

                // 1. Смайлики
                smileyButtons.forEach(btn => {
                    const orthId = btn.dataset.orthId;
                    const icon = btn.querySelector('.smiley-icon');
                    if (icon && result.results && result.results[orthId]) {
                        const isCorrect = result.results[orthId].is_correct;
                        icon.classList.remove('selected', 'correct', 'incorrect');
                        if (isCorrect) {
                            icon.classList.add('correct');
                        } else {
                            icon.classList.add('incorrect');
                        }
                    }
                });

                // 2. Текстовые поля и чекбоксы (1-3, 23-26)
                document.querySelectorAll('[data-question]').forEach(el => {
                    const q = el.dataset.question;
                    if (result.results && result.results[q]) {
                        const isCorrect = result.results[q].is_correct;
                        
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

                // === ПОДСВЕТКА РЕЗУЛЬТАТОВ ЗАДАНИЯ 4 ===
                if (result.results && result.results['4'] && result.results['4'].variant_results) {
                    const variantResults = result.results['4'].variant_results;
                    
                    // Сбрасываем ВСЕ стили для ВСЕХ чекбоксов и текста задания 4
                    document.querySelectorAll('[data-question-number="4"] input[data-question="4"]').forEach(checkbox => {
                        // Сбрасываем стили чекбокса
                        checkbox.style.border = '';
                        checkbox.style.boxShadow = '';
                        checkbox.style.outline = '';
                        checkbox.classList.remove('task-match-correct', 'task-match-incorrect');
                        
                        // Сбрасываем цвет текста (находим родительский label и span внутри)
                        const label = checkbox.closest('label');
                        if (label) {
                            const span = label.querySelector('span');
                            if (span) {
                                span.style.color = '';
                                span.style.fontWeight = '';
                            }
                        }
                    });
                    
                    // Теперь применяем подсветку для КАЖДОГО варианта
                    document.querySelectorAll('[data-question-number="4"] input[data-question="4"]').forEach((checkbox, index) => {
                        const optionId = checkbox.dataset.optionId || (index + 1).toString();
                        const resultKey = `4-${optionId}`;
                        const variantResult = variantResults[resultKey];
                        
                        if (!variantResult) return;
                        
                        // Находим родительский label и span с текстом
                        const label = checkbox.closest('label');
                        const span = label ? label.querySelector('span') : null;
                        
                        // 1. Цвет текста ЗАВИСИТ ОТ ПРАВИЛЬНОСТИ ВАРИАНТА (независимо от выбора)
                        if (span) {
                            if (variantResult.is_correct) {
                                // Правильный вариант - зелёный текст
                                span.style.color = '#28a745';
                                span.style.fontWeight = 'bold';
                            } else {
                                // Неправильный вариант - красный текст
                                span.style.color = '#dc3545';
                                span.style.fontWeight = 'bold';
                            }
                        }
                        
                        // 2. Обводка чекбокса ЗАВИСИТ ОТ ВЫБОРА ПОЛЬЗОВАТЕЛЯ
                        if (checkbox.checked) {
                            // Убираем стандартную обводку браузера
                            checkbox.style.outline = 'none';
                            
                            if (variantResult.is_correct) {
                                // Правильный выбранный - зелёная обводка
                                checkbox.style.border = '3px solid #28a745';
                                checkbox.style.boxShadow = '0 0 0 3px rgba(25, 135, 84, 0.5)';
                            } else {
                                // Неправильный выбранный - красная обводка
                                checkbox.style.border = '3px solid #dc3545';
                                checkbox.style.boxShadow = '0 0 0 3px rgba(220, 38, 38, 0.5)';
                            }
                        }
                        // Если чекбокс НЕ выбран - оставляем без подсветки обводки
                    });
                }

                // Задание 22 (select элементы)
                if (task22Container && result.results) {
                    const task22Selects = task22Container.querySelectorAll('.task-twotwo-select');
                    task22Selects.forEach((select, index) => {
                        const letters = ['А', 'Б', 'В', 'Г', 'Д'];
                        const letter = select.dataset.errorLetter || (letters[index] ? letters[index] : null);
                        
                        if (letter) {
                            const key = `22-${letter}`;
                            if (result.results[key]) {
                                const isCorrect = result.results[key].is_correct;
                                select.classList.remove('task-match-select-correct', 'task-match-select-incorrect');
                                
                                if (isCorrect) {
                                    select.classList.add('task-match-select-correct');
                                } else {
                                    select.classList.add('task-match-select-incorrect');
                                }
                            }
                        }
                    });
                }

                // 4. Задание 8 (select)
                const task8Selects = document.querySelectorAll('.task-eight-select');
                if (task8Selects.length > 0 && result.results) {
                    task8Selects.forEach(select => {
                        const letter = select.dataset.errorLetter;
                        if (letter) {
                            const key = `8-${letter}`;
                            if (result.results[key]) {
                                const isCorrect = result.results[key].is_correct;
                                select.classList.remove('task-match-select-correct', 'task-match-select-incorrect');
                                if (isCorrect) {
                                    select.classList.add('task-match-select-correct');
                                } else {
                                    select.classList.add('task-match-select-incorrect');
                                }
                            }
                        }
                    });
                }
                
                // Отображение результатов
                const essayInput = document.querySelector('input[data-question="27"]');
                let essayScore = 0;

                // Валидация балла за сочинение
                if (essayInput) {
                    let value = essayInput.value.trim();
                    
                    // Проверяем, что введено число
                    if (value === '') {
                        essayScore = 0;
                    } else {
                        // Преобразуем в целое число
                        let intValue = parseInt(value, 10);
                        
                        // Проверяем, что это действительно число и не NaN
                        if (isNaN(intValue)) {
                            essayScore = 0;
                            essayInput.value = ''; // Очищаем поле
                            alert('Пожалуйста, введите число от 0 до 22');
                        } else {
                            // Ограничиваем диапазоном 0-22
                            if (intValue < 0) {
                                essayScore = 0;
                                essayInput.value = 0;
                            } else if (intValue > 22) {  // ← ИСПРАВЛЕНО: было 27, стало 22
                                essayScore = 22;
                                essayInput.value = 22;
                                alert('Максимальный балл за сочинение - 22');
                            } else {
                                essayScore = intValue;
                            }
                        }
                    }
                }

                // Суммируем балл теста + сочинение
                const primaryScore = (result.total_score || 0) + essayScore;

                // Таблица преобразования первичных баллов во вторичные
                const conversionTable = {
                    0: 0, 1: 3, 2: 5, 3: 8, 4: 10, 5: 12, 6: 15, 7: 17, 8: 20, 9: 22,
                    10: 24, 11: 27, 12: 29, 13: 32, 14: 34, 15: 36, 16: 37, 17: 39, 18: 40, 19: 42,
                    20: 43, 21: 45, 22: 46, 23: 48, 24: 49, 25: 51, 26: 52, 27: 54, 28: 55, 29: 57,
                    30: 58, 31: 60, 32: 61, 33: 63, 34: 64, 35: 66, 36: 67, 37: 69, 38: 70, 39: 72,
                    40: 73, 41: 75, 42: 78, 43: 81, 44: 83, 45: 86, 46: 89, 47: 91, 48: 94, 49: 97,
                    50: 100
                };

                // Получаем вторичный балл
                let secondaryScore = conversionTable[primaryScore];
                if (secondaryScore === undefined) {
                    // Для баллов больше 50
                    secondaryScore = Math.min(100 + Math.floor((primaryScore - 50) * 2), 100);
                }

                // Формируем заголовок результатов
                let detailsHtml = `<h4>БАЛЛОВ: ${primaryScore} (первичных) - ${secondaryScore} (вторичных)</h4><p>Максимум: 50 (100)</p>`;

                if (result.results && result.results['8']) {
                    detailsHtml += `<p><strong>Задание 8:</strong> ${result.results['8'].correct_count || 0}/5 правильных = <strong>${result.results['8'].score || 0}/2</strong> баллов</p>`;
                }

                if (result.results && result.results['22']) {
                    detailsHtml += `<p><strong>Задание 22:</strong> ${result.results['22'].correct_count || 0}/5 правильных = <strong>${result.results['22'].score || 0}/2</strong> баллов</p>`;
                }

                // === ВИЗУАЛИЗАЦИЯ РЕЗУЛЬТАТОВ ПО ЗАДАНИЯМ ===
                let tasksHtml = '<div style="margin: 20px 0; padding: 15px; background: #f8f9fa; border-radius: 8px;">';

                for (let i = 1; i <= 26; i++) {
                    const q = String(i);
                    
                    // === ЗАДАНИЯ 8 и 22 (2 балла) ===
                    if (i === 8 || i === 22) {
                        const taskResult = result.results[q];
                        if (taskResult && taskResult.score !== undefined) {
                            const score = taskResult.score; // 0, 1, или 2
                            // Формируем символы: 2 балла = "++", 1 балл = "+-", 0 баллов = "--"
                            const symbols = score === 2 ? '++' : score === 1 ? '+-' : '--';
                            const colors = score === 2 ? ['green', 'green'] : score === 1 ? ['green', 'red'] : ['red', 'red'];
                            
                            tasksHtml += `<span style="display:inline-block; margin: 2px;">${i}</span>`;
                            for (let j = 0; j < 2; j++) {
                                tasksHtml += `<span style="display:inline-block; width:20px; height:20px; line-height:20px; text-align:center; background:${colors[j]}; color:white; border-radius:3px; margin:0 1px; font-size:12px;">${symbols[j]}</span>`;
                            }
                            tasksHtml += ' ';
                        }
                    }
                    // === ОСТАЛЬНЫЕ ЗАДАНИЯ (1 балл) ===
                    else {
                        const taskResult = result.results[q];
                        if (taskResult && taskResult.is_correct !== undefined) {
                            const isCorrect = taskResult.is_correct;
                            const symbol = isCorrect ? '+' : '-';
                            const color = isCorrect ? 'green' : 'red';
                            
                            tasksHtml += `<span style="display:inline-block; margin: 2px;">${i}</span>`;
                            tasksHtml += `<span style="display:inline-block; width:20px; height:20px; line-height:20px; text-align:center; background:${color}; color:white; border-radius:3px; margin:0 1px; font-size:12px;">${symbol}</span>`;
                            tasksHtml += ' ';
                        }
                    }
                }

                tasksHtml += '</div>';
                detailsHtml = tasksHtml + detailsHtml;

                detailsHtml += `<p><strong>Рекомендации NEUROSTAT:</strong> Анализ слабых зон доступен после прохождения всех диагностик.</p>`;

                resultDetails.innerHTML = detailsHtml;
                
                resultSection.style.display = 'block';
                window.scrollTo({ top: resultSection.offsetTop, behavior: 'smooth' });
            });
            
        } catch (err) {
            console.error('Ошибка загрузки диагностики:', err);
            document.getElementById('diagnostic-content').innerHTML =
                `<p class="error">Не удалось загрузить диагностику: ${err.message}</p>`;
        } finally {
            startBtn.disabled = false;
            startBtn.textContent = 'Начать диагностику';
        }
    });

});