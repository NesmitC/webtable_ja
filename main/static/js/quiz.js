// static/js/quiz.js

// === 1. ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ===
let currentQuiz = null;
// 🔥 Для горячих слов: индекс текущего слова в строгом порядке
let hotWordIndex = 0;
let quizScope = null;
let isAnswering = false;
let statsTimeout = null;

// === 2. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===
function getCookie(name) {
    const m = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
    return m ? m[2] : null;
}


async function loadQuiz(container = null) {
    quizScope = container || document;
    const q = quizScope.querySelector('#question');
    const o = quizScope.querySelector('#options');
    if (!q || !o) return;

    q.textContent = 'Загрузка...';
    o.innerHTML = '';
    isAnswering = false;

    try {
        const snippet = quizScope.querySelector('.quiz-snippet');
        let quizType = snippet ? snippet.dataset.quizType : 'orthography';
        
        // 🔥 Нормализация: 'hot' → 'hot_word'
        if (quizType === 'hot') {
            quizType = 'hot_word';
        }

        let endpoint = '/api/get-quiz/';
        let payload = { quiz_type: quizType };

        if (quizType === 'orthoepy') {
            endpoint = '/api/get-quiz-orthoepy-pair/';
            payload = {};
        } else if (quizType === 'planning') {
            endpoint = '/api/get-planning-quiz/';
            payload = {};
        } else if (quizType === 'hot_word') {
            endpoint = '/api/quiz/hot-word/';
            // 🔥 ПЕРЕДАЁМ ТЕКУЩИЙ ИНДЕКС
            payload = { index: hotWordIndex };
        }

        const res = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
            body: JSON.stringify(payload)
        });

        const data = await res.json();
        if (data.error) {
            q.textContent = data.error;
            return;
        }

        currentQuiz = data;
        q.textContent = data.question || 'Как правильно?';
        
        // 🔥 ОБНОВЛЯЕМ ИНДЕКС ДЛЯ ГОРЯЧИХ СЛОВ (даже до ответа)
        if (quizType === 'hot_word' && data.next_index !== undefined) {
            hotWordIndex = data.next_index;
        }

        data.options.forEach(opt => {
            const btn = document.createElement('button');
            btn.textContent = opt.text;
            btn.style.margin = '0 5px 5px 0';
            btn.style.padding = '8px 15px';
            btn.style.cursor = 'pointer';
            btn.style.borderRadius = '5px';
            btn.style.border = '1px solid #ccc';
            btn.onclick = () => checkAnswer(opt.is_correct);
            o.appendChild(btn);
        });
    } catch (e) {
        console.error('❌ Quiz load error:', e);
        q.textContent = 'Ошибка загрузки';
    }
}


async function checkAnswer(is_correct) {
    if (isAnswering) return;
    isAnswering = true;

    const scope = quizScope || document;
    const r = scope.querySelector('#result');
    const n = scope.querySelector('#next-btn');
    const o = scope.querySelector('#options');

    if (!r || !currentQuiz) { isAnswering = false; return; }

    if (o) {
        o.querySelectorAll('button').forEach(btn => {
            btn.disabled = true;
            btn.style.opacity = '0.6';
            btn.style.cursor = 'not-allowed';
        });
    }

    try {
        r.textContent = is_correct ? '✅ Верно!' : `❌ Ошибка. Правильно: ${currentQuiz.correct_answer || '?'}`;
        r.style.color = is_correct ? 'green' : 'red';
        
        if (currentQuiz.explanation) {
            r.textContent += `\n📚 ${currentQuiz.explanation}`;
        }

        // Логирование ответа
        fetch('/api/log-quiz-answer-site/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
            body: JSON.stringify({ example_id: currentQuiz.example_id, is_correct: is_correct })
        }).catch(() => {});

        // 🔹 Кнопка "Следующий"
        if (n) {
            n.style.display = 'inline-block';
            n.onclick = () => {
                if (r) { r.textContent = ''; r.style.color = ''; }
                if (n) { n.style.display = 'none'; }
                isAnswering = false;
                loadQuiz(quizScope);
            };
        }

        // Обновление статистики
        if (statsTimeout) clearTimeout(statsTimeout);
        statsTimeout = setTimeout(loadUserStats, 500);
    } catch (e) {
        console.error('❌ Answer error:', e);
        if (r) r.textContent = '⚠️ Ошибка обработки';
        isAnswering = false;
    }
}

