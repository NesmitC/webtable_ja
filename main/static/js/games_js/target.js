
//---------------- база данных - слова -------------------
//const segment = document.querySelectorAll('.svg__segm'),
const words = document.querySelector('.arrow__text');
/*    arrAll = [
		...arrPrilIskl,
		...arrKratkotPrich,
		...arrSuffOnnEnn,
		...arrSushN,
		...arrPrichsPrist,
		...arrPrichSov,
		...arrPrichOvaEva,
		...arrPrichZavis,
		...arrPrichNesov,
		...arrPrichIskl,
		...arrPrichKr,
		...arrPrilVetr,
		...arrPrilNul,
		...arrPrilAn,
		...arrPrilJan,
		...arrPrilIn
	];*/

//let denWord = arrAll[Math.floor(Math.random() * arrAll.length)];
let denWord = '';
let denWords = [];

// Функция-помощник, меняет слово на стрелке
function setDenWord(word) {
	denWord = word;
	words.textContent = `${word}`;
}

// Выбрать новое слово
function generateNewDenWord() {
	setDenWord(denWords[Math.floor(Math.random() * denWords.length)]);
}

function isSegmentValid(name) {
	if (!(name in segmentsInfo)) {
		console.error(`Неизвестный сегмент: "${name}"`);
		return false;
	}

	return true;
}

// Включить обратно все сегменты
function resetAllSegments() {
	Object.keys(segmentsInfo).forEach((segment) => segmentsInfo[segment].enabled = true);
	document.querySelectorAll("svg.blurred").forEach((e) => e.classList.remove("blurred"));
}

// Создать массив слов из включённых сегментов
function buildWordArray() {
	let newWordArray = [];
	Object.keys(segmentsInfo).forEach(segment => {
		if (segmentsInfo[segment].enabled)
			newWordArray = [...newWordArray, ...segmentsInfo[segment].wordArray];
	});
	denWords = newWordArray;

	// Выбираем новое слово, так как текущего может и не быть в выбранных сегментах
	generateNewDenWord();
}

// Посчитать количество включённых сегментов
function countEnabledSegments() {
	let count = 0;
	Object.keys(segmentsInfo).forEach((segment) => {
		if (segmentsInfo[segment].enabled == true)
			count++;
	});
	return count;
}

// Позволяет включить или выключить сегмент по имени
function setSegment(name, enabled) {
	if (!isSegmentValid(name))
		return;

	segmentsInfo[name].enabled = enabled;
	document.querySelector(`.svg__segm.${name}`).classList.toggle("blurred", !enabled);

	medalReset();
	buildWordArray();
}

// true если сегмент включён, false если сегмент выключен или сегмент с таким названием не существует
function isSegmentEnabled(name) {
	if (!isSegmentValid(name))
		return false;

	return segmentsInfo[name].enabled;
}

// Переключить состояние сегмента
function toggleSegment(name) {
	setSegment(name, !isSegmentEnabled(name));
}

// =================== МЕДАЛЬКИ ======================================

let wrapMedal = document.querySelector('.wrapper-medal');
let wordHistory = [];

for (let i = 0; i < 51; i++) {
	wrapMedal.insertAdjacentHTML('beforeend', '<figure class="medal"></figure>');
}
let denMedal = Array.from(document.querySelectorAll('.medal')),
	denCount = 0,
	denCorrect = 0;

// Сбросить окраску медалек
function medalReset() {
	denMedal.forEach((medal) => medal.removeAttribute("style"));
	denCount = 0;
	denCorrect = 0;
	wordHistory = [];
}

// Покрасить медаль. Если чистых медалей больше нет, то убирает все медали и красит самую первую
function medalColor(color) {
	if (denCount >= denMedal.length) {
		// medalReset();
		console.error("Больше нет места под медальки!");
		return;
	}

	let medal = denMedal[denCount];
	medal.style.background = color;
	denCount++;

	if (denCount == denMedal.length)
		gameOver();
}

