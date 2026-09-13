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
// УНИВЕРСАЛЬНЫЙ МАППИНГ: ID кнопки → номер задания (для заголовка)
// ===========================================================================
const ORTHOGRAM_TO_TASK_NUMBER = {
    '1_3': '1–3',
    '1_5': '1–2 (5 кл.)', '2_5': '1–2 (5 кл.)',
    '1_6': '1–2 (6 кл.)', '2_6': '1–2 (6 кл.)',
    '1_7': '1–2 (7 кл.)', '2_7': '1–2 (7 кл.)',
    '1_8': '1–2 (8 кл.)', '2_8': '1–2 (8 кл.)',
    '4000': '4 (ЕГЭ)',
    '4_5': '4 (5 кл.)', '4_6': '4 (6 кл.)', '4_7': '4 (7 кл.)', '4_8': '4 (8 кл.)',
    '5000': '5', '6000': '6', '711': '7', '8000': '8',
    '1_11,2_11,12,13,14,15,24,26,27,271,272,273,274,275': '9',
    '10,11,28,29,6': '10',
    '31,33,34,35,37,39,48,481,482,483,484,60,61,610,485': '11',
    '25,49,50,51,511,512,513': '12',
    '21,32,36,46,54,56,57,58,581,582': '13',
    '1400': '14', '1500': '15',
    '2200': '22', '23_26': '23–26',
};

const PUNKTOGRAM_TO_TASK_NUMBER = {
    '1600': '16', '1700': '17', '1800': '18', '1900': '19', '2000': '20',
    '21': '21', '2100': '21', '2101': '21', '2102': '21',
};

function getTaskNumberByButton(orthogramIds, punktogramId) {
    if (punktogramId) {
        return PUNKTOGRAM_TO_TASK_NUMBER[punktogramId] || null;
    }
    if (orthogramIds) {
        const normalized = (orthogramIds || '').replace(/\s+/g, '');

        // === СПЕЦИАЛЬНАЯ ПРОВЕРКА ДЛЯ ЗАДАНИЯ 9 ===
        const TASK9_IDS = '1_11,2_11,12,13,14,15,24,26,27,271,272,273,274,275';
        if (normalized === TASK9_IDS) {
            return '9';
        }

        return ORTHOGRAM_TO_TASK_NUMBER[normalized] || null;
    }
    return null;
}

function insertTaskHeader(answerSection, taskNumber) {
    if (!taskNumber || !answerSection) return;
    const old = answerSection.querySelector('.task-loaded-header');
    if (old) old.remove();
    const h = document.createElement('h3');
    h.className = 'task-loaded-header';
    h.textContent = `Задание ${taskNumber}`;
    answerSection.prepend(h);
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
    '1_9': ['а', 'о', 'е', 'и', 'я', 'у', 'ю'],
    '2_9': ['а', 'о', 'е', 'и', 'я', 'у', 'ю'],
    '1_11': ['а', 'о', 'е', 'и', 'я', 'у', 'ю'],
    '2_11': ['а', 'о', 'е', 'и', 'я', 'у', 'ю'],
};