function getCookie(name) {
    const m = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
    return m ? m[2] : null;
}

document.addEventListener('DOMContentLoaded', () => {
    setTimeout(loadUserStats, 100);
});

window.QuizModule = { loadQuiz };
window.loadUserStats = loadUserStats;


// === 4. СТАТИСТИКА И ОТЧЕТЫ ===

async function loadUserStats() {
    const statsEl = document.getElementById('user-stats');
    if (!statsEl) return;
    
    try {
        const res = await fetch('/api/user-stats/');
        const data = await res.json();
        const rate = data.success_rate || 0;
        const rateColor = rate >= 70 ? 'green' : rate >= 40 ? 'orange' : 'red';

        let html = `📚 Слов в планинге: ${data.total_planning || 0}<br>` +
                   `🎯 Попыток: ${data.total_quizzes || 0}<br>` +
                   `✅ Правильно: ${data.correct || 0}<br>` +
                   `📈 Успешность: <span style="color:${rateColor}; font-weight:bold;">${rate}%</span>`;
        
        if (data.recommendations && data.recommendations.length > 0) {
            html += '<br><br><strong>📋 Рекомендации:</strong><ul style="margin:5px 0; padding-left:20px;">';
            data.recommendations.forEach(rec => {
                html += `<li style="color:#d32f2f; margin:3px 0;">${rec}</li>`;
            });
            html += '</ul>';
        }
        statsEl.innerHTML = html;
    } catch (e) {
        console.error('Stats error:', e);
    }
}

function loadWeeklyReport() {
    fetch('/api/my-weekly-report/')
        .then(r => r.json())
        .then(data => {
            const el = document.getElementById('weekly-report');
            if (!el) return;
            
            if (data.status === 'inactive') {
                el.innerHTML = `<div style="color:#6c757d;">${data.message}</div>`;
            } else {
                let html = `<strong>${data.message}</strong><br><br>`;
                if (data.weak_orthograms && data.weak_orthograms.length > 0) {
                    html += "Самые частые ошибки:<ul>";
                    data.weak_orthograms.forEach(o => {
                        html += `<li>${o.orthogram__name} — ${o.errors} раз</li>`;
                    });
                    html += "</ul>";
                }
                el.innerHTML = html;
            }
        })
        .catch(err => {
            if(document.getElementById('weekly-report'))
                document.getElementById('weekly-report').textContent = "Не удалось загрузить отчёт.";
        });
}

function loadProgress() {
    fetch('/api/assistant/?action=progress')
        .then(r => r.json())
        .then(data => {
            const el = document.getElementById('progress-summary');
            if (!el) return;
            if (data.total !== undefined) {
                const rate = data.success_rate || Math.round((data.correct / data.total) * 100);
                el.innerHTML = `Выполнено заданий: ${data.total}, правильно: ${rate}%`;
            } else {
                el.textContent = data.summary || "Прогресс загружен.";
            }
        })
        .catch(() => {
            if(document.getElementById('progress-summary'))
                document.getElementById('progress-summary').textContent = "Ошибка прогресса.";
        });
}

// === 5. VK ЛОГИКА ===

async function checkVkStatus() {
    try {
        const r = await fetch('/api/vk/status/');
        const d = await r.json();
        
        const statusDiv = document.getElementById('vk-link-status');
        const btn = document.getElementById('generate-code-btn');
        const codeDiv = document.getElementById('code-display');
        const quizBtn = document.getElementById('vk-send-quiz-btn');
        
        if (d.is_linked) {
            statusDiv.innerHTML = '✅ <strong>Привязан!</strong> Вы получаете квизы в ВК.';
            statusDiv.style.color = 'green';
            if (btn) btn.style.display = 'none';
            if (codeDiv) codeDiv.style.display = 'none';
            if (quizBtn) quizBtn.style.display = 'inline-block'; 
        } else {
            statusDiv.innerHTML = '❌ <strong>Не привязан.</strong> Пройдите шаги выше.';
            statusDiv.style.color = '#d32f2f';
            if (btn) btn.style.display = 'inline-block';
            if (codeDiv) codeDiv.style.display = 'none';
            if (quizBtn) quizBtn.style.display = 'none';
        }
    } catch(e) {
        console.error('VK status error:', e);
    }
}

