document.addEventListener('DOMContentLoaded', function() {
    const textareas = document.querySelectorAll('textarea[name^="user-input-orf-"]');

    // Получаем CSRF-токен
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;

    if (!csrfToken) {
        console.error('CSRF токен не найден! Проверьте, что {% csrf_token %} есть в шаблоне.');
        return;
    }

    // Загружаем сохранённые данные
    fetch("/load-examples/")
        .then(response => response.json())
        .then(data => {
            textareas.forEach(ta => {
                if (data[ta.name]) {
                    ta.value = data[ta.name];
                }
            });
        });

    // Сохраняем при изменении
    textareas.forEach(ta => {
        ta.addEventListener('input', function() {
            fetch("/save-example/", {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'X-CSRFToken': csrfToken
                },
                body: `field_name=${encodeURIComponent(this.name)}&content=${encodeURIComponent(this.value)}`
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Ошибка сохранения');
                }
                return response.json();
            })
            .then(data => {
                console.log('Сохранено:', data);
            })
            .catch(error => {
                console.error('Ошибка:', error);
            });
        });
    });
});





function createSmileyHtml(exerciseId, letters) {
    const liItems = letters.map(letter => `<li>${letter}</li>`).join('');
    return `
        <span class="smiley-button" data-id="${exerciseId}">
            <span class="smiley-icon">😊</span>
            <ul class="smiley-options">
                ${liItems}
            </ul>
        </span>
    `;
}

const exercises = {
    1: { letters: ['з', 'с'], correct: 'з' },
    2: { letters: ['ж', 'ш'], correct: 'ж' }
};

document.addEventListener('DOMContentLoaded', function() {

    // Вставляем смайлы при загрузке страницы
    const replacements = [
        { placeholder: 'у...кой', id: 1, prefix: 'у', suffix: 'кой' },
        { placeholder: 'доро...ке', id: 2, prefix: 'доро', suffix: 'ке' }
    ];

    document.querySelectorAll('.practice-text_5_1').forEach(p => {
        let html = p.innerHTML;
        replacements.forEach(rep => {
            const smiley = createSmileyHtml(rep.id, exercises[rep.id].letters);
            html = html.replace(rep.placeholder, `${rep.prefix}${smiley}${rep.suffix}`);
        });
        p.innerHTML = html;
    });

    // Глобальный обработчик кликов
    document.addEventListener('click', function(e) {
        const target = e.target;

        // Клик по смайлу
        if (target.classList.contains('smiley-icon')) {
            e.preventDefault();
            e.stopPropagation();
            const button = target.closest('.smiley-button');
            const options = button.querySelector('.smiley-options');

            if (options.style.display === 'none' || !options.style.display) {
                options.style.display = 'block';
            } else {
                options.style.display = 'none';
            }
        }

        // Клик по букве
        if (target.tagName === 'LI' && target.closest('.smiley-options')) {
            const button = target.closest('.smiley-button');
            const exerciseId = button.dataset.id;
            const selectedLetter = target.textContent;

            // Подсветка
            const isCorrect = selectedLetter === exercises[exerciseId].correct;

            // ✅ Обновляем текст смайлика на выбранную букву
            const smileyIcon = button.querySelector('.smiley-icon');
            smileyIcon.textContent = selectedLetter;
            smileyIcon.classList.remove('correct', 'incorrect'); // Сбрасываем старые классы
            smileyIcon.classList.add(isCorrect ? 'correct' : 'incorrect');

            // ✅ Скрываем выпадающий список
            button.querySelector('.smiley-options').style.display = 'none';
        }

        // Клик вне
        if (!target.closest('.smiley-button') && !target.closest('.smiley-options')) {
            document.querySelectorAll('.smiley-options').forEach(opt => {
                opt.style.display = 'none';
            });
        }
    });
});