async function getLettersForOrthogram(orthId) {
    // === ЗАЩИТА: проверяем orthId ===
    if (!orthId) {
        console.warn('⚠️ getLettersForOrthogram: orthId is undefined!');
        return [',', 'х'];  // ← Для пунктограмм fallback
    }
    if (typeof orthId !== 'string') orthId = String(orthId);

    // Кэш
    if (lettersCache.has(orthId)) return lettersCache.get(orthId);

    // === ПУНКТОГРАММЫ 16–20 (ПРОВЕРЯЕМ ПЕРЕВЫЕ!) ===
    if (orthId === '1600' || orthId === '1700' || orthId === '1800' ||
        orthId === '1900' || orthId === '2000' ||
        orthId.startsWith('16-') || orthId.startsWith('17-') ||
        orthId.startsWith('18-') || orthId.startsWith('19-') ||
        orthId.startsWith('20-')) {
        const letters = [',', 'х'];
        lettersCache.set(orthId, letters);
        return letters;
    }

    // Задание 10
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
        const baseOrthId = orthId.split('-')[0].split('_')[1];
        const fallback = {
            "10": ["с", "з", "д", "т", "а", "о"],
            "11": ["з", "с"],
            "28": ["и", "ы"],
            "29": ["е", "и"],
            "6": ["ъ", "ь", "/"]
        };
        const letters = fallback[baseOrthId] || ['а', 'о', 'е', 'и', 'я'];
        lettersCache.set(orthId, letters);
        return letters;
    }

    // ЗАДАНИЕ 9
    if (!/^\d+(-\d+)?$/.test(orthId)) {
        const letters = ['а', 'о', 'е', 'и', 'я', 'у', 'ю'];
        lettersCache.set(orthId, letters);
        return letters;
    }

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

    if (orthId === '1' || orthId === '2') {
        const letters = ['а', 'о', 'е', 'и', 'я', 'у', 'ю'];
        lettersCache.set(orthId, letters);
        return letters;
    }

    // ЗАДАНИЕ 9
    if (orthId.startsWith('9-')) {
        // Пытаемся получить данные из скрипта в шаблоне
        try {
            const groupsElem = document.getElementById('task9-letter-groups');
            const lettersElem = document.getElementById('task9-subgroup-letters');

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
            console.warn("Ошибка при получении подгруппы для 9:", e);
        }

        // Fallback: возвращаем стандартный набор букв
        const letters = ['а', 'о', 'е', 'и', 'я', 'у', 'ю'];
        lettersCache.set(orthId, letters);
        return letters;
    }

    // ЗАДАНИЕ 14
    if (orthId.startsWith('14-')) {
        return ['|', '/', '-'];
    }
    // ЗАДАНИЕ 15
    if (orthId.startsWith('15-')) {
        return ['н', 'нн'];
    }

    // Орфограмма 35 и 37
    if (orthId === '35' || orthId.startsWith('35') || orthId === '37' || orthId.startsWith('37')) {
        const letters = ['ё', 'о', 'е'];
        lettersCache.set(orthId, letters);
        return letters;
    }

    // ЗАДАНИЕ 21
    if (orthId.startsWith('21-') || orthId === '2100' || orthId === '2101' || orthId === '2102') {
        const script = document.getElementById('task21-subgroup-letters');
        if (script) {
            try {
                const data = JSON.parse(script.textContent);
                if (data.punktum_21) {
                    lettersCache.set(orthId, data.punktum_21);
                    return data.punktum_21;
                }
            } catch (e) {
                console.error('❌ Ошибка парсинга task21-subgroup-letters:', e);
            }
        }
        // Fallback
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
        lettersCache.set(orthId, letters);
        return letters;
    }

    // ОРФОГРАММА 21: СЛИТНО/РАЗДЕЛЬНО
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
            const letters = Array.isArray(data.letters) ? data.letters : ['а', 'о', 'е', 'и', 'я'];
            lettersCache.set(orthId, letters);
            return letters;
        }
    } catch (err) { }

    const letters = ['а', 'о', 'е', 'и', 'я'];
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
    // const regex = /\*([0-9-]+)\*/g;

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
                lettersMap[id] = (letters && letters.length) ? letters : ['а', 'о', 'е', 'и', 'я'];
            }).catch(() => {
                lettersMap[id] = ['а', 'о', 'е', 'и', 'я'];
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
                        letters = fallback[baseOrthId] || ['а', 'о', 'е', 'и', 'я'];
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
                letters = fallback[baseOrthId] || ['а', 'о', 'е', 'и', 'я'];
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
        // === ДОБАВЛЯЕМ УНИВЕРСАЛЬНЫЙ СТИЛЬ КНОПКИ ПРОВЕРИТЬ ===
        button.classList.add('check-task-submit');

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

async function loadOrthoepyTest(grade = null) {
    const answerSection = document.querySelector('.block-answer');
    if (!answerSection) return;
    answerSection.innerHTML = '<p>Загрузка теста по орфоэпии...</p>';
    // === ВСТАВЛЯЕМ ЗАГОЛОВОК ЗАДАНИЯ ===
    const taskNumber = getTaskNumberByButton(orthogramIds, punktogramId);
    if (taskNumber) {
        insertTaskHeader(answerSection, taskNumber);
    }
    try {
        const csrf = getCookie('csrftoken');
        const payload = grade ? { grade } : {};

        const res = await fetch('/api/generate-orthoepy-test/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrf
            },
            body: JSON.stringify(payload)
        });

        if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
        const data = await res.json();

        if (data.html) {
            answerSection.innerHTML = `<h3 class="task-loaded-header">Задание 5</h3>${data.html}`;
            setupPaponimCheck();

            // === ВАЖНОЕ ИСПРАВЛЕНИЕ ===
            // Если сервер сказал, что это школьный режим, но в HTML нет атрибута — добавляем его вручную!
            const container = document.querySelector('.orthoepy-test-exercise');
            if (container && data.is_school_mode === true) {
                container.dataset.schoolMode = 'true';
                console.log('✅ Принудительно установлен режим: ШКОЛЬНЫЙ (из JSON)');
            } else if (container) {
                console.log('ℹ️ Режим:', container.dataset.schoolMode === 'true' ? 'ШКОЛЬНЫЙ' : 'ЕГЭ');
            }

            setupOrthoepyListeners();
        } else {
            answerSection.innerHTML = `<p class="error">${data.error || 'Ошибка загрузки теста'}</p>`;
        }
    } catch (e) {
        console.error('Ошибка загрузки теста орфоэпии:', e);
        answerSection.innerHTML = '<p class="error">Не удалось загрузить тест</p>';
    }
}

function setupOrthoepyListeners() {
    const btn = document.querySelector('.check-orthoepy-test');
    if (btn) {
        btn.onclick = checkOrthoepyTest;
    }
}


// async function checkOrthoepyTest() {
//     const container = document.querySelector('.orthoepy-test-exercise');
//     if (!container) return;

//     const selected = [...container.querySelectorAll('.orthoepy-checkbox:checked')]
//         .map(el => el.value);

//     if (!selected.length) {
//         alert('Выберите хотя бы один вариант');
//         return;
//     }

//     const btn = document.querySelector('.check-orthoepy-test');
//     if (btn) {
//         btn.disabled = true;
//         btn.textContent = 'Проверка...';
//     }

//     try {
//         const csrf = getCookie('csrftoken');
//         const res = await fetch('/api/check-orthoepy-test/', {
//             method: 'POST',
//             headers: {
//                 'Content-Type': 'application/json',
//                 'X-CSRFToken': csrf
//             },
//             body: JSON.stringify({ selected })
//         });