function medalRight() {
	medalColor("yellow");
	denCorrect++;
}

function medalWrong() {
	medalColor("red");
	// Запоминаем неправильное слово
	wordHistory.push(denWord);
}

function medalUndo() {
	if (denCount >= denMedal.length || denCount == 0)
		return;

	let medal = denMedal[denCount - 1];
	if (medal.style.background == "red") {
		medal.removeAttribute("style");
		denCount--;

		// Возвращаем неправильное слово и убираем из истории
		setDenWord(wordHistory.pop());
	}
}

// Перезапуск игры
function restart() {
	medalReset();
	generateNewDenWord();
}

//----------------------------- drag drop -------------------------------------
let isDrag = false; // Двигаем ли мы стрелку
let isEditingSegments = false; // Находимся ли мы в режиме редактирования сегментов
let currentSegment = null; // Указатель на текущий сегмент под курсором
let currentSegmentInfo = null;

function enableArrow(event) {
	// Начинаем движение только если не редактируем сегмента
	if (!isEditingSegments)
		isDrag = true;
}

drive.addEventListener('mousedown', enableArrow);
drive.addEventListener('touchstart', enableArrow);

// Возвращает имя сегмента, внутри которого лежат данные координаты экрана, или "", если такого сегмента нет
function getSegmentNameFromScreenCoordinates(sX, sY) {
	const wheelRect = svg_base.getBoundingClientRect(); // target.
	if (sX >= wheelRect.left && sX <= wheelRect.right
		&& sY >= wheelRect.top && sY <= wheelRect.bottom) {

		// Переводим координаты экрана в координаты относительно центра мишени
		const relativeX = (sX - wheelRect.left) / wheelRect.width - 0.5;
		const relativeY = (1 - (sY - wheelRect.top) / wheelRect.height) - 0.5; // ось Y надо перевернуть, потому что в браузере ось Y идёт сверху вниз

		return highlightSegment(relativeX, relativeY);
	}

	return "";
}

function documentMouseMove(event) {
	// Продолжаем только если мы тащим стрелку

	if (!isDrag)
		return;

	// Получаем координаты конца стрелки
	let arrowTipRect = tag.getBoundingClientRect();
	const arrowTipY = arrowTipRect.top + arrowTipRect.height / 2;
	const arrowTipX = arrowTipRect.left + arrowTipRect.width / 2;


	const lastActive = currentSegment; // запоминаем прошлый активный сегмент
	// Проверяем, попала ли стрелка в мишень
	let segment = getSegmentNameFromScreenCoordinates(arrowTipX, arrowTipY);

	// Отменяем выбор сегмента, если он выключен
	if (segment != "" && !isSegmentEnabled(segment))
		segment = "";

	if (segment != "") {
		// Добавляем класс active тому сегменту, в который попали, если попали в принципе, а также запоминаем его на будущее
		const el = document.querySelector(`.svg__segm.${segment}`);
		if (el == null) {
			console.error(`Не существует сегмента под тегом ${segment}!`);
			currentSegment = null;
			currentSegmentInfo = null;
		} else {
			// Задаём новый активный сегмент
			el.classList.add("active");
			currentSegment = el;
			currentSegmentInfo = segmentsInfo[segment];
		}
	} else {
		currentSegment = null;
		currentSegmentInfo = null;
	}

	// Убираем подсветку с прошлого активного сегмента, если активный сегмент поменялся
	if (lastActive != null && lastActive != currentSegment) {
		lastActive.classList.remove("active");
	}
}

document.addEventListener('mousemove', documentMouseMove);
document.addEventListener('touchmove', documentMouseMove);

