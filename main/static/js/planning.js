// ===========================================================================
// ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
// ===========================================================================
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

// ===========================================================================
// ФУНКЦИИ ОБРАБОТКИ СМАЙЛИКОВ
// ===========================================================================
// для задания 9
function isAlphabeticalTask(orthogramIds) {
    const ids = orthogramIds.split(',');
    // Задание 9 считается алфавитным, если содержит ТОЛЬКО 1_11 и/или 2_11
    const hasOnlyAlphabetical = ids.every(id => 
        id.trim() === '1_11' || id.trim() === '2_11'
    );
    const hasMainOrthograms = ids.some(id => 
        ['12', '13', '14', '15', '24', '26', '27', '271'].includes(id.trim())
    );
    return hasOnlyAlphabetical && !hasMainOrthograms;
}

// Вспомогательная функция: получает mapping групп букв для задания 10
function getTask10LetterGroups() {
    const script = document.getElementById('task10-letter-groups');
    if (!script) return null;
    try {
        return JSON.parse(script.textContent);
    } catch (e) {
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
        return null;
    }
}

// Вспомогательная функция для задания 12
function getTask12LetterGroups() {
    const script = document.getElementById('task12-letter-groups');
    if (!script) return null;
    try {
        return JSON.parse(script.textContent);
    } catch (e) {
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
        return null;
    }
}

// ===========================================================================
// ФУНКЦИЯ ПОЛУЧЕНИЯ БУКВ ДЛЯ ОРФОГРАММЫ
// ===========================================================================

// Оптимизированная функция получения букв
const lettersCache = new Map();
const quickLettersMap = {
    '1': ['а', 'о', 'е', 'и', 'я', 'у', 'ю'],
    '2': ['а', 'о', 'е', 'и', 'я', 'у', 'ю'],
    '1_5': ['а', 'о', 'е', 'и', 'я', 'у', 'ю'],
    '2_5': ['а', 'о', 'е', 'и', 'я', 'у', 'ю'],
    '1_6': ['а', 'о', 'е', 'и', 'я', 'у', 'ю'],
    '2_6': ['а', 'о', 'е', 'и', 'я', 'у', 'ю'],
    '1_7': ['а', 'о', 'е', 'и', 'я', 'у', 'ю'],
    '2_7': ['а', 'о', 'е', 'и', 'я', 'у', 'ю'],
    '1_8': ['а', 'о', 'е', 'и', 'я', 'у', 'ю'],
    '2_8': ['а', 'о', 'е', 'и', 'я', 'у', 'ю'],
    '1_11': ['а', 'о', 'е', 'и', 'я', 'у', 'ю'],
    '2_11': ['а', 'о', 'е', 'и', 'я', 'у', 'ю'],
};

