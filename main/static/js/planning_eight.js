// planning_eight.js
window.PlanningEight = (function () {
    let selectedNumbers = new Set();

    function handleCheckClick(e) {
        e.preventDefault();
        e.stopPropagation();
        submitTaskEight(false);
    }

    function setupEventListeners() {
        const container = document.querySelector('.task-eight-exercise');
        if (!container) return;

        selectedNumbers = new Set();

        container.querySelectorAll('.task-eight-select').forEach(select => {
            select.addEventListener('change', handleSelectChange);
        });

        const btn = container.querySelector('.check-task-eight');
        if (!btn) return;
        
        btn.removeEventListener('click', handleCheckClick);
        btn.addEventListener('click', handleCheckClick);
    }

    function handleSelectChange(e) {
        const select = e.target;
        const oldNumber = select.dataset.prevValue || '-';
        const newNumber = select.value;

        if (oldNumber !== '-' && oldNumber !== newNumber) {
            selectedNumbers.delete(oldNumber);
        }

        if (newNumber !== '-' && selectedNumbers.has(newNumber)) {
            alert(`Предложение №${newNumber} уже выбрано.`);
            select.value = oldNumber;
            return;
        }

        if (newNumber !== '-') {
            selectedNumbers.add(newNumber);
        }

        select.dataset.prevValue = newNumber;
        updateOtherSelects();
    }

    function updateOtherSelects() {
        document.querySelectorAll('.task-eight-select').forEach(select => {
            const currentValue = select.value;
            select.querySelectorAll('option').forEach(opt => {
                if (opt.value !== '-' && opt.value !== currentValue) {
                    opt.disabled = selectedNumbers.has(opt.value);
                } else {
                    opt.disabled = false;
                }
            });
        });
    }

async function submitTaskEight(isDiagnostic = false) {
    const selects = document.querySelectorAll('.task-eight-select');
    const userAnswers = {};
    
    selects.forEach(sel => {
        userAnswers[sel.dataset.errorLetter] = sel.value || '-';
    });

    const csrf = getCookie('csrftoken');
    const btn = document.querySelector('.check-task-eight');
    btn.disabled = true;
    btn.textContent = 'Проверяем...';

    try {
        if (isDiagnostic) {
            return userAnswers;
        }

        const res = await fetch('/api/check-task-eight-test/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrf
            },
            body: JSON.stringify({ answers: userAnswers })
        });

        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        
        const result = await res.json();
        showResult(result);
        highlightAnswers(result);
        
    } catch (e) {
        console.error('Ошибка:', e);
        alert('Ошибка при проверке.');
    } finally {
        btn.disabled = false;
        btn.textContent = 'Проверить';
    }
}

    function highlightAnswers(result) {
        if (!result.details) return;
        
        Object.entries(result.details).forEach(([letter, data]) => {
            const errorRow = document.querySelector(`.task-eight-error-row[data-error-letter="${letter}"]`);
            const select = errorRow?.querySelector('.task-eight-select');
            
            if (errorRow && select) {
                if (data.is_correct) {
                    errorRow.style.backgroundColor = '#e8f5e9';
                    errorRow.style.border = '1px solid #c8e6c9';
                    select.style.borderColor = '#4CAF50';
                } else {
                    errorRow.style.backgroundColor = '#ffebee';
                    errorRow.style.border = '1px solid #ffcdd2';
                    select.style.borderColor = '#f44336';
                }
            }
            
            if (data.user_answer && data.user_answer !== '-') {
                document.querySelectorAll('.task-eight-sentence-row').forEach(row => {
                    const numberSpan = row.querySelector('.task-eight-sentence-number');
                    if (numberSpan && numberSpan.textContent.trim() === data.user_answer) {
                        row.style.backgroundColor = data.is_correct ? '#e8f5e9' : '#ffebee';
                        row.style.border = data.is_correct ? '1px solid #c8e6c9' : '1px solid #ffcdd2';
                    }
                });
            }
        });
    }

    function showResult(result) {
        const resDiv = document.querySelector('.task-eight-result');
        if (!resDiv) return;

        let message, color, bgColor;
        
        if (result.score === 2) {
            message = '✅ Отлично! Все ответы верны. ';
            color = 'green';
            bgColor = '#e8f5e9';
        } else if (result.score === 1) {
            message = '⚠️ Хорошо! ';
            color = '#ff9800';
            bgColor = '#fff3e0';
        } else {
            message = '❌ Нужно повторить. ';
            color = '#d32f2f';
            bgColor = '#ffebee';
        }
        
        message += `Правильных ответов: ${result.correct_count} из ${result.total}`;
        
        resDiv.innerHTML = `
            <p style="color: ${color}; background: ${bgColor}; padding: 12px; border-radius: 4px; margin: 0;">
                ${message}<br>
                <strong style="font-size: 1.1em;">Баллов: ${result.score}</strong>
            </p>
        `;
        resDiv.style.display = 'block';
    }

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

    return {
        setup: setupEventListeners,
        submitTaskEight: submitTaskEight
    };
})();

(function initPlanningEight() {
    function init() {
        if (window.PlanningEight && typeof window.PlanningEight.setup === 'function') {
            window.PlanningEight.setup();
        }
    }
    
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();