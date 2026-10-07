"use strict";

// Тренажёр «Радуга»: склонение числительных. Порт движка schoolsplay.
// Правки относительно оригинала: data-min/data-max у кнопок диапазонов,
// closest() вместо строгого сравнения className, защита focusout на пустом
// вводе, дипссылка ?chislo=NNN. Логика склонений (rainbow_numToWord.js) — без изменений.

import { Gender, Case, numToWord } from "./rainbow_numToWord.js";

const trainingNumber = document.querySelector("#training-number");
const trainingControls = document.querySelector(".training-controls");
const trainingReload = document.querySelector("#training-reload");
const trainingCheck = document.querySelector("#training-check");
const trainingInput = document.querySelector("#training-input");
const trainingSheet = document.querySelector(".training-sheet");

trainingInput.value = "";

const isCorrectWord = w => !/[^а-яё]/i.test(w);
const random = (min, max) => Math.floor(Math.random() * (max - min + 1) + min);

const caseNodes = {
  [Case.Nominative]: document.querySelectorAll("#row-nominative td:not(.case-desc)"),
  [Case.Genitive]: document.querySelectorAll("#row-genitive td:not(.case-desc)"),
  [Case.Dative]: document.querySelectorAll("#row-dative td:not(.case-desc)"),
  [Case.Accusative]: document.querySelectorAll("#row-accusative td:not(.case-desc)"),
  [Case.Instrumental]: document.querySelectorAll("#row-instrumental td:not(.case-desc)"),
  [Case.Prepositional]: document.querySelectorAll("#row-prepositional td:not(.case-desc)"),
};
const noCheckNodes = [Case.Nominative, Case.Accusative];

const splitWordNumber = wordNumber => {
  const words = wordNumber.split(" ");
  const tensRexp = /(?<pref>[а-яё]+)(?<suf>десят[а-яё]*)$/i;
  const hundredsRexp = /(?<pref>[а-яё]+)(?<suf>(ста|сот|сти)[а-яё]*)$/i;
  const result = [];

  for (let i = 0; i < words.length; i++) {
    const word = words[i];

    if (word.search(tensRexp) !== -1) {
      const { pref, suf } = word.match(tensRexp).groups;
      result.push(pref, suf);

      continue;
    }

    if (word.search(hundredsRexp) !== -1 && !word.includes("девяно")) {
      const { pref, suf } = word.match(hundredsRexp).groups;

      if (suf === "сти" && !pref.startsWith("дв")) {
        result.push(word);
        continue;
      }

      result.push(pref, suf);

      continue;
    }

    result.push(word);
  }

  return result;
};

const clearCaseNodes = () => {
  for (let caseKey in caseNodes) {
    caseNodes[caseKey].forEach(node => node.textContent = "");
  }
};

const cutRules = {
  [Case.Genitive]: {
    "т[а-я]$": 1,
    "тысяч[а-я]{3}$": 3,
    "тысяч[а-я]{2}$": 2,
    "тысяч[а-я]$": 1,
    "^тысяч$": 2,
    "^один$": 2,
    "^од[а-я]{4}": 3,
    "^од[а-я]{3}": 2,
    "^од[а-я]{2}": 1,
    "^дв": 2,
    "^тр[а-я]{0,3}": 2,
    "^четы": 2,
    "^пят": 2,
    "^шест": 2,
    "^сем": 1,
    "^вос": 1,
    "^девят": 1,
    "^соро": 1,
    "^ста": 1,
    "^сот": 2,
    "^девяно": 1,
  },

  [Case.Dative]: {
    "т[а-я]$": 1,
    "тысяч[а-я]{3}$": 3,
    "тысяч[а-я]{2}$": 2,
    "тысяч[а-я]$": 1,
    "^тысяч$": 2,
    "^стам": 2,
    "^один$": 2,
    "^од[а-я]{4}": 3,
    "^од[а-я]{3}": 2,
    "^од[а-я]{2}": 1,
    "^дв": 2,
    "^тр[а-я]{0,3}": 2,
    "^четы": 2,
    "^пят": 2,
    "^шест": 2,
    "^сем": 1,
    "^вос": 1,
    "^девят": 1,
    "^соро": 1,
    "^ста": 1,
    "^сот": 2,
    "^девяно": 1,
  },

  [Case.Instrumental]: {
    "^девяно": 1,
    "тысяч[а-я]{3}$": 3,
    "тысяч[а-я]{2}$": 2,
    "тысяч[а-я]$": 1,
    "^тысяч$": 2,
    "^стам": 3,
    "^ста": 1,
    "т[а-я][а-я]?$": 2,
    "^один$": 2,
    "^од[а-я]{4}": 3,
    "^од[а-я]{3}": 2,
    "^од[а-я]{2}": 1,
    "^дв": 3,
    "^тр[а-я]{0,3}": 3,
    "^четы": 3,
    "^пят": 2,
    "^шест": 2,
    "^сем": 2,
    "^вос": 2,
    "^девят": 2,
    "^соро": 1,
    "^сот": 2,
  },

  [Case.Prepositional]: {
    "т[а-я]$": 1,
    "тысяч[а-я]{3}$": 3,
    "тысяч[а-я]{2}$": 2,
    "тысяч[а-я]$": 1,
    "^тысяч$": 2,
    "^стах": 2,
    "^один$": 2,
    "^од[а-я]{4}": 3,
    "^од[а-я]{3}": 2,
    "^од[а-я]{2}": 1,
    "^дв": 2,
    "^тр[а-я]{0,3}": 2,
    "^четы": 2,
    "^пят": 2,
    "^шест": 2,
    "^сем": 1,
    "^вос": 1,
    "^девят": 1,
    "^соро": 1,
    "^ста": 1,
    "^сот": 2,
    "^девяно": 1,
  },
};