async function getLettersForOrthogram(orthId) {
    if (typeof orthId !== 'string') orthId = String(orthId);
    
    // Кэш
    if (lettersCache.has(orthId)) return lettersCache.get(orthId);
    
    // Задание 10 - для ЕГЭ используем подгруппы из task10_letter_groups
    if (orthId.startsWith('10_')) {
        try {
            const groupsElem = document.getElementById('task10-letter-groups');
            const lettersElem = document.getElementById('task10-subgroup-letters');
            
            if (groupsElem && lettersElem) {
                const groups = JSON.parse(groupsElem.textContent);
                const subgroupLetters = JSON.parse(lettersElem.textContent);
                const subgroupKey = groups[orthId];
                
                if (subgroupKey && subgroupLetters[subgroupKey]) {
                    lettersCache.set(orthId, subgroupLetters[subgroupKey]);
                    return subgroupLetters[subgroupKey];
                }
            }
        } catch (e) {
            console.warn("Ошибка при получении подгруппы:", e);
        }
        
        // Fallback для ЕГЭ - тоже по подгруппам!
        const baseOrthId = orthId.split('-')[0].split('_')[1];
        const fallback = {
            "10": ["с", "з", "д", "т", "а", "о"],  // для 10 - все буквы
            "11": ["з", "с"],                      // для 11 - з/с
            "28": ["и", "ы"],                     // для 28 - и/ы
            "29": ["е", "и"],                     // для 29 - е/и
            "6": ["ъ", "ь", "/"]                  // для 6 - ъ/ь/
        };
        const letters = fallback[baseOrthId] || ['а','о','е','и','я'];
        lettersCache.set(orthId, letters);
        return letters;
    }

    // === ЗАДАНИЕ 9: алфавитное упражнение ===
    // Если ID содержит буквы (не только цифры) - это алфавитное задание
    if (!/^\d+(-\d+)?$/.test(orthId)) {
        const letters = ['а', 'о', 'е', 'и', 'я', 'у', 'ю'];
        lettersCache.set(orthId, letters);
        return letters;
    }

    // Задание 9
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
        const letters = groups[groupIndex] || groups[0];
        lettersCache.set(orthId, letters);
        return letters;
    }

    // === Задание 1 или 2 (обычные ID) ===
    if (orthId === '1' || orthId === '2') {
        const letters = ['а', 'о', 'е', 'и', 'я', 'у', 'ю'];
        lettersCache.set(orthId, letters);
        return letters;
    }

    // === ЗАДАНИЕ 14 ===
    if (orthId.startsWith('14-')) {
        return ['|', '/', '-'];
    }
    // === ЗАДАНИЕ 15 ===
    if (orthId.startsWith('15-')) {
        return ['н', 'нн'];
    }

    // Орфограмма 35 и 37 - буквы ё/о/е (для 6 класса)
    if (orthId === '35' || orthId.startsWith('35') || orthId === '37' || orthId.startsWith('37')) {
        const letters = ['ё', 'о', 'е'];
        lettersCache.set(orthId, letters);
        return letters;
    }

    // === ПУНКТОГРАММЫ 16–20 ===
    const PUNKTUM_TASKS = ['16', '17', '18', '19', '20'];
    if (PUNKTUM_TASKS.some(task => orthId.startsWith(task))) {
        const letters = [',', 'х'];
        lettersCache.set(orthId, letters);
        return letters;
    }

    // === ЗАДАНИЕ 21: ЦИФРЫ ПУНКТОГРАММ ===
    // if (orthId.startsWith('21')) {
    //     const script = document.getElementById('task21-subgroup-letters');
    //     if (script) {
    //         try {
    //             const data = JSON.parse(script.textContent);
    //             if (data.punktum_21) {
    //                 lettersCache.set(orthId, data.punktum_21);
    //                 return data.punktum_21;
    //             }
    //         } catch (e) {
    //             // Пропускаем ошибку
    //         }
    //     }
        
    //     // Fallback для каждого типа задания 21
    //     let letters;
    //     if (orthId.includes('2100') || document.querySelector('[data-punktogram="2100"]')) {
    //         letters = ['5', '8', '8.1', '9.2', '10', '13', '16', '18'];
    //     } else if (orthId.includes('2101') || document.querySelector('[data-punktogram="2101"]')) {
    //         letters = ['5', '9.1', '19'];
    //     } else if (orthId.includes('2102') || document.querySelector('[data-punktogram="2102"]')) {
    //         letters = ['2', '4.0', '4.1', '4.2', '5', '6', '7', '11', '12', '13', '14', '15', '16', '17'];
    //     } else {
    //         letters = ['5', '8', '8.1', '9.2', '10', '13', '16', '18'];
    //     }
        
    //     lettersCache.set(orthId, letters);
    //     return letters;
    // }
    
    // === ЗАДАНИЕ 21: ПУНКТОГРАММЫ ЕГЭ (ТОЛЬКО С ДЕФИСОМ!) ===
    if (orthId.startsWith('21-')) {
        
        // Пытаемся получить данные из скрипта в шаблоне
        const script = document.getElementById('task21-subgroup-letters');
        if (script) {
            console.log('✅ Найден script#task21-subgroup-letters');
            try {
                const data = JSON.parse(script.textContent);
                console.log('📦 Распарсенные данные:', data);
                
                if (data.punktum_21) {
                    console.log('🎯 Цифры для задания 21:', data.punktum_21);
                    lettersCache.set(orthId, data.punktum_21);
                    return data.punktum_21;
                } else {
                    console.warn('⚠️ punktum_21 не найден в данных');
                }
            } catch (e) {
                console.error('❌ Ошибка парсинга task21-subgroup-letters:', e);
            }
        } else {
            console.warn('⚠️ script#task21-subgroup-letters НЕ НАЙДЕН!');
        }
        
        // Fallback: определяем тип задания 21 по orthId или по наличию кнопки
        let letters;
        if (orthId.includes('2100') || document.querySelector('[data-punktogram="2100"]')) {
            letters = ['5', '8', '8.1', '9.2', '10', '13', '16', '18'];
        } else if (orthId.includes('2101') || document.querySelector('[data-punktogram="2101"]')) {
            letters = ['5', '9.1', '19'];
        } else if (orthId.includes('2102') || document.querySelector('[data-punktogram="2102"]')) {
            letters = ['2', '4.0', '4.1', '4.2', '5', '6', '7', '11', '12', '13', '14', '15', '16', '17'];
        } else {
            letters = ['5', '8', '8.1', '9.2', '10', '13', '16', '18'];
        }
        
        console.log('🔄 Используем fallback для задания 21:', letters);
        lettersCache.set(orthId, letters);
        return letters;
    }

    // === ОРФОГРАММА 21: СЛИТНО/РАЗДЕЛЬНО (ТОЧНО '21' - 5 класс) ===
    if (orthId === '21') {
        const letters = ['|', '/'];
        lettersCache.set(orthId, letters);
        return letters;
    }

    // Все остальные
    const baseId = orthId.includes('-') ? orthId.split('-')[0] : orthId;
    
    try {
        const res = await fetch(`/api/orthogram/${baseId}/letters/`);
        if (res.ok) {
            const data = await res.json();
            const letters = Array.isArray(data.letters) ? data.letters : ['а','о','е','и','я'];
            lettersCache.set(orthId, letters);
            return letters;
        }
    } catch (err) {
        // Пропускаем ошибку
    }
    
    const letters = ['а','о','е','и','я'];
    lettersCache.set(orthId, letters);
    return letters;
}


