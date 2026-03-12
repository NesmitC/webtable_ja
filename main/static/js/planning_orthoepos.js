// main\static\js\planning_orthoepos.js

// Отображение результатов
window.displayOrthoepyResults = function(results) {
    const container = document.querySelector('.orthoepy-test-exercise');
    const isSchoolMode = container?.dataset.schoolMode === 'true';
    
    const task4Results = results.results?.['4'];
    if (!task4Results?.variant_results) return;
    
    const variantResults = task4Results.variant_results;
    const options = document.querySelectorAll('.test-option');
    
    // Считаем статистику
    let correctCount = 0;      // Сколько ПРАВИЛЬНЫХ вариантов выбрано
    let totalSelected = 0;     // Сколько ВСЕГО вариантов выбрано
    let totalCorrect = 0;      // Сколько ВСЕГО правильных вариантов существует
    
    options.forEach((option, index) => {
        const variantResult = variantResults[`4-${index + 1}`];
        if (!variantResult) return;
        
        const checkbox = option.querySelector('.orthoepy-checkbox');
        const textSpan = option.querySelector('.variant-text');
        if (!checkbox || !textSpan) return;
        
        // Подсчитываем общее количество правильных вариантов
        if (variantResult.is_correct) totalCorrect++;
        
        // Подсветка текста
        textSpan.style.color = variantResult.is_correct ? '#28a745' : '#dc3545';
        textSpan.style.fontWeight = '600';
        
        // Обработка выбранных вариантов
        if (checkbox.checked) {
            totalSelected++;
            if (variantResult.is_correct) correctCount++;
            
            // Обводка для выбранных
            checkbox.style.outline = 'none';
            checkbox.style.border = variantResult.is_correct ? 
                '3px solid #10b981' : '3px solid #ef4444';
            checkbox.style.boxShadow = variantResult.is_correct ? 
                '0 0 6px 2px rgba(16, 185, 129, 0.7)' : 
                '0 0 6px 2px rgba(239, 68, 68, 0.7)';
        }
    });
    
    // Блокируем чекбоксы
    document.querySelectorAll('.orthoepy-checkbox').forEach(cb => cb.disabled = true);
    
    // Обновляем кнопку
    const checkBtn = document.querySelector('.check-orthoepy-test');
    if (checkBtn) {
        checkBtn.textContent = 'Проверено';
        checkBtn.disabled = true;
    }
    
    // === ПОКАЗ РЕЗУЛЬТАТА ===
    if (isSchoolMode) {
        // Создаём/находим блок результата
        let resultDiv = document.querySelector('.orthoepy-result');
        if (!resultDiv) {
            resultDiv = document.createElement('div');
            resultDiv.className = 'orthoepy-result';
            container.appendChild(resultDiv);
        }
        
        // === ДЕТАЛЬНАЯ ЛОГИКА ПРОВЕРКИ ===
        const hasMissingCorrect = totalSelected < totalCorrect;          // Не все правильные выбраны
        const hasWrongSelection = correctCount < totalSelected;          // Есть неправильные среди выбранных
        const allCorrect = !hasMissingCorrect && !hasWrongSelection && totalSelected > 0;
        
        let message = '';
        let color = '#dc3545';
        
        if (allCorrect) {
            message = '✓ Правильно!';
            color = '#28a745';
        } else if (hasMissingCorrect && hasWrongSelection) {
            message = '✗ Неправильно, не все слова выбраны, есть ошибки';
        } else if (hasMissingCorrect) {
            message = '✗ Неправильно, не все слова выбраны';
        } else if (hasWrongSelection) {
            message = '✗ Неправильно, есть ошибки';
        } else {
            // Ничего не выбрано
            message = '✗ Неправильно, не все слова выбраны';
        }
        
        // Формируем вывод
        resultDiv.innerHTML = `<p style="color: ${color}; font-weight: bold; font-size: 1.1em; margin-top: 15px;">${message}</p>`;
        resultDiv.style.display = 'block';
        
    } else {
        // Для ЕГЭ - используем существующий элемент
        const resultDiv = document.querySelector('.orthoepy-result');
        if (resultDiv) {
            resultDiv.innerHTML = `<p><strong>Балл:</strong> ${results.user_score ?? task4Results.score ?? 0}</p>`;
            resultDiv.style.display = 'block';
        }
    }
};