//         if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);

//         const result = await res.json();
//         displayOrthoepyResults(result);

//     } catch (e) {
//         alert('Ошибка при проверке');
//     } finally {
//         if (btn) {
//             btn.disabled = false;
//             btn.textContent = 'Проверить';
//         }
//     }
// }


// Функция проверки орфоэпии
async function checkOrthoepyTest() {
    const container = document.querySelector('.orthoepy-test-exercise');
    if (!container) {
        console.error('Контейнер .orthoepy-test-exercise не найден');
        return;
    }

    const selected = [...container.querySelectorAll('.orthoepy-checkbox:checked')]
        .map(el => el.value);

    if (!selected.length) {
        alert('Выберите хотя бы один вариант');
        return;
    }

    const btn = document.querySelector('.check-orthoepy-test');
    if (btn) {
        btn.disabled = true;
        btn.textContent = 'Проверка...';
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
            const errorData = await res.json().catch(() => ({}));
            throw new Error(errorData.error || `HTTP error! status: ${res.status}`);
        }

        const result = await res.json();

        // Используем глобальную функцию displayOrthoepyResults
        if (window.displayOrthoepyResults) {
            window.displayOrthoepyResults(result);
        } else {
            console.error('Функция displayOrthoepyResults не найдена');
            alert('Ошибка отображения результатов');
        }

    } catch (e) {
        console.error('Ошибка при проверке:', e);
        alert(`Ошибка при проверке: ${e.message}`);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.textContent = 'Проверить';
        }
    }
}


// Отображение результатов
// function displayOrthoepyResults(results) {
//     const container = document.querySelector('.orthoepy-test-exercise');
//     const isSchoolMode = container?.dataset.schoolMode === 'true';

//     const task4Results = results.results?.['4'];
//     if (!task4Results?.variant_results) return;

//     const variantResults = task4Results.variant_results;
//     const options = document.querySelectorAll('.test-option');

//     // Считаем количество правильных ответов
//     let correctCount = 0;
//     let totalSelected = 0;

//     options.forEach((option, index) => {
//         const variantResult = variantResults[`4-${index + 1}`];
//         if (!variantResult) return;

//         const checkbox = option.querySelector('.orthoepy-checkbox');
//         const textSpan = option.querySelector('.variant-text');
//         if (!checkbox || !textSpan) return;

//         textSpan.style.color = variantResult.is_correct ? '#28a745' : '#dc3545';
//         textSpan.style.fontWeight = '600';

//         if (checkbox.checked) {
//             totalSelected++;
//             if (variantResult.is_correct) correctCount++;

//             checkbox.style.outline = 'none';
//             checkbox.style.border = variantResult.is_correct ? 
//                 '3px solid #10b981' : '3px solid #ef4444';
//             checkbox.style.boxShadow = variantResult.is_correct ? 
//                 '0 0 6px 2px rgba(16, 185, 129, 0.7)' : 
//                 '0 0 6px 2px rgba(239, 68, 68, 0.7)';
//         }
//     });

//     document.querySelectorAll('.orthoepy-checkbox').forEach(cb => cb.disabled = true);

//     const checkBtn = document.querySelector('.check-orthoepy-test');
//     if (checkBtn) {
//         checkBtn.textContent = 'Проверено';
//         checkBtn.disabled = true;
//     }

//     // === ПОКАЗ РЕЗУЛЬТАТА ===
//     if (isSchoolMode) {
//         // Для школьного режима - создаем элемент для результата, если его нет
//         let resultDiv = document.querySelector('.orthoepy-result');

//         if (!resultDiv) {
//             // Создаем новый элемент
//             resultDiv = document.createElement('div');
//             resultDiv.className = 'orthoepy-result';
//             container.appendChild(resultDiv);
//         }

//         // Показываем сообщение
//         const allCorrect = correctCount === totalSelected && totalSelected > 0;
//         resultDiv.innerHTML = allCorrect ? 
//             '<p style="color: #28a745; font-weight: bold; font-size: 1.1em; margin-top: 15px;">✓ Правильно!</p>' : 
//             '<p style="color: #dc3545; font-weight: bold; font-size: 1.1em; margin-top: 15px;">✗ Неправильно, есть ошибки</p>';

//         resultDiv.style.display = 'block';

//     } else {
//         // Для ЕГЭ - используем существующий элемент
//         const resultDiv = document.querySelector('.orthoepy-result');
//         if (resultDiv) {
//             resultDiv.innerHTML = `<p><strong>Балл:</strong> ${results.user_score ?? task4Results.score ?? 0}</p>`;
//             resultDiv.style.display = 'block';
//         }
//     }
// }