function documentMouseUp() {
	// Нет смысла обрабатывать отпускание ЛКМ, если мы до этого ничего не тащили
	if (!isDrag)
		return;

	// Сразу же даём знать, что мы начали обработку сегмента под стрелкой
	isDrag = false;

	// возвращаем стрелку на место
	drive.style.left = '54%';
	drive.style.top = '55%';

	// Также нет смысла что-либо делать, если игрок никуда не попал
	if (currentSegment == null)
		return;

	if (currentSegmentInfo.wordArray.includes(denWord)) {
		medalRight();
	} else {
		medalWrong();
	}

	generateNewDenWord();

	// убираем подсветку с активного сегмента и забываем его
	currentSegment.classList.remove("active");
	currentSegment = null;
}
document.addEventListener('mouseup', documentMouseUp);
document.addEventListener('touchend', documentMouseUp);

// Получает: координаты [-0.5; 0.5] стрелки, где ось X идёт слева направа, а Y - снизу вверх
// Отдаёт: название сегмента, в который попала стрелка, или пустую строку
function highlightSegment(x, y) {
	// Угол в радианах [0; 2*PI]
	let angle = Math.atan2(y, x);
	if (angle < 0)
		angle += 2 * Math.PI;
	// Получаем расстояние до центра по теореме Пифагора
	const distance = Math.sqrt(x * x + y * y);
	// console.log(`Угол: ${angle}; расстояние: ${distance}`);

	// Получаем кусок окружности
	const slice = Math.floor((angle / Math.PI / 2) * targetSegments.length);

	// Получаем кольцо
	let ring = -1;
	for (let i = 0; i < targetRadiuses.length; i++) {
		if (targetRadiuses[i] > distance) {
			ring = i;
			break;
		}
	}
	// Выходим, если мишень не попала ни в одно из колец
	if (ring == -1)
		return '';

	const ringSlice = targetSegments[slice][ring];
	// если на кольце дольки окружности находится только один сегмент
	if (typeof ringSlice == "string")
		return ringSlice;

	// в противном случае тип ringSlice - массив, надо выбрать один из сегментов исходя из угла
	const sliceArc = Math.PI * 2 / targetSegments.length;
	const sliceAngleBegin = slice / targetSegments.length * Math.PI * 2;
	const subSegment = Math.floor((angle - sliceAngleBegin) / sliceArc * ringSlice.length);
	return ringSlice[subSegment];
}

document.addEventListener('mousemove', (event) => {
	if (isDrag) {
		drive.style.left = (event.pageX - 70) + 'px';
		drive.style.top = (event.pageY - 155) + 'px';
	} else {
		drive.style.left = '54%';
		drive.style.top = '55%';
	}
});

document.addEventListener('touchmove', (event) => {
	if (isDrag) {
		const firstTouch = event.targetTouches[0];
		drive.style.left = (firstTouch.pageX - 70) + 'px';
		drive.style.top = (firstTouch.pageY - 155) + 'px';
	} else {
		drive.style.left = '54%';
		drive.style.top = '55%';
	}
});

let currentSegmentEditing = null;
let currentSegmentEditingName = "";
function targetMouseMove(event) {
	// Обрабатываем перемещение мыши по мишени само по себе только если редактируем сегменты
	if (!isEditingSegments)
		return;

	const lastActive = currentSegmentEditing; // запоминаем прошлый активный сегмент
	currentSegmentEditingName = getSegmentNameFromScreenCoordinates(event.clientX, event.clientY);
	if (currentSegmentEditingName != "") {
		// Добавляем класс active тому сегменту, в который попали, если попали в принципе, а также запоминаем его на будущее
		const el = document.querySelector(`.svg__segm.${currentSegmentEditingName}`);
		if (el == null) {
			console.error(`Не существует сегмента под тегом ${currentSegmentEditingName}!`);
			currentSegmentEditing = null;
		} else {
			// Задаём новый активный сегмент
			el.classList.add("active");
			currentSegmentEditing = el;
		}
	} else {
		currentSegmentEditing = null;
	}

	// Убираем подсветку с прошлого активного сегмента, если активный сегмент поменялся
	if (lastActive != null && lastActive != currentSegmentEditing) {
		lastActive.classList.remove("active");
	}
}
target.addEventListener('mousemove', targetMouseMove);

