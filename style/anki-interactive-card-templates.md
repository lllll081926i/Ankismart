# Anki 交互式样式卡片模板（单选/多选/填空/翻转）

下面给你 4 套可直接落地的模板方案。每套都包含：
- `Fields`（字段设计）
- `Front Template`（问题交互）
- `Back Template`（答案与解析）
- `Styling`（清晰分区 + 美观样式）

建议为每种题型分别创建一个 `Note Type`，便于维护。

---

## 0) 通用 Styling（可用于所有题型）

把这段放到对应 `Note Type` 的 `Styling` 中：

```css
:root {
  --bg: #f4f7fb;
  --panel: #ffffff;
  --text: #1f2a37;
  --muted: #6b7280;
  --accent: #1769aa;
  --accent-soft: #e7f2ff;
  --ok: #1f8a4c;
  --ok-soft: #e9f8ef;
  --warn: #b45309;
  --warn-soft: #fff4e5;
  --border: #dbe4ef;
  --shadow: 0 10px 28px rgba(23, 41, 64, 0.08);
}

.card {
  font-family: "Noto Sans", "Noto Sans CJK SC", "PingFang SC", "Microsoft YaHei", sans-serif;
  font-size: 20px;
  line-height: 1.6;
  color: var(--text);
  background: radial-gradient(circle at 0% 0%, #eef5ff 0%, var(--bg) 42%);
  margin: 0;
  padding: 18px;
}

.qa-wrap {
  max-width: 860px;
  margin: 0 auto;
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 16px;
  box-shadow: var(--shadow);
  overflow: hidden;
}

.qa-head {
  padding: 12px 16px;
  background: linear-gradient(120deg, #1769aa 0%, #1e88e5 100%);
  color: #fff;
  font-weight: 700;
  letter-spacing: 0.2px;
}

.section {
  padding: 16px;
  border-top: 1px solid var(--border);
}

.label {
  display: inline-block;
  margin-bottom: 8px;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.5px;
  text-transform: uppercase;
}

.label-q {
  background: #e6f0ff;
  color: #0f4b8b;
}

.label-a {
  background: var(--ok-soft);
  color: var(--ok);
}

.label-e {
  background: #f3f4f6;
  color: #374151;
}

.question {
  font-size: 1.05em;
  font-weight: 600;
}

.options {
  margin-top: 10px;
  display: grid;
  gap: 10px;
}

.opt {
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: #fbfdff;
  cursor: pointer;
  transition: all 0.18s ease;
}

.opt:hover {
  border-color: #8fb3d9;
  background: #f4f9ff;
}

.opt.selected {
  border-color: var(--accent);
  background: var(--accent-soft);
  box-shadow: inset 0 0 0 1px #8dbff1;
}

.opt.correct {
  border-color: var(--ok);
  background: var(--ok-soft);
}

.inline-help {
  margin-top: 10px;
  color: var(--muted);
  font-size: 0.9em;
}

.answer-box {
  border: 1px solid #b7e1c7;
  background: #f3fcf6;
  border-radius: 12px;
  padding: 10px 12px;
}

.explain-box {
  border: 1px solid #d8dde6;
  background: #f9fafb;
  border-radius: 12px;
  padding: 10px 12px;
}

.pill {
  display: inline-block;
  margin-right: 6px;
  margin-top: 6px;
  padding: 2px 10px;
  border-radius: 999px;
  border: 1px solid #b7d1ef;
  background: #eef6ff;
  color: #0f4b8b;
  font-size: 0.85em;
}

.input-row {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-top: 10px;
}

.ans-input {
  flex: 1;
  min-width: 140px;
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 8px 10px;
  font-size: 1em;
}

.btn {
  border: 1px solid #6ea5dc;
  border-radius: 10px;
  background: #eaf4ff;
  color: #114a86;
  padding: 8px 12px;
  cursor: pointer;
  font-weight: 600;
}

.btn:hover {
  background: #dceeff;
}

.judge {
  margin-top: 8px;
  font-size: 0.92em;
  font-weight: 600;
}

.judge.ok {
  color: var(--ok);
}

.judge.bad {
  color: var(--warn);
}

.nightMode.card {
  --bg: #0f1724;
  --panel: #111b2b;
  --text: #e5edf7;
  --muted: #95a3b8;
  --border: #2a3951;
  --accent-soft: #1a3350;
  --ok-soft: #173326;
  --warn-soft: #3b2a17;
  background: radial-gradient(circle at 0% 0%, #1a2a40 0%, #0f1724 42%);
}
```

