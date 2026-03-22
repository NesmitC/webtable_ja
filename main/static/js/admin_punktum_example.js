(function () {
    'use strict';

    function getCsrf() {
        const el = document.querySelector('[name=csrfmiddlewaretoken]');
        return el ? el.value : '';
    }

    function getPunktumId() {
        const sel = document.getElementById('id_punktum');
        return sel ? sel.value : '';
    }

    function getMaskedWord() {
        const el = document.getElementById('id_masked_word');
        return el ? el.value : '';
    }

    function countMasks(maskedWord, punktumId) {
        if (!maskedWord || !punktumId) return 0;
        const pattern = '*' + punktumId + '*';
        let count = 0;
        let pos = 0;
        while ((pos = maskedWord.indexOf(pattern, pos)) !== -1) {
            count++;
            pos += pattern.length;
        }
        return count;
    }

    function getExplanationValues() {
        const el = document.getElementById('id_explanation');
        if (!el || !el.value.trim()) return [];
        if (el.value.includes(' ')) {
            return el.value.trim().split(' ').filter(Boolean);
        }
        return el.value.trim().split(',').map(s => s.trim()).filter(Boolean);
    }

    function setExplanation(values) {
        const el = document.getElementById('id_explanation');
        if (el) el.value = values.join(',');
    }

    let currentLetters = [];

    function renderSelectors(maskCount) {
        const container = document.getElementById('punktum-answer-selectors');
        if (!container) return;
        container.innerHTML = '';

        if (!maskCount || !currentLetters.length) return;

        const existing = getExplanationValues();

        const label = document.createElement('p');
        label.style.cssText = 'font-weight:bold; margin-bottom:6px;';
        label.textContent = 'Правильные ответы по маскам:';
        container.appendChild(label);

        const row = document.createElement('div');
        row.style.cssText = 'display:flex; flex-wrap:wrap; gap:12px;';

        for (let i = 0; i < maskCount; i++) {
            const wrap = document.createElement('div');

            const lbl = document.createElement('label');
            lbl.textContent = 'Маска ' + (i + 1) + ':';
            lbl.style.cssText = 'display:block; font-size:12px; margin-bottom:2px;';

            const sel = document.createElement('select');
            sel.dataset.maskIndex = i;
            sel.style.cssText = 'min-width:90px;';

            const blank = document.createElement('option');
            blank.value = '';
            blank.textContent = '—';
            sel.appendChild(blank);

            currentLetters.forEach(letter => {
                const opt = document.createElement('option');
                opt.value = letter;
                opt.textContent = letter;
                if (existing[i] === letter) opt.selected = true;
                sel.appendChild(opt);
            });

            sel.addEventListener('change', syncExplanation);

            wrap.appendChild(lbl);
            wrap.appendChild(sel);
            row.appendChild(wrap);
        }

        container.appendChild(row);
    }

    function syncExplanation() {
        const selects = document.querySelectorAll('#punktum-answer-selectors select');
        const values = Array.from(selects).map(s => s.value);
        setExplanation(values.filter(Boolean));
    }

    function loadLettersAndRender() {
        const punktumId = getPunktumId();
        if (!punktumId) {
            currentLetters = [];
            renderSelectors(0);
            return;
        }

        fetch('/api/oge-punktum/' + encodeURIComponent(punktumId) + '/letters/')
            .then(r => r.json())
            .then(data => {
                currentLetters = data.letters || [];
                const maskCount = countMasks(getMaskedWord(), punktumId);
                renderSelectors(maskCount);
            })
            .catch(() => {
                currentLetters = [];
            });
    }

    document.addEventListener('DOMContentLoaded', function () {
        const explanationField = document.getElementById('id_explanation');
        if (!explanationField) return;

        const container = document.createElement('div');
        container.id = 'punktum-answer-selectors';
        container.style.cssText = 'margin-top:10px; padding:10px; background:#f8f8f8; border:1px solid #ddd; border-radius:4px;';
        explanationField.parentNode.insertBefore(container, explanationField.nextSibling);

        const punktumSel = document.getElementById('id_punktum');
        const maskedWordEl = document.getElementById('id_masked_word');

        if (punktumSel) punktumSel.addEventListener('change', loadLettersAndRender);
        if (maskedWordEl) maskedWordEl.addEventListener('input', function () {
            const maskCount = countMasks(getMaskedWord(), getPunktumId());
            renderSelectors(maskCount);
        });

        loadLettersAndRender();
    });
})();
