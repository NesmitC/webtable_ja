// planning_twotwo.js
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

function setupTask22() {
    const container = document.querySelector('.task-twotwo-exercise');
    if (!container) return;
    
    const checkButton = container.querySelector('.check-task-twotwo');
    if (!checkButton) return;
    
    // Убираем старый обработчик
    if (checkButton.hasAttribute('data-initialized')) return;
    
    // Функция для уникального выбора
    function setupUniqueSelects() {
        const selects = Array.from(container.querySelectorAll('.task-twotwo-select'));
        
        function updateSelects() {
            const selectedValues = selects
                .map(s => s.value)
                .filter(v => v !== '-' && v !== '');
            
            selects.forEach(s => {
                const currentValue = s.value;
                
                Array.from(s.options).forEach(option => {
                    const value = option.value;
                    if (value === '-') return;
                    
                    const isUsed = selectedValues.includes(value) && value !== currentValue;
                    option.disabled = isUsed;
                    
                    if (isUsed) {
                        option.style.color = '#ccc';
                        option.style.fontStyle = 'italic';
                    } else {
                        option.style.color = '';
                        option.style.fontStyle = '';
                    }
                });
            });
        }
        
        selects.forEach(select => {
            select.addEventListener('change', updateSelects);
        });
        
        updateSelects();
    }
    
    // Инициализируем уникальность выбора
    setupUniqueSelects();
    
    checkButton.addEventListener('click', async function() {
        const selects = container.querySelectorAll('.task-twotwo-select');
        const answers = {};
        const letters = ['А', 'Б', 'В', 'Г', 'Д'];
        
        // Собираем ответы
        selects.forEach((select, index) => {
            answers[letters[index]] = select.value;
        });
        
        // Отправка на сервер
        const csrfToken = getCookie('csrftoken');
        if (!csrfToken) {
            alert('Сессия истекла. Обновите страницу.');
            return;
        }
        
        const button = this;
        button.disabled = true;
        const originalText = button.textContent;
        button.textContent = 'Проверяем...';
        
        try {
            const response = await fetch('/api/check-task-twotwo-test/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({ answers: answers })
            });
            
            const result = await response.json();
            
            // Подсветка результатов
            selects.forEach((select, index) => {
                const letter = letters[index];
                const correctAnswer = result.details?.[letter]?.correct_answer;
                const userAnswer = answers[letter];
                
                select.classList.remove('task-match-select-correct', 'task-match-select-incorrect');
                
                if (userAnswer === '-') {
                    // Пустой ответ = красный
                    select.classList.add('task-match-select-incorrect');
                } else if (userAnswer === correctAnswer) {
                    select.classList.add('task-match-select-correct');
                } else {
                    select.classList.add('task-match-select-incorrect');
                }
            });
            
            // ТОЛЬКО БАЛЛ
            const resultDiv = container.querySelector('.task-twotwo-result');
            if (resultDiv) {
                resultDiv.innerHTML = `<p>Балл: ${result.score}/2</p>`;
                resultDiv.style.display = 'block';
            }
            
        } catch (error) {
            alert('Ошибка при проверке. Попробуйте снова.');
        } finally {
            button.disabled = false;
            button.textContent = originalText;
        }
    });
    
    checkButton.setAttribute('data-initialized', 'true');
}

// Экспортируем глобально
window.PlanningTwoTwo = {
    setup: setupTask22
};

// Автоматическая инициализация
if (document.querySelector('.task-twotwo-exercise')) {
    setupTask22();
}