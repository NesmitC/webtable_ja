/* Модальное окно для юридических документов (политика, оферта).
   Ссылки с классом js-doc-link открывают документ в диалоге;
   без JS (или при ошибке загрузки) ссылка ведёт на отдельную страницу. */
(function () {
    'use strict';

    // Стили модального окна — инжектятся один раз
    var style = document.createElement('style');
    style.textContent = [
        '.pm-overlay{position:fixed;inset:0;z-index:1200;background:rgba(24,14,5,.45);display:flex;align-items:center;justify-content:center;padding:20px;opacity:0;transition:opacity .2s}',
        '.pm-overlay.pm-open{opacity:1}',
        '.pm-dialog{background:#FDFAF5;border:1px solid #D3C8B8;border-radius:14px;max-width:760px;width:100%;max-height:84vh;display:flex;flex-direction:column;box-shadow:0 18px 50px rgba(24,14,5,.35)}',
        '.pm-header{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:14px 20px;border-bottom:1px solid #D3C8B8}',
        '.pm-title{font-family:var(--font-heading,serif);font-size:18px;font-weight:600;color:#180E05;margin:0}',
        '.pm-actions{display:flex;align-items:center;gap:10px}',
        '.pm-ext{font-size:12px;color:#9C5A1D;text-decoration:none;white-space:nowrap}',
        '.pm-ext:hover{text-decoration:underline}',
        '.pm-close{border:none;background:transparent;font-size:22px;line-height:1;cursor:pointer;color:#7A6A54;padding:4px 6px}',
        '.pm-close:hover{color:#180E05}',
        '.pm-body{overflow-y:auto;padding:20px 24px}',
        '.pm-body h1{font-size:22px;line-height:1.3;margin:0 0 6px;font-family:var(--font-heading,serif)}',
        '.pm-body h2{font-size:17px;margin:22px 0 8px;font-family:var(--font-heading,serif)}',
        '.pm-body p,.pm-body li{font-size:13.5px;line-height:1.6;margin:0 0 8px}',
        '.pm-body ul{padding-left:18px;margin:0 0 10px}',
        '.pm-body .card{background:transparent;border:none;padding:0;margin:0;box-shadow:none}',
        '.pm-loading{color:#7A6A54;font-size:14px}'
    ].join('');
    document.head.appendChild(style);

    var overlay = null;

    function build() {
        overlay = document.createElement('div');
        overlay.className = 'pm-overlay';
        overlay.setAttribute('role', 'dialog');
        overlay.setAttribute('aria-modal', 'true');
        overlay.innerHTML =
            '<div class="pm-dialog">' +
            '<div class="pm-header">' +
            '<h3 class="pm-title">Документ</h3>' +
            '<div class="pm-actions">' +
            '<a class="pm-ext" href="/privacy/" target="_blank" rel="noopener">Открыть в отдельном окне ↗</a>' +
            '<button class="pm-close" type="button" aria-label="Закрыть">×</button>' +
            '</div></div>' +
            '<div class="pm-body"><p class="pm-loading">Загружаем документ…</p></div>' +
            '</div>';
        document.body.appendChild(overlay);

        overlay.addEventListener('click', function (e) {
            if (e.target === overlay) close();
        });
        overlay.querySelector('.pm-close').addEventListener('click', close);
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && overlay.classList.contains('pm-open')) close();
        });
    }

    function open(link) {
        if (!overlay) build();
        overlay.querySelector('.pm-title').textContent =
            link.getAttribute('data-title') || 'Документ';
        overlay.querySelector('.pm-ext').setAttribute('href', link.getAttribute('href'));
        overlay.classList.add('pm-open');
        document.body.style.overflow = 'hidden';
    }

    function close() {
        if (!overlay) return;
        overlay.classList.remove('pm-open');
        document.body.style.overflow = '';
    }

    function load(link) {
        open(link);
        fetch(link.getAttribute('href'))
            .then(function (r) { return r.text(); })
            .then(function (html) {
                var doc = new DOMParser().parseFromString(html, 'text/html');
                var content = doc.getElementById('privacy-content') ||
                    doc.getElementById('terms-content');
                var body = overlay.querySelector('.pm-body');
                if (content) {
                    body.innerHTML = content.innerHTML;
                    body.scrollTop = 0;
                } else {
                    body.innerHTML = '<p>Документ временно недоступен. ' +
                        '<a href="' + link.getAttribute('href') + '" target="_blank" rel="noopener">' +
                        'Открыть в отдельном окне</a>.</p>';
                }
            })
            .catch(function () {
                // Не смогли загрузить — честно открываем страницу
                window.open(link.getAttribute('href'), '_blank');
                close();
            });
    }

    document.addEventListener('click', function (e) {
        var link = e.target.closest ? e.target.closest('a.js-doc-link') : null;
        if (!link) return;
        e.preventDefault();
        load(link);
    });
})();
