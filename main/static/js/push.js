/* Нейростат: управление Web Push-подпиской в личном кабинете.
   Кнопки: #push-enable / #push-disable, статус: #push-status,
   подсказка для iPhone: #push-ios-hint. Подключается только на /profile/. */
(function () {
    var enableBtn = document.getElementById('push-enable');
    if (!enableBtn) return;
    var disableBtn = document.getElementById('push-disable');
    var statusEl = document.getElementById('push-status');
    var iosHint = document.getElementById('push-ios-hint');
    var csrf = (document.cookie.match(/(^| )csrftoken=([^;]+)/) || [])[2] || '';

    function setStatus(text, bad) {
        if (!statusEl) return;
        statusEl.textContent = text;
        statusEl.style.color = bad ? '#b00020' : '#2e7d32';
    }

    function isIOS() {
        var ua = navigator.userAgent;
        return /iPhone|iPad|iPod/.test(ua) ||
            (/Macintosh/.test(ua) && 'ontouchend' in document);
    }

    function supported() {
        return 'serviceWorker' in navigator &&
            'PushManager' in window && 'Notification' in window;
    }

    function urlB64ToUint8Array(base64String) {
        var padding = '='.repeat((4 - base64String.length % 4) % 4);
        var base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
        var raw = window.atob(base64);
        var arr = new Uint8Array(raw.length);
        for (var i = 0; i < raw.length; i++) arr[i] = raw.charCodeAt(i);
        return arr;
    }

    function showState(sub) {
        var on = !!sub && Notification.permission === 'granted';
        enableBtn.style.display = on ? 'none' : '';
        disableBtn.style.display = on ? '' : 'none';
        if (on) {
            setStatus('✅ Пуш включён — «Слово дня» будет приходить в 16:00 МСК.', false);
        }
    }

    function refresh() {
        if (!supported()) {
            enableBtn.style.display = 'none';
            if (isIOS()) {
                iosHint.style.display = '';
            } else {
                setStatus('Этот браузер не поддерживает push-уведомления.', true);
            }
            return;
        }
        navigator.serviceWorker.ready.then(function (reg) {
            return reg.pushManager.getSubscription();
        }).then(showState).catch(function () {});
    }

    enableBtn.onclick = async function () {
        if (!supported()) { refresh(); return; }
        // iOS даёт push только сайту с домашнего экрана (standalone-режим)
        if (isIOS() && !window.navigator.standalone) {
            iosHint.style.display = '';
            setStatus('На iPhone сначала добавьте сайт на домашний экран.', true);
            return;
        }
        var perm = await Notification.requestPermission();
        if (perm !== 'granted') {
            setStatus('Разрешение на уведомления не выдано — ' +
                'включите его в настройках браузера.', true);
            return;
        }
        try {
            var cfg = await (await fetch('/api/push/config/')).json();
            if (!cfg.enabled) {
                setStatus('Пуш ещё не настроен на сервере — зайдите позже.', true);
                return;
            }
            var reg = await navigator.serviceWorker.ready;
            var sub = await reg.pushManager.getSubscription() ||
                await reg.pushManager.subscribe({
                    userVisibleOnly: true,
                    applicationServerKey: urlB64ToUint8Array(cfg.vapid_public_key)
                });
            var keys = sub.toJSON().keys;
            var res = await fetch('/api/push/subscribe/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
                body: JSON.stringify({
                    endpoint: sub.endpoint,
                    keys: { p256dh: keys.p256dh, auth: keys.auth }
                })
            });
            var data = await res.json();
            if (data.status === 'ok') {
                showState(sub);
            } else {
                setStatus('❌ ' + (data.error || 'Ошибка сохранения подписки'), true);
            }
        } catch (e) {
            setStatus('❌ Ошибка включения: ' + e, true);
        }
    };

    disableBtn.onclick = async function () {
        try {
            var reg = await navigator.serviceWorker.ready;
            var sub = await reg.pushManager.getSubscription();
            await fetch('/api/push/unsubscribe/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
                body: JSON.stringify({ endpoint: sub ? sub.endpoint : '' })
            });
            if (sub) await sub.unsubscribe();
            showState(null);
            setStatus('Пуш отключён.', false);
        } catch (e) {
            setStatus('❌ Ошибка отключения: ' + e, true);
        }
    };

    refresh();
})();
