function displayOrthoepyResults(results) {
    const resultDiv = document.querySelector('.orthoepy-result');
    if (!resultDiv) return;

    // Находим ВСЕ варианты в тесте
    const allOptions = document.querySelectorAll('.test-option[data-variant]');
    
    allOptions.forEach(option => {
        const variant = option.getAttribute('data-variant');
        const result = results.results[variant];
        
        if (result) {
            option.classList.remove('orthoepy-correct', 'orthoepy-incorrect');
            if (result.is_correct_variant) {
                option.classList.add('orthoepy-correct');
            } else {
                option.classList.add('orthoepy-incorrect');
            }
        }
    });

    // Выводим ТОЛЬКО балл
    resultDiv.innerHTML = `<p><strong>Балл:</strong> ${results.summary.user_score}</p>`;
    resultDiv.style.display = 'block';
    resultDiv.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}