---

## 1) 单选题（Single Choice）

### Fields

- `Question`
- `OptionA`
- `OptionB`
- `OptionC`
- `OptionD`
- `CorrectOption`（填 `A/B/C/D`）
- `Explanation`

### Front Template

```html
<div class="qa-wrap" id="sc-wrap">
  <div class="qa-head">Single Choice</div>

  <div class="section">
    <div class="label label-q">Question</div>
    <div class="question">{{Question}}</div>

    <div class="options" id="sc-options">
      <button class="opt" data-key="A">A. {{OptionA}}</button>
      <button class="opt" data-key="B">B. {{OptionB}}</button>
      <button class="opt" data-key="C">C. {{OptionC}}</button>
      <button class="opt" data-key="D">D. {{OptionD}}</button>
    </div>

    <div class="inline-help" id="sc-pick">请选择一个选项。</div>
  </div>
</div>

<script>
(function () {
  var root = document.getElementById('sc-options');
  if (!root) return;
  var pick = document.getElementById('sc-pick');
  var btns = root.querySelectorAll('.opt');
  btns.forEach(function (btn) {
    btn.addEventListener('click', function () {
      btns.forEach(function (b) { b.classList.remove('selected'); });
      btn.classList.add('selected');
      if (pick) pick.textContent = '已选择：' + btn.getAttribute('data-key');
    });
  });
})();
</script>
```

### Back Template

```html
<div class="qa-wrap">
  <div class="qa-head">Single Choice</div>

  <div class="section">
    <div class="label label-q">Question</div>
    <div class="question">{{Question}}</div>
    <div class="options">
      <div class="opt {{#CorrectOption}}{{#OptionA}}{{/OptionA}}{{/CorrectOption}}">A. {{OptionA}}</div>
      <div class="opt">B. {{OptionB}}</div>
      <div class="opt">C. {{OptionC}}</div>
      <div class="opt">D. {{OptionD}}</div>
    </div>
  </div>

  <div class="section">
    <div class="label label-a">Answer</div>
    <div class="answer-box">正确答案：<strong>{{CorrectOption}}</strong></div>
  </div>

  <div class="section">
    <div class="label label-e">Explanation</div>
    <div class="explain-box">{{Explanation}}</div>
  </div>
</div>

<script>
(function () {
  var correct = '{{CorrectOption}}'.trim().toUpperCase();
  var opts = document.querySelectorAll('.options .opt');
  ['A','B','C','D'].forEach(function (k, i) {
    if (opts[i] && k === correct) opts[i].classList.add('correct');
  });
})();
</script>
```

---

## 2) 多选题（Multiple Choice）

### Fields

- `Question`
- `OptionA`
- `OptionB`
- `OptionC`
- `OptionD`
- `OptionE`
- `CorrectOptions`（如 `A,C,E`）
- `Explanation`

### Front Template

```html
<div class="qa-wrap" id="mc-wrap">
  <div class="qa-head">Multiple Choice</div>

  <div class="section">
    <div class="label label-q">Question</div>
    <div class="question">{{Question}}</div>

    <div class="options" id="mc-options">
      <button class="opt" data-key="A">A. {{OptionA}}</button>
      <button class="opt" data-key="B">B. {{OptionB}}</button>
      <button class="opt" data-key="C">C. {{OptionC}}</button>
      <button class="opt" data-key="D">D. {{OptionD}}</button>
      <button class="opt" data-key="E">E. {{OptionE}}</button>
    </div>

    <div class="inline-help" id="mc-pick">可多选，点击切换。</div>
  </div>
</div>

<script>
(function () {
  var root = document.getElementById('mc-options');
  if (!root) return;
  var pick = document.getElementById('mc-pick');
  var btns = root.querySelectorAll('.opt');

  function refresh() {
    var chosen = [];
    btns.forEach(function (b) {
      if (b.classList.contains('selected')) chosen.push(b.getAttribute('data-key'));
    });
    pick.textContent = chosen.length ? ('已选择：' + chosen.join(', ')) : '可多选，点击切换。';
  }

  btns.forEach(function (btn) {
    btn.addEventListener('click', function () {
      btn.classList.toggle('selected');
      refresh();
    });
  });
})();
</script>
```

