/*! ko-typeset.js — 한국어 웹 조판 보정 (의존성 없음)
 *
 * 1) 붙어 다녀야 하는 어절 사이 공백을 줄바꿈 없는 공백(U+00A0)으로 바꾼다.
 *    할 수 / 하고 있다 / 3 개 / 그 사람 / 김 씨 …
 * 2) 문단 마지막 줄에 짧은 어절 하나만 남지 않게 한다.
 * 3) .ko-subtitle, [data-ko="subtitle"]: 실제 글자 폭을 재서 2줄 최적 위치에 <br>을 넣는다.
 * 4) 나중에 추가되는 텍스트도 자동 처리(MutationObserver), 폰트 로딩·리사이즈 시 다시 계산.
 * 5) 복사할 때 U+00A0을 일반 공백으로 되돌린다.
 *
 * 사용: <script src="ko-typeset.js" defer></script>  — 끝.
 * 설정: 스크립트보다 먼저 window.KoTypeConfig = { auto: false, ... } 를 두면 자동 실행을 끄거나 옵션을 바꾼다.
 * 제외: data-ko="off" 를 붙인 요소와 그 안쪽.
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.KoType = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  var NBSP = ' ';
  var HANGUL = /[가-힣]/;
  var TRAIL_PUNCT = /[.,?!…~:;"'”’)\]」』》]+$/;
  var LEAD_PUNCT = /^["'“‘(\[「『《]+/;

  // 관형형 뒤 의존명사 (+조사/하다 활용)
  var DEP_RE = new RegExp(
    '^(?:수|것|거|건|걸|게|줄|적|때|때문|뿐|만큼|리|듯|채|지|바|터|법|척|체|셈|김|대로|데|만|뻔|즈음|무렵)' +
    '(?:이|가|은|는|을|를|도|만|에|에게|에서|으로|로|과|와|야|이야|예요|이에요|요|죠|지|다|이다|입니다|이라|라|란|인데|일|이고|처럼|까지|부터' +
    '|하다|해|해요|했다|했어|했어요|한|할|하는|합니다|했습니다|하게|하지|이었다|였다)?$'
  );
  // 본용언 어미 + 보조용언
  var AUX_PREV = /(?:고|지|어|아|여|워|와|게|해|돼|져|쳐|줘|봐|러|려|야)$/;
  var AUX_NEXT = /^(?:있|없|않|못|싶|보|봐|봤|주|줘|줬|달|드리|드려|드렸|버리|버려|버렸|놓|놔|놨|두|둬|뒀|계|가지|내|냈|대|댔|말|말았|되|돼|됐|오|와|왔|가|갔|하|했)/;
  // 받침 없는 축약형(만나, 가, 써 …) 뒤에는 '보다·주다·버리다·놓다' 계열만
  var AUX_NEXT_STRICT = /^(?:보|봐|봤|본|볼|주|줘|줬|준|달|버리|버려|버렸|놓|놔|놨|둬|뒀|드리|드려|드렸)/;
  // 뒷말을 꾸미는 짧은 말: 줄 끝에 홀로 남지 않게
  var MODIFIERS = toSet('이 그 저 이런 그런 저런 이러한 그러한 한 두 세 네 몇 안 못 더 덜 잘 꼭 너무 아주 매우 가장 제일 좀 다 또 ' +
    '모든 각 새 옛 첫 온 전 본 매 무슨 어떤 어느 웬 약 총 제 내 그냥 막 딱 참 왜 및 또는 혹은 즉 해당');
  // 앞말에 붙어야 하는 말: 줄 머리에 오지 않게
  var FOLLOWERS_RE = /^(?:씨|님|군|양|등|외|측|께|께서)(?:는|은|가|이|의|도|을|를|에게|과|와|만|이다|입니다)?$/;
  var NUM_WORDS = toSet('한 두 세 네 다섯 여섯 일곱 여덟 아홉 열 스무 서른 마흔 쉰 일 이 삼 사 오 육 칠 팔 구 십 백 천 만 억 몇 수십 수백 수천');
  var UNIT_RE = /^(?:개|명|번|살|시|분|초|년|월|일|원|달러|킬로|미터|센티|층|권|잔|병|마리|대|장|회|차|주|배|퍼센트|%|억|만|천|위|등|점|세|박|곳|가지|시간|개월|주년)/;
  var CLAUSE_END = /(?:는데|은데|니까|지만|면서|도록|려고|다가|거나|든지|더니|자마자|어서|아서|해서|라서|면|며|고|서)$/;

  var DEFAULTS = {
    auto: true,
    selector: 'p, li, dd, dt, blockquote, figcaption, caption, th, td, h1, h2, h3, h4, h5, h6, [data-ko]',
    subtitle: '.ko-subtitle, [data-ko="subtitle"]',
    skip: 'pre, code, kbd, samp, textarea, input, select, script, style, svg, math, [contenteditable], [data-ko="off"]',
    maxChunk: 12,   // NBSP로 묶는 덩어리 최대 글자 수 (좁은 화면에서 넘침 방지)
    orphanMax: 4,   // 마지막 어절이 이 글자 수 이하면 앞 어절과 묶음
    observe: true,
    fixCopy: true
  };

  function toSet(s) { var o = {}; s.split(' ').forEach(function (w) { o[w] = 1; }); return o; }
  function core(w) { return w.replace(LEAD_PUNCT, '').replace(TRAIL_PUNCT, ''); }
  function lastPart(w) { var p = w.split(NBSP); return p[p.length - 1]; }
  function firstPart(w) { return w.split(NBSP)[0]; }
  function jong(ch) {
    var c = ch ? ch.charCodeAt(0) : 0;
    return c >= 0xAC00 && c <= 0xD7A3 ? (c - 0xAC00) % 28 : -1;
  }
  function isAdnominal(w) {
    if (!w || TRAIL_PUNCT.test(w)) return false;
    var last = w.charAt(w.length - 1);
    return last === '던' || jong(last) === 4 || jong(last) === 8; // 받침 ㄴ/ㄹ
  }

  /** 두 어절 사이에서 줄을 바꾸면 안 되는가 */
  function mustGlue(a, b) {
    var w1 = lastPart(a), w2 = firstPart(b);
    if (TRAIL_PUNCT.test(w1)) return false;
    var c1 = core(w1), c2 = core(w2.replace(/^["'“‘(\[「『《]+/, '').replace(/["'”’)\]」』》].*$/, ''));
    if (!c1 || !c2) return false;
    if (isAdnominal(c1) && DEP_RE.test(c2)) return true;                       // 할 수, 먹을 것
    if (DEP_RE.test(c1) && /^(?:있|없|같|알|모르|몰)/.test(c2) && c2.length <= 4) return true; // 수 있다, 것 같아
    if (AUX_PREV.test(c1) && AUX_NEXT.test(c2) && c2.length <= 5) return true; // 하고 있다, 해 보다
    if (jong(c1.charAt(c1.length - 1)) === 0 && AUX_NEXT_STRICT.test(c2) && c2.length <= 5) return true; // 만나 본, 와 달라고
    if ((/\d$/.test(c1) || NUM_WORDS[c1]) && UNIT_RE.test(c2)) return true;    // 3 개, 일곱 시
    if (MODIFIERS[c1] && !LEAD_PUNCT.test(w2)) return true;                    // 그 사람, 너무 좋아
    if (FOLLOWERS_RE.test(c2)) return true;                                            // 김 씨, 사과 등
    return false;
  }

  /** 줄을 바꾸기에 얼마나 나쁜가 (자막 2줄 나눌 때, 음수 = 좋은 자리) */
  function breakCost(a, b) {
    var w1 = lastPart(a), w2 = firstPart(b), c = 0;
    if (/[.?!]["'”’)]*$/.test(w1)) c -= 60;
    else if (/[,…~:;]["'”’)]*$/.test(w1)) c -= 40;
    else if (CLAUSE_END.test(w1) && w1.length >= 2) c -= 15;
    if (isAdnominal(core(w1)) && !TRAIL_PUNCT.test(w1)) c += 25; // 수식어-명사 분리
    if (core(w2).length === 1) c += 20;
    return c;
  }

  /** 문자열 처리: 붙어야 할 공백을 NBSP로 (순수 함수, Node에서도 사용 가능) */
  function glue(text, opts) {
    opts = opts || DEFAULTS;
    var max = opts.maxChunk || DEFAULTS.maxChunk;
    var parts = text.split(/( +)/);
    var chunk = 0, prev = null;
    for (var i = 0; i < parts.length; i++) {
      var p = parts[i];
      if (p === '') continue;
      if (/^ +$/.test(p)) continue;
      if (prev !== null && parts[i - 1] === ' ' && mustGlue(parts[prev], p) &&
          chunk + 1 + p.length <= max) {
        parts[i - 1] = NBSP;
        chunk += 1 + p.length;
      } else {
        chunk = p.length;
      }
      prev = i;
    }
    return parts.join('');
  }

  /** 문단 끝 짧은 어절을 앞 어절과 묶기 */
  function glueOrphan(text, opts) {
    opts = opts || DEFAULTS;
    var m = text.match(/^([\s\S]*\S) (\S+)\s*$/);
    if (!m) return text;
    var tail = m[2], prevChunk = m[1].split(' ').pop();
    if (core(tail).length > opts.orphanMax) return text;
    if (prevChunk.length + 1 + tail.length > opts.maxChunk) return text;
    return m[1] + NBSP + text.slice(m[1].length + 1);
  }

  /** 2줄 자막 최적 분할: words는 일반 공백 기준 덩어리, widths는 px 폭 */
  function bestBreak(words, widths, spaceW, avail, em) {
    var total = widths.reduce(function (s, w) { return s + w; }, 0) + spaceW * (words.length - 1);
    if (total <= avail || words.length < 2) return -1;
    var best = null, left = 0;
    for (var i = 0; i < words.length - 1; i++) {
      left += widths[i] + (i ? spaceW : 0);
      var right = total - left - spaceW;
      var over = Math.max(0, left - avail) + Math.max(0, right - avail);
      var diff = (left - right) / em;
      var cost = over ? 1000 + over : 0;
      cost += diff * diff * 0.6 + (diff > 0 ? diff * 0.5 : 0); // 아래 줄이 약간 긴 쪽 선호
      cost += breakCost(words[i], words[i + 1]);
      var head = words.slice(0, i + 1).join(' ');
      if ((head.match(/[(\[「『《“]/g) || []).length > (head.match(/[)\]」』》”]/g) || []).length ||
          (head.match(/"/g) || []).length % 2) cost += 80; // 괄호·따옴표 안
      if (!best || cost < best.cost) best = { i: i, cost: cost, over: over };
    }
    return best.over ? -2 : best.i; // -2: 2줄에 안 들어감 → CSS에 맡김
  }

  // ---------- DOM ----------
  var cfg = null, done = typeof WeakMap !== 'undefined' ? new WeakMap() : null, mo = null, ro = null;

  function skipped(node) {
    var el = node.nodeType === 1 ? node : node.parentElement;
    return !el || !!el.closest(cfg.skip);
  }

  function processTextNodes(el) {
    var walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, null);
    var nodes = [], n;
    while ((n = walker.nextNode())) nodes.push(n);
    nodes.forEach(function (t, idx) {
      if (!HANGUL.test(t.data) || skipped(t)) return;
      if (done && done.get(t) === t.data) return;
      var v = glue(t.data, cfg);
      if (cfg.orphanMax && idx === nodes.length - 1) v = glueOrphan(v, cfg);
      if (v !== t.data) t.data = v;
      if (done) done.set(t, v);
    });
  }

  function contentWidth(el) {
    var cs = getComputedStyle(el);
    return el.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
  }

  function balanceSubtitle(el) {
    if (skipped(el)) return;
    var src = el.getAttribute('data-ko-src');
    if (src === null) {
      for (var k = 0; k < el.children.length; k++) {
        if (el.children[k].tagName !== 'BR') { processTextNodes(el); return; } // 마크업이 섞이면 붙이기만
      }
      src = glue(el.textContent.replace(/\s+/g, ' ').trim(), cfg);
      el.setAttribute('data-ko-src', src);
    }
    var avail = contentWidth(el);
    if (!avail) return;
    var words = src.split(' ');
    var probe = document.createElement('span');
    probe.style.cssText = 'position:absolute;visibility:hidden;white-space:pre;left:-9999px;top:0';
    el.appendChild(probe);
    function w(s) { probe.textContent = s; return probe.getBoundingClientRect().width; }
    var widths = words.map(w), spaceW = w('가 가') - w('가가');
    var em = parseFloat(getComputedStyle(el).fontSize) || 16;
    el.removeChild(probe);
    var i = bestBreak(words, widths, spaceW, avail, em);
    if (i < 0) { if (el.textContent !== src) el.textContent = src; }
    else {
      el.textContent = '';
      el.appendChild(document.createTextNode(words.slice(0, i + 1).join(' ')));
      el.appendChild(document.createElement('br'));
      el.appendChild(document.createTextNode(words.slice(i + 1).join(' ')));
    }
    el.__koW = avail;
    if (ro && !el.__koObserved) { ro.observe(el); el.__koObserved = true; }
  }

  function run(rootEl) {
    rootEl = rootEl || document.body;
    if (!rootEl || rootEl.nodeType !== 1) return;
    var subs = [];
    if (rootEl.matches(cfg.subtitle)) subs.push(rootEl);
    subs.push.apply(subs, rootEl.querySelectorAll(cfg.subtitle));
    var blocks = [];
    if (rootEl.matches(cfg.selector)) blocks.push(rootEl);
    blocks.push.apply(blocks, rootEl.querySelectorAll(cfg.selector));
    if (!blocks.length && rootEl.closest(cfg.selector)) blocks.push(rootEl); // 블록 안에 끼워넣은 조각
    blocks.forEach(function (b) { if (subs.indexOf(b) < 0 && !b.closest(cfg.subtitle)) processTextNodes(b); });
    subs.forEach(balanceSubtitle);
    if (mo) mo.takeRecords(); // 내가 바꾼 것은 다시 처리하지 않음
  }

  function refreshSubtitles() {
    document.querySelectorAll(cfg.subtitle).forEach(balanceSubtitle);
    if (mo) mo.takeRecords();
  }

  function init(options) {
    cfg = {};
    Object.keys(DEFAULTS).forEach(function (k) { cfg[k] = DEFAULTS[k]; });
    Object.keys(options || {}).forEach(function (k) { cfg[k] = options[k]; });

    if (typeof ResizeObserver !== 'undefined') {
      ro = new ResizeObserver(function (entries) {
        entries.forEach(function (e) {
          var el = e.target;
          if (Math.abs(contentWidth(el) - (el.__koW || 0)) > 1) balanceSubtitle(el);
        });
        if (mo) mo.takeRecords();
      });
    }
    if (cfg.observe && typeof MutationObserver !== 'undefined') {
      mo = new MutationObserver(function (records) {
        var targets = [];
        records.forEach(function (r) {
          if (r.type === 'characterData') {
            var sub = r.target.parentElement && r.target.parentElement.closest(cfg.subtitle);
            if (sub) sub.removeAttribute('data-ko-src'); // 자막 내용이 바뀜 → 다시 계산
            targets.push(sub || r.target.parentElement);
          } else {
            var host = r.target.nodeType === 1 && r.target.closest(cfg.subtitle);
            if (host) { host.removeAttribute('data-ko-src'); targets.push(host); return; }
            r.addedNodes.forEach(function (n) {
              if (n.nodeType === 1) targets.push(n);
              else if (n.nodeType === 3) targets.push(n.parentElement);
            });
          }
        });
        targets.forEach(function (t) { if (t && t.isConnected) run(t); });
      });
      mo.observe(document.body, { childList: true, subtree: true, characterData: true });
    }
    run(document.body);
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(refreshSubtitles);

    if (cfg.fixCopy) {
      document.addEventListener('copy', function (e) {
        var sel = window.getSelection();
        if (!sel || !sel.rangeCount || !e.clipboardData) return;
        var text = sel.toString();
        if (text.indexOf(NBSP) < 0) return;
        var div = document.createElement('div');
        for (var r = 0; r < sel.rangeCount; r++) div.appendChild(sel.getRangeAt(r).cloneContents());
        e.clipboardData.setData('text/plain', text.replace(/ /g, ' '));
        e.clipboardData.setData('text/html', div.innerHTML.replace(/&nbsp;| /g, ' '));
        e.preventDefault();
      });
    }
  }

  var api = {
    init: init, run: function (el) { run(el); }, refresh: refreshSubtitles,
    glue: glue, glueOrphan: glueOrphan, mustGlue: mustGlue, bestBreak: bestBreak, breakCost: breakCost
  };

  if (typeof document !== 'undefined') {
    var user = (typeof window !== 'undefined' && window.KoTypeConfig) || {};
    if (user.auto !== false) {
      if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', function () { init(user); });
      else init(user);
    }
  }
  return api;
});
