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