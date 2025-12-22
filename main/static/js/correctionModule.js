// correctionModule.js
window.CorrectionModule = (function () {
    async function loadCorrectionTest() {
        const answerSection = document.querySelector('.block-answer');
        if (!answerSection) return;

        answerSection.innerHTML = '<p>Загрузка задания 7...</p>';

        try {
            const csrf = getCookie('csrftoken');
            if (!csrf) {
                answerSection.innerHTML = '<p class="error">Сессия истекла.</p>';
                return;
            }

            const res = await fetch('/api/generate-correction-test/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrf
                },
                body: JSON.stringify({})
            });

            if (!res.ok) throw new Error(`HTTP ${res.status}`);

            const data = await res.json();
            if (data.html) {
                answerSection.innerHTML = data.html;
                setupCorrectionCheck();
            } else {
                answerSection.innerHTML = `<p class="error">${data.error || 'Ошибка загрузки'}</p>`;
            }
        } catch (e) {
            console.error('Ошибка загрузки задания 7:', e);
            answerSection.innerHTML = '<p class="error">Не удалось загрузить задание. Попробуйте позже.</p>';
        }
    }

    function setupCorrectionCheck() {
        const btn = document.querySelector('.check-correction');
        if (!btn) return;

        btn.onclick = async () => {
            const input = document.querySelector('.correction-input');
            const resultDiv = document.querySelector('.correction-result');
            if (!input || !resultDiv) return;

            const userAnswer = input.value.trim();
            if (!userAnswer) {
                alert('Введите исправленное слово.');
                return;
            }

            btn.disabled = true;
            btn.textContent = 'Проверяем...';

            try {
                const csrf = getCookie('csrftoken');
                const res = await fetch('/api/check-correction/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrf
                    },
                    body: JSON.stringify({ answer: userAnswer })
                });

                const result = await res.json();
                if (result.score === 1) {
                    resultDiv.innerHTML = `<p style="color: green;">✅ Верно! Балл: 1</p>`;
                } else {
                    resultDiv.innerHTML = `<p style="color: red;">❌ Неверно. Правильно: <strong>${result.correct}</strong></p>`;
                }
                resultDiv.style.display = 'block';
            } catch (e) {
                alert('Ошибка при проверке: ' + e.message);
            } finally {
                btn.disabled = false;
                btn.textContent = 'Проверить';
            }
        };
    }

    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    return {
        loadCorrectionTest: loadCorrectionTest
    };
})();