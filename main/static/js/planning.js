// ===========================================================================
// ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
// ===========================================================================

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

// ===========================================================================
// ГЛОБАЛЬНЫЙ ДЕЛЕГИРОВАННЫЙ ОБРАБОТЧИК
// ===========================================================================

document.addEventListener('click', async (e) => {
    // --- Смайлики (работает везде) ---
    if (e.target.classList.contains('smiley-icon')) {
        e.stopPropagation();
        const opts = e.target.closest('.smiley-button')?.querySelector('.smiley-options');
        if (opts) opts.style.display = opts.style.display === 'block' ? 'none' : 'block';
        return;
    }
    if (e.target.tagName === 'LI' && e.target.hasAttribute('data-letter')) {
        const btn = e.target.closest('.smiley-button');
        const icon = btn?.querySelector('.smiley-icon');
        if (icon) {
            icon.textContent = e.target.dataset.letter;
            icon.classList.add('selected');
            btn.querySelector('.smiley-options').style.display = 'none';
        }
        return;
    }
    if (!e.target.closest('.smiley-button')) {
        document.querySelectorAll('.smiley-options').forEach(el => el.style.display = 'none');
        // Не return — чтобы обработать орфограммы ниже
    }

    // --- Орфограммы и пунктограммы ---
    const button = e.target.closest('[data-orthogram], [data-punktogram]');
    if (!button) return;

    const orthogramIds = button.dataset.orthogram;
    const punktogramId = button.dataset.punktogram;
    const answerSection = document.querySelector('.block-answer');

    if (!answerSection) {
        console.error('❌ Не найден блок .block-answer');
        return;
    }

    answerSection.innerHTML = '<p>Загрузка...</p>';

    // // === ЗАДАНИЕ 4: Орфоэпия ===
    // if (orthogramIds === '4000') {
    //     if (typeof OrthoepyModule?.loadOrthoepyTest === 'function') {
    //         await OrthoepyModule.loadOrthoepyTest();
    //     } else {
    //         answerSection.innerHTML = '<p class="error">Модуль орфоэпии не загружен</p>';
    //     }
    //     return;
    // }


    // === ЗАДАНИЕ 4: Орфоэпия ===
    if (orthogramIds === '4000') {
        // Проверяем, загружен ли модуль
        if (window.OrthoepyModule && typeof window.OrthoepyModule.loadOrthoepyTest === 'function') {
            await OrthoepyModule.loadOrthoepyTest();
        } else {
            // Если модуль не загружен, пробуем загрузить тест напрямую
            await loadOrthoepyTest();
        }
        return;
    }

    // Добавляем функцию loadOrthoepyTest в planning.js (копия из planning_orthoepos.js)
    async function loadOrthoepyTest() {
        const answerSection = document.querySelector('.block-answer');
        if (!answerSection) return;
        
        answerSection.innerHTML = '<p>Загрузка теста по орфоэпии...</p>';
        
        try {
            const csrf = getCookie('csrftoken');
            if (!csrf) {
                answerSection.innerHTML = '<p class="error">Сессия истекла.</p>';
                return;
            }
            
            const res = await fetch('/api/generate-orthoepy-test/', {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json', 
                    'X-CSRFToken': csrf 
                },
                body: JSON.stringify({})
            });
            
            if (!res.ok) {
                throw new Error(`HTTP error! status: ${res.status}`);
            }
            
            const data = await res.json();
            
            if (data.html) {
                answerSection.innerHTML = data.html;
                // Настраиваем обработчики после загрузки HTML
                setupOrthoepyListeners();
            } else if (data.error) {
                answerSection.innerHTML = `<p class="error">${data.error}</p>`;
            } else {
                answerSection.innerHTML = '<p class="error">Неизвестная ошибка при загрузке теста.</p>';
            }
        } catch (e) {
            console.error('Ошибка загрузки теста орфоэпии:', e);
            answerSection.innerHTML = '<p class="error">Не удалось загрузить тест. Попробуйте обновить страницу.</p>';
        }
    }

    // Функция для настройки обработчиков после загрузки теста
    function setupOrthoepyListeners() {
        const btn = document.querySelector('.check-orthoepy-test');
        if (btn) {
            btn.onclick = checkOrthoepyTest;
        }
    }

    // Функция проверки теста (копия из planning_orthoepos.js)
    async function checkOrthoepyTest() {
        const container = document.querySelector('.orthoepy-test-exercise');
        if (!container) return;

        const selected = [...container.querySelectorAll('.orthoepy-checkbox:checked')]
            .map(el => el.value);
        
        if (!selected.length) {
            alert('Выберите хотя бы один вариант.');
            return;
        }

        const btn = document.querySelector('.check-orthoepy-test');
        if (btn) {
            btn.disabled = true;
            btn.textContent = 'Проверяем...';
        }

        try {
            const csrf = getCookie('csrftoken');
            const res = await fetch('/api/check-orthoepy-test/', {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json', 
                    'X-CSRFToken': csrf 
                },
                body: JSON.stringify({ selected })
            });
            
            if (!res.ok) {
                throw new Error(`HTTP error! status: ${res.status}`);
            }
            
            const result = await res.json();
            displayOrthoepyResults(result);
        } catch (e) {
            alert('Ошибка при проверке: ' + e.message);
        } finally {
            const btn = document.querySelector('.check-orthoepy-test');
            if (btn) {
                btn.disabled = false;
                btn.textContent = 'Проверить';
            }
        }
    }

    // Функция отображения результатов (исправленная версия)
    function displayOrthoepyResults(results) {
        const resultDiv = document.querySelector('.orthoepy-result');
        if (!resultDiv) return;

        // Подсветка ВСЕХ вариантов
        Object.values(results.results || {}).forEach(item => {
            const optionDiv = document.querySelector(`[data-variant="${item.variant}"]`);
            
            if (optionDiv) {
                optionDiv.classList.remove('orthoepy-correct', 'orthoepy-incorrect');
                if (item.is_correct_variant) {
                    optionDiv.classList.add('orthoepy-correct');
                } else {
                    optionDiv.classList.add('orthoepy-incorrect');
                }
            }
        });

        // Выводим балл
        resultDiv.innerHTML = `<p><strong>Балл:</strong> ${results.summary?.user_score || 0}</p>`;
        resultDiv.style.display = 'block';
        resultDiv.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    
    
    // === Текстовый анализ 1–3, 23–24 ===
    if (orthogramIds === '1_3' || orthogramIds === '23_24') {
        if (orthogramIds === '1_3' && typeof TextAnalysisModule?.loadTextAnalysis === 'function') {
            await TextAnalysisModule.loadTextAnalysis();
            return;
        }
        if (orthogramIds === '23_24' && typeof TextAnalysisModule?.loadTextAnalysis23_24 === 'function') {
            await TextAnalysisModule.loadTextAnalysis23_24();
            return;
        }
        answerSection.innerHTML = '<p class="error">Модуль анализа не загружен</p>';
        return;
    }

    // === Остальное: орфограммы и пунктограммы ===
    const csrfToken = getCookie('csrftoken');
    if (!csrfToken) {
        answerSection.innerHTML = '<p class="error">Сессия истекла. Обновите страницу.</p>';
        return;
    }

    try {
        let url, payload;

        // Задание 21 — случайный подтип
        if (punktogramId === '21') {
            const variants = ['2100', '2101', '2102'];
            const id = variants[Math.floor(Math.random() * variants.length)];
            url = '/api/generate-punktum-exercise/';
            payload = { orthogram_ids: [id] };
        }
        // Пунктограммы 16–20 с изображением
        else if (punktogramId && ['1600','1700','1800','1900','2000'].includes(punktogramId)) {
            const imgPaths = {
                '1600': '/static/images/punktum_task_16.webp',
                '1700': '/static/images/punktum_task_17.webp',
                '1800': '/static/images/punktum_task_18.webp',
                '1900': '/static/images/punktum_task_19.webp',
                '2000': '/static/images/punktum_task_20.webp'
            };
            const imgPath = imgPaths[punktogramId];
            if (imgPath) {
                answerSection.innerHTML = `<img src="${imgPath}" style="max-width:100%; height:auto; margin-bottom:20px; border-radius:8px;">`;
            }
            url = '/api/generate-punktum-exercise/';
            payload = { orthogram_ids: [punktogramId] };
        }
        // Орфограммы
        else if (orthogramIds) {
            const ids = orthogramIds.split(',').map(id => id.trim());
            const isMulti = ids.includes('1400') || ids.includes('1500');
            url = isMulti ? '/api/generate-exercise-multi/' : '/api/generate-exercise/';
            payload = { orthogram_ids: ids };
        } else {
            answerSection.innerHTML = '<p>Задание не поддерживается.</p>';
            return;
        }

        if (orthogramIds === '711') {
            if (window.CorrectionModule && typeof window.CorrectionModule.loadCorrectionTest === 'function') {
                await CorrectionModule.loadCorrectionTest();
            } else {
                // fallback: загрузить модуль динамически или показать ошибку
                answerSection.innerHTML = '<p>Модуль задания 7 не загружен.</p>';
            }
            return;
        }

        const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
            body: JSON.stringify(payload)
        });

        if (!res.ok) throw new Error('Ошибка загрузки');
        const data = await res.json();

        if (punktogramId && ['1600','1700','1800','1900','2000'].includes(punktogramId)) {
            answerSection.innerHTML += `<h3>Задание № ${punktogramId.slice(0,2)}</h3>${data.html}`;
        } else {
            answerSection.innerHTML = data.html;
        }

        // Обработка смайликов и проверки
        const container = answerSection.querySelector('.article-practice') || answerSection;
        await processPracticeContainer(container);
        setupCheckAnswers(container);

    } catch (err) {
        console.error('❌ Ошибка:', err);
        answerSection.innerHTML = `<p class="error">Ошибка: ${err.message}</p>`;
    }
});

