function displayOrthoepyResults(results) {
    const resultDiv = document.querySelector('.orthoepy-result');
    if (!resultDiv) return;

    // Получаем данные
    const task4Results = results.results?.['4'];
    if (!task4Results?.variant_results) return;

    const variantResults = task4Results.variant_results;

    // Обрабатываем все варианты
    document.querySelectorAll('.test-option').forEach((option, index) => {
        const resultKey = `4-${index + 1}`;
        const variantResult = variantResults[resultKey];
        if (!variantResult) return;

        const checkbox = option.querySelector('.orthoepy-checkbox');
        const textSpan = option.querySelector('.variant-text');
        if (!checkbox || !textSpan) return;

        // Цвет текста для всех вариантов
        textSpan.style.color = variantResult.is_correct ? '#28a745' : '#dc3545';
        textSpan.style.fontWeight = '600';

        // Обводка только для выбранных
        if (checkbox.checked) {
            checkbox.style.outline = 'none';
            if (variantResult.is_correct) {
                checkbox.style.border = '3px solid #10b981';
                checkbox.style.boxShadow = '0 0 6px 2px rgba(16, 185, 129, 0.7)';
            } else {
                checkbox.style.border = '3px solid #ef4444';
                checkbox.style.boxShadow = '0 0 6px 2px rgba(239, 68, 68, 0.7)';
            }
        }
    });

    // Блокируем и обновляем UI
    document.querySelectorAll('.orthoepy-checkbox').forEach(cb => cb.disabled = true);
    
    const checkBtn = document.querySelector('.check-orthoepy-test');
    if (checkBtn) {
        checkBtn.textContent = 'Проверено';
        checkBtn.disabled = true;
    }
    
    resultDiv.innerHTML = `<p><strong>Балл:</strong> ${results.user_score ?? task4Results.score ?? 0}</p>`;
    resultDiv.style.display = 'block';
}