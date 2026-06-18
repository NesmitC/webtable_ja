// main/static/js/test_fix_ege.js

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

// === СТРОГАЯ ВАЛИДАЦИЯ ИНПУТОВ (только цифры и кириллица) ===
function initStrictValidation() {
    // Разрешаем только: 0-9, а-я, ё, А-Я, Ё
    // Любые другие символы (включая . / - и латиницу) будут удалены
    const forbiddenCharsRegex = /[^0-9а-яёА-ЯЁ]/g;

    document.querySelectorAll('input[data-question]').forEach(input => {
        // Отключаем подсказки браузера
        input.setAttribute('autocomplete', 'off');
        input.setAttribute('spellcheck', 'false');

        // 1. Фильтрация при обычном вводе (с клавиатуры)
        input.addEventListener('input', function(e) {
            if (forbiddenCharsRegex.test(this.value)) {
                this.value = this.value.replace(forbiddenCharsRegex, '');
            }
        });

        // 2. Фильтрация при вставке (Ctrl+V)
        input.addEventListener('paste', function(e) {
            e.preventDefault(); // Отменяем стандартную вставку
            
            // Берем текст из буфера, очищаем его от мусора
            const pastedText = (e.clipboardData || window.clipboardData).getData('text/plain');
            const cleanText = pastedText.replace(forbiddenCharsRegex, '');
            
            // Вставляем чистый текст в место курсора
            const start = this.selectionStart;
            const end = this.selectionEnd;
            this.value = this.value.substring(0, start) + cleanText + this.value.substring(end);
        });
    });
}

// Вызываем валидацию после загрузки страницы
document.addEventListener('DOMContentLoaded', initStrictValidation);

// === ФОРМАТИРОВАНИЕ ЗАДАНИЙ С ВАРИАНТАМИ ОТВЕТОВ ===
document.querySelectorAll('.question h4').forEach(h4 => {
    if (h4.dataset.formatted) return; // Защита от повторной обработки
    
    let text = h4.textContent.trim();
    const qBlock = h4.closest('.question');
    const qNum = qBlock?.dataset.questionNumber;
    
    // Убираем дублирование номера, если в БД он уже есть (например: "2. 2. В тексте...")
    if (qNum && text.startsWith(`${qNum}. `)) {
        text = text.slice(qNum.length + 2).trim();
    }
    
    // Ищем начало первого варианта "1) "
    const firstOptionIndex = text.search(/\d+\)/);
    if (firstOptionIndex > 0) {
        const prompt = text.slice(0, firstOptionIndex).trim();
        let options = text.slice(firstOptionIndex);
        
        // Добавляем перенос строки перед каждым номером варианта
        options = options.replace(/(\d+\))/g, '\n$1');
        
        h4.innerHTML = `
            <div style="font-weight: bold; margin-bottom: 3px;">${prompt}</div>
            <div style="font-weight: normal; white-space: pre-line;">${options}</div>
        `;
        h4.dataset.formatted = 'true';
    }
});


// Универсальные хранилища для всех заданий
window.taskLetterGroups = {};
window.taskSubgroupLetters = {};

// При загрузке страницы заполняем для всех заданий 9-21
document.addEventListener('DOMContentLoaded', function() {
    for (let num = 9; num <= 21; num++) {
        const groupsScript = document.getElementById(`task${num}-letter-groups`);
        const subgroupsScript = document.getElementById(`task${num}-subgroup-letters`);
        
        if (groupsScript && subgroupsScript) {
            try {
                window.taskLetterGroups[num] = JSON.parse(groupsScript.textContent);
                window.taskSubgroupLetters[num] = JSON.parse(subgroupsScript.textContent);
            } catch(e) {
                console.warn(`Ошибка загрузки task${num}:`, e);
            }
        }
    }
});


