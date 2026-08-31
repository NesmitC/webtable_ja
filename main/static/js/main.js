// Аккордеон для FAQ
document.addEventListener('DOMContentLoaded', () => {
    const faqTriggers = document.querySelectorAll('.faq-item__trigger');

    faqTriggers.forEach(trigger => {
        trigger.addEventListener('click', () => {
            const item = trigger.closest('.faq-item');
            const content = item.querySelector('.faq-item__content');
            const isExpanded = trigger.getAttribute('aria-expanded') === 'true';

            // Закрыть все остальные (опционально)
            faqTriggers.forEach(otherTrigger => {
                if (otherTrigger !== trigger) {
                    otherTrigger.setAttribute('aria-expanded', 'false');
                    otherTrigger.closest('.faq-item').classList.remove('faq-item--active');
                }
            });

            // Переключить текущий
            trigger.setAttribute('aria-expanded', !isExpanded);
            item.classList.toggle('faq-item--active');
        });
    });
});

// Мобильное меню
document.addEventListener('DOMContentLoaded', function () {
    const burgerBtn = document.getElementById('burgerBtn');
    const mobileMenu = document.getElementById('mobileMenu');
    const dropdownBtn = document.querySelector('.mobile-menu__dropdown-btn');
    const dropdown = document.querySelector('.mobile-menu__dropdown');

    if (burgerBtn && mobileMenu) {
        // Открыть/закрыть меню
        burgerBtn.addEventListener('click', function () {
            burgerBtn.classList.toggle('burger--active');
            mobileMenu.classList.toggle('mobile-menu--active');
        });

        // Закрыть меню при клике на ссылку
        const menuLinks = mobileMenu.querySelectorAll('a');
        menuLinks.forEach(link => {
            link.addEventListener('click', function () {
                burgerBtn.classList.remove('burger--active');
                mobileMenu.classList.remove('mobile-menu--active');
            });
        });
    }

    // Раскрыть выпадающие меню в мобильном меню (5-9 класс, ЕГЭ и любые будущие)
    const dropdownBtns = document.querySelectorAll('.mobile-menu__dropdown-btn');
    dropdownBtns.forEach(function (btn) {
        btn.addEventListener('click', function () {
            // соседний <ul> идёт сразу после кнопки
            const dropdown = this.nextElementSibling;
            if (!dropdown) return;

            dropdown.classList.toggle('mobile-menu__dropdown--active');

            const arrow = this.querySelector('.mobile-menu__arrow');
            if (arrow) {
                arrow.style.transform = dropdown.classList.contains('mobile-menu__dropdown--active')
                    ? 'rotate(180deg)'
                    : 'rotate(0deg)';
            }
        });
    });
});

// Переключение табов при наведении
document.addEventListener('DOMContentLoaded', function () {
    const tabs = document.querySelectorAll('.au-tab');

    tabs.forEach(tab => {
        tab.addEventListener('mouseenter', function () {
            // Убираем активный класс у всех табов
            tabs.forEach(t => t.classList.remove('au-tab--active'));
            // Добавляем активный класс текущему табу
            this.classList.add('au-tab--active');
        });
    });

    // При уходе мыши с контейнера табов — возвращаем активный таб по умолчанию
    const tabsContainer = document.querySelector('.au-tabs');
    if (tabsContainer) {
        tabsContainer.addEventListener('mouseleave', function () {
            tabs.forEach(t => t.classList.remove('au-tab--active'));
            // Возвращаем активный класс на "Регистрация" (второй таб)
            tabs[1].classList.add('au-tab--active');
        });
    }
});

// Функция показа/скрытия пароля
function togglePassword(inputId) {
    const input = document.getElementById(inputId);
    if (input.type === 'password') {
        input.type = 'text';
    } else {
        input.type = 'password';
    }
}

// Получаем CSRF token из cookie
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

const csrftoken = getCookie('csrftoken');

