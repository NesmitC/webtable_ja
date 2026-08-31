/* Поповер контактов в футере: открытие, закрытие, копирование */
(function () {
    'use strict';

    var pop = document.getElementById('contactsPop');
    if (!pop) return;
    var toggle = document.querySelector('.js-contacts-toggle');

    function isOpen() { return !pop.hidden; }
    function open() {
        pop.hidden = false;
        if (toggle) toggle.setAttribute('aria-expanded', 'true');
    }
    function close() {
        pop.hidden = true;
        if (toggle) toggle.setAttribute('aria-expanded', 'false');
    }

    if (toggle) {
        toggle.addEventListener('click', function (e) {
            e.stopPropagation();
            isOpen() ? close() : open();
        });
    }

    // Кнопки «Макс» в соцсетях открывают тот же поповер
    document.querySelectorAll('.js-contacts-open').forEach(function (btn) {
        btn.addEventListener('click', function (e) {
            e.stopPropagation();
            open();
        });
    });

    // «Позвонить»: на телефоне работает tel:, на десктопе открываем карточку контактов
    var phoneLink = document.querySelector('a.footer__social-link[href^="tel:"]');
    if (phoneLink) {
        phoneLink.addEventListener('click', function (e) {
            var touch = window.matchMedia && window.matchMedia('(pointer: coarse)').matches;
            if (!touch) {
                e.preventDefault();
                e.stopPropagation();
                open();
            }
        });
    }

    // Клики внутри поповера не закрывают его
    pop.addEventListener('click', function (e) { e.stopPropagation(); });

    // Закрытие: клик мимо и Esc
    document.addEventListener('click', function () { if (isOpen()) close(); });
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && isOpen()) close();
    });

    // Копирование в буфер
    function fallbackCopy(text) {
        var ta = document.createElement('textarea');
        ta.value = text;
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        try { document.execCommand('copy'); } catch (e) { /* noop */ }
        document.body.removeChild(ta);
    }

    pop.querySelectorAll('.contacts-pop__copy').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var text = btn.getAttribute('data-copy');
            var done = function () {
                var old = btn.textContent;
                btn.textContent = 'Скопировано ✓';
                setTimeout(function () { btn.textContent = old; }, 1500);
            };
            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(text).then(done, function () { fallbackCopy(text); done(); });
            } else {
                fallbackCopy(text);
                done();
            }
        });
    });
})();