function getLettersForMask(orthId) {
    // Второй вариант задания 21 (с двоеточием)
    if (orthId.startsWith('21_1-')) return ['5', '9.1', '19'];
    // Задание 21_2 (запятые)
    if (orthId.startsWith('21_2-')) {
        return ['2', '3', '4.0', '4.1', '4.2', '5', '6', '7', '10', '11', '12', '13', '14', '15', '17'];
    }
    
    if (orthId.startsWith('14-')) return ['|', '/', '-'];
    if (orthId.startsWith('15-')) return ['н', 'нн'];
    if (orthId.match(/^(16|17|18|19|20)-/)) return [',', 'х'];
    
    // === УНИВЕРСАЛЬНАЯ ОБРАБОТКА ДЛЯ ЗАДАНИЙ 9-21 ===
    const match = orthId.match(/^(\d+)-/);
    if (match) {
        const taskNum = parseInt(match[1]);
        if (taskNum >= 9 && taskNum <= 21) {
            // Пытаемся взять из динамических данных
            if (window.taskLetterGroups && window.taskLetterGroups[taskNum] && window.taskLetterGroups[taskNum][orthId]) {
                const groupKey = window.taskLetterGroups[taskNum][orthId];
                const letters = window.taskSubgroupLetters[taskNum]?.[groupKey];
                if (letters && letters.length) return letters;
            }
            
            // Fallback для задания 9
            if (taskNum === 9) {
                const idx = parseInt(orthId.split('-')[1]);
                const groups = {
                    1: ['а', 'о'], 2: ['а', 'о'], 3: ['а', 'о'],
                    4: ['е', 'и'], 5: ['е', 'и'], 6: ['е', 'и'],
                    7: ['о', 'а'], 8: ['о', 'а'], 9: ['о', 'а'],
                    10: ['а', 'о'], 11: ['а', 'о'], 12: ['а', 'о'],
                    13: ['е', 'и', 'я'], 14: ['е', 'и', 'я'], 15: ['е', 'и', 'я']
                };
                return groups[idx] || ['а', 'о', 'е', 'и', 'я'];
            }
            
            // Fallback для заданий 10-12
            if (taskNum === 10) {
                const idx = parseInt(orthId.split('-')[1]);
                const groups = {
                    1: ['а', 'о'], 2: ['а', 'о'], 3: ['а', 'о'],
                    4: ['е', 'и'], 5: ['е', 'и'], 6: ['е', 'и'],
                    7: ['с', 'з'], 8: ['с', 'з'], 9: ['с', 'з'],
                    10: ['ъ', 'ь', '/'], 11: ['ъ', 'ь', '/'], 12: ['ъ', 'ь', '/'],
                    13: ['и', 'ы'], 14: ['и', 'ы'], 15: ['и', 'ы']
                };
                return groups[idx] || ['а', 'о', 'е', 'и', 'с', 'з', 'ъ', 'ь', 'ы'];
            }
            
            if (taskNum === 11 || taskNum === 12) {
                return ['е', 'и'];
            }
            
            if (taskNum === 13) return ['/', '|'];
            if (taskNum === 14) return ['/', '|', '-'];
            if (taskNum === 15) return ['н', 'нн'];
            if (taskNum >= 16 && taskNum <= 20) return [',', 'х'];
            if (taskNum === 21) {
                return ['2', '3', '4.0', '4.1', '4.2', '5', '6', '7', '10', '11', '12', '13', '14', '15', '17'];
            }
        }
    }
    
    return ['а', 'о', 'е', 'и', 'я'];
}

function setupSmiley(btn) {
    const icon = btn.querySelector('.smiley-icon');
    const options = btn.querySelector('.smiley-options');
    if (!icon || !options) return;

    icon.onclick = (e) => {
        e.stopPropagation();
        document.querySelectorAll('.smiley-options').forEach(opt => {
            if (opt !== options) opt.style.display = 'none';
        });
        options.style.display = options.style.display === 'block' ? 'none' : 'block';
    };

    options.querySelectorAll('li').forEach(li => {
        li.onclick = (e) => {
            e.stopPropagation();
            icon.textContent = li.dataset.letter;
            icon.classList.add('selected');
            options.style.display = 'none';
        };
    });
}