async function processLineWithMasks(lineText) {
    // АБСОЛЮТНАЯ ЗАЩИТА - если уже обработано, не трогаем
    if (lineText.includes('smiley-button') || lineText.includes('😊')) {
        return lineText;
    }
    
    if (!lineText.includes('*')) {
        return lineText;
    }
    
    // Находим ВСЕ маски в исходном тексте
    const masks = [];
    let match;
    const regex = /\*([^*]+)\*/g;
    
    while ((match = regex.exec(lineText)) !== null) {
        masks.push({
            orthId: match[1],
            index: match.index,
            length: match[0].length
        });
    }
    
    if (masks.length === 0) return lineText;
    
    // Кэш для часто используемых орфограмм
    const lettersMap = {
        '1': ['а', 'о', 'е', 'и', 'я', 'у', 'ю'],
        '2': ['а', 'о', 'е', 'и', 'я', 'у', 'ю'],
        '6': ['ъ', 'ь', '/'],
    };
    
    // Загружаем буквы только для новых орфограмм
    const uniqueIds = [...new Set(masks.map(m => m.orthId))].filter(id => !lettersMap[id]);
    
    if (uniqueIds.length > 0) {
        const promises = uniqueIds.map(id => 
            getLettersForOrthogram(id).then(letters => {
                lettersMap[id] = (letters && letters.length) ? letters : ['а','о','е','и','я'];
            }).catch(() => {
                lettersMap[id] = ['а','о','е','и','я'];
            })
        );
        await Promise.all(promises);
    }
    
    // ФОРМИРУЕМ РЕЗУЛЬТАТ
    let result = '';
    let lastIndex = 0;
    
    for (const mask of masks) {
        const orthId = mask.orthId;
        const matchStart = mask.index;
        const matchEnd = mask.index + mask.length;
        
        // Текст ДО текущей маски
        result += lineText.slice(lastIndex, matchStart);
        
        // Получаем буквы для этой орфограммы
        let letters = lettersMap[orthId];
        
        // === СПЕЦИАЛЬНАЯ ОБРАБОТКА ДЛЯ ОРФОГРАММ 10/11/28/29/6 ===
        if (orthId.startsWith('10_')) {
            try {
                const groupsElem = document.getElementById('task10-letter-groups');
                const lettersElem = document.getElementById('task10-subgroup-letters');
                
                if (groupsElem && lettersElem) {
                    const groups = JSON.parse(groupsElem.textContent);
                    const subgroupLetters = JSON.parse(lettersElem.textContent);
                    
                    const subgroupKey = groups[orthId];
                    
                    if (subgroupKey && subgroupLetters[subgroupKey]) {
                        letters = subgroupLetters[subgroupKey];
                    } else {
                        // Fallback для разных орфограмм
                        const baseOrthId = orthId.split('-')[0].split('_')[1];
                        const fallback = {
                            "10": ["с", "з", "д", "т", "а", "о"],
                            "11": ["з", "с"],
                            "28": ["и", "ы"],
                            "29": ["е", "и"],
                            "6": ["ъ", "ь", "/"]
                        };
                        letters = fallback[baseOrthId] || ['а','о','е','и','я'];
                    }
                }
            } catch (e) {
                
                // Fallback при ошибке
                const baseOrthId = orthId.split('-')[0].split('_')[1];
                const fallback = {
                    "10": ["с", "з", "д", "т", "а", "о"],
                    "11": ["з", "с"],
                    "28": ["и", "ы"],
                    "29": ["е", "и"],
                    "6": ["ъ", "ь", "/"]
                };
                letters = fallback[baseOrthId] || ['а','о','е','и','я'];
            }
        }
        
        // Финальный fallback
        if (!letters || !Array.isArray(letters) || letters.length === 0) {
            letters = ['а', 'о', 'е', 'и', 'я'];
        }

        // === ПУНКТОГРАММЫ 16–20 ===
        const PUNKTUM_TASKS = ['16', '17', '18', '19', '20'];
        if (PUNKTUM_TASKS.some(task => orthId.startsWith(task))) {
            letters = [',', 'х'];
        }
        
        // Создаем выпадающий список
        const liItems = letters.map(letter => 
            `<li data-letter="${letter}">${letter}</li>`
        ).join('');
        
        // ЗАМЕНЯЕМ маску на смайлик
        result += `<span class="smiley-button" data-orth-id="${orthId}">
            <span class="smiley-icon">😊</span>
            <ul class="smiley-options">${liItems}</ul>
        </span>&nbsp;`;
        
        lastIndex = matchEnd;
    }
    
    // Остаток текста ПОСЛЕ последней маски
    result += lineText.slice(lastIndex);
    
    return result;
}


