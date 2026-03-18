// static/js/quiz.js

// let currentQuiz = null;
// let quizScope = null;


// async function loadUserStats() {
//     console.log('🟢 loadUserStats');
//     const el = document.getElementById('user-stats');
//     if (!el) return;
    
//     el.innerHTML = 'Считаем...';
    
//     try {
//         const res = await fetch('/api/user-stats/');
//         const data = await res.json();
//         console.log('📊 Данные:', data);
        
//         el.innerHTML = `📚 Слов: ${data.total_planning}`;
//     } catch (e) {
//         el.innerHTML = 'Ошибка';
//     }
// }


// async function checkAnswer(is_correct) {
//     const o = quizScope?.querySelector('#options') || document.getElementById('options');
//     const r = quizScope?.querySelector('#result') || document.getElementById('result');
//     const n = quizScope?.querySelector('#next-btn') || document.getElementById('next-btn');
    
//     if (!o || !r) return;
    
//     [...o.getElementsByTagName('button')].forEach(b => b.disabled = true);
    
//     // 1. СНАЧАЛА показываем результат (всегда)
//     r.textContent = is_correct ? '✅ Верно!' : '❌ Ошибка. Правильно: ' + (currentQuiz.correct_answer || '?');
//     if (currentQuiz.explanation) r.textContent += '\n\n📚 ' + currentQuiz.explanation;
//     if (n) n.style.display = 'inline';
    
//     // 2. ПОТОМ пытаемся обновить статистику (не ждём ответа)
    
//     // 3. Логируем отдельно (не ждём, игнорируем ошибки)
//     if (currentQuiz?.example_id) {
//         fetch('/api/log-quiz-answer/', {
//             method: 'POST',
//             headers: {
//                 'Content-Type': 'application/json',
//                 'X-CSRFToken': getCookie('csrftoken')
//             },
//             body: JSON.stringify({
//                 example_id: currentQuiz.example_id,
//                 is_correct: is_correct
//             })
//         }).catch(e => console.log('Лог не удался, но это не важно'));
//     }
// }

// function initQuiz(scope = null) {
//     const s = scope || document;
//     const n = s.querySelector('#next-btn');
//     if (n && !n._h) {
//         n._h = () => { const r = s.querySelector('#result'); if (r) r.textContent = ''; loadQuiz(scope); };
//         n.addEventListener('click', n._h);
//     }
//     loadQuiz(scope);
// }

// function getCookie(name) {
//     const m = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
//     return m ? m[2] : null;
// }

// // Экспорт
// window.QuizModule = { loadQuiz, checkAnswer, initQuiz, getCookie };


// // async function loadUserStats() {
// //     console.log('🟢 loadUserStats вызвана!');
// //     try {
// //         const response = await fetch('/api/user-stats/');
// //         const data = await response.json();
        
// //         let html = `
// //             <div style="margin: 15px 0;">
// //                 📚 Всего слов в планинге: ${data.total_planning}<br>
// //                 🎯 Всего пройдено квизов: ${data.total_quizzes}<br>
// //                 📈 Успешность: ${data.success_rate}%<br>
// //                 <br>
// //                 ✨ Выучено слов: ${data.learned_words}<br>
// //                 📝 Требуют повторения: ${data.need_repeat}<br>
// //                 <br>
// //                 💡 Рекомендации:<br>
// //         `;
        
// //         data.recommendations.forEach(rec => {
// //             html += `• ${rec}<br>`;
// //         });
        
// //         html += `</div>`;
        
// //         document.getElementById('user-stats').innerHTML = html;
// //     } catch (error) {
// //         document.getElementById('user-stats').innerHTML = 'Ошибка загрузки статистики';
// //     }
// // }


// async function loadUserStats() {
//     console.log('🟢 loadUserStats');
//     const el = document.getElementById('user-stats');
//     if (!el) return;
    
//     try {
//         const res = await fetch('/api/user-stats/');
//         const data = await res.json();
        
//         el.innerHTML = `
//             📚 Слов: ${data.total_planning}<br>
//             🎯 Квизов: ${data.total_quizzes}<br>
//             📈 Успешность: ${data.success_rate}%
//         `;
//     } catch (e) {
//         console.error('Ошибка:', e);
//     }
// }

