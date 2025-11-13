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
    if (['21', '32', '36', '46', '54', '56', '58', '581'].includes(orthId)) {
        return ['/', '|'];
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

            if (['21', '32', '36', '46', '54', '56', '58', '581'].includes(orthId)) {
                // Показываем "(не) 😊" 
                result += `
                    <span class="smiley-button" 
                          data-orth-id="${orthId}" 
                          data-word-template="${word}">
                        (не)&nbsp;<span class="smiley-icon">😊</span>
                        <ul class="smiley-options">${liItems}</ul>
                    </span>
                `;
            } else {
                result += `
                    <span class="smiley-button" 
                          data-orth-id="${orthId}" 
                          data-word-template="${word}">
                        <span class="smiley-icon">😊</span>
                        <ul class="smiley-options">${liItems}</ul>
                    </span>
                `;
            }

            lastIndex = match.index + match[0].length;
        }

        result += word.slice(lastIndex);
        processedWords.push(result);
    }

    return processedWords.join(', ');
}


// --- Обработчик проверки ---
function setupCheckAnswers(container = document) {
    container.querySelectorAll('.check-answers').forEach(button => {
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
                let adviceBlock = article.querySelector('.advice-block');
                if (!adviceBlock) {
                    adviceBlock = document.createElement('div');
                    adviceBlock.className = 'advice-block';
                    article.appendChild(adviceBlock);
                }
                adviceBlock.textContent = data.advice;
                adviceBlock.style.display = 'block';
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
    // Инициализация стартовых упражнений (если есть на странице)
    document.querySelectorAll('.practice-text').forEach(async (paragraph) => {
        const originalText = paragraph.textContent.trim();
        const processedHtml = await replaceOrthMarkersInText(originalText);
        paragraph.innerHTML = processedHtml;
    });

    setupCheckAnswers(); // Подключаем проверку для стартовых упражнений

    // Глобальный обработчик выпадающих списков
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
                icon.textContent = selectedLetter; // ← Просто вставляем символ
                icon.className = 'smiley-icon selected';
            }

            const options = button.querySelector('.smiley-options');
            if (options) {
                options.style.display = 'none';
            }
            return;
        }

        if (!e.target.closest('.smiley-button')) {
            document.querySelectorAll('.smiley-options').forEach(el => {
                el.style.display = 'none';
            });
        }
    });

    // === ЗАДАНИЕ 9: СТАТИЧЕСКИЕ УПРАЖНЕНИЯ ===
    const stillButtons = document.querySelectorAll('.check-task-still');
    const stillAnswerSection = document.querySelector('.block-answer-still-content');

    if (stillAnswerSection && stillButtons.length) {
        stillButtons.forEach(btn => {
            const handler = async () => {
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
                    // Чередующиеся гласные
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

                    // Вставляем новое упражнение
                    stillAnswerSection.innerHTML = `<h3 class="subtitle-still">${label}</h3>${data.html}`;

                    const newText = stillAnswerSection.querySelector('.practice-text');
                    if (newText) {
                        const originalText = newText.textContent.trim();
                        newText.innerHTML = await replaceOrthMarkersInText(originalText);
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

    // === ОСНОВНЫЕ ЗАДАНИЯ: 1–8, 10–27 (ЕГЭ) ===
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

                        answerSection.innerHTML = `<h2 class="title-practice">Задание № ${taskNum}</h2>${data.html}`;

                        const newText = answerSection.querySelector('.practice-text');
                        if (newText) {
                            const originalText = newText.textContent.trim();
                            newText.innerHTML = await replaceOrthMarkersInText(originalText);
                        }

                        setupCheckAnswers(answerSection);

                    } catch (err) {
                        console.error(`Ошибка при загрузке упражнения ${orthogramId}${rangeCode ? `, диапазон ${rangeCode}` : ''}:`, err);
                        answerSection.innerHTML = '<p>Ошибка при загрузке упражнения.</p>';
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

    // === НОВЫЙ БЛОК: ВЫБОР ОРФОГРАММ ПО НОМЕРУ (5–7 кл) ===
    const orthogramButtons = document.querySelectorAll('.orthogram-buttons-container .orthogram-button');
    const orthogramAnswerSection = document.querySelector('.block-answer'); // или отдельный контейнер

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

                    const newText = orthogramAnswerSection.querySelector('.practice-text');
                    if (newText) {
                        const originalText = newText.textContent.trim();
                        newText.innerHTML = await replaceOrthMarkersInText(originalText);
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