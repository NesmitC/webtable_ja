export let Gender;

(function(Gender) {
  Gender[(Gender["Masculine"] = 0)] = "Masculine"
  Gender[(Gender["Feminine"] = 1)] = "Feminine"
  Gender[(Gender["Neuter"] = 2)] = "Neuter"
})(Gender || (Gender = {}));

export let Case;

(function(Case) {
  Case[(Case["Nominative"] = 0)] = "Nominative"
  Case[(Case["Genitive"] = 1)] = "Genitive"
  Case[(Case["Dative"] = 2)] = "Dative"
  Case[(Case["Accusative"] = 3)] = "Accusative"
  Case[(Case["Instrumental"] = 4)] = "Instrumental"
  Case[(Case["Prepositional"] = 5)] = "Prepositional"
})(Case || (Case = {}));

const MINORS = [
  ["ноль", "нуля", "нулю", "ноль", "нулём", "нуле"],
  [
    ["один", "одна", "одно"],
    ["одного", "одной", "одного"],
    ["одному", "одной", "одному"],
    [["одного", "один"], "одну", "одно"],
    ["одним", "одной", "одним"],
    ["одном", "одной", "одном"]
  ],
  [
    ["два", "две", "два"],
    "двух",
    "двум",
    [["двух", "два"], ["двух", "две"], "два"],
    "двумя",
    "двух"
  ],
  [
    "три",
    "трёх",
    "трём",
    [["трёх", "три"], ["трёх", "три"], "три"],
    "тремя",
    "трёх"
  ],
  [
    "четыре",
    "четырёх",
    "четырём",
    [["четырёх", "четыре"], ["четырёх", "четыре"], "четыре"],
    "четырьмя",
    "четырёх"
  ],
  ["пять", "пяти", "пяти", "пять", "пятью", "пяти"],
  ["шесть", "шести", "шести", "шесть", "шестью", "шести"],
  ["семь", "семи", "семи", "семь", "семью", "семи"],
  ["восемь", "восьми", "восьми", "восемь", "восьмью", "восьми"],
  ["девять", "девяти", "девяти", "девять", "девятью", "девяти"],
  ["десять", "десяти", "десяти", "десять", "десятью", "десяти"],
  ...[
    "один",
    "две",
    "три",
    "четыр",
    "пят",
    "шест",
    "сем",
    "восем",
    "девят"
  ].map(prefix =>
    ["надцать", "надцати", "надцати", "надцать", "надцатью", "надцати"].map(
      suffix => `${prefix}${suffix}`
    )
  )
]

const TENS = [
  false,
  false,
  ["двадцать", "двадцати", "двадцати", "двадцать", "двадцатью", "двадцати"],
  ["тридцать", "тридцати", "тридцати", "тридцать", "тридцатью", "тридцати"],
  ["сорок", "сорока", "сорока", "сорок", "сорока", "сорока"],
  [
    "пятьдесят",
    "пятидесяти",
    "пятидесяти",
    "пятьдесят",
    "пятьюдесятью",
    "пятидесяти"
  ],
  [
    "шестьдесят",
    "шестидесяти",
    "шестидесяти",
    "шестьдесят",
    "шестьюдесятью",
    "шестидесяти"
  ],
  [
    "семьдесят",
    "семидесяти",
    "семидесяти",
    "семьдесят",
    "семьюдесятью",
    "семидесяти"
  ],
  [
    "восемьдесят",
    "восьмидесяти",
    "восьмидесяти",
    "восемьдесят",
    "восьмьюдесятью",
    "восьмидесяти"
  ],
  ["девяносто", "девяноста", "девяноста", "девяносто", "девяноста", "девяноста"]
]

const HUNDREDS = [
  false,
  ["сто", "ста", "ста", "сто", "ста", "ста"],
  ["двести", "двухсот", "двумстам", "двести", "двумястами", "двухстах"],
  ["триста", "трёхсот", "трёмстам", "триста", "тремястами", "трёхстах"],
  [
    "четыреста",
    "четырёхсот",
    "четырёмстам",
    "четыреста",
    "четырьмястами",
    "четырёхстах"
  ],
  ["пятьсот", "пятисот", "пятистам", "пятьсот", "пятьюстами", "пятистах"],
  ["шестьсот", "шестисот", "шестистам", "шестьсот", "шестьюстами", "шестистах"],
  ["семьсот", "семисот", "семистам", "семьсот", "семьюстами", "семистах"],
  [
    "восемьсот",
    "восьмисот",
    "восьмистам",
    "восемьсот",
    "восьмьюстами",
    "восьмистах"
  ],
  [
    "девятьсот",
    "девятисот",
    "девятистам",
    "девятьсот",
    "девятьюстами",
    "девятистах"
  ]
]

const LARGES = [
  false,
  [
    Gender.Feminine,
    ["тысяча", "тысячи", "тысяч"],
    ["тысячи", "тысяч", "тысяч"],
    ["тысяче", "тысячам", "тысячам"],
    ["тысячу", "тысячи", "тысяч"],
    ["тысячей", "тысячами", "тысячами"],
    ["тысяче", "тысячах", "тысячах"]
  ],
  ...["миллион", "миллиард", "триллион"].map(base => [
    Gender.Masculine,
    ...[
      ["", "а", "ов"],
      ["а", "ов", "ов"],
      ["у", "ам", "ам"],
      ["", "а", "ов"],
      ["ом", "ами", "ами"],
      ["е", "ах", "ах"]
    ].map(kase => kase.map(suffix => `${base}${suffix}`))
  ])
]

function small(number, gender, kase) {
  const result = []

  const hundreds = HUNDREDS[Math.floor(number / 100)]
  if (hundreds) {
    result.push(hundreds[kase])
  }

  const tens = TENS[Math.floor((number % 100) / 10)]
  if (tens) {
    result.push(tens[kase])
  }

  let minors = number % 100
  if (minors >= MINORS.length) {
    minors = number % 10
  }
  if (minors) {
    let part
    if (
      ((part = MINORS[minors][kase]) && typeof part === "string") ||
      ((part = MINORS[minors][kase][gender]) && typeof part === "string") ||
      (part = MINORS[minors][kase][gender][1])
    ) {
      result.push(part)
    }
  }

  return result.join(" ")
}

const pluralize = (count, one, two, five) => {
  count = Math.floor(Math.abs(count)) % 100;
  if (count > 10 && count < 20) {
    return five;
  }
  count = count % 10;
  if (1 === count) {
    return one;
  }
  if (count >= 2 && count <= 4) {
    return two;
  }
  return five;
}

export function numToWord(
  number,
  gender = Gender.Masculine,
  kase = Case.Nominative,
) {
  number = Math.abs(parseInt(String(number), 10))

  const result = []

  for (let l = LARGES.length, i = l; i >= 0; i--) {
    const base = Math.pow(10, i * 3)
    const current = Math.floor(number / base)
    number = number % base

    if (current) {
      const large = i ? LARGES[i] : null
      const numeral = small(
        current,
        large ? large[0] : gender,
        kase,
      )
      if (numeral) {
        result.push(numeral)
        if (large) {
          const [, ...forms] = large
          const plural = pluralize(
            current,
            forms[kase][0],
            forms[kase][1],
            forms[kase][2]
          )
          result.push(plural)
        }
      }
    }
  }

  return result.join(" ")
}