// === 6. ИНИЦИАЛИЗАЦИЯ (ЗАПУСК ПРИ ЗАГРУЗКЕ СТРАНИЦЫ) ===

document.addEventListener('DOMContentLoaded', () => {
    
    // --- Инициализация Квизов ---
    const container = document.querySelector('.block-answer-quiz-content');
    const buttons = document.querySelectorAll('.quiz-trigger');

    if (container && buttons.length > 0) {
        buttons.forEach(btn => {
            btn.onclick = async function(e) {
                e.preventDefault();
                const type = this.dataset.quizType;
                
                // Toggle (скрыть/показать)
                if (container.dataset.active === type && container.style.display !== 'none') {
                    container.style.display = 'none';
                    container.dataset.active = '';
                    return;
                }
                
                container.dataset.active = type;
                
                // 🔥 ДЛЯ ГОРЯЧИХ СЛОВ: НЕ СБРАСЫВАЕМ ИНДЕКС ПРИ ОТКРЫТИИ
                // if (type === 'hot') { hotWordIndex = 0; }  ← УДАЛИТЬ ЭТУ СТРОКУ!
                
                container.style.display = 'block';
                container.innerHTML = `
                    <div class="quiz-snippet" data-quiz-type="${type}">
                        <div id="question">Загрузка...</div>
                        <div id="options"></div>
                        <div id="result" style="font-weight:bold; margin-top:10px;"></div>
                        <button id="next-btn" style="display:none; background:#4c75a3; color:white; border:none; padding:5px 10px; border-radius:4px; margin-top:10px;">Следующий</button>
                    </div>
                `;
                
                // Запускаем загрузку данных
                setTimeout(() => loadQuiz(container), 50);
            };
        });
    }

    // --- Инициализация VK Кнопок ---
    
    // 1. Кнопка получения кода
    const getCodeBtn = document.getElementById('generate-code-btn');
    if (getCodeBtn) {
        getCodeBtn.onclick = async () => {
            try {
                const r = await fetch('/api/vk/generate-code/');
                const d = await r.json();
                if (d.status === 'success') {
                    document.getElementById('link-code').textContent = d.code;
                    document.getElementById('code-expires').textContent = d.expires;
                    document.getElementById('code-display').style.display = 'block';
                    getCodeBtn.style.display = 'none';
                } else {
                    alert('Ошибка: ' + d.message);
                }
            } catch(e) {
                alert('Ошибка сети');
            }
        };
    }

    // 2. Кнопка отправки квиза в ВК
    const sendQuizBtn = document.getElementById('vk-send-quiz-btn');
    const sendQuizStatus = document.getElementById('vk-quiz-status');
    
    if (sendQuizBtn) {
        sendQuizBtn.onclick = async () => {
            sendQuizBtn.disabled = true;
            sendQuizBtn.textContent = '⏳ Отправка...';
            sendQuizStatus.textContent = '';
            
            try {
                const res = await fetch('/api/vk/send-quiz/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
                    body: JSON.stringify({})
                });
                const data = await res.json();
                if (data.status === 'success') {
                    sendQuizStatus.textContent = '✅ ' + data.message;
                    sendQuizStatus.style.color = 'green';
                } else {
                    sendQuizStatus.textContent = '❌ ' + (data.error || 'Ошибка');
                    sendQuizStatus.style.color = 'red';
                }
            } catch(e) {
                sendQuizStatus.textContent = '❌ Ошибка сети';
                sendQuizStatus.style.color = 'red';
            } finally {
                sendQuizBtn.disabled = false;
                sendQuizBtn.textContent = '📩 Прислать квиз в ВК';
            }
        };
    }

    // --- Загрузка Данных при старте ---
    checkVkStatus();
    setTimeout(loadUserStats, 100);
    loadWeeklyReport();
    loadProgress();

    // Экспорт для глобального доступа
    window.QuizModule = { loadQuiz, checkAnswer };
});