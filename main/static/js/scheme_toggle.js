// Ленивая схема пунктуации: <img> создаётся только по первому клику «Показать схему»,
// повторные открытия не делают новых запросов. Кнопка .scheme-toggle[data-src]
// управляет панелью из aria-controls; тиражируется на задания 17–21 без правок JS.
(function () {
    'use strict';

    var toggles = [];

    function initToggle(btn) {
        var panel = document.getElementById(btn.getAttribute('aria-controls'));
        if (!panel) return;
        var label = btn.querySelector('.scheme-toggle__label');
        var skeleton = panel.querySelector('.scheme-skeleton');
        var figure = panel.querySelector('.scheme-figure');
        var scroller = panel.querySelector('.scheme-scroller');
        if (!skeleton || !figure || !scroller) return;

        var img = null;
        var loaded = false;

        function setLabel(open) {
            btn.setAttribute('aria-expanded', String(open));
            if (label) label.textContent = open ? 'Скрыть схему' : 'Показать схему';
        }

        function openPanel() {
            panel.hidden = false;
            setLabel(true);
            if (loaded) {
                skeleton.hidden = true;
                figure.hidden = false;
                return;
            }
            btn.setAttribute('aria-busy', 'true');
            skeleton.hidden = false;
            skeleton.textContent = 'Загружаем схему…';
            figure.hidden = true;
            if (!img) {
                img = document.createElement('img');
                img.alt = btn.getAttribute('data-alt') || 'Схема правила';
                img.width = parseInt(btn.getAttribute('data-width'), 10) || 3399;
                img.height = parseInt(btn.getAttribute('data-height'), 10) || 1155;
                img.decoding = 'async';
                img.addEventListener('load', function () {
                    loaded = true;
                    btn.removeAttribute('aria-busy');
                    skeleton.hidden = true;
                    figure.hidden = false;
                });
                img.addEventListener('error', function () {
                    btn.removeAttribute('aria-busy');
                    skeleton.textContent = 'Не удалось загрузить схему. Нажмите кнопку ещё раз.';
                    if (img) {
                        img.remove();
                        img = null;
                    }
                });
                scroller.appendChild(img);
                img.src = btn.getAttribute('data-src');
            }
        }

        function closePanel() {
            panel.hidden = true;
            setLabel(false);
        }

        btn.addEventListener('click', function () {
            if (btn.getAttribute('aria-busy') === 'true') return;
            if (panel.hidden) openPanel(); else closePanel();
        });

        toggles.push({ panel: panel, close: closePanel });
    }

    document.addEventListener('keydown', function (e) {
        if (e.key !== 'Escape') return;
        toggles.forEach(function (t) {
            if (!t.panel.hidden) t.close();
        });
    });

    document.querySelectorAll('.scheme-toggle').forEach(initToggle);
})();