// ===========================================================================
// ФУНКЦИИ ОБРАБОТКИ СМАЙЛИКОВ (остаются без изменений)
// ===========================================================================

const orthogramLettersCache = {};

async function getLettersForOrthogram(orthId) {
    if (typeof orthId !== 'string') orthId = String(orthId);
    if (orthId.startsWith('14')) return ['/', '|', '-'];
    // Задание 15: Н/НН (только 1500)
    if (orthId === '1500') {
        return ['н', 'нн'];
    }
    // Орфограмма 15: И/Ы после Ц
    if (orthId === '15') {
        return ['и', 'ы'];
    }
    if (['16','17','18','19','20'].includes(orthId.slice(0, 2))) return [',', 'х'];
    if (orthId === '2100') return ['5','8','8.1','9.2','10','13','16','18'];
    if (orthId === '2101') return ['5','9.1','19'];
    if (orthId === '2102') return ['2','4.1','4.2','4.3','5','6','7','11','12','13','14','15','16','17'];
    if (['21','32','36','46','54','56','58','581'].includes(orthId)) return ['/', '|'];
    if (orthId == '6') return ['ъ', 'ь', '/'];
    if (orthogramLettersCache[orthId]) return orthogramLettersCache[orthId];
    try {
        const res = await fetch(`/api/orthogram/${orthId}/letters/`);
        const data = await res.json();
        const letters = Array.isArray(data.letters) ? data.letters : ['а','о','е','и','я'];
        orthogramLettersCache[orthId] = letters;
        return letters;
    } catch (err) {
        return ['а','о','е','и','я'];
    }
}