function processLine(line) {
    if (line.querySelector('.smiley-button')) {
        line.querySelectorAll('.smiley-button').forEach(setupSmiley);
        return;
    }

    let html = line.textContent;
    // Поддерживаем цифры, подчёркивание и дефис
    const regex = /\*\(([0-9_\-]+)\)\*/g;
    let result = '';
    let lastIndex = 0;
    let match;

    while ((match = regex.exec(html)) !== null) {
        result += html.slice(lastIndex, match.index);
        const orthId = match[1];
        const letters = getLettersForMask(orthId);
        const liItems = letters.map(l => `<li data-letter="${l}">${l}</li>`).join('');
        result += `<span class="smiley-button" data-orth-id="${orthId}" style="position:relative; display:inline-block; margin:0 0;">
            <span class="smiley-icon" style="cursor:pointer; font-size:1.2rem; display:inline-block; padding:2px 4px; border-radius:4px;">😊</span>
            <ul class="smiley-options" style="display:none; position:absolute; top:100%; left:0; background:white; border:1px solid #ccc; list-style:none; padding:5px; margin:0; z-index:100; border-radius:5px; box-shadow:0 2px 5px rgba(0,0,0,0.2); white-space:nowrap;">
                ${liItems}
            </ul>
        </span>`;
        lastIndex = match.index + match[0].length;
    }
    result += html.slice(lastIndex);
    
    if (result !== html) {
        line.innerHTML = result;
        line.querySelectorAll('.smiley-button').forEach(setupSmiley);
    }
}