async function processPracticeContainer(container) {
    // === ВАЛИДАЦИЯ ===
    if (!container) {
        return false;
    }
    
    // === ЗАЩИТА ОТ ПОВТОРНОЙ ОБРАБОТКИ ===
    if (container.dataset.processing === 'true') {
        return false;
    }
    
    // Помечаем как обрабатываемый
    container.dataset.processing = 'true';
    
    try {
        // === ПОЛУЧАЕМ СТРОКИ ===
        const lines = container.querySelectorAll('.practice-line');
        const linesArray = Array.from(lines);
        
        // === ПРОВЕРКА: есть ли что обрабатывать? ===
        if (linesArray.length === 0) {
            container.dataset.processing = 'false';
            return false;
        }
        
        // === ФИЛЬТР: только необработанные строки ===
        const linesToProcess = linesArray.filter(line => 
            !line.querySelector('.smiley-button') && 
            !line.hasAttribute('data-processed')
        );
        
        if (linesToProcess.length === 0) {
            container.dataset.processing = 'false';
            return true;
        }
        
        // === ОБРАБАТЫВАЕМ ПАРАЛЛЕЛЬНО ===
        const promises = linesToProcess.map(async (line) => {
            const originalText = line.textContent?.trim() || '';
            
            if (!originalText) {
                line.setAttribute('data-processed', 'empty');
                return;
            }
            
            try {
                const html = await processLineWithMasks(originalText);
                line.innerHTML = html;
                line.setAttribute('data-processed', 'true');
            } catch (err) {
                console.error('❌ Ошибка обработки строки:', err, 'Текст:', originalText);
                line.textContent = originalText;
                line.setAttribute('data-processed', 'error');
            }
        });
        
        // Ждём завершения всех обработок
        await Promise.all(promises);
        return true;
        
    } catch (err) {
        console.error('❌ Критическая ошибка в processPracticeContainer:', err);
        return false;
        
    } finally {
        // === ВСЕГДА снимаем флаг (даже при ошибке!) ===
        container.dataset.processing = 'false';
    }
}



function setupCheckAnswers(container = document) {
    container.querySelectorAll('.check-answers').forEach(button => {
        if (button._clickHandler) {
            button.removeEventListener('click', button._clickHandler);
        }
        button._clickHandler = function () {
            const article = button.closest('.article-practice');
            const smileyButtons = article ? Array.from(article.querySelectorAll('.smiley-button')) : [];
            if (smileyButtons.length === 0) return;
            const userAnswers = [];
            let hasSelection = false;
            smileyButtons.forEach(btn => {
                const orthId = btn.dataset.orthId;
                const icon = btn.querySelector('.smiley-icon');
                let selectedLetter = icon ? icon.textContent : '😊';

                // Нормализация для пунктограмм
                if (selectedLetter === ',') selectedLetter = '!';
                else if (selectedLetter === 'х') selectedLetter = '?';
                // === ИСПРАВЛЕНИЕ: преобразуем | в \ для орфограмм 32, 36 и других с раздельным написанием ===
                if (selectedLetter === '|') {
                    selectedLetter = '\\';  // Заменяем вертикальную черту на обратный слеш
                }
                if (selectedLetter !== '😊') hasSelection = true;
                userAnswers.push(selectedLetter);
            });
            if (!hasSelection) {
                alert("Сначала выбери хотя бы одну букву!");
                return;
            }
            const csrfToken = getCookie('csrftoken');
            if (!csrfToken) {
                alert('Сессия истекла. Обновите страницу.');
                return;
            }
            fetch('/api/check-exercise/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                body: JSON.stringify({ user_words: userAnswers })
            })
            .then(r => r.ok ? r.json() : r.text().then(text => { throw new Error(`HTTP ${r.status}: ${text}`); }))
            .then(results => {
                if (!Array.isArray(results)) throw new Error('Некорректный ответ');
                const icons = article.querySelectorAll('.smiley-icon');
                icons.forEach((icon, i) => {
                    icon.classList.remove('selected', 'correct', 'incorrect');
                    if (i < results.length) {
                        icon.classList.add(results[i] ? 'correct' : 'incorrect');
                    }
                });
            })
            .catch(err => {
                console.error('❌ Ошибка проверки:', err);
                alert('Ошибка при проверке.');
            });
        };
        button.addEventListener('click', button._clickHandler);
    });
}


// === ФУНКЦИЯ ПРОВЕРКИ ЗАДАНИЯ 5 (ПАРОНИМЫ) ===
function setupPaponimCheck() {
    const container = document.querySelector('.task-paponim-exercise');
    if (!container) return;
    const btn = container.querySelector('.check-task-paponim');
    const input = container.querySelector('.paponim-input');
    const resultDiv = container.querySelector('.task-paponim-result');
    if (!btn || !input || !resultDiv) return;
    btn.onclick = async function () {
        const userWord = input.value.trim();
        if (!userWord) {
            alert('Введите слово!');
            return;
        }
        const csrf = getCookie('csrftoken');
        try {
            const res = await fetch('/api/check-task-paponim-test/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
                body: JSON.stringify({ answer: userWord })
            });
            const result = await res.json();
            resultDiv.style.display = 'block';
            if (result.is_correct) {
                resultDiv.innerHTML = `<span style="color:green;">✅ Верно! Балл: ${result.score}</span>`;
            } else {
                resultDiv.innerHTML = `<span style="color:red;">❌ Неверно. Правильный ответ: <strong>${result.correct}</strong></span>`;
            }
        } catch (err) {
            console.error('Ошибка проверки задания 5:', err);
            resultDiv.style.display = 'block';
            resultDiv.innerHTML = '<span style="color:red;">Ошибка при проверке.</span>';
        }
    };
}

// === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ ОРФОЭПИИ ===
async function loadOrthoepyTest() {
    const answerSection = document.querySelector('.block-answer');
    if (!answerSection) return;
    answerSection.innerHTML = '<p>Загрузка теста по орфоэпии...</p>';
    try {
        const csrf = getCookie('csrftoken');
        if (!csrf) {
            answerSection.innerHTML = '<p class="error">Сессия истекла.</p>';
            return;
        }
        const res = await fetch('/api/generate-orthoepy-test/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrf
            },
            body: JSON.stringify({})
        });
        if (!res.ok) {
            throw new Error(`HTTP error! status: ${res.status}`);
        }
        const data = await res.json();
        if (data.html) {
            answerSection.innerHTML = data.html;
            setupOrthoepyListeners();
        } else if (data.error) {
            answerSection.innerHTML = `<p class="error">${data.error}</p>`;
        } else {
            answerSection.innerHTML = '<p class="error">Неизвестная ошибка при загрузке теста.</p>';
        }
    } catch (e) {
        console.error('Ошибка загрузки теста орфоэпии:', e);
        answerSection.innerHTML = '<p class="error">Не удалось загрузить тест. Попробуйте обновить страницу.</p>';
    }
}

function setupOrthoepyListeners() {
    const btn = document.querySelector('.check-orthoepy-test');
    if (btn) {
        btn.onclick = checkOrthoepyTest;
    }
}

async function checkOrthoepyTest() {
    const container = document.querySelector('.orthoepy-test-exercise');
    if (!container) return;
    const selected = [...container.querySelectorAll('.orthoepy-checkbox:checked')]
        .map(el => el.value);
    if (!selected.length) {
        alert('Выберите хотя бы один вариант.');
        return;
    }
    const btn = document.querySelector('.check-orthoepy-test');
    if (btn) {
        btn.disabled = true;
        btn.textContent = 'Проверяем...';
    }
    try {
        const csrf = getCookie('csrftoken');
        const res = await fetch('/api/check-orthoepy-test/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrf
            },
            body: JSON.stringify({ selected })
        });
        if (!res.ok) {
            throw new Error(`HTTP error! status: ${res.status}`);
        }
        const result = await res.json();
        displayOrthoepyResults(result);
    } catch (e) {
        alert('Ошибка при проверке: ' + e.message);
    } finally {
        const btn = document.querySelector('.check-orthoepy-test');
        if (btn) {
            btn.disabled = false;
            btn.textContent = 'Проверить';
        }
    }
}

function displayOrthoepyResults(results) {
    const resultDiv = document.querySelector('.orthoepy-result');
    if (!resultDiv) return;
    Object.values(results.results || {}).forEach(item => {
        const optionDiv = document.querySelector(`[data-variant="${item.variant}"]`);
        if (optionDiv) {
            optionDiv.classList.remove('orthoepy-correct', 'orthoepy-incorrect');
            if (item.is_correct_variant) {
                optionDiv.classList.add('orthoepy-correct');
            } else {
                optionDiv.classList.add('orthoepy-incorrect');
            }
        }
    });
    resultDiv.innerHTML = `<p><strong>Балл:</strong> ${results.summary?.user_score || 0}</p>`;
    resultDiv.style.display = 'block';
    resultDiv.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// === ФУНКЦИЯ ПРОВЕРКИ ЗАДАНИЯ 6 ===
function setupWordOkCheck() {
    const container = document.querySelector('.task-wordok-exercise');
    if (!container) return;
    const btn = container.querySelector('.check-task-wordok');
    const input = container.querySelector('.wordok-input');
    const resultDiv = container.querySelector('.task-wordok-result');
    if (!btn || !input || !resultDiv) return;
    btn.onclick = async function () {
        const userWord = input.value.trim().toLowerCase();
        if (!userWord) {
            alert('Введите слово!');
            return;
        }
        const csrf = getCookie('csrftoken');
        try {
            const res = await fetch('/api/check-task-wordok-test/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
                body: JSON.stringify({ answer: userWord })
            });
            const result = await res.json();
            resultDiv.style.display = 'block';
            if (result.is_correct) {
                resultDiv.innerHTML = `<span style="color:green;">✅ Верно! Балл: ${result.score}</span>`;
            } else {
                resultDiv.innerHTML = `<span style="color:red;">❌ Неверно. Правильный ответ: <strong>${result.correct}</strong></span>`;
            }
        } catch (err) {
            console.error('Ошибка проверки задания 6:', err);
            resultDiv.style.display = 'block';
            resultDiv.innerHTML = '<span style="color:red;">Ошибка при проверке.</span>';
        }
    };
}

