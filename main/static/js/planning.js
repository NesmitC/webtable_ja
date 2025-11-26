document.addEventListener('DOMContentLoaded', function() {
    const textareas = document.querySelectorAll('textarea[name^="user-input-orf-"]');

    // Получаем CSRF-токен
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;

    if (!csrfToken) {
        console.error('CSRF токен не найден! Проверьте, что {% csrf_token %} есть в шаблоне.');
        return;
    }

    // Загружаем сохранённые данные
    fetch("/load-examples/")
        .then(response => response.json())
        .then(data => {
            textareas.forEach(ta => {
                if (data[ta.name]) {
                    ta.value = data[ta.name];
                }
            });
        });

    // Сохраняем при изменении
    textareas.forEach(ta => {
        ta.addEventListener('input', function() {
            fetch("/save-example/", {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'X-CSRFToken': csrfToken
                },
                body: `field_name=${encodeURIComponent(this.name)}&content=${encodeURIComponent(this.value)}`
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Ошибка сохранения');
                }
                return response.json();
            })
            .then(data => {
                console.log('Сохранено:', data);
            })
            .catch(error => {
                console.error('Ошибка:', error);
            });
        });
    });
});

// ===========================================================================

// --- Глобальные функции ---
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

// --- Кэш для букв орфограмм ---
const orthogramLettersCache = {};

async function getLettersForOrthogram(orthId) {
    // Защита от некорректного ID
    if (typeof orthId !== 'string') orthId = String(orthId);

    // Задание 14 и связанные коды — три варианта
    if (orthId.startsWith('14')) {
        return ['/', '|', '-'];
    }

    // Орфограммы с НЕ — слитно/раздельно
    if (['21', '32', '36', '46', '54', '56', '58', '581'].includes(orthId)) {
        return ['/', '|'];
    }

    // Ъ/Ь
    if (orthId == '6') {
        return ['ъ', 'ь', '/'];
    }

    // Кэш
    if (orthogramLettersCache[orthId]) {
        return orthogramLettersCache[orthId];
    }

    // API-запрос (на случай новых орфограмм)
    try {
        const response = await fetch(`/api/orthogram/${orthId}/letters/`);
        const data = await response.json();
        const letters = Array.isArray(data.letters) ? data.letters : ['а', 'о', 'е', 'и', 'я'];
        orthogramLettersCache[orthId] = letters;
        return letters;
    } catch (err) {
        console.warn(`Не удалось загрузить буквы для орфограммы ${orthId}`, err);
        return ['а', 'о', 'е', 'и', 'я'];
    }
}

// --- Обработка одной строки с масками ---
async function processLineWithMasks(lineText) {
    try {
        const matches = [...lineText.matchAll(/\*(\d+)\*/g)];
        if (matches.length === 0) return lineText;

        let result = '';
        let lastIndex = 0;

        for (const match of matches) {
            const orthId = match[1];
            const letters = await getLettersForOrthogram(orthId);
            const liItems = letters.map(letter =>
                `<li data-letter="${letter}">${letter}</li>`
            ).join('');

            result += lineText.slice(lastIndex, match.index);

            const isSplit = ['21', '32', '36', '46', '54', '56', '58', '581'].includes(orthId);
            let prefix = '';
            let removeLength = 0;

            if (isSplit) {
                const beforeMask = lineText.slice(0, match.index);
                const parts = beforeMask.split(/\s+/).filter(Boolean);
                const lastPart = parts.length > 0 ? parts[parts.length - 1] : '';

                if (
                    (lastPart.endsWith('не') || lastPart.endsWith('НЕ') || lastPart.endsWith('Не')) &&
                    lastPart.length >= 2
                ) {
                    const suffix = lastPart.slice(-2);
                    if (['не', 'НЕ', 'Не'].includes(suffix)) {
                        const pos = match.index - 2;
                        if (pos <= 0 || /\s/.test(lineText[pos - 1])) {
                            removeLength = 2;
                            prefix = '(не)';
                        }
                    }
                }

                if (removeLength > 0) {
                    result = result.slice(0, -removeLength);
                }
            }

            const buttonHtml = isSplit
                ? `<span class="smiley-button" data-orth-id="${orthId}" data-word-template="${lineText}">
                     ${prefix}&nbsp;<span class="smiley-icon">😊</span>
                     <ul class="smiley-options">${liItems}</ul>
                   </span>`
                : `<span class="smiley-button" data-orth-id="${orthId}" data-word-template="${lineText}">
                     <span class="smiley-icon">😊</span>
                     <ul class="smiley-options">${liItems}</ul>
                   </span>`;

            result += buttonHtml;
            lastIndex = match.index + match[0].length;
        }

        result += lineText.slice(lastIndex);
        return result;
    } catch (err) {
        console.error('Ошибка в processLineWithMasks:', err, 'Текст:', lineText);
        return lineText; // возвращаем как есть при ошибке
    }
}