document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.practice-line').forEach(processLine);

    document.addEventListener('click', function(e) {
        if (!e.target.closest('.smiley-button')) {
            document.querySelectorAll('.smiley-options').forEach(opt => opt.style.display = 'none');
        }
    });

    const checkBtn = document.getElementById('check-fix-test-btn');
    if (checkBtn) {
        checkBtn.addEventListener('click', async () => {
            const answers = {};
            
            document.querySelectorAll('[data-question]').forEach(el => {
                const q = el.dataset.question;
                if (el.type === 'checkbox') {
                    if (el.checked) {
                        if (!answers[q]) answers[q] = [];
                        answers[q].push(el.value);
                    }
                } else {
                    const val = (el.value || '').trim();
                    if (val !== '') answers[q] = val;
                }
            });
            
            document.querySelectorAll('[data-question^="8_"]').forEach(el => {
                const val = (el.value || '').trim();
                if (val !== '') answers[el.dataset.question] = val;
            });
 
            // === СБОР ОТВЕТОВ ДЛЯ ВСЕХ ЗАДАНИЙ СО СМАЙЛИКАМИ (9, 14, 15, 16 и т.д.) ===
            document.querySelectorAll('.smiley-button').forEach(btn => {
                const orthId = btn.dataset.orthId;
                if (!orthId) return;
                
                const icon = btn.querySelector('.smiley-icon');
                let letter = icon ? icon.textContent.trim() : '😊';
                
                // Пропускаем невыбранные смайлики
                if (letter === '😊') return;
                
                // Нормализация: во всех заданиях со смайликами используем одинаковые правила
                // Для пунктуации (запятая → !, Х → ?)
                if (!orthId.startsWith('16-') && !orthId.startsWith('17-') && !orthId.startsWith('18-') && !orthId.startsWith('19-') && !orthId.startsWith('20-')) {
                    if (letter === ',') letter = '!';
                    else if (letter === 'х' || letter === 'x') letter = '?';
                }
                // Для задания 14 (раздельное/дефис) оставляем как есть: | / -
                
                answers[orthId] = letter;
            });

            // === ВАЛИДАЦИЯ ИНПУТОВ (СТАНДАРТ ЕГЭ) ===
            function initAnswerValidation() {
                const sanitizer = (val) => {
                    let clean = val.replace(/[\s\t\n\r]+/g, '');          // Удаляем пробелы и переносы
                    clean = clean.replace(/[^0-9а-яёА-ЯЁ]/g, '');         // Оставляем только цифры и кириллицу
                    clean = clean.toLowerCase();                           // Приводим к нижнему регистру

                    const hasNum = /\d/.test(clean);
                    const hasLet = /[а-яё]/.test(clean);

                    // Если случайно смешались цифры и буквы, оставляем только один тип
                    if (hasNum && hasLet) {
                        clean = /\d/.test(clean.charAt(0)) 
                            ? clean.replace(/[^0-9]/g, '') 
                            : clean.replace(/[^а-яё]/g, '');
                    } else if (hasNum) {
                        clean = clean.replace(/[^0-9]/g, '');
                    } else {
                        clean = clean.replace(/[^а-яё]/g, '');
                    }

                    // Ограничение длины: цифры ≤7, буквы ≤17
                    const isNum = /^\d+$/.test(clean);
                    const maxLen = isNum ? 7 : 17;
                    return clean.length > maxLen ? clean.substring(0, maxLen) : clean;
                };

                document.querySelectorAll('input[data-question]').forEach(input => {
                    // Отключаем автозаполнение и проверку орфографии браузера
                    input.setAttribute('autocomplete', 'off');
                    input.setAttribute('spellcheck', 'false');

                    // Фильтрация на лету
                    input.addEventListener('input', (e) => {
                        const newVal = sanitizer(e.target.value);
                        if (e.target.value !== newVal) e.target.value = newVal;
                    });

                    // Корректная обработка вставки (Ctrl+V)
                    input.addEventListener('paste', (e) => {
                        e.preventDefault();
                        const pasted = (e.clipboardData || window.clipboardData).getData('text');
                        const start = input.selectionStart;
                        const end = input.selectionEnd;
                        const newValue = input.value.substring(0, start) + pasted + input.value.substring(end);
                        input.value = sanitizer(newValue);
                        input.dispatchEvent(new Event('input'));
                    });

                    // Блокируем контекстное меню (стандарт для тестовых сред)
                    input.addEventListener('contextmenu', e => e.preventDefault());
                });
            }

            // Вызов функции
            initAnswerValidation();
            
            try {
                const res = await fetch(window.location.href, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken')
                    },
                    body: JSON.stringify({ answers })
                });

                // ✅ ПРОВЕРКА СТАТУСА ДО парсинга JSON
                if (!res.ok) {
                    const errorText = await res.text();
                    console.error('❌ Ошибка сервера:', errorText);
                    throw new Error(`Сервер вернул ${res.status}. Откройте консоль (F12 → Console) и скопируйте красную ошибку.`);
                }

                const result = await res.json();
                const container = document.getElementById('test-results');
                if (container) {
                    // 1. Подсчет первичных баллов на основе детальных результатов
                    let primaryScore = 0;
                    const res = result.results || {};

                    // Задания 1-7, 9-21, 23-26 (по 1 баллу)
                    for (let i = 1; i <= 26; i++) {
                        if (i === 8 || i === 22) continue;
                        if (res[String(i)]?.is_correct) primaryScore++;
                    }

                    // Задания 8 и 22 (0–2 балла)
                    primaryScore += (res['8']?.score || 0);
                    primaryScore += (res['22']?.score || 0);

                    // Задание 27 (сочинение)
                    const essayInput = document.querySelector('input[data-question="27"]');
                    if (essayInput) {
                        const val = parseInt(essayInput.value.trim(), 10);
                        if (!isNaN(val) && val >= 0 && val <= 22) primaryScore += val;
                    }

                    // 2. Конвертация во вторичные баллы
                    const conversionTable = {
                        0:0,1:3,2:5,3:8,4:10,5:12,6:15,7:17,8:20,9:22,10:24,11:27,12:29,13:32,14:34,
                        15:36,16:37,17:39,18:40,19:42,20:43,21:45,22:46,23:48,24:49,25:51,26:52,27:54,
                        28:55,29:57,30:58,31:60,32:61,33:63,34:64,35:66,36:67,37:69,38:70,39:72,40:73,
                        41:75,42:78,43:81,44:83,45:86,46:89,47:91,48:94,49:97,50:100
                    };
                    let secondaryScore = conversionTable[primaryScore];
                    if (secondaryScore === undefined) {
                        secondaryScore = primaryScore > 50 ? Math.min(100, 100 + (primaryScore - 50) * 2) : 100;
                    }

                    // 3. Вывод (ровно 2 строки, как просили)
                    let html = '<div style="display:flex;flex-wrap:wrap;gap:4px;margin-bottom:8px;">';
                    for (let i = 1; i <= 26; i++) {
                        const task = res[String(i)];
                        if (!task) continue;

                        if (i === 8 || i === 22) {
                            const score = task.score || 0;
                            const s1 = score >= 1 ? '+' : '−', c1 = score >= 1 ? '#28a745' : '#dc3545';
                            const s2 = score === 2 ? '+' : '−', c2 = score === 2 ? '#28a745' : '#dc3545';
                            html += `<span style="display:inline-flex;align-items:center;font-size:13px;"><b>${i}</b>` +
                                `<span style="display:inline-block;width:14px;height:14px;line-height:14px;text-align:center;background:${c1};color:#fff;border-radius:2px;margin:0 1px;font-size:10px;">${s1}</span>` +
                                `<span style="display:inline-block;width:14px;height:14px;line-height:14px;text-align:center;background:${c2};color:#fff;border-radius:2px;margin:0 1px;font-size:10px;">${s2}</span></span>`;
                        } else {
                            const sym = task.is_correct ? '+' : '−';
                            const color = task.is_correct ? '#28a745' : '#dc3545';
                            html += `<span style="display:inline-flex;align-items:center;font-size:13px;"><b>${i}</b>` +
                                `<span style="display:inline-block;width:16px;height:14px;line-height:14px;text-align:center;background:${color};color:#fff;border-radius:2px;margin:0 2px;font-size:10px;">${sym}</span></span>`;
                        }
                    }
                    html += '</div>';
                    html += `<div style="font-weight:500;font-size:14px;">Результаты: ${primaryScore} первичных баллов — ${secondaryScore} вторичных баллов</div>`;

                    container.innerHTML = html;
                    container.style.display = 'block';
                    container.scrollIntoView({ behavior: 'smooth' });
                }

                // === ПОДСВЕТКА СМАЙЛИКОВ И ВЫПАДАЮЩИХ СПИСКОВ ПОСЛЕ ПРОВЕРКИ ===
                if (result.results) {
                    // Подсветка смайликов (задания 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21)
                    document.querySelectorAll('.smiley-button').forEach(btn => {
                        const orthId = btn.dataset.orthId;
                        if (!orthId) return;
                        
                        const icon = btn.querySelector('.smiley-icon');
                        if (!icon) return;
                        
                        const taskResult = result.results[orthId];
                        
                        if (taskResult) {
                            icon.classList.remove('correct', 'incorrect', 'selected');
                            
                            if (taskResult.is_correct === true) {
                                icon.classList.add('correct');
                            } else if (taskResult.is_correct === false) {
                                icon.classList.add('incorrect');
                            }
                        }
                    });

                    // === ПОДСВЕТКА ДЛЯ ЗАДАНИЯ 8 (ВЫПАДАЮЩИЕ СПИСКИ) ===
                    document.querySelectorAll('[data-question^="8_"]').forEach(select => {
                        const questionKey = select.dataset.question; // "8_А", "8_Б" и т.д.
                        const taskResult = result.results[questionKey]; // ← Теперь это работает!
                        
                        if (taskResult) {
                            select.classList.remove('task-match-correct', 'task-match-incorrect');
                            select.style.borderColor = '';
                            select.style.backgroundColor = '';
                            
                            if (taskResult.is_correct === true) {
                                select.classList.add('task-match-correct');
                                select.style.backgroundColor = '#d4edda';
                                select.style.borderColor = '#4CAF50';
                            } else if (taskResult.is_correct === false) {
                                select.classList.add('task-match-incorrect');
                                select.style.backgroundColor = '#f8d7da';
                                select.style.borderColor = '#f44336';
                            }
                        }
                    });

                    // Подсветка для задания 22 (выпадающие списки)
                    document.querySelectorAll('[data-question^="22_"]').forEach(select => {
                        const questionKey = select.dataset.question;
                        const taskResult = result.results[questionKey];
                        
                        if (taskResult) {
                            select.classList.remove('task-match-correct', 'task-match-incorrect');
                            
                            if (taskResult.is_correct === true) {
                                select.classList.add('task-match-correct');
                                select.style.backgroundColor = '#d4edda';
                            } else if (taskResult.is_correct === false) {
                                select.classList.add('task-match-incorrect');
                                select.style.backgroundColor = '#f8d7da';
                            }
                        }
                    });
                }

                // Синхронизация чекбоксов и текстового поля для заданий 23, 24
                document.querySelectorAll('.question').forEach(question => {
                    const checkboxes = question.querySelectorAll('input[type="checkbox"][data-question]');
                    const textInput = question.querySelector('input[type="text"][data-question]');
                    
                    if (checkboxes.length > 0 && textInput) {
                        // Функция обновления текстового поля
                        const updateTextInput = () => {
                            const checkedValues = Array.from(checkboxes)
                                .filter(cb => cb.checked)
                                .map(cb => cb.value)
                                .sort()
                                .join('');
                            textInput.value = checkedValues;
                        };
                        
                        // Добавляем обработчики на чекбоксы
                        checkboxes.forEach(cb => {
                            cb.addEventListener('change', updateTextInput);
                        });
                    }
                });

                // === УНИВЕРСАЛЬНАЯ ПОДСВЕТКА ТЕКСТОВЫХ ИНПУТОВ (1, 2, 3, 4, 6, 23-27) ===
                document.querySelectorAll('input[data-question]').forEach(input => {
                    const qKey = input.dataset.question;
                    const taskResult = result.results[qKey];

                    // Сброс предыдущих стилей
                    input.style.backgroundColor = '';
                    input.style.border = '';
                    input.classList.remove('correct-input', 'incorrect-input');

                    // Применяем цвета, если сервер вернул результат
                    if (taskResult && typeof taskResult.is_correct === 'boolean') {
                        if (taskResult.is_correct === true) {
                            input.style.backgroundColor = '#d4edda'; // ✅ Зелёный фон
                            input.style.border = '1px solid #4CAF50';
                        } else {
                            input.style.backgroundColor = '#f8d7da'; // ❌ Красный фон
                            input.style.border = '1px solid #f44336';
                        }
                    }
                });

                // === РАЗДЕЛЕНИЕ ЗАГОЛОВКА И ВАРИАНТОВ (ЗАДАНИЯ 1-3) ===
                document.querySelectorAll('.task-header').forEach(h4 => {
                    if (h4.dataset.formatted) return;
                    let text = h4.textContent.trim();
                    
                    // Ищем начало первого варианта: "1) ", "1." и т.д.
                    const match = text.match(/(\d+\)\s+)/);
                    if (match) {
                        const prompt = text.slice(0, match.index).trim();
                        let options = text.slice(match.index);
                        
                        // Добавляем перенос строки перед каждым номером варианта
                        options = options.replace(/(\d+\)\s+)/g, '\n$1').trim();
                        
                        h4.innerHTML = `
                            <div style="font-weight: bold; margin-bottom: 3px;">${prompt}</div>
                            <div class="task-options">${options}</div>
                        `;
                        h4.dataset.formatted = 'true';
                    }
                });

            } catch (err) {
                console.error('Ошибка проверки теста:', err);
                alert('Ошибка при проверке теста');
            }
        });
    }
});