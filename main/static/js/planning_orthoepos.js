// main/static/js/planning_orthoepos.js
/**
 * Отображение результатов проверки орфоэпии (Задание 4)
 * Поддерживает два режима:
 * 1. Школьный (6-9 классы): Текстовая обратная связь, без баллов.
 * 2. ЕГЭ (10-11 классы): Балльная система (0 или 1).
 */
window.displayOrthoepyResults = function(results) {
    const container = document.querySelector('.orthoepy-test-exercise');
    if (!container) {
        console.error('❌ Контейнер .orthoepy-test-exercise не найден');
        return;
    }

    // 1. ОПРЕДЕЛЕНИЕ РЕЖИМА (Школа vs ЕГЭ)
    // Проверяем атрибут data-school-mode. Он может быть "true", true или отсутствовать.
    const schoolModeAttr = container.dataset.schoolMode;
    const isSchoolMode = (schoolModeAttr === 'true' || schoolModeAttr === true);
    
    console.log(`🔍 [CHECK] Атрибут data-school-mode: "${schoolModeAttr}" | Режим: ${isSchoolMode ? 'ШКОЛЬНЫЙ' : 'ЕГЭ'}`);

    // 2. ИЗВЛЕЧЕНИЕ ДАННЫХ
    // Ожидаемая структура от бэкенда: results.results['4'].variant_results
    const task4Data = results.results?.['4'];
    if (!task4Data || !task4Data.variant_results) {
        console.error('❌ Нет данных variant_results в ответе сервера:', results);
        return;
    }
    
    const variantResults = task4Data.variant_results;
    const options = document.querySelectorAll('.test-option');
    
    // Счетчики для логики проверки
    let correctCount = 0;       // Сколько ПРАВИЛЬНЫХ вариантов выбрал пользователь
    let totalSelected = 0;      // Сколько ВСЕГО вариантов выбрал пользователь
    let totalCorrectExists = 0; // Сколько ВСЕГО правильных вариантов есть в тесте

    // 3. ПОДСВЕТКА ВАРИАНТОВ
    options.forEach((option) => {
        // Получаем ID варианта из data-option-id (1, 2, 3...)
        const optionId = option.dataset.optionId;
        if (!optionId) return;

        // Ключ в ответе сервера имеет вид "4-1", "4-2"...
        const resultKey = `4-${optionId}`;
        const data = variantResults[resultKey];
        
        if (!data) {
            console.warn(`⚠️ Не найден результат для ключа ${resultKey}`);
            return;
        }

        const checkbox = option.querySelector('.orthoepy-checkbox');
        const textSpan = option.querySelector('.variant-text') || option;
        if (!checkbox) return;

        // Подсчет статистики
        if (data.is_correct) totalCorrectExists++;

        // А. Красим ТЕКСТ (зеленый если правильный, красный если нет)
        // Это делается независимо от выбора пользователя, чтобы показать истину
        if (textSpan) {
            textSpan.style.color = data.is_correct ? '#28a745' : '#dc3545';
            textSpan.style.fontWeight = 'bold';
        }

        // Б. Обрабатываем ВЫБОР пользователя (рамка чекбокса)
        if (checkbox.checked) {
            totalSelected++;
            if (data.is_correct) {
                correctCount++;
                // Правильно выбрано
                checkbox.style.border = '3px solid #10b981';
                checkbox.style.boxShadow = '0 0 6px 2px rgba(16, 185, 129, 0.7)';
            } else {
                // Ошибка выбора
                checkbox.style.border = '3px solid #ef4444';
                checkbox.style.boxShadow = '0 0 6px 2px rgba(239, 68, 68, 0.7)';
            }
            checkbox.style.outline = 'none';
        } else {
            // Сброс стилей для невыбранных
            checkbox.style.border = '';
            checkbox.style.boxShadow = '';
        }
        
        // Блокируем изменение после проверки
        checkbox.disabled = true;
    });

    // 4. БЛОКИРОВКА КНОПКИ
    const checkBtn = document.querySelector('.check-orthoepy-test');
    if (checkBtn) {
        checkBtn.textContent = 'Проверено';
        checkBtn.disabled = true;
    }

    // 5. ВЫВОД ИТОГОВОГО СООБЩЕНИЯ
    let resultDiv = document.querySelector('.orthoepy-result');
    
    // === ШКОЛЬНЫЙ РЕЖИМ (6-9 классы) ===
    if (isSchoolMode) {
        // Если блока нет в HTML (так как шаблон его не рендерит для школы) — создаем его
        if (!resultDiv) {
            resultDiv = document.createElement('div');
            resultDiv.className = 'orthoepy-result';
            resultDiv.style.marginTop = '15px';
            resultDiv.style.padding = '10px';
            resultDiv.style.borderRadius = '5px';
            resultDiv.style.background = '#f8f9fa';
            container.appendChild(resultDiv);
            console.log('✅ Блок результата создан динамически для школьного режима');
        }

        // Логика анализа ошибок
        const hasMissing = totalSelected < totalCorrectExists; // Не все правильные выбраны
        const hasWrong = correctCount < totalSelected;         // Есть лишние неправильные
        const allCorrect = !hasMissing && !hasWrong && totalSelected > 0;

        let message = '';
        let color = '#dc3545'; // Красный по умолчанию

        if (allCorrect) {
            message = '✓ Всё верно! Все слова с правильным ударением отмечены.';
            color = '#28a745';
        } else if (totalSelected === 0) {
            message = '✗ Неправильно: вы ничего не выбрали.';
        } else if (hasMissing && hasWrong) {
            message = '✗ Есть ошибки: не все верные слова отмечены, плюс есть лишние.';
        } else if (hasMissing) {
            message = '✗ Неправильно: вы отметили не все слова с правильным ударением.';
        } else if (hasWrong) {
            message = '✗ Неправильно: среди выбранных есть слова с ошибочным ударением.';
        }

        resultDiv.innerHTML = `<p style="color: ${color}; font-weight: bold; font-size: 1.1em; margin:0;">${message}</p>`;
        resultDiv.style.display = 'block';

    } 
    // === РЕЖИМ ЕГЭ (10-11 классы) ===
    else {
        // Для ЕГЭ блок обычно есть в HTML, но на всякий случай создадим, если нет
        if (!resultDiv) {
            resultDiv = document.createElement('div');
            resultDiv.className = 'orthoepy-result';
            container.appendChild(resultDiv);
        }
        
        // Берем балл из ответа сервера
        const score = results.user_score !== undefined ? results.user_score : (task4Data.score || 0);
        const color = score === 1 ? '#28a745' : '#dc3545';

        // Выводим ТОЛЬКО балл, без текста в скобках
        resultDiv.innerHTML = `
            <p style="font-size: 1.2em; margin:0;">
                <strong style="color:${color}">Балл: ${score} из 1</strong>
            </p>`;
        resultDiv.style.display = 'block';
    }
    
    // Плавная прокрутка к результату
    resultDiv.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
};