async function processLineWithMasks(lineText) {
    const matches = [...lineText.matchAll(/\*(\d+)\*/g)];
    if (matches.length === 0) return lineText;
    let result = '';
    let lastIndex = 0;
    for (const match of matches) {
        const orthId = match[1];
        const letters = await getLettersForOrthogram(orthId);
        const liItems = letters.map(letter => `<li data-letter="${letter}">${letter}</li>`).join('');
        result += lineText.slice(lastIndex, match.index);
        result += `<span class="smiley-button" data-orth-id="${orthId}">
                    <span class="smiley-icon">😊</span>
                    <ul class="smiley-options">${liItems}</ul>
                  </span>`;
        lastIndex = match.index + match[0].length;
    }
    result += lineText.slice(lastIndex);
    return result;
}

async function processPracticeContainer(container) {
    if (!container) return;
    const lines = container.querySelectorAll('.practice-line');
    for (const line of lines) {
        const text = line.textContent || '';
        if (text) {
            const html = await processLineWithMasks(text);
            line.innerHTML = html;
        }
    }
}

function setupCheckAnswers(container = document) {
    container.querySelectorAll('.check-answers').forEach(button => {
        if (button._clickHandler) {
            button.removeEventListener('click', button._clickHandler);
        }
        button._clickHandler = function () {
            const article = button.closest('.article-practice');
            const smileyButtons = article ? Array.from(article.querySelectorAll('.smiley-button')) : [];
            if (smileyButtons.length === 0) return;
            const userAnswers = [];
            let hasSelection = false;
            smileyButtons.forEach(btn => {
                const icon = btn.querySelector('.smiley-icon');
                let selectedLetter = icon ? icon.textContent : '😊';
                if (selectedLetter === ',') selectedLetter = '!';
                else if (selectedLetter === 'х') selectedLetter = '?';
                if (selectedLetter === '|') selectedLetter = '\\';
                if (selectedLetter !== '😊') hasSelection = true;
                userAnswers.push(selectedLetter);
            });
            if (!hasSelection) {
                alert("Сначала выбери хотя бы одну букву!");
                return;
            }
            const csrfToken = getCookie('csrftoken');
            if (!csrfToken) {
                alert('Сессия истекла. Обновите страницу.');
                return;
            }
            fetch('/api/check-exercise/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                body: JSON.stringify({ user_words: userAnswers })
            })
            .then(r => r.ok ? r.json() : r.text().then(text => { throw new Error(`HTTP ${r.status}: ${text}`); }))
            .then(results => {
                if (!Array.isArray(results)) throw new Error('Некорректный ответ');
                const icons = article.querySelectorAll('.smiley-icon');
                icons.forEach((icon, i) => {
                    icon.classList.remove('selected', 'correct', 'incorrect');
                    if (i < results.length) {
                        icon.classList.add(results[i] ? 'correct' : 'incorrect');
                    }
                });
            })
            .catch(err => {
                console.error('❌ Ошибка проверки:', err);
                alert('Ошибка при проверке.');
            });
        };
        button.addEventListener('click', button._clickHandler);
    });
}