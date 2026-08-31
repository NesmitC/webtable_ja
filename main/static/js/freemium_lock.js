// Freemium-замки: перехватывает клики по заблокированным блокам и кнопкам квизов
(function () {
    'use strict';

    function showToast() {
        var t = document.querySelector('.freemium-toast');
        if (!t) {
            t = document.createElement('div');
            t.className = 'freemium-toast';
            t.style.cssText = 'position:fixed;left:50%;bottom:24px;transform:translateX(-50%);' +
                'background:#4A3520;color:#FDFAF5;padding:12px 20px;border-radius:12px;' +
                'font-size:14px;z-index:2000;box-shadow:0 8px 24px rgba(24,14,5,.3);' +
                'max-width:92vw;text-align:center;transition:opacity .4s;';
            t.innerHTML = '🔒 Этот раздел — часть платных тарифов. ' +
                '<a href="/#pricing" style="color:#FFD9A0;font-weight:600;">Выбрать тариф →</a>';
            document.body.appendChild(t);
        }
        t.style.opacity = '1';
        clearTimeout(t._h);
        t._h = setTimeout(function () { t.style.opacity = '0'; }, 5000);
    }

    // capture=true — срабатываем РАНЬШЕ обработчиков quiz.js/planning.js
    document.addEventListener('click', function (e) {
        if (e.target.closest('.quiz-trigger.locked') || e.target.closest('.locked-feature')) {
            e.preventDefault();
            e.stopPropagation();
            showToast();
        }
    }, true);

    // защита от фокуса/ввода в заблокированных полях
    document.addEventListener('focusin', function (e) {
        if (e.target.closest && e.target.closest('.locked-feature')) {
            e.target.blur();
            showToast();
        }
    }, true);
})();
