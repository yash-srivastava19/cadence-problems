"use strict";
(() => {
  const SITE = window.SITE || {};
  const NAME = (SITE.SITE_NAME || "").trim();
  const C = (k, d) => (SITE[k] === undefined || SITE[k] === null ? d : SITE[k]);  // config value, with a safe fallback
  const TRIES = C("TRIES", 3);
  const N = 15;
  const COLS = "ABCDEFGHIJKLMNO";
  const PREMIUM = [
    "T..d...T...d..T", ".D...t...t...D.", "..D...d.d...D..", "d..D...d...D..d",
    "....D.....D....", ".t...t...t...t.", "..d...d.d...d..", "T..d...*...d..T",
    "..d...d.d...d..", ".t...t...t...t.", "....D.....D....", "d..D...d...D..d",
    "..D...d.d...D..", ".D...t...t...D.", "T..d...T...d..T",
  ];
  const PREM = { T: ["tw", "3W", "triple word"], D: ["dw", "2W", "double word"], "*": ["dw star", "★", "centre, double word"],
    t: ["tl", "3L", "triple letter"], d: ["dl", "2L", "double letter"] };
  const VALUES = { A: 1, B: 3, C: 3, D: 2, E: 1, F: 4, G: 2, H: 4, I: 1, J: 8, K: 5, L: 1, M: 3, N: 1, O: 1,
    P: 3, Q: 10, R: 1, S: 1, T: 1, U: 1, V: 4, W: 4, X: 8, Y: 4, Z: 10 };
  const $ = (id) => document.getElementById(id);
  const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };

  // ---- storage: never trusted to exist -------------------------------------
  // Saved progress must survive every release. The key never changes; the shape
  // carries a schema number and migrate() upgrades it forward, keeping any field
  // it doesn't know. Results are keyed by date (daily) or "practice:NNNN".
  const KEY = C("STORAGE_KEY", "bestplay:v1");
  const SCHEMA = 1;
  function read(key) {
    try { const v = JSON.parse(localStorage.getItem(key)); return v && typeof v === "object" ? v : null; } catch (e) { return null; }
  }
  function migrate(saved) {
    const s = { ...saved };
    if (!s.results || typeof s.results !== "object") s.results = {};
    if (!s.schema) s.schema = 1;  // schema 0 (no number) had the same shape
    // Later: if (s.schema === 1) { ...; s.schema = 2; }
    return s;
  }
  function loadStore() {
    const s = migrate(read(KEY) || {});
    const checked = new Set(Array.isArray(s.migratedFrom) ? s.migratedFrom : []);
    for (const k of C("LEGACY_STORAGE_KEYS", [])) {
      if (k === KEY || checked.has(k)) continue;
      const old = read(k);
      if (old) {
        const o = migrate(old);
        for (const [id, r] of Object.entries(o.results)) if (!(id in s.results)) s.results[id] = r;
        for (const [f, v] of Object.entries(o)) if (!(f in s)) s[f] = v;
      }
      checked.add(k);  // the old key itself is left as it was
    }
    s.migratedFrom = [...checked];
    s.schema = Math.max(s.schema, SCHEMA);
    return s;
  }
  let store = loadStore();
  save();  // persist any migration at once
  function save() { try { localStorage.setItem(KEY, JSON.stringify(store)); } catch (e) { /* storage full or blocked */ } }

  // Where anonymous "how others played" results would go. Nothing is sent today.
  function reportResult(puzzle, guesses, solved, ms) { /* no-op until there is a backend */ }

  // ---- dates ---------------------------------------------------------------
  function iso(d) { return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`; }
  const params = new URLSearchParams(location.search);
  const LOCAL = ["localhost", "127.0.0.1"].includes(location.hostname);
  const TZ = C("ROLLOVER_TIMEZONE", "local"), HOUR = C("ROLLOVER_HOUR", 0);
  // The puzzle date: the calendar date in the rollover zone, HOUR hours ago.
  function puzzleDate(now) {
    const t = new Date(now.getTime() - HOUR * 3600e3);
    if (TZ === "local") return iso(t);
    try { return new Intl.DateTimeFormat("en-CA", { timeZone: TZ, year: "numeric", month: "2-digit", day: "2-digit" }).format(t); } catch (e) { return iso(t); }
  }
  function minutesToRollover(now) {
    let h = now.getHours(), m = now.getMinutes();
    if (TZ !== "local") {
      try {
        const parts = new Intl.DateTimeFormat("en-GB", { timeZone: TZ, hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).formatToParts(now);
        h = +parts.find((x) => x.type === "hour").value; m = +parts.find((x) => x.type === "minute").value;
      } catch (e) { /* fall back to local time */ }
    }
    return ((HOUR * 60 - (h * 60 + m)) % 1440 + 1440) % 1440 || 1440;
  }
  const TODAY = LOCAL && /^\d{4}-\d{2}-\d{2}$/.test(params.get("today") || "") ? params.get("today") : puzzleDate(new Date());
  function nice(date, opts) { return new Date(date + "T12:00:00").toLocaleDateString("en-GB", opts || { weekday: "long", day: "numeric", month: "long", year: "numeric" }); }
  function prevDay(date) { const d = new Date(date + "T12:00:00"); d.setDate(d.getDate() - 1); return iso(d); }

  // ---- state ---------------------------------------------------------------
  let index = [];
  let P = null;          // the puzzle
  let grid = [];         // grid[r][c] = {ch, blank} | null
  let plays = [];        // [{where, word, s, leave, v, rank, key, tiles}]
  let byKey = new Map();
  let rack = [];         // [{id, ch}] in display order
  let pending = [];      // [{r, c, id, ch, blank}]
  let cursor = null;     // {r, c, dir: "across" | "down"}
  let selected = null;   // rack tile id waiting for a square
  let rec = null;        // this puzzle's saved record
  let shown = 0;         // index into plays previewed on the board once done
  let popKey = "";
  const cells = [];

  // ---- the puzzle data -----------------------------------------------------
  function parseWhere(where) {
    const m = /^(\d+)([A-Z])$/.exec(where);
    if (m) return { r: +m[1] - 1, c: COLS.indexOf(m[2]), dr: 0, dc: 1 };
    const k = /^([A-Z])(\d+)$/.exec(where);
    return { r: +k[2] - 1, c: COLS.indexOf(k[1]), dr: 1, dc: 0 };
  }
  function keyOf(tiles) {
    return tiles.map((t) => [t.r, t.c, t.blank ? t.ch.toLowerCase() : t.ch]).sort((a, b) => a[0] - b[0] || a[1] - b[1]).map((t) => t.join(",")).join(";");
  }
  function prepare(doc) {
    P = doc;
    grid = doc.board.map((row) => [...row].map((ch) => ch === "." ? null : { ch: ch.toUpperCase(), blank: ch !== ch.toUpperCase() }));
    const bestV = doc.plays[0][4];
    plays = doc.plays.map(([where, word, s, leave, v], i) => {
      const w = parseWhere(where);
      const tiles = [];
      [...word].forEach((ch, k) => {
        const r = w.r + w.dr * k, c = w.c + w.dc * k;
        if (!grid[r][c]) tiles.push({ r, c, ch: ch.toUpperCase(), blank: ch !== ch.toUpperCase() });
      });
      return { where, word, s, leave, v, lv: v - s, rank: i + 1, tiles, pct: Math.max(0, Math.round((100 * v) / bestV)) };
    });
    // Equal value is equally best.
    plays.forEach((p) => { p.best = p.v >= bestV - C("BEST_TOLERANCE", 0.05); if (p.best) p.pct = 100; });
    byKey = new Map(plays.map((p) => [keyOf(p.tiles), p]));
    rack = [...doc.rack].map((ch, i) => ({ id: i, ch }));
    pending = []; cursor = null; selected = null; shown = 0;
    rec = store.results[recKey(doc)] || { tries: [], done: false, solved: false, daily: !!doc.date && doc.date === TODAY };
    rec.opened = rec.opened || Date.now();
  }

  // ---- board ---------------------------------------------------------------
  function buildBoard() {
    const b = $("board");
    b.textContent = "";
    for (let r = 0; r < N; r++) {
      const row = el("div", "row"); row.setAttribute("role", "row");
      for (let c = 0; c < N; c++) {
        const p = PREMIUM[r][c];
        const sq = el("div", "sq" + (PREM[p] ? " " + PREM[p][0] : ""));
        sq.id = `sq-${r}-${c}`;
        sq.setAttribute("role", "gridcell");
        sq.dataset.r = r; sq.dataset.c = c;
        sq.addEventListener("click", () => tapSquare(r, c));
        row.append(sq);
        cells[r * N + c] = sq;
      }
      b.append(row);
    }
  }
  function tileEl(ch, blank) {
    const t = el("span", "tile" + (blank ? " blank" : ""));
    t.append(el("b", null, ch));
    if (!blank) t.append(el("sub", null, String(VALUES[ch] || "")));
    return t;
  }
  function renderBoard() {
    const done = rec.done;
    const ghost = done ? plays[shown] : null;
    const ghostMap = new Map((ghost ? ghost.tiles : []).map((t) => [t.r * N + t.c, t]));
    const pendMap = new Map(pending.map((t) => [t.r * N + t.c, t]));
    const last = new Set((P.last || []).map(([r, c]) => r * N + c));
    const yours = done && ghost && rec.tries.some((t) => t.where === ghost.where && t.word === ghost.word);
    for (let r = 0; r < N; r++) for (let c = 0; c < N; c++) {
      const i = r * N + c, sq = cells[i], p = PREMIUM[r][c], fixed = grid[r][c];
      const t = fixed || pendMap.get(i) || ghostMap.get(i);
      sq.textContent = "";
      sq.classList.toggle("pending", !!pendMap.get(i));
      sq.classList.toggle("ghost", !fixed && !!ghostMap.get(i));
      sq.classList.toggle("yours", !fixed && !!ghostMap.get(i) && yours);
      sq.classList.toggle("last", !!fixed && last.has(i));
      sq.classList.toggle("pop", !!pendMap.get(i) && popKey === `${r},${c}`);
      const isCur = !done && cursor && cursor.r === r && cursor.c === c;
      sq.classList.toggle("cursor", !!isCur);
      sq.classList.toggle("across", !!isCur && cursor.dir === "across");
      sq.classList.toggle("down", !!isCur && cursor.dir === "down");
      let label = `${COLS[c]}${r + 1}`;
      if (t) {
        sq.append(tileEl(t.ch, t.blank));
        label += t.blank ? `, blank as ${t.ch}` : `, ${t.ch}`;
        if (pendMap.get(i)) label += ", your tile";
        else if (!fixed) label += ", shown play";
        else if (last.has(i)) label += ", their last play";
      } else {
        if (PREM[p]) { sq.append(el("span", "prem", PREM[p][1])); label += `, ${PREM[p][2]}`; }
        label += ", empty";
      }
      if (isCur) label += `, cursor ${cursor.dir}`;
      sq.setAttribute("aria-label", label);
    }
    const b = $("board");
    b.classList.toggle("done", done);
    if (cursor && !done) b.setAttribute("aria-activedescendant", `sq-${cursor.r}-${cursor.c}`);
    else b.removeAttribute("aria-activedescendant");
    popKey = "";
  }

  // ---- rack ----------------------------------------------------------------
  function renderRack() {
    const box = $("rack");
    box.textContent = "";
    const used = new Set(pending.map((t) => t.id));
    rack.forEach((t) => {
      const isUsed = used.has(t.id);
      const btn = el("button", "rt" + (isUsed ? " used" : "") + (selected === t.id ? " sel" : ""));
      btn.type = "button";
      btn.disabled = isUsed || rec.done;
      const blank = t.ch === "?";
      btn.append(document.createTextNode(blank ? "" : t.ch));
      if (!blank) btn.append(el("sub", null, String(VALUES[t.ch])));
      btn.setAttribute("aria-label", isUsed ? "Placed" : blank ? "Blank tile" : `${t.ch}, ${VALUES[t.ch]} point${VALUES[t.ch] === 1 ? "" : "s"}`);
      btn.addEventListener("click", () => tapRack(t.id));
      box.append(btn);
    });
    const match = byKey.get(keyOf(pending));
    $("preview-pts").textContent = match ? `${match.s} pts` : "";
    $("submit").disabled = rec.done || !pending.length;
    $("clear").disabled = rec.done || !pending.length;
    $("shuffle").disabled = rec.done;
  }

  // ---- placing tiles -------------------------------------------------------
  function occupied(r, c) { return !!grid[r][c] || pending.some((t) => t.r === r && t.c === c); }
  function advance() {
    if (!cursor) return;
    let { r, c } = cursor;
    const dr = cursor.dir === "down" ? 1 : 0, dc = 1 - dr;
    do { r += dr; c += dc; } while (r < N && c < N && occupied(r, c));
    cursor = r < N && c < N ? { r, c, dir: cursor.dir } : null;
  }
  function place(id, letter) {
    const t = rack.find((x) => x.id === id);
    if (!t || !cursor || occupied(cursor.r, cursor.c)) return;
    const blank = t.ch === "?";
    pending.push({ r: cursor.r, c: cursor.c, id, ch: blank ? letter : t.ch, blank });
    popKey = `${cursor.r},${cursor.c}`;
    selected = null;
    advance();
    say("");
    render();
  }
  function startAt(r, c) {
    if (!cursor || cursor.r !== r || cursor.c !== c) {
      // Guess the direction: along the tiles already placed, else across.
      let dir = cursor ? cursor.dir : "across";
      if (pending.length) dir = pending.every((t) => t.r === r) ? "across" : pending.every((t) => t.c === c) ? "down" : dir;
      cursor = { r, c, dir };
    } else cursor = { r, c, dir: cursor.dir === "across" ? "down" : "across" };
  }
  function tapSquare(r, c) {
    if (rec.done) return;
    const p = pending.findIndex((t) => t.r === r && t.c === c);
    if (p >= 0) { pending.splice(p, 1); cursor = { r, c, dir: cursor ? cursor.dir : "across" }; render(); return; }
    if (grid[r][c]) return;
    startAt(r, c);
    if (selected != null) { const id = selected; tryPlace(id); return; }
    render();
    $("board").focus({ preventScroll: true });
  }
  function tryPlace(id) {
    const t = rack.find((x) => x.id === id);
    if (t.ch === "?") askBlank((letter) => place(id, letter));
    else place(id, t.ch);
  }
  function tapRack(id) {
    if (rec.done) return;
    if (!cursor) { selected = selected === id ? null : id; say(selected == null ? "" : "Now tap a square."); render(); return; }
    tryPlace(id);
  }
  function typeLetter(L) {
    if (rec.done) return;
    if (!cursor) { say("Tap a square first.", true); return; }
    const used = new Set(pending.map((t) => t.id));
    const free = rack.filter((t) => !used.has(t.id));
    const t = free.find((x) => x.ch === L) || free.find((x) => x.ch === "?");
    if (!t) { say(`No ${L} on your rack.`, true); nope(); return; }
    place(t.id, L);
  }
  function backspace() {
    if (rec.done || !pending.length) return;
    const t = pending.pop();
    cursor = { r: t.r, c: t.c, dir: cursor ? cursor.dir : "across" };
    render();
  }
  function clearAll() {
    if (!pending.length) return;
    const first = pending.slice().sort((a, b) => a.r - b.r || a.c - b.c)[0];
    cursor = { r: first.r, c: first.c, dir: cursor ? cursor.dir : "across" };
    pending = []; selected = null; say(""); render();
  }
  function shuffle() {
    for (let i = rack.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [rack[i], rack[j]] = [rack[j], rack[i]]; }
    const box = $("rack");
    renderRack();
    box.classList.remove("shuffling"); void box.offsetWidth; box.classList.add("shuffling");
  }
  function nope() { const box = $("rack"); box.classList.remove("nope"); void box.offsetWidth; box.classList.add("nope"); }

  // ---- the blank ----------------------------------------------------------
  let blankCb = null;
  function askBlank(cb) {
    blankCb = cb;
    const d = $("blank-dialog");
    try { d.showModal(); } catch (e) { d.setAttribute("open", ""); }
    d.querySelector(".letters button").focus();
  }
  function buildLetters() {
    const box = $("letters");
    for (const L of "ABCDEFGHIJKLMNOPQRSTUVWXYZ") {
      if (box.querySelector(`[data-l="${L}"]`)) continue;
      const b = el("button", null, L); b.value = L; b.dataset.l = L; b.setAttribute("aria-label", `Blank as ${L}`);
      box.append(b);
    }
    $("blank-dialog").addEventListener("close", () => {
      const v = $("blank-dialog").returnValue;
      const cb = blankCb; blankCb = null;
      if (cb && /^[A-Z]$/.test(v)) cb(v);
      $("blank-dialog").returnValue = "";
    });
    $("blank-dialog").addEventListener("keydown", (e) => {
      const L = e.key.length === 1 ? e.key.toUpperCase() : "";
      if (/^[A-Z]$/.test(L)) { e.preventDefault(); $("blank-dialog").close(L); }
    });
  }

  // ---- submitting ---------------------------------------------------------
  function shapeProblem() {
    if (!pending.length) return "Place some tiles first.";
    const rows = new Set(pending.map((t) => t.r)), cols = new Set(pending.map((t) => t.c));
    if (rows.size > 1 && cols.size > 1) return "Tiles must go in one row or one column.";
    const across = rows.size === 1 && (cols.size > 1 || (cursor ? cursor.dir === "across" : true));
    const along = pending.map((t) => (across ? t.c : t.r)).sort((a, b) => a - b);
    const fixed = across ? pending[0].r : pending[0].c;
    for (let k = along[0]; k <= along[along.length - 1]; k++) {
      const r = across ? fixed : k, c = across ? k : fixed;
      if (!occupied(r, c)) return "Leave no gaps between your tiles.";
    }
    return "";
  }
  function submit() {
    if (rec.done) return;
    const problem = shapeProblem();
    if (problem) { say(problem, true); nope(); return; }
    const p = byKey.get(keyOf(pending));
    if (!p) {
      say("That isn't a valid play: a word isn't in the word list, or the tiles don't join the board. It didn't use a try.", true);
      nope(); return;
    }
    if (rec.tries.some((t) => t.where === p.where && t.word === p.word)) { say("You already tried that one. Pick another play.", true); return; }
    if (!rec.started) rec.started = Date.now();
    rec.tries.push({ where: p.where, word: p.word });
    if (p.best) rec.solved = true;
    if (p.best || rec.tries.length >= TRIES) rec.done = true;
    store.results[recKey(P)] = rec; save();
    if (rec.done) reportResult(recKey(P), rec.tries.map((t) => t.word), rec.solved, Date.now() - (rec.opened || rec.started));
    pending = []; cursor = null; selected = null;
    say(rec.done ? "" : nudge(p) + ` ${TRIES - rec.tries.length} ${TRIES - rec.tries.length === 1 ? "try" : "tries"} left.`);
    if (rec.done) shown = 0;
    render(true);
    if (rec.done) { const r = $("result"); r.classList.add("reveal"); r.focus({ preventScroll: true }); r.scrollIntoView({ block: "nearest", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" }); }
  }
  // A one-line nudge after a try that missed, from the numbers alone.
  function nudge(p) {
    const b = plays[0];
    if (p.s > b.s) return "That outscores the best play. Look at what you keep.";
    if (p.lv >= b.lv - C("KEPT_FINE_MARGIN", 1)) return "Your kept tiles are fine. There are more points somewhere.";
    return "A better play scores more and keeps better tiles.";
  }

  // ---- tries, result and teaching -----------------------------------------
  function find(t) { return plays.find((p) => p.where === t.where && p.word === t.word); }
  function renderTries(fresh) {
    const box = $("tries");
    box.textContent = "";
    for (let k = 0; k < rec.tries.length; k++) {
      const t = rec.tries[k], li = el("li", "try");
      li.append(el("span", "k", String(k + 1)));
      const p = find(t);
      if (!p) {
        li.append(el("span", "w", t.word.toUpperCase()), el("span", "pct"));
        li.lastChild.append(el("small", null, "puzzle updated"));
        li.setAttribute("aria-label", `Try ${k + 1}: ${t.word}, from before this puzzle was updated`);
      } else {
        if (p.best) li.classList.add("best");
        if (fresh && k === rec.tries.length - 1) li.classList.add("fresh");
        const w = el("span", "w", p.word.toUpperCase());
        w.append(el("small", null, `${p.s} points · value ${Math.round(p.v)}`));
        const pct = el("span", "pct", `${p.pct}%`);
        pct.append(el("small", null, p.best ? "the best" : "of best"));
        li.append(w, pct);
        li.setAttribute("aria-label", `Try ${k + 1}: ${p.word}, ${p.s} points, value ${Math.round(p.v)}, ${p.pct}% of the best${p.best ? ", the best play" : ""}`);
      }
      box.append(li);
    }
  }
  const signed = (x) => { const n = Math.round(x); return (n > 0 ? "+" : n < 0 ? "−" : "±") + Math.abs(n); };
  function keptHTML(leave) {
    if (!leave) return "<span class=\"kept none\">nothing</span>";
    const label = [...leave].map((c) => (c === "?" ? "blank" : c)).join(" ");
    return `<span class="kept" role="img" aria-label="${label}">${[...leave].map((c) => `<i class="mini${c === "?" ? " b" : ""}">${c === "?" ? "" : c}</i>`).join("")}</span>`;
  }
  function worth(x) { const r = C("WORTH_ROUNDING", 0.5); return `<span class="${x >= r ? "pos" : x <= -r ? "neg" : ""}">${signed(x)}</span>`; }
  function esc(s) { return s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" })[c]); }
  function W(p) { return `<strong>${esc(p.word.toUpperCase())}</strong>`; }

  function explain(b, y) {
    const bingo = b.tiles.length === 7;
    if (rec.solved) {
      if (bingo) return `${W(b)} uses all seven tiles: ${b.s} points with the 50-point bonus.`;
      const t = plays.reduce((a, p) => (p.s > a.s ? p : a), b);
      if (t === b) return `${W(b)} scores ${b.s} and keeps ${keptHTML(b.leave)} <span class="nw">(worth ${worth(b.lv)})</span>.`;
      return `${W(b)} scores ${b.s} and keeps ${keptHTML(b.leave)} <span class="nw">(worth ${worth(b.lv)})</span>. The top scorer, ${W(t)} for ${t.s}, keeps ${keptHTML(t.leave)} <span class="nw">(${worth(t.lv)})</span>.`;
    }
    const d = y.s - b.s;
    if (bingo) return `${W(b)} uses all seven tiles for ${b.s} points, bonus included. Your ${W(y)} scored ${y.s}.`;
    if (d > 0) return `Your ${W(y)} scored ${d} more, but kept ${keptHTML(y.leave)} <span class="nw">(worth ${worth(y.lv)})</span>. The bot's ${W(b)} kept ${keptHTML(b.leave)} <span class="nw">(${worth(b.lv)})</span>.`;
    if (d === 0) return `Same points, but ${W(b)} keeps ${keptHTML(b.leave)} <span class="nw">(${worth(b.lv)})</span> instead of your ${keptHTML(y.leave)} <span class="nw">(${worth(y.lv)})</span>.`;
    if (b.lv > y.lv + C("WORTH_ROUNDING", 0.5)) return `${W(b)} scores ${-d} more and keeps better tiles: ${keptHTML(b.leave)} <span class="nw">(${worth(b.lv)})</span> against your ${keptHTML(y.leave)} <span class="nw">(${worth(y.lv)})</span>.`;
    return `${W(b)} scores ${-d} more. Your kept tiles, ${keptHTML(y.leave)} <span class="nw">(${worth(y.lv)})</span>, don't make up the difference.`;
  }
  // One habit worth remembering, chosen from what the plays kept.
  function tip(b, y) {
    const vowels = (s) => [...s].filter((c) => "AEIOU".includes(c)).length;
    const dup = (s) => [...s].find((c, i) => c !== "?" && s.indexOf(c) !== i);
    const lose = y && !rec.solved ? y.leave : null;
    if (b.leave.includes("?") && (!lose || !lose.includes("?"))) return "A blank can be any letter, so it is usually worth more kept than spent on a few points.";
    if (b.leave.includes("S") && (!lose || !lose.includes("S"))) return "An S fits on the end of so many words that it is worth saving for a bigger play.";
    if (lose) {
      if (lose.includes("Q") && !lose.includes("U")) return "A Q without a U is hard to play. Getting rid of it is often worth some points.";
      const d = dup(lose); if (d) return `Two of the same letter, like ${d}${d}, cut your chances of a good next rack.`;
      if (lose.length >= 3 && vowels(lose) === 0) return "Keeping only consonants makes the next rack hard to play.";
      if (lose.length >= 3 && vowels(lose) >= lose.length - 1) return "Too many vowels left behind makes the next rack clunky.";
    }
    if (b.tiles.length >= 5) return "Playing more tiles turns over more of the bag: more chances at the blanks and S's.";
    return "Points now and tiles for later are traded against each other on every turn.";
  }

  function renderResult() {
    const box = $("result");
    box.hidden = !rec.done;
    $("play-area").hidden = rec.done;
    if (!rec.done) return;
    const b = plays[0];
    const tried = rec.tries.map(find).filter(Boolean);
    const y = tried.slice().sort((a, b2) => b2.v - a.v)[0];
    const n = rec.tries.length;
    $("result-title").textContent = rec.solved ? (n === 1 ? "Found it, first try." : `Found it in ${n}.`) : `The best play was ${b.word.toUpperCase()}.`;
    // A puzzle file changed after it was played: keep the result, explain what we can.
    $("explain").innerHTML = y || rec.solved ? explain(b, y || b)
      : `You played this one before it was updated, so your plays can't be shown. The best play now is ${W(b)}: ${b.s} points, keeping ${keptHTML(b.leave)} <span class="nw">(${worth(b.lv)})</span>.`;
    $("tip").textContent = tip(b, y);

    const tb = $("plays").querySelector("tbody");
    tb.textContent = "";
    const TOP = C("TOP_PLAYS", 5);
    const rows = plays.slice(0, TOP);
    tried.forEach((p) => { if (!rows.includes(p)) rows.push(p); });
    rows.sort((a, b2) => a.rank - b2.rank);
    let lastRank = 0;
    rows.forEach((p) => {
      if (p.rank > lastRank + 1 && lastRank >= TOP) { const g = el("tr", "gap"); const td = el("td", null, "⋯"); td.colSpan = 5; g.append(td); tb.append(g); }
      lastRank = p.rank;
      const tr = el("tr");
      tr.tabIndex = 0;
      tr.setAttribute("aria-selected", String(plays[shown] === p));
      const mine = tried.includes(p);
      tr.innerHTML = `<td class="rk">${p.rank}</td><td><span class="word">${esc(p.word.toUpperCase())}</span>${mine ? "<span class=\"you\">you</span>" : ""}</td>` +
        `<td class="n">${p.s}</td><td>${keptHTML(p.leave)}<span class="lv">${signed(p.lv)}</span></td><td class="n"><strong>${Math.round(p.v)}</strong></td>`;
      tr.setAttribute("aria-label", `Rank ${p.rank}: ${p.word}, ${p.s} points, keeps ${p.leave || "nothing"} worth ${signed(p.lv)}, value ${Math.round(p.v)}${mine ? ", your try" : ""}. Show on board.`);
      const showIt = () => { shown = plays.indexOf(p); renderBoard(); [...tb.querySelectorAll("tr")].forEach((x) => x.setAttribute("aria-selected", String(x === tr))); };
      tr.addEventListener("click", showIt);
      tr.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); showIt(); } });
      tb.append(tr);
    });
    $("next").textContent = rec.daily && P.date === TODAY ? nextText() : "";
    $("random-2").textContent = P.id ? "Another random one" : "Play a random one";
  }
  function nextText() {
    const m = minutesToRollover(new Date());
    return `Next puzzle in ${Math.floor(m / 60)} h ${m % 60} min.`;
  }

  // ---- share --------------------------------------------------------------
  const BARS = [...C("SHARE_MARKS", "▁▂▃▄▅▆▇")];
  function shareText() {
    const mark = (p) => (p.best ? C("SHARE_BEST_MARK", "■") : BARS[Math.min(BARS.length - 1, Math.floor((p.pct / 100) * BARS.length))]);
    const marks = rec.tries.map((t) => { const p = find(t); return p ? `${mark(p)} ${p.pct}%` : "·"; });
    const what = P.id ? `practice #${P.id}` : nice(P.date, { day: "numeric", month: "short" });
    const head = `${NAME || "Best play"} · ${what}  ${rec.solved ? rec.tries.length : "X"}/${TRIES}`;
    return [head, marks.join("  "), SITE.SITE_URL || location.origin].join("\n");
  }
  async function share() {
    const text = shareText();
    let ok = false;
    try { await navigator.clipboard.writeText(text); ok = true; } catch (e) {
      try { const ta = el("textarea"); ta.value = text; ta.style.position = "fixed"; ta.style.opacity = "0"; document.body.append(ta); ta.select(); ok = document.execCommand("copy"); ta.remove(); } catch (e2) { ok = false; }
    }
    toast(ok ? "Copied. Paste it anywhere." : text);
  }

  // ---- stats ---------------------------------------------------------------
  function stats() {
    const daily = Object.entries(store.results).filter(([, r]) => r.daily && r.done);
    const solvedDates = new Set(daily.filter(([, r]) => r.solved).map(([d]) => d));
    const dist = { 1: 0, 2: 0, 3: 0, X: 0 };
    daily.forEach(([, r]) => { dist[r.solved ? r.tries.length : "X"]++; });
    let streak = 0, d = solvedDates.has(TODAY) ? TODAY : prevDay(TODAY);
    while (solvedDates.has(d)) { streak++; d = prevDay(d); }
    let best = 0, run = 0, prev = null;
    [...solvedDates].sort().forEach((x) => { run = prev && prevDay(x) === prev ? run + 1 : 1; best = Math.max(best, run); prev = x; });
    return { played: daily.length, solved: solvedDates.size, streak, best, dist };
  }
  function openStats() {
    const s = stats();
    const nums = $("stat-nums"); nums.textContent = "";
    [["Played", s.played], ["Solved", s.played ? Math.round((100 * s.solved) / s.played) + "%" : "–"], ["Streak", s.streak], ["Best streak", s.best]].forEach(([k, v]) => {
      const div = el("div"); div.append(el("dt", null, k), el("dd", null, String(v))); nums.append(div);
    });
    const dist = $("dist"); dist.textContent = "";
    const max = Math.max(1, ...Object.values(s.dist));
    const mine = P && rec && rec.done && rec.daily ? (rec.solved ? String(rec.tries.length) : "X") : null;
    ["1", "2", "3", "X"].forEach((k) => {
      const row = el("div", "bar" + (mine === k ? " now" : ""));
      row.append(el("b", null, k));
      const span = el("span", null, String(s.dist[k])); span.style.setProperty("--w", `${(100 * s.dist[k]) / max}%`);
      row.append(span);
      row.setAttribute("aria-label", `${k === "X" ? "Missed" : `Solved in ${k}`}: ${s.dist[k]}`);
      dist.append(row);
    });
    const prac = Object.entries(store.results).filter(([k, r]) => k.startsWith("practice:") && r.done);
    $("practice-count").textContent = prac.length ? `Practice: ${prac.filter(([, r]) => r.solved).length} solved of ${prac.length} played. Practice doesn't count above.` : "";
    const d = $("stats-dialog");
    try { d.showModal(); } catch (e) { d.setAttribute("open", ""); }
  }

  // ---- status and toast ----------------------------------------------------
  function say(msg, err) { const s = $("status"); s.textContent = msg; s.classList.toggle("err", !!err); }
  let toastT = 0;
  function toast(msg) { const t = $("toast"); t.textContent = msg; t.classList.add("on"); clearTimeout(toastT); toastT = setTimeout(() => t.classList.remove("on"), C("TOAST_MS", 2600)); }

  // ---- whole page ----------------------------------------------------------
  function render(fresh) {
    renderBoard(); renderRack(); renderTries(fresh); renderResult();
    if (!rec.done && !rec.tries.length && !cursor && !pending.length && !$("status").textContent) say(`Tap a square to start. ${TRIES} tries.`);
  }
  function renderHead() {
    $("pz-title").textContent = "Find the best play";
    $("pz-sub").hidden = false;
    $("pz-date").textContent = P.id ? `Practice · #${P.id}` : P.date === TODAY ? `Today · ${nice(P.date, { weekday: "long", day: "numeric", month: "long" })}` : `${nice(P.date)} · from the archive`;
    const sl = $("scoreline"); sl.textContent = "";
    [["You", P.score[0]], ["Them", P.score[1]], ["in the bag", P.bag]].forEach(([k, v], i) => {
      const d = el("div", i === 2 ? "bag" : null); d.append(el("dt", null, k), el("dd", null, String(v))); sl.append(d);
    });
    document.title = NAME ? `${NAME} · Find the best play` : "Find the best play";
  }
  const cache = new Map();
  async function getJSON(path) {
    if (!cache.has(path)) cache.set(path, fetch(path).then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); }));
    return cache.get(path);
  }
  async function openPuzzle(date) {
    const entry = index.find((x) => x.date === date);
    const view = $("view-puzzle");
    if (!entry || date > TODAY) {
      const last = index.filter((x) => x.date <= TODAY).pop();
      $("pz-title").textContent = date > TODAY ? "Not out yet" : "No puzzle today";
      $("pz-sub").innerHTML = last ? `Try one from the <a href="#/archive">archive</a>.` : "The first puzzle arrives soon.";
      $("pz-date").textContent = "";
      view.querySelector(".layout").hidden = true;
      return;
    }
    await load(`puzzles/${date}.json`);
  }
  async function load(path) {
    const view = $("view-puzzle");
    view.querySelector(".layout").hidden = false;
    try { prepare(await getJSON(path)); } catch (e) {
      console.error(e);
      $("pz-title").textContent = "Couldn't load the puzzle";
      $("pz-sub").textContent = "Check your connection and reload.";
      view.querySelector(".layout").hidden = true;
      return;
    }
    say("");
    renderHead();
    $("result").classList.remove("reveal");
    render();
  }
  function renderArchive() {
    const box = $("archive"); box.textContent = "";
    const past = index.filter((x) => x.date <= TODAY), days = C("ARCHIVE_DAYS", 0);
    (days > 0 ? past.slice(-days) : past).slice().reverse().forEach((x) => {
      const r = store.results[x.date];
      const li = el("li"), a = el("a"); a.href = x.date === TODAY ? "#/today" : `#/archive/${x.date}`;
      const d = el("span", "d", nice(x.date, { weekday: "short", day: "numeric", month: "short" }));
      if (x.date === TODAY) d.append(el("small", null, "Today"));
      const st = r && r.done ? (r.solved ? ["solved", `Solved in ${r.tries.length}`] : ["missed", "Missed"]) : r && r.tries.length ? ["", `${r.tries.length} of ${TRIES} tries`] : ["open", "Not played"];
      a.append(d, el("span", "st " + st[0], st[1]));
      li.append(a); box.append(li);
    });
  }
  function show(view) {
    ["puzzle", "archive", "how", "about"].forEach((v) => { $(`view-${v}`).hidden = v !== view; });
  }
  async function route() {
    const h = location.hash.replace(/^#\/?/, "");
    if (h === "archive") { show("archive"); renderArchive(); document.title = NAME ? `Archive · ${NAME}` : "Archive"; }
    else if (h === "how") { show("how"); document.title = NAME ? `How to play · ${NAME}` : "How to play"; }
    else if (h === "about") { show("about"); document.title = NAME ? `About · ${NAME}` : "About"; }
    else if (h === "practice") { location.replace(`#/practice/${pad(await randomId())}`); return; }
    else {
      show("puzzle");
      const pr = /^practice\/(\d+)$/.exec(h);
      const m = /^(?:p|archive)\/(\d{4}-\d{2}-\d{2})$/.exec(h);
      if (pr) await openPractice(+pr[1]);
      else await openPuzzle(m ? m[1] : TODAY);
    }
    if (h) $("main").focus({ preventScroll: true });
    window.scrollTo(0, 0);
  }

  // ---- practice: a separate pool, so it never spoils a daily ---------------
  const pad = (n) => String(n).padStart(4, "0");
  function recKey(doc) { return doc.id ? `practice:${pad(doc.id)}` : doc.date; }
  async function poolSize() {
    const fixed = C("PRACTICE_POOL_SIZE", 0);
    if (fixed > 0) return fixed;
    try { return (await getJSON("puzzles/practice/index.json")).count || 0; } catch (e) { return 0; }
  }
  async function randomId() {
    const n = await poolSize();
    if (!n) return 1;
    const current = P && P.id;
    const played = new Set(Object.keys(store.results).filter((k) => k.startsWith("practice:")).map((k) => +k.slice(9)));
    let ids = Array.from({ length: n }, (_, i) => i + 1).filter((i) => i !== current);
    const fresh = ids.filter((i) => !played.has(i));
    if (C("PRACTICE_AVOID_REPEATS", true) && fresh.length) ids = fresh;  // all played: start over
    return ids.length ? ids[Math.floor(Math.random() * ids.length)] : 1;
  }
  async function openPractice(id) {
    const n = await poolSize();
    if (!n || id < 1 || id > n) {
      $("pz-title").textContent = "No such practice puzzle";
      $("pz-sub").innerHTML = `Try <a href="#/practice">a random one</a>.`;
      $("pz-date").textContent = "";
      $("view-puzzle").querySelector(".layout").hidden = true;
      return;
    }
    await load(`puzzles/practice/${pad(id)}.json`);
  }

  // ---- site statistics: Vercel Web Analytics and Speed Insights ------------
  // Cookieless page-view and performance counts, only on the production host.
  function loadAnalytics() {
    if (!C("ANALYTICS", false) || LOCAL) return;
    let host = "";
    try { host = new URL(SITE.SITE_URL).hostname; } catch (e) { return; }
    if (location.hostname !== host) return;
    window.va = window.va || function () { (window.vaq = window.vaq || []).push(arguments); };
    window.si = window.si || function () { (window.siq = window.siq || []).push(arguments); };
    ["/_vercel/insights/script.js", "/_vercel/speed-insights/script.js"].forEach((src) => {
      const sc = document.createElement("script"); sc.src = src; sc.defer = true; document.head.append(sc);
    });
  }

  // ---- input wiring --------------------------------------------------------
  function onKey(e) {
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    if (document.querySelector("dialog[open]")) return;
    if ($("view-puzzle").hidden || !P || rec.done) return;
    const tag = (e.target.tagName || "").toLowerCase();
    if (tag === "input" || tag === "textarea") return;
    const onBoard = e.target === $("board");
    const onButton = tag === "button" || tag === "a" || tag === "summary" || tag === "tr";
    if (/^[a-zA-Z]$/.test(e.key)) { e.preventDefault(); typeLetter(e.key.toUpperCase()); return; }
    if (e.key === "?" && cursor) {
      const used = new Set(pending.map((t) => t.id)); const b = rack.find((t) => t.ch === "?" && !used.has(t.id));
      if (b) { e.preventDefault(); tryPlace(b.id); }
      return;
    }
    if (e.key === "Backspace" || e.key === "Delete") { e.preventDefault(); backspace(); return; }
    if (e.key === "Escape") { clearAll(); return; }
    if (e.key === "Enter" && !onButton) { e.preventDefault(); submit(); return; }
    if (onBoard) {
      const moves = { ArrowUp: [-1, 0], ArrowDown: [1, 0], ArrowLeft: [0, -1], ArrowRight: [0, 1] };
      if (moves[e.key]) {
        e.preventDefault();
        const [dr, dc] = moves[e.key];
        const cur = cursor || { r: 7, c: 7, dir: "across" };
        const r = Math.min(N - 1, Math.max(0, cur.r + (cursor ? dr : 0))), c = Math.min(N - 1, Math.max(0, cur.c + (cursor ? dc : 0)));
        cursor = { r, c, dir: dr ? "down" : dc ? "across" : cur.dir };
        renderBoard(); return;
      }
      if (e.key === " ") {
        e.preventDefault();
        if (!cursor) cursor = { r: 7, c: 7, dir: "across" };
        else cursor = { ...cursor, dir: cursor.dir === "across" ? "down" : "across" };
        renderBoard();
      }
    }
  }

  function applyTheme(t) {
    if (t) document.documentElement.dataset.theme = t; else delete document.documentElement.dataset.theme;
    const dark = t ? t === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
    $("theme").setAttribute("aria-label", dark ? "Switch to light mode" : "Switch to dark mode");
  }

  async function init() {
    $("site-name").textContent = NAME;
    $("site-name").hidden = !NAME;
    applyTheme(store.theme);
    $("theme").addEventListener("click", () => {
      const dark = document.documentElement.dataset.theme ? document.documentElement.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
      store.theme = dark ? "light" : "dark"; save(); applyTheme(store.theme);
    });
    buildBoard(); buildLetters();
    $("shuffle").addEventListener("click", shuffle);
    $("clear").addEventListener("click", clearAll);
    $("submit").addEventListener("click", submit);
    $("share").addEventListener("click", share);
    $("open-stats").addEventListener("click", openStats);

    $("term-btn").addEventListener("click", () => {
      const pop = $("term-pop"), open = pop.hidden;
      pop.hidden = !open; $("term-btn").setAttribute("aria-expanded", String(open));
    });
    document.addEventListener("keydown", onKey);
    const links = $("about-links");
    [["Blog", SITE.BLOG_URL], ["X", SITE.X_URL], ["GitHub", SITE.GITHUB_URL]].forEach(([t, u]) => {
      if (!u) return; const a = el("a", null, t); a.href = u; a.rel = "noopener"; links.append(a);
    });
    const story = SITE.STORY_URL ? `<a href="${SITE.STORY_URL}" rel="noopener">long story</a>` : "long story";
    $("about-copy").innerHTML = C("ABOUT", []).map((p) => `<p>${p.replace("{story}", story)}</p>`).join("");
    $("about-fine").textContent = C("ABOUT_FINE", "");
    loadAnalytics();
    (SITE.LEARN || []).forEach((l) => {
      const li = el("li"), a = el("a", null, l.name); a.href = l.url; a.rel = "noopener";
      li.append(a, el("span", null, l.note)); $("learn").append(li);
    });
    try { index = await getJSON("puzzles/index.json"); } catch (e) { index = []; }
    window.addEventListener("hashchange", route);
    await route();
  }
  init();
})();
