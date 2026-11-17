// Ленивая схема пунктуации: <img> создаётся только по первому клику «Показать схему»,
// повторные открытия не делают новых запросов. Кнопка .scheme-toggle[data-src]
// управляет панелью из aria-controls; тиражируется на задания 17–21 без правок JS.
// data-src может содержать список URL через запятую (сдвоенные уроки 19–20):
// картинки встают одна под другой, у каждой свой горизонтальный скролл.
// data-width/data-height — списки через запятую, data-alt — через «|».
(function () {
    'use strict';

    var toggles = [];

    function splitAttr(btn, name, sep) {
        return (btn.getAttribute(name) || '').split(sep).map(function (s) { return s.trim(); });
    }

    function initToggle(btn) {
        var panel = document.getElementById(btn.getAttribute('aria-controls'));
        if (!panel) return;
        var label = btn.querySelector('.scheme-toggle__label');
        var skeleton = panel.querySelector('.scheme-skeleton');
        var figure = panel.querySelector('.scheme-figure');
        var scroller = panel.querySelector('.scheme-scroller');
        if (!skeleton || !figure || !scroller) return;

        var imgs = [];
        var loaded = false;
        var attempt = 0;

        function setLabel(open) {
            btn.setAttribute('aria-expanded', String(open));
            if (label) label.textContent = open ? 'Скрыть схему' : 'Показать схему';
        }

        function resetImages() {
            // удалить все скроллеры кроме первого, первый очистить
            figure.querySelectorAll('.scheme-scroller').forEach(function (sc) {
                if (sc === scroller) sc.innerHTML = ''; else sc.remove();
            });
            imgs = [];
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
            if (!imgs.length) {
                var srcs = splitAttr(btn, 'data-src', ',').filter(Boolean);
                var widths = splitAttr(btn, 'data-width', ',');
                var heights = splitAttr(btn, 'data-height', ',');
                var alts = splitAttr(btn, 'data-alt', '|');
                var remaining = srcs.length;
                var myAttempt = ++attempt;
                srcs.forEach(function (src, i) {
                    var sc = scroller;
                    if (i > 0) {
                        sc = document.createElement('div');
                        sc.className = 'scheme-scroller';
                        figure.appendChild(sc);
                    }
                    var img = document.createElement('img');
                    img.alt = alts[i] || alts[0] || 'Схема правила';
                    img.width = parseInt(widths[i], 10) || 3399;
                    img.height = parseInt(heights[i], 10) || 1155;
                    img.decoding = 'async';
                    img.addEventListener('load', function () {
                        if (myAttempt !== attempt) return;
                        remaining -= 1;
                        if (remaining === 0) {
                            loaded = true;
                            btn.removeAttribute('aria-busy');
                            skeleton.hidden = true;
                            figure.hidden = false;
                        }
                    });
                    img.addEventListener('error', function () {
                        if (myAttempt !== attempt) return;
                        attempt += 1;
                        btn.removeAttribute('aria-busy');
                        skeleton.textContent = 'Не удалось загрузить схему. Нажмите кнопку ещё раз.';
                        resetImages();
                    });
                    sc.appendChild(img);
                    img.src = src;
                    imgs.push(img);
                });
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
        toggles.forEach(function (t) { if (!t.panel.hidden) t.close(); });
    });

    document.querySelectorAll('.scheme-toggle').forEach(initToggle);
})();