### Back Template

```html
<div class="qa-wrap">
  <div class="qa-head">Multiple Choice</div>

  <div class="section">
    <div class="label label-q">Question</div>
    <div class="question">{{Question}}</div>
    <div class="options" id="mc-back-options">
      <div class="opt" data-key="A">A. {{OptionA}}</div>
      <div class="opt" data-key="B">B. {{OptionB}}</div>
      <div class="opt" data-key="C">C. {{OptionC}}</div>
      <div class="opt" data-key="D">D. {{OptionD}}</div>
      <div class="opt" data-key="E">E. {{OptionE}}</div>
    </div>
  </div>

  <div class="section">
    <div class="label label-a">Answer</div>
    <div class="answer-box">正确答案：<strong>{{CorrectOptions}}</strong></div>
    <div id="mc-pills"></div>
  </div>

  <div class="section">
    <div class="label label-e">Explanation</div>
    <div class="explain-box">{{Explanation}}</div>
  </div>
</div>

<script>
(function () {
  var raw = '{{CorrectOptions}}';
  var keys = raw.split(',').map(function (s) { return s.trim().toUpperCase(); }).filter(Boolean);

  var backOpts = document.querySelectorAll('#mc-back-options .opt');
  backOpts.forEach(function (el) {
    if (keys.indexOf(el.getAttribute('data-key')) >= 0) el.classList.add('correct');
  });

  var pills = document.getElementById('mc-pills');
  if (pills) {
    keys.forEach(function (k) {
      var span = document.createElement('span');
      span.className = 'pill';
      span.textContent = 'Option ' + k;
      pills.appendChild(span);
    });
  }
})();
</script>
```

---

## 3) 填空题（Fill in the Blank）

### Fields

- `Question`（题干中可写 `____`）
- `CorrectAnswer`
- `AltAnswers`（可选，多个用英文逗号分隔，如 `USA,United States`）
- `Explanation`

### Front Template

```html
<div class="qa-wrap" id="fb-wrap">
  <div class="qa-head">Fill in the Blank</div>

  <div class="section">
    <div class="label label-q">Question</div>
    <div class="question">{{Question}}</div>

    <div class="input-row">
      <input id="fb-input" class="ans-input" placeholder="输入你的答案...">
      <button id="fb-check" class="btn" type="button">检查</button>
    </div>
    <div id="fb-judge" class="judge"></div>
    <div class="inline-help">提示：先自测，再点 Show Answer 看标准答案与解析。</div>
  </div>
</div>

<script>
(function () {
  var input = document.getElementById('fb-input');
  var check = document.getElementById('fb-check');
  var judge = document.getElementById('fb-judge');
  if (!input || !check || !judge) return;

  var right = '{{CorrectAnswer}}'.trim().toLowerCase();
  var altsRaw = '{{AltAnswers}}';
  var alts = altsRaw.split(',').map(function (s) { return s.trim().toLowerCase(); }).filter(Boolean);
  var all = [right].concat(alts);

  function norm(v) {
    return v.trim().toLowerCase().replace(/\s+/g, ' ');
  }

  function run() {
    var user = norm(input.value);
    var ok = all.indexOf(user) >= 0;
    judge.className = 'judge ' + (ok ? 'ok' : 'bad');
    judge.textContent = ok ? '回答匹配，做得不错。' : '暂不匹配，建议再想想或查看答案。';
  }

  check.addEventListener('click', run);
  input.addEventListener('keydown', function (e) {
    if (e.key === 'Enter') run();
  });
})();
</script>
```

### Back Template