target.addEventListener('mouseup', (event) => {
	// Обрабатываем нажатие ЛКМ по мишени само по себе только если редактируем сегменты
	if (!isEditingSegments)
		return;

	// Нет смысла обрабатывать нажатие, если игрок никуда не попал
	if (currentSegmentEditing === null || currentSegmentEditingName === "")
		return;

	// Если мы собираемся выключить сегмент, но активных сегментов всего два, то отменим действие
	if (isSegmentEnabled(currentSegmentEditingName) && countEnabledSegments() <= 2) {
		console.error("Нельзя играть с количеством сегментов, меньшим двух");
		return;
	}

	toggleSegment(currentSegmentEditingName);
});
target.addEventListener('touchend', (event) => {
	// Обрабатываем нажатие ЛКМ по мишени само по себе только если редактируем сегменты
	if (!isEditingSegments)
		return;

	currentSegmentEditingName = getSegmentNameFromScreenCoordinates(event.clientX, event.clientY);

	// Нет смысла обрабатывать нажатие, если игрок никуда не попал
	if (currentSegmentEditing === null || currentSegmentEditingName === "")
		return;

	// Если мы собираемся выключить сегмент, но активных сегментов всего два, то отменим действие
	if (isSegmentEnabled(currentSegmentEditingName) && countEnabledSegments() <= 2) {
		console.error("Нельзя играть с количеством сегментов, меньшим двух");
		return;
	}

	toggleSegment(currentSegmentEditingName);
});

const btnClose = document.querySelectorAll('[data-btn="0"]'),
	modal = document.querySelectorAll('.modal');

function closeModal(ii) {
	btnClose[ii].addEventListener('click', () => {
		modal[ii].close();
	})
}


// =================== МОДАЛЬНОЕ ОКНО ПРАВИЛА ===============================

const btnOpenPrav = document.querySelector('[data-btn="prav"]'),
	btnClosePrav = document.querySelector('[data-btn="pravClose"]');

btnOpenPrav.addEventListener('click', () => {
	modal[9].showModal();
})

btnClosePrav.addEventListener('click', () => {
	modal[9].close();
})

// =================== МОДАЛЬНОЕ ОКНО КОНЦА ИГРЫ =============================

function gameOver() {
	if (denCount == 0)
		return; // Медалек нет, игра ещё не началась, нечего заканчивать

	game_over_count.textContent = `${denCorrect}`;

	const percent = denCorrect / denCount;
	let description = '2 - Начинающий стрелок';
	if (percent >= 0.90) // 90%, Превосходный стрелок
		description = '5 - Превосходный стрелок';
	else if (percent >= 0.70) // 70%, Хороший стрелок
		description = '4 - Хороший стрелок';
	else if (percent >= 0.45) // 45%, Перспективный стрелок
		description = '3 - Перспективный стрелок'

	game_over_mark.textContent = description;

	modal_game_over.showModal();
}

function closeGameOver() {
	modal_game_over.close();
	resetAllSegments();
	restart();
}


// ============== КНОПКИ НАВИГАЦИИ ====================================

// Для элементов, имеющих id, сразу же создаются переменные в JavaScript

// Начать заново
b_restart.onclick = () => {
	restart();
}

// Удалить/добавить сегмент
b_edit.onclick = () => {
	isEditingSegments = !isEditingSegments;
	b_edit.classList.toggle("highlight", isEditingSegments);
	b_edit.innerText = isEditingSegments ? "Продолжить игру" : "Удалить / добавить сегмент";
	drive.style.display = isEditingSegments ? "none" : "";
	document.body.classList.toggle("editing", isEditingSegments);

	// Если режим редактирования выключен, то возвращаем всё как было
	if (!isEditingSegments) {
		currentSegmentEditing?.classList.remove("active");
		currentSegmentEditing = null;
	}
}

// Отменить ход
b_undo.onclick = () => {
	medalUndo();
}

// Пропустить ход
b_skip.onclick = () => {
	generateNewDenWord();
}

// Инициализация
buildWordArray();
restart();