// ===========================================================================
// МОДУЛЬ ДЛЯ ТЕКСТОВЫХ ЗАДАНИЙ (1-3 и 23-26)
// ===========================================================================

// Унифицированная функция обработки и отображения результатов
function processTextAnalysisResult(container, data) {
    const resultDiv = container.querySelector('.result-diagnostic');
    if (!resultDiv) return;

    // 1. Подсветка полей
    container.querySelectorAll('[data-question]').forEach(el => {
        const q = el.dataset.question;
        const res = data.results[q];
        if (!res) return;

        el.classList.remove('task-match-correct', 'task-match-incorrect');
        const shouldHighlight = el.type === 'checkbox' ? el.checked : el.value.trim() !== '';

        if (shouldHighlight) {
            el.classList.add(res.is_correct ? 'task-match-correct' : 'task-match-incorrect');
        }
    });

    // 2. Формирование блока с результатами
    let html = `<div style="margin-top: 20px; padding: 15px; background: #f8f9fa; border-radius: 8px; border: 1px solid #dee2e6;">`;
    html += `<h4 style="margin: 0 0 10px; color: #212529;">Результаты проверки</h4>`;
    html += `<p style="font-size: 16px; font-weight: bold; color: #495057; margin: 0 0 10px;">Правильных ответов: ${data.total_correct} из ${data.total_questions}</p>`;

    for (const [qNum, res] of Object.entries(data.results)) {
        const icon = res.is_correct ? '✅' : '❌';
        html += `<p style="margin: 5px 0; font-size: 14px;">${icon} <strong>Вопрос ${qNum}:</strong> "${res.user_answer}"`;
        if (!res.is_correct) {
            html += ` <span style="color: #dc3545;">(Правильно: "${res.correct_answer}")</span>`;
        }
        html += `</p>`;
    }
    html += `</div>`;

    resultDiv.innerHTML = html;
    resultDiv.style.display = 'block';
    resultDiv.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// Унифицированная функция навешивания обработчика проверки
function setupTextCheck(container, apiUrl) {
    if (!container) return;
    const checkBtn = container.querySelector('.check-text-analysis');
    if (!checkBtn) return;

    // Защита от дублирования обработчиков при повторной загрузке
    const newBtn = checkBtn.cloneNode(true);
    checkBtn.parentNode.replaceChild(newBtn, checkBtn);

    newBtn.addEventListener('click', async function () {
        const answers = {};

        // Сбор ответов (универсально для любых типов input)
        container.querySelectorAll('[data-question]').forEach(el => {
            const q = el.dataset.question;
            if (el.type === 'checkbox') {
                if (el.checked) {
                    if (!answers[q]) answers[q] = [];
                    answers[q].push(el.value);
                }
            } else {
                answers[q] = el.value.trim();
            }
        });

        newBtn.disabled = true;
        newBtn.textContent = 'Проверка...';

        try {
            const res = await fetch(apiUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken')
                },
                body: JSON.stringify({ answers })
            });

            const data = await res.json();
            if (data.error) throw new Error(data.error);

            processTextAnalysisResult(container, data);
        } catch (err) {
            console.error('Ошибка проверки:', err);
            const resultDiv = container.querySelector('.result-diagnostic');
            if (resultDiv) {
                resultDiv.innerHTML = `<p class="error" style="color: #dc3545; margin-top: 15px;">Ошибка: ${err.message}</p>`;
                resultDiv.style.display = 'block';
            }
        } finally {
            newBtn.disabled = false;
            newBtn.textContent = 'Проверить';
        }
    });
}

// --- Загрузка заданий 1-3 ---
async function loadTextAnalysis() {
    const answerSection = document.querySelector('.block-answer');
    if (!answerSection) return;

    answerSection.innerHTML = '<p>Загружаем текст для анализа...</p>';

    try {
        const res = await fetch('/api/generate-text-analysis/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
            body: JSON.stringify({})
        });

        const data = await res.json();
        if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);

        answerSection.innerHTML = data.html;
        setupTextCheck(answerSection.querySelector('.text-analysis-exercise'), '/api/check-text-analysis/');
    } catch (err) {
        console.error('Ошибка загрузки 1-3:', err);
        answerSection.innerHTML = '<p class="error">Не удалось загрузить текст</p>';
    }
}

// --- Загрузка заданий 23-26 ---
async function loadTextAnalysis23_26() {
    const answerSection = document.querySelector('.block-answer');
    if (!answerSection) return;

    answerSection.innerHTML = '<p>Загружаем текст для анализа (задания 23–26)...</p>';

    try {
        const res = await fetch('/api/generate-text-analysis-23-26/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
            body: JSON.stringify({})
        });

        const data = await res.json();
        if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);

        answerSection.innerHTML = data.html;
        setupTextCheck(answerSection.querySelector('.text-analysis-exercise'), '/api/check-text-analysis-23-26/');
    } catch (err) {
        console.error('Ошибка загрузки 23-26:', err);
        answerSection.innerHTML = '<p class="error">Не удалось загрузить текст</p>';
    }
}

// --- Экспорт модуля ---
window.TextAnalysisModule = {
    ...window.TextAnalysisModule,
    loadTextAnalysis,
    loadTextAnalysis23_26
};