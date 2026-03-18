// === planning_oge.js ===
// Тренажёры ОГЭ: одиночные задания, смайлики, проверка.

function getCookieOgePlanning(name) {
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

function getOgeJsonData(elementId) {
    const el = document.getElementById(elementId);
    if (!el) return null;
    try { return JSON.parse(el.textContent); } catch (e) { return null; }
}

function activateOgeSnippetInteractivity(container, taskNumber) {
    setTimeout(() => {
        const practiceLines = container.querySelectorAll('.practice-line');
        if (practiceLines.length > 0) {
            const allLetterGroups = {
                ...(getOgeJsonData('task4-letter-groups') || {}),
                ...(getOgeJsonData('task6-letter-groups') || {})
            };
            const allSubgroupLetters = {
                ...(getOgeJsonData('task4-subgroup-letters') || {}),
                ...(getOgeJsonData('task6-subgroup-letters') || {})
            };

            container.querySelectorAll('.practice-line').forEach(line => {
                const originalText = line.textContent || line.innerText || '';
                const regex = /\*([^*]+)\*/g;
                let result = originalText;
                let match;

                while ((match = regex.exec(originalText)) !== null) {
                    const maskId = match[1];
                    const fullMask = match[0];
                    const groupName = allLetterGroups[maskId] || '';
                    const letters = allSubgroupLetters[groupName] || ['а', 'о', 'е', 'и', 'я'];

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
            });

            container.querySelectorAll('.smiley-button').forEach(btn => {
                btn.addEventListener('click', function (e) {
                    e.stopPropagation();
                    const options = this.querySelector('.smiley-options');
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
                document.querySelectorAll('.smiley-options').forEach(el => el.style.display = 'none');
            });
        }
    }, 50);

    if (taskNumber === '4') {
        setTimeout(() => {
            const selects = container.querySelectorAll('.error-select');
            function updateSelects() {
                const usedValues = new Set();
                selects.forEach(sel => { if (sel.value && sel.value !== '-') usedValues.add(sel.value); });
                selects.forEach(sel => {
                    const curr = sel.value;
                    sel.querySelectorAll('option').forEach(opt => {
                        if (opt.value && opt.value !== '-') {
                            opt.disabled = usedValues.has(opt.value) && opt.value !== curr;
                        }
                    });
                });
            }
            selects.forEach(s => s.addEventListener('change', updateSelects));
            updateSelects();
        }, 100);
    }
}

function handleOgeSingleTask(taskNumber) {
    const container = document.querySelector('.block-answer');
    if (!container) return;

    container.innerHTML = `<div class="loading" style="text-align:center; padding: 20px;">Загрузка задания ${taskNumber}...</div>`;

    document.querySelectorAll('.task-buttons .check-task').forEach(btn => btn.classList.remove('active'));

    fetch('/api/generate-oge-single-task/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookieOgePlanning('csrftoken')
        },
        body: JSON.stringify({ task_number: taskNumber })
    })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                container.innerHTML = `<div class="error" style="color:red;">${data.error}</div>`;
            } else {
                container.innerHTML = data.html;
                activateOgeSnippetInteractivity(container, taskNumber);

                const checkBtn = container.querySelector('.check-task-single');
                if (checkBtn) {
                    checkBtn.addEventListener('click', async () => {
                        checkBtn.disabled = true;
                        checkBtn.textContent = 'Проверяем...';

                        const answers = {};
                        container.querySelectorAll('[data-question-number]').forEach(block => {
                            const qNum = block.dataset.questionNumber;
                            const checked = block.querySelectorAll('input[type="checkbox"]:checked');
                            if (checked.length > 0) {
                                answers[qNum] = Array.from(checked).map(cb => cb.value);
                            }
                            const textInput = block.querySelector('input[type="text"][data-question]');
                            if (textInput && textInput.value.trim()) {
                                answers[textInput.dataset.question] = textInput.value.trim();
                            }
                            block.querySelectorAll('.smiley-button').forEach(sm => {
                                const mId = sm.dataset.maskId;
                                const icon = sm.querySelector('.smiley-icon');
                                if (mId && icon && icon.textContent !== '😊') {
                                    answers[mId] = icon.textContent;
                                }
                            });
                            block.querySelectorAll('.error-select').forEach(sel => {
                                const letter = sel.dataset.letter;
                                if (letter && sel.value && sel.value !== '-') {
                                    answers[`4-${letter}`] = sel.value;
                                }
                            });
                        });

                        try {
                            const checkRes = await fetch('/api/check-oge-diagnostic/', {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json',
                                    'X-CSRFToken': getCookieOgePlanning('csrftoken'),
                                },
                                body: JSON.stringify({ answers }),
                            });

                            const checkData = await checkRes.json();
                            container.querySelectorAll('.task-score-display').forEach(el => el.remove());
                            container.querySelectorAll('.task-result-message').forEach(el => el.remove());

                            let hasErrors = false;

                            if (checkData.results) {
                                for (const [key, val] of Object.entries(checkData.results)) {
                                    if (val.is_correct !== undefined && !val.is_correct) hasErrors = true;

                                    // Смайлики ищем прямо в контейнере (маски вида "5-1", "6-1" и т.д.)
                                    if (key.match(/^\d+-\d+$/) && !key.startsWith('4-')) {
                                        const smBtn = container.querySelector(`.smiley-button[data-mask-id="${key}"]`);
                                        if (smBtn) {
                                            const icon = smBtn.querySelector('.smiley-icon');
                                            if (icon) {
                                                icon.style.backgroundColor = val.is_correct ? '#c8e6c9' : '#ffcdd2';
                                                icon.style.borderRadius = '4px';
                                            }
                                        }
                                        continue;
                                    }

                                    let domKey = key;
                                    if (key.startsWith('4-')) domKey = '4';

                                    const qBlock = container.querySelector(`[data-question-number="${domKey}"]`);
                                    if (!qBlock) continue;

                                    if (key.startsWith('4-')) {
                                        const sel = qBlock.querySelector(`select[data-letter="${key.split('-')[1]}"]`);
                                        if (sel) {
                                            sel.style.backgroundColor = val.is_correct ? '#c8e6c9' : '#ffcdd2';
                                            sel.style.borderColor = val.is_correct ? '#4CAF50' : '#f44336';
                                        }
                                        continue;
                                    }

                                    if (val.correct_answer) {
                                        const correctArr = String(val.correct_answer).toLowerCase().split('');
                                        qBlock.querySelectorAll('input[type="checkbox"]').forEach(cb => {
                                            const label = cb.closest('label');
                                            const isCorrectCb = correctArr.includes(cb.value.toLowerCase());
                                            if (cb.checked) {
                                                cb.style.outline = isCorrectCb ? '2px solid #4CAF50' : '2px solid #f44336';
                                                cb.style.outlineOffset = '2px';
                                                if (label) {
                                                    label.style.color = isCorrectCb ? '#4CAF50' : '#f44336';
                                                    label.style.fontWeight = 'bold';
                                                }
                                            }
                                        });
                                    }

                                    const ti = qBlock.querySelector('input[type="text"]');
                                    if (ti) {
                                        ti.style.backgroundColor = val.is_correct ? '#c8e6c9' : '#ffcdd2';
                                        ti.style.borderColor = val.is_correct ? '#4CAF50' : '#f44336';
                                    }
                                }
                            }

                            const resultMsg = document.createElement('div');
                            resultMsg.className = 'task-result-message';
                            resultMsg.style.cssText = 'margin-top: 15px; font-weight: bold; font-size: 1.1em;';
                            if (hasErrors) {
                                if (taskNumber === '10-12') {
                                    resultMsg.innerHTML = '<span style="color: #f44336;">❌ Есть ошибки!</span>';
                                } else {
                                    resultMsg.innerHTML = '<span style="color: #f44336;">❌ Есть ошибки! По номерам пунктограмм найди информацию в планингах</span>';
                                }
                            } else {
                                resultMsg.innerHTML = '<span style="color: #4CAF50;">✅ Все правильно!</span>';
                            }
                            container.appendChild(resultMsg);
                            checkBtn.textContent = 'Готово!';
                        } catch (e) {
                            alert('Ошибка проверки');
                            checkBtn.disabled = false;
                            checkBtn.textContent = 'Проверить';
                        }
                    });
                }
            }
        })
        .catch(error => {
            console.error('Ошибка:', error);
            container.innerHTML = `<div class="error" style="color:red;">Ошибка загрузки</div>`;
        });
}