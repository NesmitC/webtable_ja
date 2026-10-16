// main/static/js/task9_report.js — отчёт задания 9: «Работа над ошибками»
// и «История прохождений». Общий для тренажёров (planning.js) и открытых
// SEO-страниц (task9.js): стилизацию оценили ученики, не расходимся.
// ============================================================================

window.Task9Report = {

    // Блоки задания 9, где включена летопись:
    // 1 — проверяемые гласные, 2 — непроверяемые, CHERED — чередующиеся
    SUPPORTED: ['1', '2', 'CHERED'],

    esc(s) {
        const d = document.createElement('div');
        d.textContent = (s === null || s === undefined) ? '' : String(s);
        return d.innerHTML;
    },

    /** Карточка ошибки: слово, в котором красным стоит буква ученика */
    correctionItemHtml(item) {
        const chosen = (item.chosen_letter || '').toLowerCase();
        if (!chosen) return '';
        const html = this.esc(item.word).replace(
            /\*\d+\*/,
            '<span class="wrong-stress">' + this.esc(chosen) + '</span>'
        );
        return '<div class="correction-item">' + html + '</div>';
    },

    /** Слово с правильной буквой (для заметки «Отработано») */
    correctWordHtml(item) {
        const letter = (item.correct_letter || '').toLowerCase();
        return this.esc(item.word).replace(
            /\*\d+\*/,
            '<b>' + this.esc(letter) + '</b>'
        );
    },

    /** Блоки ошибок по датам; пусто — вердикт «Молодца» */
    renderCorrection(items, resolved) {
        const host = document.getElementById('task9-correction-blocks');
        if (!host) return;
        const cnt = document.getElementById('task9-correction-count');
        const note = document.getElementById('task9-resolved-note');

        if (note) {
            note.innerHTML = (resolved && resolved.length)
                ? '<div class="correction-resolved">✓ Отработано в этот раз: ' +
                  resolved.map(it => this.correctWordHtml(it)).join(', ') + '</div>'
                : '';
        }

        if (!items || !items.length) {
            if (cnt) cnt.textContent = '';
            host.innerHTML = '<div class="correction-success">Молодца, ошибок в этом блоке нет!</div>';
            return;
        }
        if (cnt) cnt.textContent = '(слов: ' + items.length + ')';

        const byDate = {};
        items.forEach(it => {
            const key = it.correction_since || '';
            (byDate[key] = byDate[key] || []).push(it);
        });

        let html = '';
        Object.keys(byDate).sort().reverse().forEach(date => {
            html += '<div class="correction-group">' +
                '<div class="correction-group__title">Блок ошибок от ' + this.esc(date) + '</div>' +
                '<div class="correction-group__items">';
            byDate[date].forEach(it => { html += this.correctionItemHtml(it); });
            html += '</div></div>';
        });
        host.innerHTML = html;
    },

    /** История прохождений: дата, результат, процент */
    renderHistory(attempts) {
        const host = document.getElementById('task9-history-container');
        if (!host) return;
        if (!attempts || !attempts.length) {
            host.innerHTML = '<div class="history-empty">Прохождений пока нет.</div>';
            return;
        }
        let html = '<table class="history-table">' +
            '<thead><tr><th>Дата</th><th>Результат</th><th>%</th></tr></thead><tbody>';
        attempts.forEach(a => {
            const pct = a.chosen ? Math.round(a.correct / a.chosen * 100) : 0;
            const cls = pct >= 80 ? 'history-pct--high' : (pct >= 50 ? 'history-pct--mid' : 'history-pct--low');
            html += '<tr>' +
                '<td>' + this.esc(a.date) + '</td>' +
                '<td>верно ' + a.correct + ' из ' + a.chosen + '</td>' +
                '<td class="history-pct ' + cls + '">' + pct + '%</td>' +
                '</tr>';
        });
        html += '</tbody></table>';
        host.innerHTML = html;
    },

    /** Монтирует оба блока отчёта в конец контейнера упражнения */
    renderInto(container, report, resolved) {
        if (!container || !report) return;
        container.querySelectorAll('.task9-report').forEach(el => el.remove());
        const wrap = document.createElement('div');
        wrap.className = 'task9-report';
        wrap.innerHTML =
            '<section class="block-correction">' +
            '<h2 class="title-planing">Работа над ошибками <span id="task9-correction-count"></span></h2>' +
            '<div id="task9-resolved-note"></div>' +
            '<div id="task9-correction-blocks"></div>' +
            '</section>' +
            '<section class="block-history">' +
            '<h2 class="title-planing">История прохождений</h2>' +
            '<div id="task9-history-container"></div>' +
            '</section>';
        container.appendChild(wrap);
        this.renderCorrection(report.correction || [], resolved || []);
        this.renderHistory(report.attempts || []);
    },
};