// window.loadUserStats = loadUserStats;

// // Загружаем при старте
// document.addEventListener('DOMContentLoaded', loadUserStats);

// // Загружаем при загрузке страницы
// document.addEventListener('DOMContentLoaded', loadUserStats);

// static/js/quiz.js


let currentQuiz = null;
let quizScope = null;
let statsTimeout = null;

async function loadQuiz(container = null) {
    quizScope = container || document;
    const q = quizScope.querySelector('#question');
    const o = quizScope.querySelector('#options');
    
    if (!q || !o) return;
    
    q.textContent = 'Загрузка...';
    o.innerHTML = '';
    
    try {
        const snippet = quizScope.closest('.quiz-snippet');
        const quizType = snippet ? snippet.dataset.quizType : 'orthography';
        
        let endpoint = '/api/get-quiz/';
        let payload = { quiz_type: quizType };
        
        if (quizType === 'orthoepy') {
            endpoint = '/api/get-quiz-orthoepy-pair/';
            payload = {};
        } else if (quizType === 'planning') {
            endpoint = '/api/get-planning-quiz/';
            payload = {};
        }
        
        const res = await fetch(endpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify(payload)
        });
        
        const data = await res.json();
        
        if (data.error) {
            q.textContent = data.error;
            return;
        }
        
        currentQuiz = data;
        q.textContent = data.question || 'Как правильно?';
        
        data.options.forEach(opt => {
            const btn = document.createElement('button');
            btn.textContent = opt.text;
            btn.onclick = () => checkAnswer(opt.is_correct);
            o.appendChild(btn);
        });
        
    } catch (e) {
        q.textContent = 'Ошибка загрузки';
    }
}

async function loadUserStats() {
    const statsEl = document.getElementById('user-stats');
    if (!statsEl) return;
    
    try {
        const res = await fetch('/api/user-stats/');
        const data = await res.json();
        
        statsEl.innerHTML = 
            '📚 Слов в планинге: ' + data.total_planning + '<br>' +
            '🎯 Всего квизов: ' + data.total_quizzes + '<br>' +
            '📈 Успешность: ' + data.success_rate + '%<br>' +
            '✨ Выучено: ' + data.learned_words + '<br>' +
            '📝 Повторить: ' + data.need_repeat + '<br><br>' +
            '💡 Рекомендации:<br>' +
            '• ' + data.recommendations.join('<br>• ');
            
    } catch (e) {}
}


async function checkAnswer(is_correct) {
    const r = quizScope?.querySelector('#result') || document.getElementById('result');
    const n = quizScope?.querySelector('#next-btn') || document.getElementById('next-btn');
    const o = quizScope?.querySelector('#options') || document.getElementById('options');
    
    if (!r) return;
    
    // Блокируем кнопки
    if (o) {
        [...o.getElementsByTagName('button')].forEach(b => b.disabled = true);
    }
    
    // Показываем результат
    if (is_correct) {
        r.textContent = '✅ Верно!';
    } else {
        r.textContent = '❌ Ошибка. Правильно: ' + (currentQuiz.correct_answer || '?');
    }
    
    if (currentQuiz.explanation) {
        r.textContent += '\n\n📚 ' + currentQuiz.explanation;
    }
    
    // 🔹 ОТПРАВЛЯЕМ РЕЗУЛЬТАТ НА СЕРВЕР
    try {
        await fetch('/api/log-quiz-answer/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({
                example_id: currentQuiz.example_id,
                is_correct: is_correct
            })
        });
        console.log('✅ Результат сохранён');
    } catch (e) {
        console.error('❌ Не удалось сохранить результат:', e);
    }
    
    // Показываем кнопку "Дальше"
    if (n) {
        n.style.display = 'inline';
        n.onclick = () => {
            r.textContent = '';
            n.style.display = 'none';
            loadQuiz(quizScope);
        };
    }
    
    // Обновляем статистику через 500мс
    if (statsTimeout) clearTimeout(statsTimeout);
    statsTimeout = setTimeout(loadUserStats, 500);
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