// --- Обработка контейнера ---
async function processPracticeContainer(container) {
    const lines = container.querySelectorAll('.practice-line');
    for (const line of lines) {
        const original = line.textContent.trim();
        if (original) {
            const processed = await processLineWithMasks(original);
            line.innerHTML = processed;
        }
    }
}

// --- Обработчик проверки ---
function setupCheckAnswers(container = document) {
    container.querySelectorAll('.check-answers').forEach(button => {
        if (button._clickHandler) {
            button.removeEventListener('click', button._clickHandler);
        }
        button._clickHandler = function () {
            const article = button.closest('.article-practice');
            const smileyButtons = article.querySelectorAll('.smiley-button');

            if (smileyButtons.length === 0) {
                console.warn('Нет смайликов для проверки');
                return;
            }

            const userAnswers = [];
            let hasSelection = false;

            smileyButtons.forEach(btn => {
                const icon = btn.querySelector('.smiley-icon');
                let selectedLetter = icon ? icon.textContent : '😊';

                if (selectedLetter === '|') {
                    selectedLetter = '\\';
                }

                if (selectedLetter !== '😊') {
                    hasSelection = true;
                }
                userAnswers.push(selectedLetter);
            });

            if (!hasSelection) {
                alert("Сначала выбери буквы в пропусках!");
                return;
            }

            const csrfToken = getCookie('csrftoken');
            if (!csrfToken) {
                alert('Сессия истекла. Пожалуйста, обновите страницу.');
                return;
            }

            fetch('/api/check-exercise/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({ user_words: userAnswers })
            })
            .then(r => {
                if (!r.ok) {
                    return r.text().then(text => {
                        throw new Error(`HTTP ${r.status}: ${text}`);
                    });
                }
                return r.json();
            })
            .then(results => {
                if (!Array.isArray(results)) {
                    throw new Error('Некорректный ответ от сервера');
                }

                const icons = article.querySelectorAll('.smiley-icon');
                icons.forEach((icon, i) => {
                    icon.classList.remove('selected', 'correct', 'incorrect');
                    if (i < results.length) {
                        icon.classList.add(results[i] ? 'correct' : 'incorrect');
                    }
                });
            })
            .catch(err => {
                console.error('Ошибка проверки:', err);
                alert('Произошла ошибка. Попробуйте ещё раз.');
            });
        };
        button.addEventListener('click', button._clickHandler);
    });
}