// Отображение результатов орфоэпии planning.js
function displayOrthoepyResults(results) {
    const container = document.querySelector('.orthoepy-test-exercise');
    if (!container) {
        console.error('Контейнер .orthoepy-test-exercise не найден');
        return;
    }

    const isSchoolMode = container.dataset.schoolMode === 'true';

    // Извлекаем данные. Бэкенд отдает: results.results['4'].variant_results
    const task4Data = results.results?.['4'];
    if (!task4Data || !task4Data.variant_results) {
        console.error('Нет данных variant_results в ответе:', results);
        return;
    }

    const variantResults = task4Data.variant_results;
    const options = document.querySelectorAll('.test-option');

    let correctCount = 0;
    let totalSelected = 0;
    let totalCorrectExists = 0;

    options.forEach((option) => {
        // Берем ID из атрибута data-option-id (он есть в новом шаблоне)
        const optionId = option.dataset.optionId;
        if (!optionId) {
            console.warn('У варианта нет data-option-id, пропускаем');
            return;
        }

        // Ключ в ответе сервера: "4-1", "4-2" и т.д.
        const resultKey = `4-${optionId}`;
        const data = variantResults[resultKey];

        if (!data) {
            console.warn(`Не найден результат для ключа ${resultKey}`);
            return;
        }

        const checkbox = option.querySelector('.orthoepy-checkbox');
        const textSpan = option.querySelector('.variant-text') || option;
        if (!checkbox) return;

        // Статистика
        if (data.is_correct) totalCorrectExists++;

        // 1. Красим ТЕКСТ (зеленый если правильный, красный если нет)
        if (textSpan) {
            textSpan.style.color = data.is_correct ? '#28a745' : '#dc3545';
            textSpan.style.fontWeight = 'bold';
        }

        // 2. Обрабатываем ВЫБОР
        if (checkbox.checked) {
            totalSelected++;
            if (data.is_correct) correctCount++;

            checkbox.style.outline = 'none';
            if (data.is_correct) {
                checkbox.style.border = '3px solid #10b981';
                checkbox.style.boxShadow = '0 0 6px 2px rgba(16, 185, 129, 0.7)';
            } else {
                checkbox.style.border = '3px solid #ef4444';
                checkbox.style.boxShadow = '0 0 6px 2px rgba(239, 68, 68, 0.7)';
            }
        } else {
            checkbox.style.border = '';
            checkbox.style.boxShadow = '';
        }

        checkbox.disabled = true;
    });

    // Блокируем кнопку
    const checkBtn = document.querySelector('.check-orthoepy-test');
    if (checkBtn) {
        checkBtn.textContent = 'Проверено';
        checkBtn.disabled = true;
    }

    // === ВЫВОД СООБЩЕНИЯ ===
    let resultDiv = document.querySelector('.orthoepy-result');

    if (isSchoolMode) {
        if (!resultDiv) {
            resultDiv = document.createElement('div');
            resultDiv.className = 'orthoepy-result';
            resultDiv.style.marginTop = '15px';
            container.appendChild(resultDiv);
        }

        const hasMissing = totalSelected < totalCorrectExists;
        const hasWrong = correctCount < totalSelected;
        const allCorrect = !hasMissing && !hasWrong && totalSelected > 0;

        let message = '';
        let color = '#dc3545';

        if (allCorrect) {
            message = '✓ Правильно! Все слова с верным ударением отмечены.';
            color = '#28a745';
        } else if (totalSelected === 0) {
            message = '✗ Неправильно: ничего не выбрано.';
        } else if (hasMissing && hasWrong) {
            message = '✗ Неправильно: есть ошибки и не все верные слова отмечены.';
        } else if (hasMissing) {
            message = '✗ Неправильно: вы отметили не все слова с правильным ударением.';
        } else if (hasWrong) {
            message = '✗ Неправильно: среди выбранных есть слова с ошибочным ударением.';
        }

        resultDiv.innerHTML = `<p style="color: ${color}; font-weight: bold; font-size: 1.1em;">${message}</p>`;
        resultDiv.style.display = 'block';

    } else {
        // Режим ЕГЭ
        if (!resultDiv) {
            resultDiv = document.createElement('div');
            resultDiv.className = 'orthoepy-result';
            container.appendChild(resultDiv);
        }
        const score = results.user_score !== undefined ? results.user_score : (task4Data.score || 0);
        resultDiv.innerHTML = `<p style="font-size: 1.2em; margin-top: 15px;"><strong>Балл:</strong> ${score} из 1</p>`;
        resultDiv.style.display = 'block';
    }
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
    // === ВСТАВЛЯЕМ ЗАГОЛОВОК ЗАДАНИЯ ===
    const taskNumber = getTaskNumberByButton(orthogramIds, punktogramId);
    if (taskNumber) {
        insertTaskHeader(answerSection, taskNumber);
    }

    // === НОВЫЙ БЛОК: ПУНКТОГРАММЫ 16-21 ===
    if (punktogramId) {
        e.preventDefault();

        // Задание 21 - случайный подтип
        let punktumId = punktogramId;
        if (punktogramId === '21') {
            const variants = ['2100', '2101', '2102'];
            punktumId = variants[Math.floor(Math.random() * variants.length)];
        }

        try {
            const csrf = getCookie('csrftoken');
            const res = await fetch('/api/generate-punktum-exercise-multi/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrf
                },
                body: JSON.stringify({ orthogram_ids: [punktumId] })
            });

            if (!res.ok) throw new Error('Ошибка загрузки');
            const data = await res.json();

            // Добавляем заголовок для заданий 16-20
            const taskNumber = punktumId.slice(0, 2);
            answerSection.innerHTML = `<h3 class="task-loaded-header">Задание ${taskNumber}</h3>${data.html}`;

            // Обработка смайликов
            const container = answerSection.querySelector('.article-practice') || answerSection;
            await processPracticeContainer(container);
            setupCheckAnswers(container);

        } catch (err) {
            console.error('❌ Ошибка:', err);
            answerSection.innerHTML = `<p class="error">Ошибка: ${err.message}</p>`;
        }
        return; // ВАЖНО: выходим, чтобы не обрабатывать дальше
    }

    // ... остальной код (орфоэпия, паронимы, задания 8, 22 и т.д.)

    // === ОРФОЭПИЯ (задание 4) ===
    if (orthogramIds === '4000' || orthogramIds.startsWith('4_')) {
        e.preventDefault();

        // Извлекаем класс: '4_6' → 6, '4000' → null (ЕГЭ режим)
        let grade = null;
        if (orthogramIds.startsWith('4_')) {
            grade = parseInt(orthogramIds.split('_')[1]);
            console.log(`🎯 Загрузка орфоэпии для ${grade} класса`);
        } else {
            console.log(`🎯 Загрузка орфоэпии (ЕГЭ режим)`);
        }

        const answerSection = document.querySelector('.block-answer');
        if (!answerSection) {
            console.error('Блок .block-answer не найден');
            return;
        }

        answerSection.innerHTML = '<p>Загрузка теста по орфоэпии...</p>';
        // === ВСТАВЛЯЕМ ЗАГОЛОВОК ЗАДАНИЯ ===
        const taskNumber = getTaskNumberByButton(orthogramIds, punktogramId);
        if (taskNumber) {
            insertTaskHeader(answerSection, taskNumber);
        }

        try {
            const csrf = getCookie('csrftoken');
            if (!csrf) {
                answerSection.innerHTML = '<p class="error">Сессия истекла. Обновите страницу.</p>';
                return;
            }

            // Для ЕГЭ режима передаем grade: null или вообще не передаем
            const payload = grade ? { grade: grade } : {};

            fetch('/api/generate-orthoepy-test/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrf
                },
                body: JSON.stringify(payload)
            })
                .then(async res => {
                    if (!res.ok) {
                        const errorData = await res.json().catch(() => ({}));
                        throw new Error(errorData.error || `HTTP error! status: ${res.status}`);
                    }
                    return res.json();
                })
                .then(data => {
                    if (data.html) {
                        const taskTitle = grade ? `Задание 4 (${grade} класс)` : 'Задание 4 (ЕГЭ)';
                        answerSection.innerHTML = `<h3 class="task-loaded-header">${taskTitle}</h3>${data.html}`;


                        // Добавляем data-атрибут school-mode из ответа сервера
                        const container = document.querySelector('.orthoepy-test-exercise');
                        if (container) {
                            container.dataset.schoolMode = data.is_school_mode ? 'true' : 'false';
                        }

                        // Назначаем обработчик для кнопки проверки
                        const checkBtn = document.querySelector('.check-orthoepy-test');
                        if (checkBtn) {
                            checkBtn.onclick = function () {
                                checkOrthoepyTest();
                            };
                        }

                    } else {
                        answerSection.innerHTML = `<p class="error">${data.error || 'Ошибка загрузки теста'}</p>`;
                    }
                })
                .catch(error => {
                    console.error('Ошибка загрузки теста:', error);
                    answerSection.innerHTML = `<p class="error">Не удалось загрузить тест: ${error.message}</p>`;
                });

        } catch (error) {
            console.error('Критическая ошибка:', error);
            answerSection.innerHTML = '<p class="error">Произошла ошибка при загрузке</p>';
        }

        return; // ВАЖНО: выходим, чтобы не выполнялся другой код
    }

    // === ЗАДАНИЕ 5: Паронимы ===
    if (orthogramIds === '5000') {
        answerSection.innerHTML = '<p>Загрузка задания 5...</p>';
        // === ВСТАВЛЯЕМ ЗАГОЛОВОК ЗАДАНИЯ ===
        const taskNumber = getTaskNumberByButton(orthogramIds, punktogramId);
        if (taskNumber) {
            insertTaskHeader(answerSection, taskNumber);
        }
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
        // === ВСТАВЛЯЕМ ЗАГОЛОВОК ЗАДАНИЯ ===
        const taskNumber = getTaskNumberByButton(orthogramIds, punktogramId);
        if (taskNumber) {
            insertTaskHeader(answerSection, taskNumber);
        }
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
    const TASK9_IDS = '1_11,2_11,12,13,14,15,24,26,27,271,272,273,274,275';

    // === СПЕЦИАЛЬНАЯ ОБРАБОТКА ЗАДАНИЯ 9 ===
    if (normalizedOrthogramIds === TASK9_IDS) {
        e.preventDefault();

        // ✅ ВСТАВЛЯЕМ ЗАГОЛОВОК СРАЗУ
        answerSection.innerHTML = `<h3 class="task-loaded-header">Задание 9</h3><p>Загрузка...</p>`;

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
                    answerSection.innerHTML = `<h3 class="task-loaded-header">Задание 9</h3><p class="error">${data.error}</p>`;
                } else {
                    // ✅ ВСТАВЛЯЕМ ЗАГОЛОВОК ВМЕСТЕ С HTML
                    answerSection.innerHTML = `<h3 class="task-loaded-header">Задание 9</h3>${data.html}`;

                    // Обработка смайликов
                    const container = answerSection.querySelector('.article-practice') || answerSection;
                    setTimeout(() => processPracticeContainer(container), 0);
                    setupCheckAnswers(container);
                }
            })
            .catch(err => {
                console.error('❌ Ошибка задания 9:', err);
                answerSection.innerHTML = `<h3 class="task-loaded-header">Задание 9</h3><p class="error">Не удалось загрузить задание 9</p>`;
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
        else if (punktogramId && ['1600', '1700', '1800', '1900', '2000'].includes(punktogramId)) {
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
            // === ВСТАВЛЯЕМ ЗАГОЛОВОК ЗАДАНИЯ ===
            const taskNumber = getTaskNumberByButton(orthogramIds, punktogramId);
            if (taskNumber) {
                insertTaskHeader(answerSection, taskNumber);
            }
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
            // === ВСТАВЛЯЕМ ЗАГОЛОВОК ЗАДАНИЯ ===
            const taskNumber = getTaskNumberByButton(orthogramIds, punktogramId);
            if (taskNumber) {
                insertTaskHeader(answerSection, taskNumber);
            }
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
                btn.onclick = function () {
                    alert('Кнопка работает! (fallback)');
                };
            }
        }

        // === ОБЩИЙ ЗАПРОС ДЛЯ ОРФОГРАММ (9-13) ===
        const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
            body: JSON.stringify(payload)
        });
        if (!res.ok) throw new Error('Ошибка загрузки');
        const data = await res.json();

        // === ВСТАВЛЯЕМ ЗАГОЛОВОК ДО HTML ===
        let taskNumber = null;
        if (orthogramIds) {
            // Пытаемся получить номер задания из маппинга
            const normalized = orthogramIds.replace(/\s+/g, '');
            taskNumber = ORTHOGRAM_TO_TASK_NUMBER[normalized] || null;
        }

        // Формируем HTML с заголовком
        let htmlWithHeader = '';
        if (taskNumber) {
            htmlWithHeader = `<h3 class="task-loaded-header">Задание ${taskNumber}</h3>${data.html}`;
        } else {
            htmlWithHeader = data.html;
        }

        // Если это пунктограммы (16-20) — используем другой формат
        if (punktogramId && ['1600', '1700', '1800', '1900', '2000'].includes(punktogramId)) {
            const taskNum = punktogramId.slice(0, 2);
            htmlWithHeader = `<h3>Задание № ${taskNum}</h3>${data.html}`;
        }

        answerSection.innerHTML = htmlWithHeader;

        // === ВСТАВЛЯЕМ КАРТИНКУ ДЛЯ ЗАДАНИЯ 15 (Н/НН) ===
        if (orthogramIds === '1500') {
            const article = answerSection.querySelector('.article-practice');
            if (article && !article.querySelector('.nn-reference-image')) {
                const img = document.createElement('img');
                img.src = '/static/images/nn.webp';
                img.alt = 'Н и НН — справочная таблица';
                img.className = 'nn-reference-image';
                img.loading = 'lazy';
                article.insertBefore(img, article.firstChild);
            }
            // Ссылка на игру "Попади в цель" — в КОНЕЦ блока
            if (!article.querySelector('.nn-game-link')) {
                article.insertAdjacentHTML('beforeend', `
            <a href="/targetn/" class="orthoepy-dictionary-link nn-game-link">
                Играть в «Попади в цель»: Н и НН
                <span class="arrow">→</span>
            </a>
        `);
            }
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
document.addEventListener('click', function (e) {
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
document.addEventListener('click', function (e) {
    if (!e.target.classList.contains('check-answers')) return;

    e.preventDefault();
    checkAlphabeticalExercise();
});

// 3. Обработчик смайликов (выбор буквы)
document.addEventListener('click', function (e) {
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

    // Летопись задания 9: проверочно-отчётный блок под упражнением
    if (data.orthogram_id && Task9Report.SUPPORTED.includes(data.orthogram_id) && data.report) {
        Task9Report.renderInto(container, data.report, data.resolved || []);
    }
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
                // Летопись: проверочно-отчётный блок под упражнением
                if (Task9Report.SUPPORTED.includes(orthogramId) && data.report) {
                    Task9Report.renderInto(container, data.report, []);
                }
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
                // Летопись: проверочно-отчётный блок под упражнением
                if (data.report) {
                    Task9Report.renderInto(container, data.report, []);
                }
            }
        })
        .catch(error => {
            console.error('Ошибка:', error);
            container.innerHTML = `<div class="error">Ошибка загрузки</div>`;
        });
}


// ========================================================================
// ✅ АВТО-СОХРАНЕНИЕ ПЛАНИНГА — НА ГЛОБАЛЬНОМ УРОВНЕ!
// ========================================================================
(function () {
    'use strict';

    // ← НЕ определяем getCookie здесь! Используем глобальную из начала файла
    const csrftoken = getCookie('csrftoken');

    // Лёгкий тост для сообщений планинга (лимиты и т.п.)
    function planningToast(text) {
        let t = document.querySelector('.planning-toast');
        if (!t) {
            t = document.createElement('div');
            t.className = 'planning-toast';
            t.style.cssText = 'position:fixed;left:50%;bottom:24px;transform:translateX(-50%);' +
                'background:#4A3520;color:#FDFAF5;padding:10px 18px;border-radius:10px;' +
                'font-size:14px;z-index:2000;box-shadow:0 8px 24px rgba(24,14,5,.3);max-width:90vw;text-align:center;';
            document.body.appendChild(t);
        }
        t.textContent = text;
        t.style.opacity = '1';
        clearTimeout(t._h);
        t._h = setTimeout(() => { t.style.opacity = '0'; }, 5000);
        t.style.transition = 'opacity .4s';
    }

    async function saveField(field) {
        const fieldName = field.name;
        const content = field.value.trim();
        console.log(`💾 Saving ${fieldName}: "${content.substring(0, 30) || '(пусто)'}..."`);
        if (!csrftoken) {
            console.error('❌ CSRF token not found!');
            return;
        }
        try {
            const response = await fetch('/api/save-example/', {
                method: 'POST',
                credentials: 'same-origin',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'X-CSRFToken': csrftoken
                },
                body: new URLSearchParams({
                    'field_name': fieldName,
                    'content': content
                })
            });
            const contentType = response.headers.get('content-type');
            if (!contentType || !contentType.includes('application/json')) {
                const text = await response.text();
                console.error(`❌ Ожидался JSON, получено: ${text.substring(0, 100)}`);
                return;
            }
            const result = await response.json();
            if (result.status === 'success') {
                console.log(`✅ Saved: ${fieldName}`);
                field.style.borderColor = '#4caf50';
                setTimeout(() => { field.style.borderColor = ''; }, 1000);
                if (result.cap_reached) planningToast(result.message);
            } else {
                console.error(`❌ Save failed: ${result.message}`);
            }
        } catch (error) {
            console.error(`🔥 Fetch error: ${error}`);
        }
    }

    async function loadSavedExamples() {
        console.log('🔄 Loading saved planning examples...');
        try {
            const response = await fetch('/api/load-examples/', {
                method: 'GET',
                headers: { 'X-CSRFToken': csrftoken }
            });
            if (!response.ok) {
                console.warn('⚠️ Load examples failed:', response.status);
                return;
            }
            const examples = await response.json();
            console.log('📦 Loaded:', Object.keys(examples).length, 'fields');
            Object.entries(examples).forEach(([fieldName, content]) => {
                const field = document.querySelector(`[name="${fieldName}"]`);
                if (field && content) {
                    field.value = content;
                    console.log(`✅ Restored: ${fieldName}`);
                }
            });
        } catch (error) {
            console.error('🔥 Load error:', error);
        }
    }

    function init() {
        const planFields = document.querySelectorAll(
            '.input-text[name^="user-input-orf-"], .input-text[name^="user-input-punktum-"]'
        );
        if (planFields.length === 0) {
            console.log('📋 Planning: no auto-save fields found');
            return;
        }
        planFields.forEach(field => {
            field.addEventListener('blur', function () {
                saveField(this);
            });
        });
        window.addEventListener('beforeunload', function () {
            planFields.forEach(field => {
                navigator.sendBeacon('/api/save-example/', new URLSearchParams({
                    'field_name': field.name,
                    'content': field.value.trim()
                }));
            });
        });
        loadSavedExamples();
        console.log(`🚀 Planning auto-save/load ready (${planFields.length} fields)`);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();  // ← IIFE авто-сохранения закрывается ЗДЕСЬ

// ========================================================================
// ✅ ИНИЦИАЛИЗАЦИЯ СТРАНИЦЫ ТРЕНАЖЁРОВ ОГЭ (oge.html) — ОТДЕЛЬНО!
// ========================================================================
document.addEventListener('DOMContentLoaded', function () {
    'use strict';

    var taskButtonsContainer = document.querySelector('.task-buttons');
    if (!taskButtonsContainer) {
        console.log('📋 OGE Trainer: не страница тренажёров');
        return;
    }

    var taskButtons = taskButtonsContainer.querySelectorAll('.check-task');
    if (taskButtons.length === 0) {
        console.log('📋 OGE Trainer: нет кнопок');
        return;
    }

    console.log('🚀 OGE Trainer: инициализация', taskButtons.length, 'кнопок');

    taskButtons.forEach(function (btn) {
        if (btn._ogeClickHandler) {
            btn.removeEventListener('click', btn._ogeClickHandler);
        }

        btn._ogeClickHandler = function (e) {
            e.preventDefault();

            var taskNumber = this.textContent.trim();
            var orthogramData = this.dataset.orthogram;

            document.querySelectorAll('.task-buttons .check-task').forEach(function (b) {
                b.classList.remove('active');
            });
            this.classList.add('active');

            if (taskNumber === '2-3' || orthogramData === '2_3') {
                if (typeof handleOgeTask2_3 === 'function') {
                    handleOgeTask2_3();
                } else {
                    console.error('❌ handleOgeTask2_3 не найдена!');
                }
            } else if (['4', '5', '6', '7', '8', '9', '10-12'].indexOf(taskNumber) !== -1) {
                if (typeof handleOgeSingleTask === 'function') {
                    handleOgeSingleTask(taskNumber);
                } else {
                    console.error('❌ handleOgeSingleTask не найдена!');
                }
            } else if (['13.1', '13.2', '13.3'].indexOf(taskNumber) !== -1) {
                var container = document.querySelector('.block-answer');
                if (container) {
                    container.innerHTML = '<p style="text-align:center; padding:20px; color:#666;">Задание в разработке 🔧</p>';
                }
            }
        };

        btn.addEventListener('click', btn._ogeClickHandler);
    });

    console.log('✅ OGE Trainer: инициализация завершена');
});

// защита от вставки HTML (текстовые поля планингов - пользователи вносят примеры слов) + счётчик
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.input-text').forEach(textarea => {
        const idNum = textarea.id.split('-').pop();
        const counter = document.getElementById(`counter-${idNum}`);
        const MAX = 300;

        // Счётчик при загрузке
        if (counter) counter.textContent = `${textarea.value.length} / ${MAX}`;

        textarea.addEventListener('input', () => {
            // 1. Удаляем любые HTML-теги из вставленного текста
            let clean = textarea.value.replace(/<[^>]*>/g, '');
            // 2. Обрезаем, если вставка превысила лимит
            if (clean.length > MAX) clean = clean.slice(0, MAX);

            textarea.value = clean;
            if (counter) counter.textContent = `${clean.length} / ${MAX}`;
        });
    });
});
// ============================================================================
// ЛЕТОПИСЬ ЗАДАНИЯ 9: работа над ошибками + история прохождений
// Стилистика и логика повторяют тренажёр ударений (planning_orthoepos.js),
// классы оформления уже есть в planning_style.css — новых стилей не нужно.
// ============================================================================

