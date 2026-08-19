// QA forcing switch — summon any gated screen on demand, on a real device.
//
// Why it exists: several screens only ever appear once (first-run intro cards,
// the install pitch, the stranger's landing) or in states you cannot reach by
// wanting to (a dead streak's obituary, the new-edition bar). On the owner's
// own phone — already a returning player — most of them are unreachable, so
// they shipped unseen. This panel makes every one of them a button.
//
// Activation: append ?qa=1 once. The flag persists in misc.qaMode, so the
// panel survives navigation and app restarts until switched off from inside.
// Deliberately NOT gated to localhost (unlike ?dailydate=, which changes which
// edition you see): this has to work on the live site, on a real phone, in the
// installed app. That is safe because nothing here reveals content — every
// action only forces a UI state the player could already reach by playing.
// It never unlocks an unaired edition, an answer, or an archive entry.
//
// Loaded dynamically (app.js imports it only when active), so ordinary players
// never download it and it stays out of the service-worker precache.

const ACTIONS = [
  // "Install pitch" is the strip on Home; the six screens below it are the
  // full-page ask, one per detected browser (js/install.js). Every branch has
  // a button because almost none of them can be reached on the phone you
  // happen to be holding — which is exactly how the old, wrong iOS
  // instructions survived for months.
  ['Install pitch', 'installTip'],
  ['Save it · iOS Safari', 'installSafari'],
  ['Save it · Chrome iPhone', 'installChromeIOS'],
  ['Save it · Android button', 'installNative'],
  ['Save it · other browser', 'installGeneric'],
  ['Escape · Instagram', 'webviewInstagram'],
  ['Escape · other app', 'webviewGeneric'],
  ['Webview banner', 'webviewNote'],
  ['Intro · Face Value', 'introWho'],
  ['Intro · Lifeline', 'introMap'],
  ['Intro · Relic', 'introWhat'],
  ['Intro · Thread', 'introThread'],
  ['Streak obituary', 'obituary'],
  ['Full-house celebration', 'celebration'],
  ['New edition bar', 'newEdition'],
  ['Edition-closed strip', 'issueClosed'],
];

function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text) n.textContent = text;
  return n;
}

// ---------- the crash note ----------
// app.js's crash beacon can only put a script BASENAME in an analytics event —
// an error message can carry a URL, and nothing identifying may leave the
// device. So the readable half (message, file:line, build, when) is written to
// misc.lastError instead... where, until now, nothing ever read it. A week of
// "9-app-error-mapgamejs" told us a file and nothing else.
//
// This is that missing window: read-only, no clearing, no copying out, and
// reachable only from the QA panel — which ordinary players never load (app.js
// imports js/qa.js only when ?qa=1 has been used on that device). It adds
// nothing to normal navigation, so the no-dead-ends contract is untouched.
function crashNote(store) {
  const wrap = el('div', 'qa-note');
  wrap.append(el('strong', null, 'Last crash on this device'));
  let e = null;
  try { e = store.getMisc().lastError; } catch (err) { /* storage refused */ }
  if (!e || !e.detail) {
    wrap.append(el('p', null, 'None recorded.'));
    return wrap;
  }
  const when = Number.isFinite(e.at) ? new Date(e.at) : null;
  wrap.append(el('p', 'qa-note-meta',
    [when ? when.toLocaleString() : 'time unknown',
      e.build || 'build unknown',
      e.kind || 'error'].join(' · ')));
  // textContent, never innerHTML: this string is an error message from the
  // wild and may hold anything at all.
  wrap.append(el('p', 'qa-note-detail', String(e.detail)));
  return wrap;
}

export function initQA(actions, store) {
  if (document.getElementById('qa-panel')) return;

  const panel = el('div');
  panel.id = 'qa-panel';
  panel.setAttribute('role', 'region');
  panel.setAttribute('aria-label', 'QA screen forcing panel');

  const bar = el('div', 'qa-bar');
  const title = el('strong', null, 'QA');
  const toggle = el('button', 'qa-toggle', 'Hide');
  bar.append(title, toggle);

  const body = el('div', 'qa-body');
  for (const [label, key] of ACTIONS) {
    const b = el('button', 'qa-btn', label);
    b.addEventListener('click', () => {
      try {
        const fn = actions[key];
        if (typeof fn === 'function') fn();
        else console.warn('QA: no action for', key);
      } catch (e) {
        console.error('QA action failed:', key, e);
      }
    });
    body.appendChild(b);
  }

  // What the last crash on this device actually said, above the destructive
  // controls (the wipe below erases it along with everything else).
  body.appendChild(crashNote(store));

  // Destructive actions live at the end, visually separated.
  const wipe = el('button', 'qa-btn qa-danger', 'Fresh device (wipe + reload)');
  wipe.addEventListener('click', () => {
    if (!confirm('Erase ALL play data on this device and reload as a brand-new visitor?')) return;
    try {
      localStorage.removeItem('chronicle.v1');
      localStorage.removeItem('chronicle.v1.backup');
    } catch (e) { /* storage refused; reload anyway */ }
    location.href = location.pathname + '?qa=1';
  });

  const off = el('button', 'qa-btn qa-off', 'Turn QA off');
  off.addEventListener('click', () => {
    store.setMisc({ qaMode: false });
    location.href = location.pathname;
  });
  body.append(wipe, off);

  toggle.addEventListener('click', () => {
    const hidden = body.hasAttribute('hidden');
    if (hidden) body.removeAttribute('hidden'); else body.setAttribute('hidden', '');
    toggle.textContent = hidden ? 'Hide' : 'Show';
  });

  panel.append(bar, body);
  document.body.appendChild(panel);
}