/**
 * Инициализация страницы тренировки орфоэпии
 * Рендерит слова с кликабельными гласными, обрабатывает выбор ударения, валидирует пакетно
 */
window.initOrthoepyTrening = function() {
    const container = document.getElementById('orthoepy-words-container');
    if (!container || !window.ORTHOEPY_WORDS?.length) return;

    window.orthoepyUserChoices = {};
    let currentLetter = '';

    // Рендер слов
    window.ORTHOEPY_WORDS.forEach(({id, word, vowel_indices}) => {
        const firstChar = word ? word[0].toUpperCase() : '';
        if (firstChar && firstChar !== currentLetter) {
            currentLetter = firstChar;
            const h3 = document.createElement('h3');
            h3.className = 'orthoepy-alpha-heading';
            h3.textContent = currentLetter;
            container.appendChild(h3);
        }

        const el = document.createElement('div');
        el.className = 'orthoepy-word';
        el.dataset.wordId = id;
        el.innerHTML = [...word].map((char, i) =>
            vowel_indices.includes(i)
                ? `<span class="orthoepy-vowel" data-wid="${id}" data-vid="${i}">${char}</span>`
                : char
        ).join('');
        container.appendChild(el);
    });

    // Клик по гласной
    container.addEventListener('click', e => {
        const v = e.target.closest('.orthoepy-vowel');
        if (!v) return;
        const {wid, vid} = v.dataset;
        const wordEl = v.closest('.orthoepy-word');

        wordEl.querySelectorAll('.orthoepy-vowel').forEach(s => {
            s.textContent = s.textContent.toLowerCase();
            s.style.color = '';
            s.style.fontWeight = '';
        });

        if (window.orthoepyUserChoices[wid] == vid) {
            delete window.orthoepyUserChoices[wid];
        } else {
            v.textContent = v.textContent.toUpperCase();
            window.orthoepyUserChoices[wid] = vid;
        }
    });

    // ✅ Проверка: только подсветка, без счётчиков
    document.getElementById('check-orthoepy-trening')?.addEventListener('click', function() {
        window.ORTHOEPY_WORDS.forEach(({id, correct_index}) => {
            const choice = window.orthoepyUserChoices[id];
            if (choice === undefined) return;

            const span = document.querySelector(`.orthoepy-vowel[data-wid="${id}"][data-vid="${choice}"]`);
            if (span) {
                span.style.color = (choice == correct_index) ? '#28a745' : '#dc3545';
                span.style.fontWeight = 'bold';
            }
        });
        // Очищаем блок результатов
        const resDiv = document.getElementById('orthoepy-trening-result');
        if (resDiv) resDiv.innerHTML = '';
    });
};
