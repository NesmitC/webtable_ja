/* main/static/js/checkpoint.js
   Сбор ответов рубежного теста и отправка на свою страницу.
   Логика сбора и санитайзер скопированы из test_fix_ege.js (стандарт ЕГЭ),
   отличие одно: после проверки уходим на страницу вердикта result_url. */
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
        document.querySelectorAll('[data-question]').forEach(el => {
            const q = el.dataset.question;
            if (el.type === 'checkbox') {
                if (el.checked) {
                    if (!answers[q]) answers[q] = [];
                    answers[q].push(el.value);
                }
            } else if (el.tagName === 'SELECT') {
                const val = (el.value || '').trim();
                if (val !== '') answers[q] = val;
            } else {
                const val = (el.value || '').trim();
                if (val !== '') answers[q] = val;
            }
        });
        // Задание 8: селекты соответствия размечены data-error-letter
        // (так же, как в диагностике), приводим к ключам 8_А…8_Д.
        document.querySelectorAll('.task-eight-select').forEach(sel => {
            const val = (sel.value || '').trim();
            if (val !== '' && sel.dataset.errorLetter) {
                answers['8_' + sel.dataset.errorLetter] = val;
            }
        });
        return answers;
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
                    btn.textContent = 'Проверить и завершить рубеж';
                    return;
                }
                const result = await res.json();
                if (result.result_url) {
                    window.location.href = result.result_url;
                } else {
                    alert(result.error || 'Неизвестная ошибка проверки.');
                    btn.disabled = false;
                    btn.textContent = 'Проверить и завершить рубеж';
                }
            } catch (e) {
                console.error(e);
                alert('Ошибка сети. Попробуйте ещё раз.');
                btn.disabled = false;
                btn.textContent = 'Проверить и завершить рубеж';
            }
        });
    });
})();