```html
<div class="qa-wrap">
  <div class="qa-head">Fill in the Blank</div>

  <div class="section">
    <div class="label label-q">Question</div>
    <div class="question">{{Question}}</div>
  </div>

  <div class="section">
    <div class="label label-a">Answer</div>
    <div class="answer-box">
      标准答案：<strong>{{CorrectAnswer}}</strong><br>
      {{#AltAnswers}}可接受答案：{{AltAnswers}}{{/AltAnswers}}
    </div>
  </div>

  <div class="section">
    <div class="label label-e">Explanation</div>
    <div class="explain-box">{{Explanation}}</div>
  </div>
</div>
```

---

## 4) 翻转卡片（Reverse Card，双向记忆）

这一类建议一个 `Note Type` 配两张卡：
- `Card 1`：`Term -> Definition`
- `Card 2`：`Definition -> Term`

### Fields

- `Term`
- `Definition`
- `Example`
- `Explanation`

### Card 1 Front（Term -> Definition）

```html
<div class="qa-wrap" id="rv1-front">
  <div class="qa-head">Reverse Card · Term → Definition</div>

  <div class="section">
    <div class="label label-q">Question</div>
    <div class="question">请写出这个术语的定义：</div>
    <div class="answer-box" style="margin-top: 8px;"><strong>{{Term}}</strong></div>

    {{#Example}}
    <div class="inline-help">
      <button id="show-eg-1" class="btn" type="button">显示例句提示</button>
      <div id="eg-1" style="display:none; margin-top:8px;">{{Example}}</div>
    </div>
    {{/Example}}
  </div>
</div>

<script>
(function () {
  var btn = document.getElementById('show-eg-1');
  var eg = document.getElementById('eg-1');
  if (!btn || !eg) return;
  btn.addEventListener('click', function () {
    var hidden = eg.style.display === 'none';
    eg.style.display = hidden ? 'block' : 'none';
    btn.textContent = hidden ? '隐藏例句提示' : '显示例句提示';
  });
})();
</script>
```

### Card 1 Back

```html
<div class="qa-wrap">
  <div class="qa-head">Reverse Card · Term → Definition</div>

  <div class="section">
    <div class="label label-q">Question</div>
    <div class="question">术语：{{Term}}</div>
  </div>

  <div class="section">
    <div class="label label-a">Answer</div>
    <div class="answer-box">{{Definition}}</div>
  </div>

  <div class="section">
    <div class="label label-e">Explanation</div>
    <div class="explain-box">
      {{#Example}}例句：{{Example}}<br>{{/Example}}
      {{Explanation}}
    </div>
  </div>
</div>
```

### Card 2 Front（Definition -> Term）

```html
<div class="qa-wrap" id="rv2-front">
  <div class="qa-head">Reverse Card · Definition → Term</div>

  <div class="section">
    <div class="label label-q">Question</div>
    <div class="question">请写出对应术语：</div>
    <div class="answer-box" style="margin-top: 8px;">{{Definition}}</div>
  </div>
</div>
```

### Card 2 Back

```html
<div class="qa-wrap">
  <div class="qa-head">Reverse Card · Definition → Term</div>

  <div class="section">
    <div class="label label-q">Question</div>
    <div class="question">定义：{{Definition}}</div>
  </div>

  <div class="section">
    <div class="label label-a">Answer</div>
    <div class="answer-box"><strong>{{Term}}</strong></div>
  </div>

  <div class="section">
    <div class="label label-e">Explanation</div>
    <div class="explain-box">
      {{#Example}}例句：{{Example}}<br>{{/Example}}
      {{Explanation}}
    </div>
  </div>
</div>
```

---

## 5) 使用建议（确保效果稳定）

- 每个题型单独建 `Note Type`，避免字段互相污染。
- 先粘贴 `Styling`，再粘贴各题型模板。
- 多选答案字段统一用英文逗号分隔（如 `A,C,E`）。
- 填空建议统一大小写/空格规则，避免误判。
- 若你需要“记录前面交互状态到背面”，建议加一个隐藏字段做持久化（Anki 原生前后模板不保证前端状态保留）。
