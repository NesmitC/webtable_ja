// main/static/js/task9.js — лёгкий тренажёр для открытых SEO-страниц задания 9.
// Самодостаточен: planning.js сюда не тянем (2 000+ строк ради смайликов —
// минус к скорости загрузки органического трафика).
(function () {
    'use strict';

    var container = document.querySelector('.task9-seo-content');
    if (!container) return;

    var endpoint = container.dataset.endpoint || 'alphabetical';
    var orthogramId = container.dataset.orthogram || '';

    function getCookie(name) {
        var matches = document.cookie.match(
            new RegExp('(?:^|; )' + name.replace(/([\.$?*|{}\(\)\[\]\\\/\+^])/g, '\\$1') + '=([^;]*)'));
        return matches ? decodeURIComponent(matches[1]) : null;
    }

    // === Буквы для смайликов ===
    var lettersCache = {
        '1': ['а', 'о', 'е', 'и', 'я', 'у', 'ю'],
        '2': ['а', 'о', 'е', 'и', 'я', 'у', 'ю']
    };

    function getLetters(orthId) {
        if (lettersCache[orthId]) return Promise.resolve(lettersCache[orthId]);
        return fetch('/api/orthogram/' + encodeURIComponent(orthId) + '/letters/')
            .then(function (r) { return r.json(); })
            .then(function (data) {
                var letters = (data && data.letters && data.letters.length)
                    ? data.letters : ['а', 'о', 'е', 'и', 'я'];
                lettersCache[orthId] = letters;
                return letters;
            })
            .catch(function () {
                lettersCache[orthId] = ['а', 'о', 'е', 'и', 'я'];
                return lettersCache[orthId];
            });
    }

    var MASK_RE = /\*([^*]+)\*/;

    function smileyHtml(orthId) {
        var items = (lettersCache[orthId] || ['а', 'о', 'е', 'и', 'я'])
            .map(function (l) { return '<span class="smiley-option" data-letter="' + l + '">' + l + '</span>'; })
            .join('');
        return '<span class="smiley-button" data-orth-id="' + orthId + '">'
            + '<span class="smiley-icon">😊</span>'
            + '<span class="smiley-options" style="display:none">' + items + '</span>'
            + '</span>&nbsp;';
    }

    // Маски вида *1* → смайлик с выпадающим списком букв.
    // ВАЖНО: ни ul, ни li внутри <p class="practice-line"> — парсер закрывает
    // параграф на блоке и ломает nowrap-обёртку слова. Только span'ы.
    // Слово с пропуском собирается в один nowrap-блок: иначе браузер
    // разрывает строку на границе inline-block (смайлика) и слово
    // «воскл😊 / цание» читается как два — ученики не понимают слово.
    function masksToSmileys(lineText) {
        var tokens = lineText.split(' ');
        var ids = [];
        tokens.forEach(function (tok) {
            var re = /\*([^*]+)\*/g;
            var m;
            while ((m = re.exec(tok)) !== null) {
                if (ids.indexOf(m[1]) === -1) ids.push(m[1]);
            }
        });
        if (!ids.length) return Promise.resolve(lineText);

        return Promise.all(ids.map(getLetters)).then(function () {
            return tokens.map(function (tok) {
                if (!MASK_RE.test(tok)) return tok;
                var inner = tok.replace(/\*([^*]+)\*/g, function (m, id) {
                    return smileyHtml(id);
                });
                return '<span class="task9-word">' + inner + '</span>';
            }).join(' ');
        });
    }

    function processContainer(root) {
        var lines = root.querySelectorAll('.practice-line');
        Array.prototype.forEach.call(lines, function (line) {
            if (line.hasAttribute('data-processed')) return;
            var text = (line.textContent || '').trim();
            if (!text) { line.setAttribute('data-processed', 'empty'); return; }
            line.setAttribute('data-processed', 'true');
            masksToSmileys(text).then(function (html) { line.innerHTML = html; });
        });
    }

    function resultBox() {
        var box = container.querySelector('.task9-result');
        if (!box) {
            box = document.createElement('p');
            box.className = 'task9-result';
            container.appendChild(box);
        }
        return box;
    }

    // === Загрузка упражнения по диапазону ===
    Array.prototype.forEach.call(
        document.querySelectorAll('.task9-range-btn'),
        function (btn) {
            btn.addEventListener('click', function () {
                var body = { mode: 'seo', range: btn.dataset.range };
                var url = '/api/generate-chered-exercise/';
                if (endpoint === 'alphabetical') {
                    url = '/api/generate-alphabetical-exercise/';
                    body.orthogram_id = orthogramId;
                    body.range = btn.dataset.range;
                }
                container.innerHTML = '<div class="loading">Загрузка...</div>';
                fetch(url, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken')
                    },
                    body: JSON.stringify(body)
                })
                    .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
                    .then(function (res) {
                        if (!res.ok || res.d.error) {
                            container.innerHTML = '';
                            resultBox().classList.add('is-error');
                            resultBox().textContent = res.d.error || 'Не удалось загрузить упражнение';
                            return;
                        }
                        container.innerHTML = res.d.html;
                        processContainer(container);
                        if (res.d.report) {
                            Task9Report.renderInto(container, res.d.report, []);
                        }
                    })
                    .catch(function () {
                        container.innerHTML = '';
                        resultBox().classList.add('is-error');
                        resultBox().textContent = 'Ошибка загрузки. Обновите страницу.';
                    });
            });
        });

    // === Смайлики: открыть список, выбрать букву, закрыть по клику вне ===
    document.addEventListener('click', function (e) {
        if (!container.contains(e.target)) return;

        if (!e.target.closest('.smiley-button')) {
            container.querySelectorAll('.smiley-options').forEach(function (o) {
                o.style.display = 'none';
            });
            return;
        }
        if (e.target.classList.contains('smiley-icon')) {
            e.preventDefault();
            e.stopPropagation();
            var opts = e.target.closest('.smiley-button').querySelector('.smiley-options');
            container.querySelectorAll('.smiley-options').forEach(function (o) {
                if (o !== opts) o.style.display = 'none';
            });
            opts.style.display = opts.style.display === 'block' ? 'none' : 'block';
            return;
        }
        if (e.target.classList.contains('smiley-option')) {
            e.preventDefault();
            e.stopPropagation();
            var icon = e.target.closest('.smiley-button').querySelector('.smiley-icon');
            icon.textContent = e.target.dataset.letter;
            icon.classList.add('selected');
            icon.classList.remove('correct', 'incorrect');
            e.target.closest('.smiley-options').style.display = 'none';
        }
    });

    // === Проверка: только подсветка и счёт, без летописи и отчётов ===
    container.addEventListener('click', function (e) {
        if (!e.target.classList.contains('check-answers')) return;
        e.preventDefault();

        var smileys = container.querySelectorAll('.smiley-button');
        if (!smileys.length) return;

        var selected = [];
        var hasSelection = false;
        smileys.forEach(function (s) {
            var letter = s.querySelector('.smiley-icon').textContent.trim();
            if (letter !== '😊') hasSelection = true;
            selected.push(letter === '😊' ? null : letter);
        });
        if (!hasSelection) {
            resultBox().classList.add('is-error');
            resultBox().textContent = 'Сначала выбери хотя бы одну букву!';
            return;
        }

        fetch('/api/check-alphabetical-exercise/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({ selected_letters: selected })
        })
            .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
            .then(function (res) {
                var box = resultBox();
                box.classList.remove('is-error');
                if (!res.ok || res.d.error) {
                    box.classList.add('is-error');
                    box.textContent = res.d.error || 'Не удалось проверить';
                    return;
                }
                var icons = container.querySelectorAll('.smiley-icon');
                icons.forEach(function (icon, i) {
                    icon.classList.remove('selected', 'correct', 'incorrect');
                    if (i < res.d.results.length) {
                        icon.classList.add(res.d.results[i] ? 'correct' : 'incorrect');
                    }
                });
                box.remove();
                if (res.d.report) {
                    Task9Report.renderInto(container, res.d.report, res.d.resolved || []);
                }
            })
            .catch(function () {
                var box = resultBox();
                box.classList.add('is-error');
                box.textContent = 'Ошибка проверки. Попробуйте ещё раз.';
            });
    });
    // === Серверный рендер упражнения (страница приставок): смайлики и
    // отчёт сразу после загрузки, без клика по диапазону ===
    if (container.querySelector('.practice-line')) {
        processContainer(container);
        var initialNode = document.getElementById('task10-initial-report');
        if (initialNode) {
            try {
                var initial = JSON.parse(initialNode.textContent);
                if (initial && typeof initial.attempts !== 'undefined') {
                    Task9Report.renderInto(container, initial, []);
                }
            } catch (e) { /* отчёт не критичен для тренажёра */ }
        }
    }
})();