window.Task9Report = {

    // Блоки задания 9, где включена летопись:
    // 1 — проверяемые гласные, 2 — непроверяемые, CHERED — чередующиеся
    SUPPORTED: ['1', '2', 'CHERED'],

    esc(s) {
        const d = document.createElement('div');
        d.textContent = (s === null || s === undefined) ? '' : String(s);
        return d.innerHTML;
    },

    /** Карточка ошибки: слово, в котором красным стоит буква ученика */
    correctionItemHtml(item) {
        const chosen = (item.chosen_letter || '').toLowerCase();
        if (!chosen) return '';
        const html = this.esc(item.word).replace(
            /\*\d+\*/,
            '<span class="wrong-stress">' + this.esc(chosen) + '</span>'
        );
        return '<div class="correction-item">' + html + '</div>';
    },

    /** Слово с правильной буквой (для заметки «Отработано») */
    correctWordHtml(item) {
        const letter = (item.correct_letter || '').toLowerCase();
        return this.esc(item.word).replace(
            /\*\d+\*/,
            '<b>' + this.esc(letter) + '</b>'
        );
    },

    /** Блоки ошибок по датам; пусто — вердикт «Молодца» */
    renderCorrection(items, resolved) {
        const host = document.getElementById('task9-correction-blocks');
        if (!host) return;
        const cnt = document.getElementById('task9-correction-count');
        const note = document.getElementById('task9-resolved-note');

        if (note) {
            note.innerHTML = (resolved && resolved.length)
                ? '<div class="correction-resolved">✓ Отработано в этот раз: ' +
                  resolved.map(it => this.correctWordHtml(it)).join(', ') + '</div>'
                : '';
        }

        if (!items || !items.length) {
            if (cnt) cnt.textContent = '';
            host.innerHTML = '<div class="correction-success">Молодца, ошибок в этом блоке нет!</div>';
            return;
        }
        if (cnt) cnt.textContent = '(слов: ' + items.length + ')';

        const byDate = {};
        items.forEach(it => {
            const key = it.correction_since || '';
            (byDate[key] = byDate[key] || []).push(it);
        });

        let html = '';
        Object.keys(byDate).sort().reverse().forEach(date => {
            html += '<div class="correction-group">' +
                '<div class="correction-group__title">Блок ошибок от ' + this.esc(date) + '</div>' +
                '<div class="correction-group__items">';
            byDate[date].forEach(it => { html += this.correctionItemHtml(it); });
            html += '</div></div>';
        });
        host.innerHTML = html;
    },

    /** История прохождений: дата, результат, процент */
    renderHistory(attempts) {
        const host = document.getElementById('task9-history-container');
        if (!host) return;
        if (!attempts || !attempts.length) {
            host.innerHTML = '<div class="history-empty">Прохождений пока нет.</div>';
            return;
        }
        let html = '<table class="history-table">' +
            '<thead><tr><th>Дата</th><th>Результат</th><th>%</th></tr></thead><tbody>';
        attempts.forEach(a => {
            const pct = a.chosen ? Math.round(a.correct / a.chosen * 100) : 0;
            const cls = pct >= 80 ? 'history-pct--high' : (pct >= 50 ? 'history-pct--mid' : 'history-pct--low');
            html += '<tr>' +
                '<td>' + this.esc(a.date) + '</td>' +
                '<td>верно ' + a.correct + ' из ' + a.chosen + '</td>' +
                '<td class="history-pct ' + cls + '">' + pct + '%</td>' +
                '</tr>';
        });
        html += '</tbody></table>';
        host.innerHTML = html;
    },

    /** Монтирует оба блока отчёта в конец контейнера упражнения */
    renderInto(container, report, resolved) {
        if (!container || !report) return;
        container.querySelectorAll('.task9-report').forEach(el => el.remove());
        const wrap = document.createElement('div');
        wrap.className = 'task9-report';
        wrap.innerHTML =
            '<section class="block-correction">' +
            '<h2 class="title-planing">Работа над ошибками <span id="task9-correction-count"></span></h2>' +
            '<div id="task9-resolved-note"></div>' +
            '<div id="task9-correction-blocks"></div>' +
            '</section>' +
            '<section class="block-history">' +
            '<h2 class="title-planing">История прохождений</h2>' +
            '<div id="task9-history-container"></div>' +
            '</section>';
        container.appendChild(wrap);
        this.renderCorrection(report.correction || [], resolved || []);
        this.renderHistory(report.attempts || []);
    },
};
