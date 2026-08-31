/* Видеоуроки: модальный плеер (Rutube / Kinescope) */
(function () {
    var modal = document.getElementById('videoModal');
    var frame = document.getElementById('videoModalFrame');
    var toast = document.getElementById('videoToast');
    if (!modal || !frame) return;

    function open(src) {
        frame.src = src;
        modal.hidden = false;
        document.body.style.overflow = 'hidden';
    }

    function close() {
        modal.hidden = true;
        frame.src = ''; // останавливаем видео
        document.body.style.overflow = '';
    }

    var toastTimer;
    function showToast(msg) {
        if (!toast) return;
        toast.textContent = msg;
        toast.hidden = false;
        clearTimeout(toastTimer);
        toastTimer = setTimeout(function () { toast.hidden = true; }, 2500);
    }

    document.addEventListener('click', function (e) {
        var btn = e.target.closest('[data-video-src]');
        if (btn) {
            e.preventDefault();
            var src = btn.getAttribute('data-video-src');
            if (src) open(src);
            else showToast('Видео к этому уроку скоро появится 🎬');
            return;
        }
        if (e.target.closest('[data-video-close]')) close();
    });

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && !modal.hidden) close();
    });
})();