// --- Инициализация DOM ---
document.addEventListener('DOMContentLoaded', async () => {
    // Обработка стартовых упражнений
    document.querySelectorAll('.practice-text-container').forEach(async (container) => {
        await processPracticeContainer(container);
    });

    // Подключение проверки
    setupCheckAnswers();

    // --- Глобальный обработчик выпадающих списков ---
    document.addEventListener('click', (e) => {
        const target = e.target;

        if (target.classList.contains('smiley-icon')) {
            e.stopPropagation();
            const button = target.closest('.smiley-button');
            if (button) {
                const options = button.querySelector('.smiley-options');
                if (options) {
                    options.style.display = options.style.display === 'block' ? 'none' : 'block';
                }
            }
            return;
        }

        if (target.tagName === 'LI' && target.hasAttribute('data-letter')) {
            const button = target.closest('.smiley-button');
            if (!button) return;

            const selectedLetter = target.dataset.letter;
            const icon = button.querySelector('.smiley-icon');
            if (icon) {
                icon.textContent = selectedLetter;
                icon.className = 'smiley-icon selected';
            }

            const options = button.querySelector('.smiley-options');
            if (options) {
                options.style.display = 'none';
            }
            return;
        }

        // Закрытие всех выпадашек при клике вне
        if (!e.target.closest('.smiley-button')) {
            document.querySelectorAll('.smiley-options').forEach(el => {
                el.style.display = 'none';
            });
        }
    });

    // === ЗАДАНИЕ 9 ===
    const stillButtons = document.querySelectorAll('.check-task-still');
    const stillAnswerSection = document.querySelector('.block-answer-still-content');

    if (stillAnswerSection && stillButtons.length) {
        stillButtons.forEach(btn => {
            const handler = async () => {
                /* логика генерации — без изменений */
                const label = btn.textContent.trim();
                let orthId = null;
                let rangeCode = null;
                let orthogramIds = null;

                if (['А-О', 'П-С', 'Т-Я'].includes(label)) {
                    orthId = '1';
                    rangeCode = label === 'А-О' ? 'A-O' :
                                label === 'П-С' ? 'P-S' : 'T-YA';
                } else if (['А-Д', 'Е-К', 'Л-Р', 'С-Я'].includes(label)) {
                    orthId = '2';
                    rangeCode = label === 'А-Д' ? 'A-D' :
                                label === 'Е-К' ? 'E-K' :
                                label === 'Л-Р' ? 'L-R' : 'S-YA';
                } else if (btn.dataset.range === 'CHERED') {
                    orthogramIds = [12, 13, 24, 26, 27, 271];
                } else {
                    alert('Неизвестное упражнение');
                    return;
                }

                const csrfToken = getCookie('csrftoken');
                if (!csrfToken) {
                    stillAnswerSection.innerHTML = '<p class="error">Сессия истекла. Обновите страницу.</p>';
                    return;
                }

                try {
                    let url, payload;
                    if (rangeCode && orthId) {
                        url = '/api/generate-alphabetical-exercise/';
                        payload = { orthogram_id: orthId, range: rangeCode };
                    } else if (orthogramIds) {
                        url = '/api/generate-exercise/';
                        payload = { orthogram_ids: orthogramIds };
                    } else {
                        throw new Error('Нет данных для генерации');
                    }

                    const response = await fetch(url, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': csrfToken
                        },
                        body: JSON.stringify(payload)
                    });

                    if (!response.ok) {
                        const errorText = await response.text();
                        throw new Error(`HTTP ${response.status}: ${errorText}`);
                    }

                    const data = await response.json();
                    if (!data.html) {
                        stillAnswerSection.innerHTML = `<p class="error">${data.error || 'Не удалось загрузить упражнение.'}</p>`;
                        return;
                    }

                    stillAnswerSection.innerHTML = `<h3 class="subtitle-still">${label}</h3>${data.html}`;

                    const container = stillAnswerSection.querySelector('.practice-text-container');
                    if (container) {
                        await processPracticeContainer(container);
                    }

                    setupCheckAnswers(stillAnswerSection);

                } catch (err) {
                    console.error('Ошибка при загрузке упражнения:', err);
                    stillAnswerSection.innerHTML = '<p class="error">Ошибка при загрузке упражнения.</p>';
                }
            };

            btn.removeEventListener('click', handler);
            btn.addEventListener('click', handler);
        });
    }

    // === ОСНОВНЫЕ ЗАДАНИЯ ===
    const taskButtons = document.querySelectorAll('.block-task-num .check-task');
    const answerSection = document.querySelector('.block-answer');

    if (taskButtons.length && answerSection) {
        taskButtons.forEach(button => {
            button.addEventListener('click', async (e) => {
                const taskNum = e.target.textContent.trim();

                if (taskNum === '1' || taskNum === '2') {
                    answerSection.innerHTML = '<p>Эти упражнения перемещены в раздел «Задание 9».</p>';
                    return;
                }

                const orthogramIds = e.target.dataset.orthogram;
                const range = e.target.dataset.range;
                answerSection.innerHTML = '';

                const renderExercise = async (orthogramId, rangeCode = null) => {
                    const csrfToken = getCookie('csrftoken');
                    if (!csrfToken) {
                        answerSection.innerHTML = '<p class="error">Сессия истекла. Обновите страницу.</p>';
                        return;
                    }

                    try {
                        let url, payload;
                        if (rangeCode !== null) {
                            url = '/api/generate-alphabetical-exercise/';
                            payload = { orthogram_id: orthogramId, range: rangeCode };
                        } else {
                            url = '/api/generate-exercise/';
                            payload = { orthogram_ids: Array.isArray(orthogramId) ? orthogramId : [orthogramId] };
                        }

                        const response = await fetch(url, {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                                'X-CSRFToken': csrfToken
                            },
                            body: JSON.stringify(payload)
                        });

                        const contentType = response.headers.get('content-type');
                        if (!contentType || !contentType.includes('application/json')) {
                            const errorHtml = await response.text();
                            console.error('Получен HTML вместо JSON:', errorHtml);
                            throw new Error(`Сервер вернул ошибку (статус ${response.status}).`);
                        }

                        if (!response.ok) {
                            const errorData = await response.json().catch(() => ({}));
                            throw new Error(errorData.error || `HTTP ${response.status}`);
                        }

                        const data = await response.json();
                        if (!data.html) {
                            answerSection.innerHTML = `<p class="error">${data.error || 'Не удалось загрузить упражнение.'}</p>`;
                            return;
                        }

                        answerSection.innerHTML = `<h2 class="title-practice">Задание № ${taskNum}</h2>${data.html}`;

                        const container = answerSection.querySelector('.practice-text-container');
                        if (container) {
                            await processPracticeContainer(container);
                        }

                        setupCheckAnswers(answerSection);

                    } catch (err) {
                        console.error(`Ошибка при загрузке упражнения ${orthogramId}${rangeCode ? `, диапазон ${rangeCode}` : ''}:`, err);
                        answerSection.innerHTML = '<p class="error">Не удалось загрузить упражнение. Попробуйте позже.</p>';
                    }
                };

                if (range && orthogramIds) {
                    renderExercise(orthogramIds, range);
                } else if (range) {
                    renderExercise(taskNum, range);
                } else if (orthogramIds) {
                    const ids = orthogramIds.split(',').map(id => id.trim());
                    renderExercise(ids);
                } else {
                    answerSection.innerHTML = `<p>Упражнение для задания ${taskNum} пока не готово.</p>`;
                }
            });
        });
    }

    // === ОРФОГРАММЫ ПО НОМЕРУ ===
    const orthogramButtons = document.querySelectorAll('.orthogram-buttons-container .orthogram-button');
    const orthogramAnswerSection = document.querySelector('.block-answer');

    if (orthogramButtons.length && orthogramAnswerSection) {
        orthogramButtons.forEach(button => {
            button.addEventListener('click', async (e) => {
                const displayNumber = e.target.textContent.trim();
                const orthogramId = e.target.dataset.orthogram;

                if (!orthogramId) {
                    alert(`Задание ${displayNumber} пока не готово.`);
                    return;
                }

                orthogramAnswerSection.innerHTML = '<p>Загрузка...</p>';

                const csrfToken = getCookie('csrftoken');
                if (!csrfToken) {
                    orthogramAnswerSection.innerHTML = '<p>Сессия истекла. Обновите страницу.</p>';
                    return;
                }

                try {
                    const response = await fetch('/api/generate-exercise/', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': csrfToken
                        },
                        body: JSON.stringify({ orthogram_ids: [orthogramId] })
                    });

                    if (!response.ok) {
                        const errorText = await response.text();
                        throw new Error(`HTTP ${response.status}: ${errorText}`);
                    }

                    const data = await response.json();
                    if (!data.html) {
                        orthogramAnswerSection.innerHTML = `<p>${data.error || 'Не удалось загрузить упражнение.'}</p>`;
                        return;
                    }

                    orthogramAnswerSection.innerHTML = `
                        <h2 class="title-practice">Орфограмма № ${displayNumber}</h2>
                        ${data.html}
                    `;

                    const container = orthogramAnswerSection.querySelector('.practice-text-container');
                    if (container) {
                        await processPracticeContainer(container);
                    }

                    setupCheckAnswers(orthogramAnswerSection);

                } catch (err) {
                    console.error('Ошибка загрузки орфограммы', orthogramId, err);
                    orthogramAnswerSection.innerHTML = '<p>Произошла ошибка. Попробуйте позже.</p>';
                }
            });
        });
    }
});