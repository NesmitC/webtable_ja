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
    if (orthId == '6') {
        return ['ъ', 'ь', '/'];
    }
    if (orthogramLettersCache[orthId]) {
        return orthogramLettersCache[orthId];
    }
    try {
        const response = await fetch(`/api/orthogram/${orthId}/letters/`);
        const data = await response.json();
        orthogramLettersCache[orthId] = data.letters || ['а', 'о', 'е', 'и', 'я'];
        return orthogramLettersCache[orthId];
    } catch (err) {
        return ['а', 'о', 'е', 'и', 'я'];
    }
}

// --- Замена *N* на смайлы ---
async function replaceOrthMarkersInText(text) {
    const wordsWithMasks = text.split(/,\s*/);
    const processedWords = [];
    for (const word of wordsWithMasks) {
        const matches = [...word.matchAll(/\*(\d+)\*/g)];
        if (matches.length === 0) {
            processedWords.push(word);
            continue;
        }
        let result = '';
        let lastIndex = 0;
        for (const match of matches) {
            const orthId = match[1];
            const letters = await getLettersForOrthogram(orthId);
            const liItems = letters.map(letter =>
                `<li data-letter="${letter}">${letter}</li>`
            ).join('');
            result += word.slice(lastIndex, match.index);
            result += `
                <span class="smiley-button" 
                      data-orth-id="${orthId}" 
                      data-word-template="${word}">
                    <span class="smiley-icon">😊</span>
                    <ul class="smiley-options">${liItems}</ul>
                </span>
            `;
            lastIndex = match.index + match[0].length;
        }
        result += word.slice(lastIndex);
        processedWords.push(result);
    }
    return processedWords.join(', ');
}

// --- Обработчик проверки ---
function setupCheckAnswers() {
    document.querySelectorAll('.check-answers').forEach(button => {
        if (button._clickHandler) {
            button.removeEventListener('click', button._clickHandler);
        }
        button._clickHandler = function () {
            const article = button.closest('.article-practice');
            const userLetters = [];
            const smileyButtons = article.querySelectorAll('.smiley-button');
            let hasSelection = false;

            smileyButtons.forEach(smileyButton => {
                const selectedLetter = smileyButton.querySelector('.smiley-icon').textContent;
                if (selectedLetter !== '😊') hasSelection = true;
                userLetters.push(selectedLetter);
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
                body: JSON.stringify({ user_words: userLetters })
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
                article.querySelectorAll('.smiley-icon').forEach((icon, i) => {
                    icon.classList.remove('selected', 'correct', 'incorrect');
                    if (results[i]) {
                        icon.classList.add('correct');
                    } else {
                        icon.classList.add('incorrect');
                    }
                });
                return fetch('/api/get-advice/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken
                    },
                    body: JSON.stringify({ user_words: userLetters })
                });
            })
            .then(r => r.json())
            .then(data => {
                const adviceBlock = article.querySelector('.advice-block');
                if (adviceBlock) {
                    adviceBlock.textContent = data.advice;
                    adviceBlock.style.display = 'block';
                }
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
    // Инициализация стартовых упражнений
    document.querySelectorAll('.practice-text').forEach(async (paragraph) => {
        const originalText = paragraph.textContent.trim();
        const processedHtml = await replaceOrthMarkersInText(originalText);
        paragraph.innerHTML = processedHtml;
    });

    // Глобальный обработчик кликов по смайликам и выпадающим спискам
    document.addEventListener('click', (e) => {
        const target = e.target;
        if (target.classList.contains('smiley-icon')) {
            e.stopPropagation();
            const button = target.closest('.smiley-button');
            const options = button.querySelector('.smiley-options');
            options.style.display = options.style.display === 'block' ? 'none' : 'block';
        }
        if (target.tagName === 'LI' && target.hasAttribute('data-letter')) {
            const button = target.closest('.smiley-button');
            const selectedLetter = target.dataset.letter;
            const icon = button.querySelector('.smiley-icon');
            icon.textContent = selectedLetter;
            icon.className = 'smiley-icon selected';
            button.querySelector('.smiley-options').style.display = 'none';
        }
        if (!e.target.closest('.smiley-button')) {
            document.querySelectorAll('.smiley-options').forEach(el => {
                el.style.display = 'none';
            });
        }
    });

    // Обработчики кнопок "Задание №N"
    const taskButtons = document.querySelectorAll('.block-task-num .check-task');
    const answerSection = document.querySelector('.block-answer');

    taskButtons.forEach(button => {
        button.addEventListener('click', async (e) => {
            const taskNum = e.target.textContent.trim();
            const orthogramIds = e.target.dataset.orthogram;
            const range = e.target.dataset.range;
            answerSection.innerHTML = '';

            const renderExercise = async (orthogramId, rangeCode = null) => {
                const csrfToken = getCookie('csrftoken');
                if (!csrfToken) {
                    answerSection.innerHTML = '<p>Сессия истекла. Обновите страницу.</p>';
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

                    if (!response.ok) {
                        const errorText = await response.text();
                        throw new Error(`HTTP ${response.status}: ${errorText}`);
                    }

                    const data = await response.json();
                    if (!data.html) {
                        answerSection.innerHTML = `<p>${data.error || 'Не удалось загрузить упражнение.'}</p>`;
                        return;
                    }

                    let content = `<h2 class="title-practice">Задание № ${taskNum}</h2>${data.html}`;

                    if (orthogramId === '1') {
                        content = `
                            <h2 class="title-practice">Задание № ${taskNum}</h2>
                            <div class="sub-range-buttons">
                                <button class="check-task-sub" data-range="A-O">А-О</button>
                                <button class="check-task-sub" data-range="P-S">П-С</button>
                                <button class="check-task-sub" data-range="T-YA">Т-Я</button>
                            </div>
                            ${data.html}
                        `;
                    } else if (orthogramId === '2') {
                        content = `
                            <h2 class="title-practice">Задание № ${taskNum}</h2>
                            <div class="sub-range-buttons">
                                <button class="check-task-sub" data-range="A-D">А-Д</button>
                                <button class="check-task-sub" data-range="E-K">Е-К</button>
                                <button class="check-task-sub" data-range="L-R">Л-Р</button>
                                <button class="check-task-sub" data-range="S-YA">С-Я</button>
                            </div>
                            ${data.html}
                        `;
                    }

                    answerSection.innerHTML = content;
                    const newText = answerSection.querySelector('.practice-text');
                    if (newText) {
                        const originalText = newText.textContent.trim();
                        const processedHtml = await replaceOrthMarkersInText(originalText);
                        newText.innerHTML = processedHtml;
                    }

                    setupCheckAnswers();

                    answerSection.querySelectorAll('.check-task-sub').forEach(btn => {
                        const handler = () => renderExercise(orthogramId, btn.dataset.range);
                        btn.removeEventListener('click', handler);
                        btn.addEventListener('click', handler);
                    });
                } catch (err) {
                    console.error(`Ошибка при загрузке упражнения ${orthogramId}${rangeCode ? `, диапазон ${rangeCode}` : ''}:`, err);
                    answerSection.innerHTML = '<p>Ошибка при загрузке упражнения.</p>';
                }
            };

            if (taskNum === '1') {
                renderExercise('1', 'A-O');
                return;
            }
            if (taskNum === '2') {
                renderExercise('2', 'A-D');
                return;
            }
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
});