// ===========================================================================
// ГЛОБАЛЬНЫЙ ДЕЛЕГИРОВАННЫЙ ОБРАБОТЧИК
// ===========================================================================
document.addEventListener('click', async (e) => {

// --- Орфограммы и пунктограммы ---
const button = e.target.closest('[data-orthogram], [data-punktogram]');
if (!button) return;

const orthogramIds = button.dataset.orthogram;
const punktogramId = button.dataset.punktogram;

const answerSection = document.querySelector('.block-answer');
if (!answerSection) {
    console.error('❌ Не найден блок .block-answer');
    return;
}
answerSection.innerHTML = '<p>Загрузка...</p>';

// === ЗАДАНИЕ 4: Орфоэпия ===
if (orthogramIds === '4000') {
    if (window.OrthoepyModule && typeof window.OrthoepyModule.loadOrthoepyTest === 'function') {
        await OrthoepyModule.loadOrthoepyTest();
    } else {
        await loadOrthoepyTest();
    }
    return;
}

// === ЗАДАНИЕ 5: Паронимы ===
if (orthogramIds === '5000') {
    answerSection.innerHTML = '<p>Загрузка задания 5...</p>';
    const csrf = getCookie('csrftoken');
    try {
        const res = await fetch('/api/generate-task-paponim-test/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
            body: JSON.stringify({})
        });
        const data = await res.json();
        if (data.html) {
            answerSection.innerHTML = data.html;
            setupPaponimCheck();
        } else {
            answerSection.innerHTML = `<p class="error">${data.error || 'Ошибка загрузки'}</p>`;
        }
    } catch (err) {
        console.error('Ошибка загрузки задания 5:', err);
        answerSection.innerHTML = `<p class="error">Не удалось загрузить задание 5.</p>`;
    }
    return;
}

// === ЗАДАНИЕ 6: Лексические нормы ===
if (orthogramIds === '6000') {
    answerSection.innerHTML = '<p>Загрузка задания 6...</p>';
    const csrf = getCookie('csrftoken');
    try {
        const res = await fetch('/api/generate-task-wordok-test/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
            body: JSON.stringify({})
        });
        const data = await res.json();
        if (data.html) {
            answerSection.innerHTML = data.html;
            setupWordOkCheck();
        } else {
            answerSection.innerHTML = `<p class="error">${data.error || 'Ошибка загрузки'}</p>`;
        }
    } catch (err) {
        console.error('Ошибка загрузки задания 6:', err);
        answerSection.innerHTML = `<p class="error">Не удалось загрузить задание 6.</p>`;
    }
    return;
}