const cutSuf = (word, caseKey) => {
  const rules = cutRules[caseKey];
  for (let rule in rules) {
    if (new RegExp(`${rule}`, "i").test(word)) {
      const delSuf = rules[rule];
      const pref = word.substring(0, word.length - delSuf);
      const suf = word.substring(word.length - delSuf);

      return [pref, suf];
    }
  }

  const pref = word.substring(0, word.length - 2);
  const suf = word.substring(word.length - 2);

  return [pref, suf];
};

const insertCaseNodes = (currentCases) => {
  clearCaseNodes();

  for (let caseKey in currentCases) {
    const cases = currentCases[caseKey];
    const nodes = caseNodes[caseKey];

    cases.forEach((word, i) => {
      let cut, suf;

      if (!noCheckNodes.includes(+caseKey)) {
        const cuted = cutSuf(word, +caseKey);
        cut = cuted[0];
        suf = cuted[1];
      }

      if (noCheckNodes.includes(+caseKey)) {
        nodes[i].textContent = word;
        nodes[i].dataset.suf = "";
      } else {
        nodes[i].innerHTML =
          `<span>${cut}</span>
           <input
             class="suf-check"
             type="text"
             maxlength="3"
             autocomplete="off"
             data-suf=${suf}
           />`;
      }
    });
  }
};

const updateCurrentNumber = num => {
  if (!num) {
    clearCaseNodes();
    trainingNumber.textContent = "";
    return;
  }

  trainingNumber.textContent = num;

  const currentCases = {
    [Case.Nominative]: [],
    [Case.Genitive]: [],
    [Case.Dative]: [],
    [Case.Accusative]: [],
    [Case.Instrumental]: [],
    [Case.Prepositional]: [],
  };

  for (let key in currentCases) {
    const wordNumber = numToWord(num, Gender.Masculine, key);
    currentCases[key] = splitWordNumber(wordNumber);
  }

  insertCaseNodes(currentCases);
};

trainingCheck.addEventListener("click", () => {
  const inputs = document.querySelectorAll(".suf-check");
  if (inputs.length) {
    let needAlert = false;

    for (let i = 0; i < inputs.length; i++) {
      inputs[i].classList.remove("empty-input");

      if (inputs[i].value === "") {
        inputs[i].classList.add("empty-input");
        needAlert = true;
      }
    }

    if (needAlert) return alert("Заполните все поля");

    for (let i = 0; i < inputs.length; i++) {
      const suf = inputs[i].dataset.suf;
      const value = inputs[i].value;
      inputs[i].classList.remove("done", "mistake");

      if (suf === value || suf === value.replace("е", "ё"))
        inputs[i].classList.add("done");
      else {
        inputs[i].classList.add("mistake");
        inputs[i].value = suf;
      }
    }
  }
});

trainingReload.addEventListener("click", () => {
  trainingInput.value = "";
  lastInput = null;
  updateCurrentNumber(null);
  clearCaseNodes();
});

trainingSheet.addEventListener("input", e => {
  const target = e.target;
  if (target.className.includes("suf-check")) {
    target.classList.remove("done", "mistake");
    const value = target.value;
    if (!isCorrectWord(value)) {
      target.value = value.replace(/[^а-яё]/gi, "");
    }
  }
});

trainingControls.addEventListener("click", e => {
  const btn = e.target.closest(".training-generate");
  if (btn && btn.dataset.min && btn.dataset.max) {
    trainingInput.value = "";
    lastInput = null;
    updateCurrentNumber(random(+btn.dataset.min, +btn.dataset.max));
  }
});

let lastInput = null;
trainingInput.addEventListener("input", e => {
  const target = e.target;
  const value = +target.value;

  if (e.target.value.search(/[^0-9]/) !== -1) {
    target.blur();
    trainingInput.value = lastInput || "";
    alert("Разрешены только числа.");
    return;
  }

  if (value > 999999) {
    target.blur();
    trainingInput.value = lastInput || "";
    alert("Слишком большое число.");
    return;
  }

  if (value === 0 && e.target.value !== "") {
    target.blur();
    trainingInput.value = "";
    alert("Это должно быть число больше нуля.");
    return;
  }

  lastInput = value;
});

trainingInput.addEventListener("focusout", () => {
  if (lastInput && +trainingNumber.textContent !== lastInput)
    updateCurrentNumber(lastInput);
});
trainingInput.addEventListener("keyup", e => {
  if (e.key === "Enter" && lastInput) {
    updateCurrentNumber(lastInput);
    trainingInput.blur();
  }
});

// Дипссылка: /sklonenie-chislitelnyh/?chislo=387 — открыть сразу с числом
// (для ссылок из рассылок, чатов и «домашних заданий» репетиторов).
const params = new URLSearchParams(window.location.search);
const prefill = params.get("chislo");
if (prefill && /^\d{1,6}$/.test(prefill) && +prefill > 0 && +prefill <= 999999) {
  lastInput = +prefill;
  trainingInput.value = prefill;
  updateCurrentNumber(+prefill);
}
