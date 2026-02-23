// === diagnostic_oge.js ===
// JS для ОГЭ-диагностики: загрузка, смайлики, сбор ответов, проверка.

function getCookieOge(name) {
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

// Вспомогательная: парсинг JSON из <script> тегов
function getOgeJsonData(elementId) {
    const el = document.getElementById(elementId);
    if (!el) return {};
    try {
        return JSON.parse(el.textContent || '{}');
    } catch (e) {
        return {};
    }
}

// Получение букв для орфограммы ОГЭ
function getOgeLettersForOrthogram(orthId) {
    const subgroupLettersMap = getOgeJsonData('task6-subgroup-letters');
    const key = 'orth_' + orthId;
    if (subgroupLettersMap[key]) {
        return subgroupLettersMap[key];
    }
    // Фоллбэк
    return ['а', 'о', 'е', 'и', 'я'];
}

// Получение символов для пунктуации ОГЭ
function getOgePunktumLetters(groupName) {
    const subgroupLettersMap = getOgeJsonData('task4-subgroup-letters');
    if (subgroupLettersMap[groupName]) {
        return subgroupLettersMap[groupName];
    }
    return ['!', '?', '—', ':', '«»'];
}


document.addEventListener('DOMContentLoaded', function () {
    const startBtn = document.getElementById('start-diagnostic-btn');
    if (!startBtn) return;

    const csrfToken = getCookieOge('csrftoken');
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
            // 1. Загружаем диагностику ОГЭ
            const res = await fetch('/api/generate-oge-diagnostic/', {
                method: 'POST',
                headers: { 'X-CSRFToken': csrfToken },
            });

            const data = await res.json();
            if (data.error) throw new Error(data.error);

            contentDiv.innerHTML = data.html;

            // 2. Ждем обновления DOM
            setTimeout(async () => {
                // === УНИВЕРСАЛЬНАЯ ОБРАБОТКА ВСЕХ ПРАКТИЧЕСКИХ СТРОК ===
                const practiceBlocks = contentDiv.querySelectorAll('[data-question-number]');

                // Данные для смайликов
                const letterGroupsTask4 = getOgeJsonData('task4-letter-groups');
                const letterGroupsTask6 = getOgeJsonData('task6-letter-groups');

                // Объединяем все letter groups
                const allLetterGroups = Object.assign({}, letterGroupsTask4, letterGroupsTask6);

                for (const block of practiceBlocks) {
                    const practiceLines = block.querySelectorAll('.practice-line');

                    for (const line of practiceLines) {
                        const originalText = line.textContent || line.innerText || '';
                        if (!originalText.trim()) continue;

                        const regex = /\*([^*]+)\*/g;
                        let result = originalText;
                        let match;

                        while ((match = regex.exec(originalText)) !== null) {
                            const maskId = match[1];
                            const fullMask = match[0];

                            // Определяем группу для кнопок
                            let letters = ['а', 'о', 'е', 'и', 'я'];
                            const groupName = allLetterGroups[maskId] || '';

                            if (groupName.startsWith('punktum_')) {
                                letters = getOgePunktumLetters(groupName);
                            } else if (groupName.startsWith('orth_')) {
                                const orthId = groupName.replace('orth_', '');
                                letters = getOgeLettersForOrthogram(orthId);
                            }

                            const optionsHtml = letters
                                .map(letter => `<span class="smiley-option" data-value="${letter}">${letter}</span>`)
                                .join('');

                            const smileyHtml = `
                                <span class="smiley-button" data-mask-id="${maskId}" title="Кликни для выбора">
                                    <span class="smiley-icon">😊</span>
                                    <span class="smiley-options" style="display:none; flex-direction: column; text-align: center; gap: 4px; padding: 6px; border-radius: 8px;">${optionsHtml}</span>
                                </span>
                            `;

                            result = result.replace(fullMask, smileyHtml);
                        }

                        line.innerHTML = result;
                    }
                }

                // === АКТИВАЦИЯ ИНТЕРАКТИВНЫХ СМАЙЛИКОВ ===
                document.querySelectorAll('.smiley-button').forEach(btn => {
                    btn.addEventListener('click', function (e) {
                        e.stopPropagation();
                        const options = this.querySelector('.smiley-options');
                        // Закрываем все остальные
                        document.querySelectorAll('.smiley-options').forEach(el => {
                            if (el !== options) el.style.display = 'none';
                        });
                        options.style.display = options.style.display === 'flex' ? 'none' : 'flex';

                        options.querySelectorAll('.smiley-option').forEach(opt => {
                            opt.onclick = function (ev) {
                                ev.stopPropagation();
                                const icon = btn.querySelector('.smiley-icon');
                                icon.textContent = this.dataset.value;
                                icon.classList.add('selected');
                                options.style.display = 'none';
                            };
                        });
                    });
                });

                document.addEventListener('click', () => {
                    document.querySelectorAll('.smiley-options').forEach(el => {
                        el.style.display = 'none';
                    });
                });

            }, 50);

            // === АКТИВАЦИЯ SELECT (задание 3) ===
            function setupOgeUniqueSelects() {
                function setupSelects(containerSelector, selectClass) {
                    const container = document.querySelector(containerSelector);
                    if (!container) return;
                    const selects = container.querySelectorAll(selectClass);
                    if (selects.length === 0) return;

                    function updateSelects() {
                        const usedValues = new Set();
                        selects.forEach(sel => {
                            if (sel.value && sel.value !== '-') {
                                usedValues.add(sel.value);
                            }
                        });
                        selects.forEach(sel => {
                            const currentValue = sel.value;
                            sel.querySelectorAll('option').forEach(opt => {
                                if (opt.value && opt.value !== '-') {
                                    opt.disabled = usedValues.has(opt.value) && opt.value !== currentValue;
                                }
                            });
                        });
                    }

                    selects.forEach(sel => sel.addEventListener('change', updateSelects));
                    updateSelects();
                }

                // Задание 3 ОГЭ (тот же формат, что задание 8 ЕГЭ)
                setupSelects('[data-question-number="3"]', '.error-select');
            }

            setTimeout(setupOgeUniqueSelects, 100);

            // Убираем отдельные кнопки проверки из вложенных шаблонов
            setTimeout(() => {
                document.querySelectorAll('.check-task-eight, .check-task-twotwo').forEach(btn => btn.remove());
            }, 120);

            // 3. Добавляем кнопку проверки
            const checkBtn = document.createElement('button');
            checkBtn.className = 'check-task green';
            checkBtn.textContent = 'Проверить всё';
            checkBtn.style.cssText = 'margin-top: 30px; display: block; margin: 30px auto 0 auto;';
            contentDiv.appendChild(checkBtn);

            // 4. Обработчик проверки
            checkBtn.addEventListener('click', async () => {
                checkBtn.disabled = true;
                checkBtn.textContent = 'Проверяем...';

                const answers = {};

                // Собираем все ответы
                contentDiv.querySelectorAll('[data-question-number]').forEach(block => {
                    const qNum = block.dataset.questionNumber;

                    // Чекбоксы
                    const checked = block.querySelectorAll('input[type="checkbox"]:checked');
                    if (checked.length > 0) {
                        answers[qNum] = Array.from(checked).map(cb => cb.value);
                    }

                    // Текстовые инпуты
                    const textInput = block.querySelector('input[type="text"][data-question]');
                    if (textInput && textInput.value.trim()) {
                        answers[textInput.dataset.question] = textInput.value.trim();
                    }

                    // Числовые инпуты
                    const numInput = block.querySelector('input[type="number"][data-question]');
                    if (numInput && numInput.value.trim()) {
                        answers[numInput.dataset.question] = numInput.value.trim();
                    }

                    // Смайлики
                    block.querySelectorAll('.smiley-button').forEach(btn => {
                        const maskId = btn.dataset.maskId;
                        const icon = btn.querySelector('.smiley-icon');
                        if (maskId && icon && icon.textContent !== '😊') {
                            answers[maskId] = icon.textContent;
                        }
                    });

                    // Выпадающие списки (задание 3)
                    block.querySelectorAll('.error-select').forEach(sel => {
                        const letter = sel.dataset.letter;
                        if (letter && sel.value && sel.value !== '-') {
                            answers[`3-${letter}`] = sel.value;
                        }
                    });
                });

                try {
                    const checkRes = await fetch('/api/check-oge-diagnostic/', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': csrfToken,
                        },
                        body: JSON.stringify({ answers }),
                    });

                    const checkData = await checkRes.json();

                    if (checkData.error) {
                        alert('Ошибка: ' + checkData.error);
                        checkBtn.disabled = false;
                        checkBtn.textContent = 'Проверить всё';
                        return;
                    }

                    // Подсветка результатов
                    if (checkData.results) {
                        for (const [key, val] of Object.entries(checkData.results)) {
                            // Подсветка общего блоку
                            const qBlock = contentDiv.querySelector(`[data-question-number="${key}"]`);

                            if (qBlock && val.score !== undefined) {
                                // Добавляем Баллы и правильный ответ в конец блока
                                let scoreHtml = `<div style="margin-top: 15px; font-weight: bold;">`;
                                const scoreColor = val.score === val.max_score ? '#4CAF50' : '#f44336';
                                scoreHtml += `<span style="color: ${scoreColor}">Баллов: ${val.score}. `;
                                if (val.score < val.max_score || key === '3' || key === '5') {
                                    if (key === '4' || key === '6') {
                                        // Форматируем ответы в столбик: 1 - а, 2 - б...
                                        const ansArr = String(val.correct_answer).split('');
                                        const formattedAns = ansArr.map((char, index) => `${index + 1} - ${char}`).join('<br>');
                                        scoreHtml += `Правильные ответы:<br>${formattedAns}</span>`;
                                    } else {
                                        scoreHtml += `Правильный ответ: ${val.correct_answer}</span>`;
                                    }
                                } else {
                                    scoreHtml += `</span>`;
                                }
                                if (val.extras) {
                                    scoreHtml += `<br><span style="color: ${scoreColor}">${val.extras}</span>`;
                                }
                                scoreHtml += `</div>`;

                                // Удаляем старый если есть
                                const oldScore = qBlock.querySelector('.task-score-display');
                                if (oldScore) oldScore.remove();

                                const scoreDiv = document.createElement('div');
                                scoreDiv.className = 'task-score-display';
                                scoreDiv.innerHTML = scoreHtml;
                                qBlock.appendChild(scoreDiv);

                                // Подсветка чекбоксов и инпутов внутри блока
                                const correctAnsStr = String(val.correct_answer).toLowerCase();
                                const correctArr = (key === '1' || key === '2' || key === '5' || key === '9' || key === '10') ? correctAnsStr.split('') : [];

                                // Инпуты (7, 8, 11)
                                const textInput = qBlock.querySelector('input[type="text"][data-question]');
                                if (textInput && (key === '7' || key === '8' || key === '11')) {
                                    textInput.style.backgroundColor = val.is_correct ? '#c8e6c9' : '#ffcdd2';
                                    textInput.style.borderColor = val.is_correct ? '#4CAF50' : '#f44336';
                                }

                                // Чекбоксы (1, 2, 5, 9, 10)
                                const checkboxes = qBlock.querySelectorAll('input[type="checkbox"]');
                                checkboxes.forEach(cb => {
                                    const valStr = cb.value;
                                    const label = cb.closest('label') || cb.parentElement;
                                    const isCorrectCb = correctArr.includes(valStr);

                                    // Галочка в чек-боксе, который правильный вообще
                                    if (isCorrectCb && !cb.checked) {
                                        // Пользователь не выбрал, но это правильный ответ. Покажем зелёную галочку.
                                        const span = cb.nextElementSibling;
                                        if (span && !span.textContent.startsWith('☑')) {
                                            span.innerHTML = '<span style="color:#4CAF50; font-weight:bold;">☑</span> ' + span.innerHTML;
                                        }
                                    }

                                    // Зеленая/красная обводка при ответе пользователя
                                    if (cb.checked) {
                                        label.style.border = isCorrectCb ? '2px solid #4CAF50' : '2px solid #f44336';
                                        label.style.borderRadius = '4px';
                                        label.style.padding = '2px 4px';
                                        label.style.display = 'inline-block';

                                        const span = cb.nextElementSibling;
                                        if (span) {
                                            const icon = isCorrectCb ? '<span style="color:#4CAF50; font-weight:bold;">☑</span> ' : '<span style="color:#f44336; font-weight:bold;">☒</span> ';
                                            if (!span.textContent.startsWith('☑') && !span.textContent.startsWith('☒')) {
                                                span.innerHTML = icon + span.innerHTML;
                                            }
                                        }
                                    }
                                });
                            }

                            // Выпадающие списки (задание 3)
                            if (key.startsWith('3-')) {
                                const sel = contentDiv.querySelector(`select[data-letter="${key.split('-')[1]}"]`);
                                if (sel) {
                                    sel.style.backgroundColor = val.is_correct ? '#c8e6c9' : '#ffcdd2';
                                    sel.style.borderColor = val.is_correct ? '#4CAF50' : '#f44336';
                                }
                            }

                            // Смайлики (задания 4, 6)
                            const smiley = contentDiv.querySelector(`.smiley-button[data-mask-id="${key}"]`);
                            if (smiley) {
                                const icon = smiley.querySelector('.smiley-icon');
                                if (icon) {
                                    icon.style.backgroundColor = val.is_correct ? '#c8e6c9' : '#ffcdd2';
                                    icon.style.borderRadius = '4px';
                                    icon.style.padding = '2px 4px';
                                }
                            }
                        }
                    }

                    // Отображение аналитики
                    resultSection.style.display = 'block';
                    resultDetails.innerHTML = `
                        <div style="margin-bottom: 15px; font-size: 1.2em;">
                            <strong>Результаты проверки БАЛЛОВ: ${checkData.total_score}</strong>
                        </div>
                    `;

                    resultSection.scrollIntoView({ behavior: 'smooth' });

                    checkBtn.textContent = 'Готово!';

                } catch (err) {
                    console.error('Ошибка проверки:', err);
                    alert('Ошибка проверки: ' + err.message);
                    checkBtn.disabled = false;
                    checkBtn.textContent = 'Проверить всё';
                }
            });

        } catch (err) {
            console.error('Ошибка загрузки:', err);
            contentDiv.innerHTML = '<p style="color: red;">Ошибка загрузки диагностики: ' + err.message + '</p>';
            startBtn.disabled = false;
            startBtn.textContent = 'Начать диагностику ОГЭ';
        }
    });
});