// === Текстовый анализ: группы заданий ===
const textAnalysisGroups = {
    '1_3': 'loadTextAnalysis',
    '23_24': 'loadTextAnalysis23_24',
    '23_26': 'loadTextAnalysis23_26',
};
if (orthogramIds in textAnalysisGroups) {
    const methodName = textAnalysisGroups[orthogramIds];
    if (typeof TextAnalysisModule?.[methodName] === 'function') {
        await TextAnalysisModule[methodName]();
        return;
    }
    answerSection.innerHTML = '<p class="error">Модуль анализа не загружен</p>';
    return;
}

    // === ОЧИСТКА АЛФАВИТНОГО БЛОКА ===
    const alphabeticalSection = document.querySelector('.block-answer-still-content');
    if (alphabeticalSection) {
        alphabeticalSection.innerHTML = '';
    }

    // === СПЕЦИАЛЬНАЯ ОБРАБОТКА ЗАДАНИЯ 9 ===
    // Нормализуем строку: убираем пробелы
    const normalizedOrthogramIds = (orthogramIds || '').replace(/\s+/g, '');
    const TASK9_IDS = '1_11,2_11,12,13,14,15,24,26,27,271';

    if (normalizedOrthogramIds === TASK9_IDS) {
        e.preventDefault();
        answerSection.innerHTML = '<p>Загрузка задания 9...</p>';
        
        fetch('/api/generate-task9-exercise/', {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json', 
                'X-CSRFToken': getCookie('csrftoken') 
            },
            body: JSON.stringify({})
        })
        .then(response => {
            if (!response.ok) throw new Error('Ошибка загрузки');
            return response.json();
        })
        .then(data => {
            if (data.error) {
                answerSection.innerHTML = `<p class="error">${data.error}</p>`;
            } else {
                answerSection.innerHTML = data.html;
                
                // Обработка смайликов
                const container = answerSection.querySelector('.article-practice') || answerSection;
                setTimeout(() => processPracticeContainer(container), 0);
                setupCheckAnswers(container);
            }
        })
        .catch(err => {
            console.error('❌ Ошибка задания 9:', err);
            answerSection.innerHTML = '<p class="error">Не удалось загрузить задание 9</p>';
        });
        return;
    }

    // === Остальное: орфограммы и пунктограммы ===
    const csrfToken = getCookie('csrftoken');
    if (!csrfToken) {
        answerSection.innerHTML = '<p class="error">Сессия истекла. Обновите страницу.</p>';
        return;
    }

    try {
        let url, payload;
        
        // Задание 21 — случайный подтип → используем MULTI
        if (punktogramId === '21') {
            const variants = ['2100', '2101', '2102'];
            const id = variants[Math.floor(Math.random() * variants.length)];
            url = '/api/generate-punktum-exercise-multi/';
            payload = { orthogram_ids: [id] };
        }
        // Пунктограммы 16–20
        else if (punktogramId && ['1600','1700','1800','1900','2000'].includes(punktogramId)) {
            url = '/api/generate-punktum-exercise-multi/';
            payload = { orthogram_ids: [punktogramId] };
        }
        // Орфограммы
        else if (orthogramIds) {
            const ids = orthogramIds.split(',').map(id => id.trim());
            const isMulti = ids.includes('1400') || ids.includes('1500');
            url = isMulti ? '/api/generate-exercise-multi/' : '/api/generate-exercise/';
            payload = { orthogram_ids: ids };
        } else {
            answerSection.innerHTML = '<p>Задание не поддерживается.</p>';
            return;
        }
        
        // Задание 7
        if (orthogramIds === '711') {
            if (window.CorrectionModule && typeof window.CorrectionModule.loadCorrectionTest === 'function') {
                await CorrectionModule.loadCorrectionTest();
            } else {
                answerSection.innerHTML = '<p>Модуль задания 7 не загружен.</p>';
            }
            return;
        }
        
        // Задание 8
        if (orthogramIds === '8000') {
            answerSection.innerHTML = '<p>Загрузка задания 8...</p>';
            const csrf = getCookie('csrftoken');
            fetch('/api/generate-task-eight-test/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
                body: JSON.stringify({})
            })
            .then(r => r.json())
            .then(data => {
                answerSection.innerHTML = data.html || '<p>Ошибка загрузки</p>';
                if (window.PlanningEight) {
                    PlanningEight.setup();
                }
            })
            .catch(err => {
                answerSection.innerHTML = `<p>Ошибка: ${err.message}</p>`;
            });
            return;
        }
        
        // Задание 22
        if (orthogramIds === '2200') {
            answerSection.innerHTML = '<p>Загрузка задания 22...</p>';
            const csrf = getCookie('csrftoken');
            fetch('/api/generate-task-twotwo-test/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
                body: JSON.stringify({})
            })
            .then(r => {
                if (!r.ok) throw new Error(`HTTP ${r.status}`);
                return r.json();
            })
            .then(data => {
                answerSection.innerHTML = data.html || '<p>Ошибка загрузки</p>';
                setTimeout(() => {
                    if (window.PlanningTwoTwo && typeof window.PlanningTwoTwo.setup === 'function') {
                        window.PlanningTwoTwo.setup();
                    } else {
                        initTaskTwoTwoFallback();
                    }
                }, 50);
            })
            .catch(err => {
                console.error('❌ Ошибка загрузки задания 22:', err);
                answerSection.innerHTML = `<p>Ошибка: ${err.message}</p>`;
            });
            return;
        }
        
        // Fallback для задания 22
        function initTaskTwoTwoFallback() {
            const container = document.querySelector('.task-twotwo-exercise') || document.querySelector('.task-match-exercise');
            if (!container) return;
            const btn = container.querySelector('.check-task-twotwo');
            if (btn) {
                btn.onclick = function() {
                    alert('Кнопка работает! (fallback)');
                };
            }
        }
        
        // Общий запрос
        const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
            body: JSON.stringify(payload)
        });
        if (!res.ok) throw new Error('Ошибка загрузки');
        const data = await res.json();
        if (punktogramId && ['1600','1700','1800','1900','2000'].includes(punktogramId)) {
            answerSection.innerHTML = `<h3>Задание № ${punktogramId.slice(0,2)}</h3>${data.html}`;
        } else {
            answerSection.innerHTML = data.html;
        }
        
        // === СОЗДАЁМ СКРИПТЫ ДЛЯ ЗАДАНИЯ 10 ===
        if (data.task10_letter_groups && Object.keys(data.task10_letter_groups).length > 0) {
            const article = answerSection.querySelector('.article-practice');
            if (article) {
                const script1 = document.createElement('script');
                script1.id = 'task10-letter-groups';
                script1.type = 'application/json';
                script1.textContent = JSON.stringify(data.task10_letter_groups);
                article.appendChild(script1);
                
                const script2 = document.createElement('script');
                script2.id = 'task10-subgroup-letters';
                script2.type = 'application/json';
                script2.textContent = JSON.stringify(data.task10_subgroup_letters);
                article.appendChild(script2);
            }
        }

        // Обработка смайликов и проверки
        const container = answerSection.querySelector('.article-practice') || answerSection;
        await processPracticeContainer(container);
        setupCheckAnswers(container);
        
    } catch (err) {
        console.error('❌ Ошибка:', err);
        answerSection.innerHTML = `<p class="error">Ошибка: ${err.message}</p>`;
    }
});


// ============================================================================
// ПРОВЕРКА АЛФАВИТНЫХ ЗАДАНИЙ (ЗАДАНИЕ 9)
// ============================================================================

// ============================================================================
// ГЛОБАЛЬНЫЕ ОБРАБОТЧИКИ (без конфликтов)
// ============================================================================

// 1. Обработчик кнопок выбора блока (А-Д, Е-К и т.д.)
document.addEventListener('click', function(e) {
    const btn = e.target.closest('.check-task-still');
    if (!btn) return;
    
    e.preventDefault();

    // === ОЧИСТКА ОБЫЧНОГО БЛОКА ===
    const answerSection = document.querySelector('.block-answer');
    if (answerSection) {
        answerSection.innerHTML = '';
    }
    
    // Определяем параметры по тексту кнопки
    const text = btn.textContent.trim();
    
    if (text.includes('А-О') || text.includes('П-С') || text.includes('Т-Я')) {
        const orthogramId = '1';
        const rangeCode = text.includes('А-О') ? 'A-O' : text.includes('П-С') ? 'P-S' : 'T-YA';
        handleAlphabeticalExercise(orthogramId, rangeCode);
    } else if (text.includes('А-Д') || text.includes('Е-К') || text.includes('Л-Р') || text.includes('С-Я')) {
        const orthogramId = '2';
        const rangeCode = text.includes('А-Д') ? 'A-D' : text.includes('Е-К') ? 'E-K' : text.includes('Л-Р') ? 'L-R' : 'S-YA';
        handleAlphabeticalExercise(orthogramId, rangeCode);
    } else if (text.includes('а / о, е / и')) {
        // Чередующиеся гласные - отдельная функция
        handleCheredExercise();
    }
});

