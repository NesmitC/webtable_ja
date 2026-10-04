/* Онлайн-диктанты: родной виджет смайликов (как в диагностике) + проверка.
   Поведение один в один с test_fix_ege.js: клик по смайлу — список,
   выбор — буква встаёт на место, после проверки — зелёный/красный фон. */
(function () {
    'use strict';

    var checkBtn = document.getElementById('dctCheck');
    var scoreEl = document.getElementById('dctScore');

    function setupSmiley(btn) {
        var icon = btn.querySelector('.smiley-icon');
        var options = btn.querySelector('.smiley-options');
        if (!icon || !options) return;

        icon.onclick = function (e) {
            e.stopPropagation();
            document.querySelectorAll('.smiley-options').forEach(function (o) {
                if (o !== options) o.style.display = 'none';
            });
            options.style.display = options.style.display === 'block' ? 'none' : 'block';
        };

        options.querySelectorAll('li').forEach(function (li) {
            li.onclick = function (e) {
                e.stopPropagation();
                icon.textContent = li.dataset.letter;
                icon.classList.add('selected');
                options.style.display = 'none';
            };
        });
    }

    document.querySelectorAll('.smiley-button').forEach(setupSmiley);

    document.addEventListener('click', function (e) {
        if (!e.target.closest('.smiley-button')) {
            document.querySelectorAll('.smiley-options').forEach(function (o) {
                o.style.display = 'none';
            });
        }
    });

    if (!checkBtn) return;

    function cookie(name) {
        var m = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'));
        return m ? decodeURIComponent(m[1]) : '';
    }

    checkBtn.addEventListener('click', async function () {
        checkBtn.disabled = true;
        var answers = {};
        document.querySelectorAll('.smiley-button').forEach(function (btn) {
            var icon = btn.querySelector('.smiley-icon');
            answers[btn.dataset.slot] = icon.classList.contains('selected') ? icon.textContent : '';
        });
        try {
            var res = await fetch(checkBtn.dataset.checkUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': cookie('csrftoken')
                },
                body: JSON.stringify({ answers: answers })
            });
            var data = await res.json();
            if (!res.ok || data.error) {
                if (scoreEl) {
                    scoreEl.textContent = data.error || 'Не удалось проверить. Попробуй ещё раз.';
                    scoreEl.style.display = 'block';
                }
                checkBtn.disabled = false;
                return;
            }
            document.querySelectorAll('.smiley-button').forEach(function (btn) {
                var icon = btn.querySelector('.smiley-icon');
                var r = data.results[btn.dataset.slot];
                icon.classList.remove('correct', 'incorrect', 'selected');
                if (!r || r.skipped) return;          // не отвечал — смайл как был
                icon.classList.add(r.ok ? 'correct' : 'incorrect');
            });
            if (scoreEl) {
                var s = data.score;
                scoreEl.textContent = 'Верно ' + s.ok + ' из ' + s.total +
                    (s.answered < s.total ? ' · не отвечено: ' + (s.total - s.answered) : '');
                scoreEl.style.display = 'block';
                scoreEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }
        } catch (e) {
            if (scoreEl) {
                scoreEl.textContent = 'Ошибка сети. Попробуй ещё раз.';
                scoreEl.style.display = 'block';
            }
        }
        checkBtn.disabled = false;
    });
})();
