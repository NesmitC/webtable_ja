/* main/static/js/checkpoint.js
   Рубежный тест: сбор ответов и подсветка — ровно как в текущей/контрольной
   диагностике (diagnostic.js): классы task-match-correct/incorrect для
   инпутов, чекбоксов и селектов, correct/incorrect для букв под смайликами.
   Ключи задания 8: '8_А'… (селекты размечены data-error-letter). */
(function () {
    'use strict';

    function getCookie(name) {
        const matches = document.cookie.match(
            new RegExp('(?:^|; )' + name.replace(/([\.$?*|{}\(\)\[\]\\\/\+^])/g, '\\$1') + '=([^;]*)'));
        return matches ? decodeURIComponent(matches[1]) : '';
    }

    const sanitizer = (val) => {
        let clean = val.replace(/[\s\t\n\r]+/g, '');
        clean = clean.replace(/[^0-9а-яёА-ЯЁ]/g, '');
        clean = clean.toLowerCase();
        const hasNum = /\d/.test(clean);
        const hasLet = /[а-яё]/.test(clean);
        if (hasNum && hasLet) {
            clean = /\d/.test(clean.charAt(0))
                ? clean.replace(/[^0-9]/g, '')
                : clean.replace(/[^а-яё]/g, '');
        } else if (hasNum) {
            clean = clean.replace(/[^0-9]/g, '');
        } else {
            clean = clean.replace(/[^а-яё]/g, '');
        }
        const isNum = /^\d+$/.test(clean);
        const maxLen = isNum ? 7 : 17;
        return clean.length > maxLen ? clean.substring(0, maxLen) : clean;
    };

    function initInputs() {
        document.querySelectorAll('input[data-question]').forEach(input => {
            if (input.type === 'checkbox') return;
            input.setAttribute('autocomplete', 'off');
            input.setAttribute('spellcheck', 'false');
            input.addEventListener('input', (e) => {
                const newVal = sanitizer(e.target.value);
                if (e.target.value !== newVal) e.target.value = newVal;
            });
            input.addEventListener('paste', (e) => {
                e.preventDefault();
                const pasted = (e.clipboardData || window.clipboardData).getData('text');
                const start = input.selectionStart;
                const end = input.selectionEnd;
                const newValue = input.value.substring(0, start) + pasted + input.value.substring(end);
                input.value = sanitizer(newValue);
                input.dispatchEvent(new Event('input'));
            });
            input.addEventListener('contextmenu', e => e.preventDefault());
        });
    }

    function collectAnswers() {
        const answers = {};
        // Текстовые поля и чекбоксы (задания 1-7)
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
        // Задание 8: селекты соответствия (data-error-letter -> '8_А')
        document.querySelectorAll('.task-eight-select').forEach(sel => {
            const letter = sel.dataset.errorLetter;
            if (!letter) return;
            answers['8_' + letter] = (sel.value || '').trim();
        });
        // Задание 9: смайлики (как в diagnostic.js)
        document.querySelectorAll('.smiley-button').forEach(btn => {
            const orthId = btn.dataset.orthId;
            if (!orthId) return;
            const icon = btn.querySelector('.smiley-icon');
            let selectedLetter = icon ? icon.textContent : '😊';
            if (selectedLetter === ',') selectedLetter = '!';
            else if (selectedLetter === 'х') selectedLetter = '?';
            answers[orthId] = selectedLetter;
        });
        return answers;
    }

    function applyResults(results) {
        // Инпуты и чекбоксы (задания 1-7) — классы как в diagnostic.js
        document.querySelectorAll('[data-question]').forEach(el => {
            const q = el.dataset.question;
            const taskResult = results[q];
            if (!taskResult) return;
            el.classList.remove('task-match-correct', 'task-match-incorrect');
            const shouldHighlight = el.type === 'checkbox' ? el.checked : (el.value || '').trim() !== '';
            if (shouldHighlight) {
                el.classList.add(taskResult.is_correct ? 'task-match-correct' : 'task-match-incorrect');
            }
        });
        // Задание 8: селекты
        document.querySelectorAll('.task-eight-select').forEach(sel => {
            const letter = sel.dataset.errorLetter;
            if (!letter) return;
            const taskResult = results['8_' + letter];
            sel.classList.remove('task-match-correct', 'task-match-incorrect');
            sel.style.backgroundColor = '';
            sel.style.borderColor = '';
            if (taskResult) {
                if (taskResult.is_correct) {
                    sel.classList.add('task-match-correct');
                    sel.style.backgroundColor = '#d4edda';
                    sel.style.borderColor = '#4CAF50';
                } else {
                    sel.classList.add('task-match-incorrect');
                    sel.style.backgroundColor = '#f8d7da';
                    sel.style.borderColor = '#f44336';
                }
            }
        });
        // Задание 9: буквы под смайликами
        document.querySelectorAll('.smiley-button').forEach(btn => {
            const orthId = btn.dataset.orthId;
            if (!orthId) return;
            const icon = btn.querySelector('.smiley-icon');
            if (!icon) return;
            const taskResult = results[orthId];
            if (taskResult) {
                icon.classList.remove('selected', 'correct', 'incorrect');
                icon.classList.add(taskResult.is_correct ? 'correct' : 'incorrect');
            }
        });
    }

    function showVerdictLink(resultUrl, passed, errorCount) {
        const btn = document.getElementById('check-checkpoint-btn');
        if (!btn) return;
        const link = document.createElement('a');
        link.href = resultUrl;
        link.className = 'check-task-submit';
        link.style.display = 'block';
        link.style.textAlign = 'center';
        link.style.textDecoration = 'none';
        link.textContent = passed
            ? 'Рубеж сдан — смотреть вердикт →'
            : `Ошибок: ${errorCount} — смотреть вердикт и рекомендации →`;
        btn.replaceWith(link);
        link.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    document.addEventListener('DOMContentLoaded', () => {
        initInputs();
        const btn = document.getElementById('check-checkpoint-btn');
        if (!btn) return;
        btn.addEventListener('click', async () => {
            const answers = collectAnswers();
            btn.disabled = true;
            btn.textContent = 'Проверяем…';
            try {
                const res = await fetch(window.location.href, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken')
                    },
                    body: JSON.stringify({ answers })
                });
                if (!res.ok) {
                    const errText = await res.text();
                    console.error('Ошибка сервера:', errText);
                    alert('Не удалось проверить ответы. Обновите страницу и попробуйте снова.');
                    btn.disabled = false;
                    btn.textContent = 'Проверить и сдать рубеж';
                    return;
                }
                const result = await res.json();
                if (result.result_url) {
                    if (result.results) applyResults(result.results);
                    document.querySelectorAll('input[data-question]').forEach(el => { el.disabled = true; });
                    document.querySelectorAll('.task-eight-select').forEach(el => { el.disabled = true; });
                    document.querySelectorAll('.smiley-button').forEach(b => { b.style.pointerEvents = 'none'; });
                    showVerdictLink(result.result_url, result.passed, result.error_count);
                } else {
                    alert(result.error || 'Неизвестная ошибка проверки.');
                    btn.disabled = false;
                    btn.textContent = 'Проверить и сдать рубеж';
                }
            } catch (e) {
                console.error(e);
                alert('Ошибка сети. Попробуйте ещё раз.');
                btn.disabled = false;
                btn.textContent = 'Проверить и сдать рубеж';
            }
        });
    });
})();