// 2. Обработчик кнопки "Проверить"
document.addEventListener('click', function(e) {
    if (!e.target.classList.contains('check-answers')) return;
    
    e.preventDefault();
    checkAlphabeticalExercise();
});

// 3. Обработчик смайликов (выбор буквы)
document.addEventListener('click', function(e) {
    // Закрываем все списки при клике вне смайлика
    if (!e.target.closest('.smiley-button')) {
        document.querySelectorAll('.smiley-options').forEach(opt => {
            opt.style.display = 'none';
        });
        return;
    }
    
    // Открытие/закрытие списка
    if (e.target.classList.contains('smiley-icon')) {
        e.preventDefault();
        e.stopPropagation();
        
        const btn = e.target.closest('.smiley-button');
        const opts = btn.querySelector('.smiley-options');
        
        // Закрываем все другие списки
        document.querySelectorAll('.smiley-options').forEach(o => {
            if (o !== opts) o.style.display = 'none';
        });
        
        // Переключаем текущий
        opts.style.display = opts.style.display === 'block' ? 'none' : 'block';
        return;
    }
    
    // Выбор буквы
    if (e.target.tagName === 'LI' && e.target.closest('.smiley-options')) {
        e.preventDefault();
        e.stopPropagation();
        
        const li = e.target;
        const letter = li.dataset.letter;
        const btn = li.closest('.smiley-button');
        const icon = btn.querySelector('.smiley-icon');
        
        // Устанавливаем букву
        icon.textContent = letter;
        icon.classList.add('selected');
        icon.classList.remove('correct', 'incorrect');
        
        // Закрываем список
        li.closest('.smiley-options').style.display = 'none';
    }
});

// ============================================================================
// ФУНКЦИИ ПРОВЕРКИ
// ============================================================================
async function checkAlphabeticalExercise() {
    const container = document.querySelector('.block-answer-still-content');
    if (!container) return;
    
    const smileys = container.querySelectorAll('.smiley-button');
    if (smileys.length === 0) return;
    
    // Собираем выбранные буквы
    const selectedLetters = [];
    smileys.forEach(smiley => {
        const icon = smiley.querySelector('.smiley-icon');
        const currentText = icon.textContent.trim();
        selectedLetters.push(currentText !== '😊' ? currentText : null);
    });
    
    // Отправляем на сервер
    const response = await fetch('/api/check-alphabetical-exercise/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({ selected_letters: selectedLetters })
    });
    
    const data = await response.json();
    if (data.error) return;
    
    // Подсвечиваем ответы
    smileys.forEach((smiley, index) => {
        const icon = smiley.querySelector('.smiley-icon');
        const currentText = icon.textContent.trim();
        
        if (currentText !== '😊') {
            if (data.results[index]) {
                icon.classList.add('correct');
            } else {
                icon.classList.add('incorrect');
            }
        }
    });
}

// ============================================================================
// ГЕНЕРАЦИЯ АЛФАВИТНЫХ УПРАЖНЕНИЙ
// ============================================================================

function handleAlphabeticalExercise(orthogramId, rangeCode) {
    const container = document.querySelector('.block-answer-still-content');
    if (!container) return;
    
    container.innerHTML = '<div class="loading">Загрузка...</div>';
    
    fetch('/api/generate-alphabetical-exercise/', {
        method: 'POST',
        headers: { 
            'Content-Type': 'application/json', 
            'X-CSRFToken': getCookie('csrftoken') 
        },
        body: JSON.stringify({ orthogram_id: orthogramId, range: rangeCode })
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            container.innerHTML = `<div class="error">${data.error}</div>`;
        } else {
            container.innerHTML = data.html;
            setTimeout(() => {
                processPracticeContainer(container);
            }, 0);
        }
    })
    .catch(error => {
        console.error('Ошибка:', error);
        container.innerHTML = `<div class="error">Ошибка загрузки</div>`;
    });
}

// ========================================================================
// ГЕНЕРАЦИЯ УПРАЖНЕНИЯ ДЛЯ ЧЕРЕДУЮЩИХСЯ ГЛАСНЫХ
// ========================================================================
function handleCheredExercise() {
    const container = document.querySelector('.block-answer-still-content');
    if (!container) return;
    
    container.innerHTML = '<div class="loading">Загрузка...</div>';
    
    fetch('/api/generate-chered-exercise/', {
        method: 'POST',
        headers: { 
            'Content-Type': 'application/json', 
            'X-CSRFToken': getCookie('csrftoken') 
        },
        body: JSON.stringify({})
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            container.innerHTML = `<div class="error">${data.error}</div>`;
        } else {
            container.innerHTML = data.html;
            setTimeout(() => {
                const article = container.querySelector('.article-practice');
                processPracticeContainer(article || container);
                setupCheckAnswers(article || container);
            }, 0);
        }
    })
    .catch(error => {
        console.error('Ошибка:', error);
        container.innerHTML = `<div class="error">Ошибка загрузки</div>`;
    });
}