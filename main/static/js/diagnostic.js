// main/static/js/diagnostic.js

// === ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ: CSRF токен ===
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

// === ОБРАБОТЧИК СТАРТОВОЙ СТРАНИЦЫ (редирект на тест) ===
document.addEventListener('DOMContentLoaded', () => {
    const startBtn = document.getElementById('start-diagnostic-btn');
    if (startBtn) {
        const diagnosticType = startBtn.getAttribute('data-diagnostic-type');
        startBtn.addEventListener('click', (e) => {
            e.preventDefault();
            if (diagnosticType) {
                window.location.href = `/diagnostic/test/${diagnosticType}/`;
            } else {
                console.error('Ошибка: атрибут data-diagnostic-type пуст!');
            }
        });
    }
});

// === ОБРАБОТЧИК КНОПКИ ПРОВЕРКИ (на странице теста) ===
document.addEventListener('DOMContentLoaded', function () {
    const checkBtn = document.getElementById('check-diagnostic-btn');
    if (!checkBtn) return; // Кнопки нет — выходим

    const csrfToken = getCookie('csrftoken');
    if (!csrfToken) {
        console.error('CSRF токен не найден. Обновите страницу.');
        return;
    }

    checkBtn.addEventListener('click', async () => {
        const answers = {};

        // === 1. СБОР ОТВЕТОВ ИЗ ТЕКСТОВЫХ ПОЛЕЙ И ЧЕКБОКСОВ ===
        document.querySelectorAll('[data-question]').forEach(el => {
            const q = el.dataset.question;
            if (el.type === 'checkbox') {
                if (el.checked) {
                    if (!answers[q]) answers[q] = [];
                    answers[q].push(el.value);
                }
            } else {
                answers[q] = (el.value || '').trim();
            }
        });

        // === 2. СБОР ОТВЕТОВ ИЗ СМАЙЛИКОВ (задания 9-21) ===
        document.querySelectorAll('.smiley-button').forEach(btn => {
            const orthId = btn.dataset.orthId;
            if (!orthId) return;
            const icon = btn.querySelector('.smiley-icon');
            let selectedLetter = icon ? icon.textContent : '😊';

            // Нормализация для пунктограмм
            if (selectedLetter === ',') selectedLetter = '!';
            else if (selectedLetter === 'х') selectedLetter = '?';

            // Для задания 13: | → \
            if (orthId.startsWith('13-') && selectedLetter === '|') {
                selectedLetter = '\\';
            }

            answers[orthId] = selectedLetter;
        });

        // === 3. СБОР ОТВЕТОВ ЗАДАНИЯ 8 (select элементы) ===
        document.querySelectorAll('[data-question^="8_"]').forEach(select => {
            const val = (select.value || '').trim();
            if (val !== '') answers[select.dataset.question] = val;
        });

        // === 4. СБОР ОТВЕТОВ ЗАДАНИЯ 22 (select элементы) ===
        document.querySelectorAll('[data-question^="22_"]').forEach(select => {
            const val = (select.value || '').trim();
            if (val !== '') answers[select.dataset.question] = val;
        });

        // === 5. ОТПРАВКА НА СЕРВЕР ===
        try {
            const checkRes = await fetch('/api/check-starting-diagnostic/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({ answers: answers })
            });

            const result = await checkRes.json();

            if (result.error) {
                alert(`Ошибка: ${result.error}`);
                return;
            }

            // === 6. ПОДСВЕТКА РЕЗУЛЬТАТОВ ===

            // 6.1. Смайлики (задания 9-21)
            document.querySelectorAll('.smiley-button').forEach(btn => {
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

            // 6.2. Текстовые поля и чекбоксы (задания 1-7, 23-27)
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

            // 6.3. Select элементы задания 8
            document.querySelectorAll('[data-question^="8_"]').forEach(select => {
                const key = select.dataset.question;
                if (result.results && result.results[key]) {
                    const isCorrect = result.results[key].is_correct;
                    select.classList.remove('task-match-correct', 'task-match-incorrect');
                    if (isCorrect) {
                        select.classList.add('task-match-correct');
                    } else {
                        select.classList.add('task-match-incorrect');
                    }
                }
            });

            // 6.4. Select элементы задания 22
            document.querySelectorAll('[data-question^="22_"]').forEach(select => {
                const key = select.dataset.question;
                if (result.results && result.results[key]) {
                    const isCorrect = result.results[key].is_correct;
                    select.classList.remove('task-match-correct', 'task-match-incorrect');
                    if (isCorrect) {
                        select.classList.add('task-match-correct');
                    } else {
                        select.classList.add('task-match-incorrect');
                    }
                }
            });

            // === 7. ОТОБРАЖЕНИЕ ИТОГОВОГО РЕЗУЛЬТАТА ===
            const essayInput = document.querySelector('input[data-question="27"]');
            let essayScore = 0;

            if (essayInput) {
                const value = essayInput.value.trim();
                if (value !== '') {
                    const intValue = parseInt(value, 10);
                    if (!isNaN(intValue)) {
                        essayScore = Math.max(0, Math.min(22, intValue));
                    }
                }
            }

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

            let secondaryScore = conversionTable[primaryScore];
            if (secondaryScore === undefined) {
                secondaryScore = primaryScore > 50 ? 100 : 0;
            }

            // Формируем HTML результата
            let detailsHtml = `
                <div style="margin-top: 30px; padding: 20px; background: #f8f9fa; border-radius: 12px; border: 2px solid #dee2e6;">
                    <h3 style="margin: 0 0 15px; font-size: 20px; color: #212529;">Результаты проверки</h3>
                    <div style="font-size: 24px; font-weight: bold; color: #495057;">
                        Балл: ${primaryScore} из 50 (первичных) — ${secondaryScore} из 100 (вторичных)
                    </div>
            `;

            // Детализация по заданиям 8 и 22
            if (result.results && result.results['8']) {
                detailsHtml += `<p style="margin: 10px 0 0;"><strong>Задание 8:</strong> ${result.results['8'].correct_count || 0}/5 правильных = <strong>${result.results['8'].score || 0}/2</strong> баллов</p>`;
            }
            if (result.results && result.results['22']) {
                detailsHtml += `<p style="margin: 10px 0 0;"><strong>Задание 22:</strong> ${result.results['22'].correct_count || 0}/5 правильных = <strong>${result.results['22'].score || 0}/2</strong> баллов</p>`;
            }

            // Визуализация по заданиям 1-26
            detailsHtml += '<div style="margin: 20px 0; padding: 15px; background: #ffffff; border-radius: 8px; display: flex; flex-wrap: wrap; gap: 4px;">';
            for (let i = 1; i <= 26; i++) {
                const q = String(i);
                if (i === 8 || i === 22) {
                    const taskResult = result.results[q];
                    if (taskResult && taskResult.score !== undefined) {
                        const score = taskResult.score;
                        const symbols = score === 2 ? '++' : score === 1 ? '+-' : '--';
                        const colors = score === 2 ? ['#28a745', '#28a745'] : score === 1 ? ['#28a745', '#dc3545'] : ['#dc3545', '#dc3545'];
                        detailsHtml += `<span style="display:inline-flex; align-items:center; font-size:13px;"><b>${i}</b>`;
                        for (let j = 0; j < 2; j++) {
                            detailsHtml += `<span style="display:inline-block; width:14px; height:14px; line-height:14px; text-align:center; background:${colors[j]}; color:#fff; border-radius:2px; margin:0 1px; font-size:10px;">${symbols[j]}</span>`;
                        }
                        detailsHtml += '</span>';
                    }
                } else {
                    const taskResult = result.results[q];
                    if (taskResult && taskResult.is_correct !== undefined) {
                        const symbol = taskResult.is_correct ? '+' : '-';
                        const color = taskResult.is_correct ? '#28a745' : '#dc3545';
                        detailsHtml += `<span style="display:inline-flex; align-items:center; font-size:13px;"><b>${i}</b>`;
                        detailsHtml += `<span style="display:inline-block; width:16px; height:14px; line-height:14px; text-align:center; background:${color}; color:#fff; border-radius:2px; margin:0 2px; font-size:10px;">${symbol}</span></span>`;
                    }
                }
            }
            detailsHtml += '</div>';

            detailsHtml += '<p style="margin: 15px 0 0; font-size: 14px; color: #6c757d;"><strong>Рекомендации NEUROSTAT:</strong> Анализ слабых зон доступен после прохождения всех диагностик.</p>';
            detailsHtml += '</div>';

            // Вставляем результат после кнопки проверки
            let resultDiv = document.getElementById('diagnostic-results');
            if (!resultDiv) {
                resultDiv = document.createElement('div');
                resultDiv.id = 'diagnostic-results';
                checkBtn.parentNode.insertBefore(resultDiv, checkBtn.nextSibling);
            }
            resultDiv.innerHTML = detailsHtml;
            resultDiv.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

        } catch (err) {
            console.error('Ошибка проверки:', err);
            alert('Ошибка при проверке диагностики. Попробуйте ещё раз.');
        }
    });
});