// Отправка формы через AJAX
const registerForm = document.getElementById('registerForm');
if (registerForm) {
    registerForm.addEventListener('submit', async function (e) {
        e.preventDefault();

        const form = this;
        const submitBtn = document.getElementById('submitBtn');
        const formData = new FormData(form);
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;

        console.log('Отправка формы...');
        console.log('URL:', '{% url "register" %}');
        console.log('CSRF:', csrfToken ? 'есть' : 'нет');

        submitBtn.disabled = true;
        submitBtn.textContent = 'Отправка...';

        try {
            const response = await fetch('{% url "register" %}', {
                method: 'POST',
                body: formData,
                headers: {
                    'X-CSRFToken': csrfToken,
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });

            console.log('Status:', response.status);
            console.log('Content-Type:', response.headers.get('content-type'));

            // Проверяем, что вернулся JSON
            const contentType = response.headers.get('content-type') || '';

            if (!contentType.includes('application/json')) {
                console.warn('Сервер вернул HTML вместо JSON. Используем фоллбэк.');
                // Фоллбэк: обычная отправка формы
                form.submit();
                return;
            }

            const data = await response.json();
            console.log('Data:', data);

            if (response.ok && data.success) {
                document.getElementById('userEmail').textContent = formData.get('email');
                document.getElementById('registerFormContainer').style.display = 'none';
                const divider = document.querySelector('.au-divider');
                if (divider) divider.style.display = 'none';
                document.getElementById('successMessage').style.display = 'block';
            } else if (response.status === 429) {
                alert(data.error || 'Слишком много попыток');
                submitBtn.disabled = false;
                submitBtn.textContent = 'Зарегистрироваться';
            } else if (response.status === 400) {
                if (data.errors) {
                    Object.entries(data.errors).forEach(([field, errors]) => {
                        const input = document.querySelector(`[name="${field}"]`);
                        if (input) {
                            const errorDiv = document.createElement('div');
                            errorDiv.style.color = '#dc2626';
                            errorDiv.style.fontSize = '12px';
                            errorDiv.style.marginTop = '4px';
                            errorDiv.textContent = errors.join(', ');
                            input.parentElement.insertAdjacentElement('afterend', errorDiv);
                        }
                    });
                }
                submitBtn.disabled = false;
                submitBtn.textContent = 'Зарегистрироваться';
            } else {
                alert(data.error || 'Ошибка при регистрации');
                submitBtn.disabled = false;
                submitBtn.textContent = 'Зарегистрироваться';
            }
        } catch (error) {
            console.error('Error:', error);
            // Фоллбэк: обычная отправка формы
            console.log('Используем фоллбэк (обычная отправка)');
            form.submit();
        }
    });
}

// Логика переключения диагностик
document.addEventListener('DOMContentLoaded', function () {
    const tabs = document.querySelectorAll('.diag-tab');
    const content = document.getElementById('diagContent');

    // Заглушки контента. Позже замени на fetch/загрузку реального теста.
    const diagData = {
        incoming: {
            title: 'Входящая диагностика',
            text: 'Здесь будет тест для определения стартового уровня.'
        },
        current: {
            title: 'Текущая диагностика',
            text: 'Здесь будет тест для проверки прогресса по темам.'
        },
        final: {
            title: 'Финальная диагностика',
            text: 'Здесь будет итоговый тест-срез перед экзаменом.'
        }
    };

    tabs.forEach(function (tab) {
        tab.addEventListener('click', function () {
            // Убираем активное состояние у всех
            tabs.forEach(function (t) {
                t.classList.remove('diag-tab--active');
            });
            // Ставим активное текущей
            this.classList.add('diag-tab--active');

            // Подгружаем контент выбранной диагностики
            const type = this.getAttribute('data-diag-type');
            const data = diagData[type];

            if (data && content) {
                content.innerHTML =
                    '<div class="diag-content__card">' +
                    '<h2 class="diag-content__title">' + data.title + '</h2>' +
                    '<p class="diag-content__text">' + data.text + '</p>' +
                    // сюда позже вставишь сам тест / кнопку "Начать"
                    '</div>';
            }
        });
    });
});

document.addEventListener('DOMContentLoaded', function () {
    const tabs = document.querySelectorAll('.demo-tab');
    const content = document.getElementById('demoContent');

    // Заглушки контента. Позже замени на fetch/загрузку реального теста.
    const demoData = {
        demo2026: { title: 'Демоверсия ЕГЭ по русскому · 2026', text: 'Здесь будет демоверсия 2026 года.' },
        demo2027: { title: 'Демоверсия ЕГЭ по русскому · 2027', text: 'Здесь будет демоверсия 2027 года.' },
        early2025: { title: 'Досрочный вариант ЕГЭ по русскому · 2025', text: 'Здесь будет досрочный вариант 2025 года.' },
        early2026: { title: 'Досрочный вариант ЕГЭ по русскому · 2026', text: 'Здесь будет досрочный вариант 2026 года.' }
    };

    tabs.forEach(function (tab) {
        tab.addEventListener('click', function () {
            // Снимаем активное состояние со всех кнопок (в обеих колонках)
            tabs.forEach(function (t) {
                t.classList.remove('demo-tab--active');
            });
            // Ставим активное на нажатую
            this.classList.add('demo-tab--active');

            // Подгружаем контент выбранного варианта
            const type = this.getAttribute('data-demo-type');
            const data = demoData[type];

            if (data && content) {
                content.innerHTML =
                    '<div class="demo-content__card">' +
                    '<h2 class="demo-content__title">' + data.title + '</h2>' +
                    '<p class="demo-content__text">' + data.text + '</p>' +
                    // сюда позже вставишь сам тест / кнопку "Начать"
                    '</div>';
            }
        });
    });
});

(function () {
    var toggle = document.getElementById('paponimReveal');
    var label = document.getElementById('paponimToggleLabel');
    var page = document.querySelector('.paponim-page');
    if (!toggle || !page) return;
    toggle.addEventListener('change', function () {
        page.classList.toggle('paponim-page--revealed', toggle.checked);
        if (label) {
            label.textContent = toggle.checked
                ? 'Скрыть значения'
                : 'Показать значения';
        }
    });
})();

// === ОТСЛЕЖИВАНИЕ АКТИВНОСТИ ДЛЯ ДАШБОРДА ===
(function () {
    function getCsrf(name) {
        const m = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
        return m ? m[2] : null;
    }
    function trackPost(endpoint, payload) {
        fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf('csrftoken') },
            body: JSON.stringify(payload)
        }).catch(() => { });
    }

    // Уроки: аккордеоны <details class="lesson-card"> — считаем раскрытие
    document.addEventListener('DOMContentLoaded', function () {
        document.querySelectorAll('details.lesson-card').forEach(function (details, idx) {
            details.addEventListener('toggle', function () {
                if (!details.open) return;   // только открытие
                const titleEl = details.querySelector('.lesson-card__title');
                const code = titleEl ? titleEl.textContent.trim() : ('lesson_' + (idx + 1));
                trackPost('/api/track-lesson/', { lesson_code: code });
            });
        });

        // Паронимы: клик по карточке с data-track-paponim
        document.addEventListener('click', function (e) {
            const card = e.target.closest('[data-track-paponim]');
            if (card) trackPost('/api/track-paponim/', { paponim_code: card.dataset.trackPaponim });
        });
    });
})();
