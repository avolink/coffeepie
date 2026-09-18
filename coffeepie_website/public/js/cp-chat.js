/* ===========================================================================
   Coffee Pie® — asistente virtual (site-wide).

   Dos capas, deliberadamente:
     · un MENÚ GUIADO leído de /chat.json (instantáneo, sin coste, funciona
       aunque el modelo esté caído) que cubre lo que la gente pregunta de
       verdad: cómo empezar, precios, un problema, ser proveedor o fabricante;
     · texto libre → POST /v1/chat, que responde sólo desde una base de
       conocimiento generada de ESTE sitio público y, si no puede, ofrece
       soporte humano.

   /chat.json es el mismo fichero que lee el generador de la base de
   conocimiento, así que el menú que ve el visitante y el texto que el asistente
   puede recuperar no pueden separarse.

   La conversación vive en localStorage: cada página del sitio es un documento
   nuevo, y sin esto el chat se reiniciaría en cada clic.

   Los botones de soporte de la aplicación (el "?" de Mis Máquinas, "Soporte
   Técnico" del menú) abren este panel llamando a window.CoffeePieChat.open().
   =========================================================================== */
(function () {
  'use strict';

  var LOCAL = /^(localhost|127\.0\.0\.1)$/.test(location.hostname);
  /* En producción el endpoint cuelga del PROPIO sitio (coffeepie.co/v1/chat),
     no de api.coffeepie.co. Dos razones:
       · api.coffeepie.co redirige sobre sí mismo (bucle 301) y hoy no sirve
         nada; el asistente no debe depender de que eso se arregle;
       · mismo origen = sin preflight CORS, una ida y vuelta menos por mensaje.
     Base vacía → fetch('/v1/chat'), relativo al host que sirvió la página. */
  var API_BASE = LOCAL ? 'http://localhost:8791' : '';
  var SUPPORT_URL = 'mailto:soporte@coffeepie.co';
  var STORE = 'cp_chat';
  var TTL = 6 * 60 * 60 * 1000;      // una conversación más vieja que esto empieza de cero
  var MAX_KEEP = 40;
  var MAX_CHARS = 500;

  /* ---- idioma -------------------------------------------------------------
     El sitio ofrece 12 idiomas y guarda el elegido en cp_lang. Las RESPUESTAS
     ya llegan traducidas (la ruta recibe el idioma y se lo impone al modelo),
     así que aquí sólo hace falta traducir el cromado del panel. Está en español
     e inglés; añadir un idioma es añadir un bloque a UI, nada más.
     El menú de /chat.json sigue en español — es el límite conocido de esta
     versión y está anotado en el README del servicio. */
  var UI = {
    es: {
      title: 'Asistente Coffee Pie', sub: 'Respuestas al instante',
      ph: 'Escribe tu pregunta…', send: 'Enviar', close: 'Cerrar',
      reset: 'Reiniciar conversación', open: 'Abrir el asistente',
      back: 'Volver al menú', support: 'Contactar Soporte',
      legal: 'Asistente automático. Para casos particulares te conectamos con soporte.',
      down: 'No pude conectarme en este momento. Puedes escribirnos y te atendemos enseguida.'
    },
    en: {
      title: 'Coffee Pie Assistant', sub: 'Instant answers',
      ph: 'Type your question…', send: 'Send', close: 'Close',
      reset: 'Restart conversation', open: 'Open the assistant',
      back: 'Back to menu', support: 'Contact Support',
      legal: 'Automated assistant. For specific cases we connect you with support.',
      down: "I couldn't connect right now. Write to us and we'll help you straight away."
    }
  };
  function uiLang() {
    try {
      var l = (localStorage.getItem('cp_lang') || 'es').slice(0, 2);
      return l;
    } catch (e) { return 'es'; }
  }
  function T() { return UI[uiLang()] || UI.es; }

  /* ---- estado ------------------------------------------------------------- */
  var FLOW = null;                 // /chat.json, cargado una vez
  var msgs = [];                   // [{r:'bot'|'me', t, links, options, support}]
  var open = false, busy = false, booted = false;
  var panel = null, logEl = null, fab = null, inputEl = null;

  function load() {
    try {
      var s = JSON.parse(localStorage.getItem(STORE) || 'null');
      if (!s || Date.now() - (s.ts || 0) > TTL) return false;
      msgs = Array.isArray(s.msgs) ? s.msgs.slice(-MAX_KEEP) : [];
      open = !!s.open;
      return msgs.length > 0;
    } catch (e) { return false; }
  }
  function save() {
    try { localStorage.setItem(STORE, JSON.stringify({ ts: Date.now(), open: open, msgs: msgs.slice(-MAX_KEEP) })); } catch (e) {}
  }

  /* ---- markup ------------------------------------------------------------- */
  function esc(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }
  /* [etiqueta](destino) → enlace. Sólo rutas del sitio y https. La API aplica la
     misma regla en el servidor; ésta es la segunda puerta, por si acaso.
     El cierre es opcional y puede ser ')' o ']': un modelo pequeño escribe
     "[Precios](/pricing.html]" lo bastante a menudo como para que un parser
     estricto deje el markdown crudo a la vista del visitante. */
  function md(text) {
    return esc(text).replace(/\[([^\]]{1,80})\]\(\s*([^\s)\]]{1,200})(?:\s*[)\]]+)?/g, function (m, label, href) {
      if (/^\/[\w\-./?=&#%]*$/.test(href)) return '<a href="' + href + '">' + label + '</a>';
      if (/^https:\/\/[\w.\-]+\/?[\w\-./?=&#%]*$/.test(href)) return '<a href="' + href + '" target="_blank" rel="noopener">' + label + '</a>';
      if (/^mailto:[^\s"<>]+$/.test(href)) return '<a href="' + href + '">' + label + '</a>';
      return label;
    });
  }

  var BOT_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="4" y="8" width="16" height="11" rx="3"/><path d="M12 8V4.5M9.5 13h.01M14.5 13h.01M9 16.5h6M2.5 12.5v2M21.5 12.5v2"/><circle cx="12" cy="3.5" r="1.4" fill="currentColor" stroke="none"/></svg>';
  var MAIL_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="2.5" y="4.5" width="19" height="15" rx="2.5"/><path d="M3 6.5l9 6 9-6"/></svg>';
  var SEND_ICON = '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M3.4 20.4 21 12 3.4 3.6 3.4 10l12.6 2-12.6 2z"/></svg>';

  /* ---- render ------------------------------------------------------------- */
  function renderMsg(m) {
    var wrap = document.createDocumentFragment();
    if (m.t) {
      var b = document.createElement('div');
      b.className = 'cpchat-msg ' + (m.r === 'me' ? 'cpchat-me' : 'cpchat-bot');
      b.innerHTML = md(m.t);
      wrap.appendChild(b);
    }
    if (m.links && m.links.length) {
      var lc = document.createElement('div'); lc.className = 'cpchat-chips';
      m.links.forEach(function (l) {
        var a = document.createElement('a');
        a.className = 'cpchat-chip cpchat-chip-link';
        a.href = l.url; a.textContent = l.label;
        if (/^https?:/.test(l.url)) { a.target = '_blank'; a.rel = 'noopener'; }
        lc.appendChild(a);
      });
      wrap.appendChild(lc);
    }
    if (m.support) {
      var s = document.createElement('a');
      s.className = 'cpchat-support';
      s.href = m.supportUrl || SUPPORT_URL;
      if (/^https?:/.test(s.href)) { s.target = '_blank'; s.rel = 'noopener'; }
      s.innerHTML = MAIL_ICON + '<span>' + esc(m.supportLabel || T().support) + '</span>';
      wrap.appendChild(s);
    }
    if (m.options && m.options.length) {
      var oc = document.createElement('div'); oc.className = 'cpchat-chips';
      m.options.forEach(function (o) {
        var btn = document.createElement('button');
        btn.type = 'button'; btn.className = 'cpchat-chip'; btn.textContent = o.label;
        btn.addEventListener('click', function () { pick(o); });
        oc.appendChild(btn);
      });
      wrap.appendChild(oc);
    }
    return wrap;
  }
  function draw() {
    if (!logEl) return;
    logEl.innerHTML = '';
    msgs.forEach(function (m) { logEl.appendChild(renderMsg(m)); });
    logEl.scrollTop = logEl.scrollHeight;
  }
  function push(m) { msgs.push(m); if (msgs.length > MAX_KEEP) msgs = msgs.slice(-MAX_KEEP); save(); draw(); }

  function typing(on) {
    var old = logEl.querySelector('.cpchat-typing');
    if (old) old.remove();
    if (on) {
      var d = document.createElement('div');
      d.className = 'cpchat-msg cpchat-bot cpchat-typing';
      d.innerHTML = '<span></span><span></span><span></span>';
      logEl.appendChild(d); logEl.scrollTop = logEl.scrollHeight;
    }
  }

  /* ---- menú guiado -------------------------------------------------------- */
  function node(key) {
    var n = FLOW && FLOW[key];
    if (!n) {   // sin /chat.json el asistente sigue siendo útil: texto libre
      push({ r: 'bot', t: T().sub, support: true });
      return;
    }
    push({
      r: 'bot', t: n.text,
      links: (n.links || []).slice(),
      options: (n.options || []).slice(),
      support: !!n.support
    });
  }
  function pick(o) {
    push({ r: 'me', t: o.label });
    if (o.go) setTimeout(function () { node(o.go); }, 160);
  }

  /* ---- API ---------------------------------------------------------------- */
  function ask(text) {
    busy = true; syncSend();
    typing(true);
    var history = msgs.filter(function (m) { return m.t; }).slice(-6)
      .map(function (m) { return { role: m.r === 'me' ? 'user' : 'assistant', content: String(m.t).slice(0, 400) }; });
    history.pop();   // el mensaje que estamos enviando ya está en msgs

    fetch(API_BASE + '/v1/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text, lang: uiLang(), history: history })
    })
      .then(function (r) { return r.ok ? r.json() : Promise.reject(new Error(r.status)); })
      .then(function (d) {
        typing(false);
        push({
          r: 'bot', t: d.reply || '',          // ya viene en el idioma del visitante
          links: d.links || [],
          support: !!d.showSupport,
          supportUrl: (d.support && d.support.url) || SUPPORT_URL,
          supportLabel: (d.support && d.support.label) || T().support,
          options: [{ label: T().back, go: 'start' }]
        });
      })
      .catch(function () {
        typing(false);
        // El asistente es una comodidad; si no responde, el visitante tiene que
        // seguir pudiendo llegar a una persona.
        push({ r: 'bot', t: T().down, support: true, options: [{ label: T().back, go: 'start' }] });
      })
      .then(function () { busy = false; syncSend(); });
  }

  /* ---- panel -------------------------------------------------------------- */
  function syncSend() {
    var btn = panel && panel.querySelector('.cpchat-send');
    if (btn) btn.disabled = busy || !inputEl.value.trim();
  }

  function build() {
    var t = T();
    panel = document.createElement('div');
    panel.className = 'cpchat-panel';
    panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-label', t.title);
    panel.hidden = true;
    panel.innerHTML =
      '<div class="cpchat-head">' +
        '<span class="cpchat-head-ico">' + BOT_ICON + '</span>' +
        // BETA a la vista: el asistente orienta, no decide. La fuente de verdad
        // es soporte, y por eso el botón está siempre a un clic.
        '<span><span class="cpchat-title">' + esc(t.title) + '</span><span class="cpchat-beta">BETA</span><br>' +
        '<span class="cpchat-sub">' + esc(t.sub) + '</span></span>' +
        '<span class="cpchat-head-actions">' +
          '<button type="button" class="cpchat-x cpchat-reset" title="' + esc(t.reset) + '" aria-label="' + esc(t.reset) + '">⟳</button>' +
          '<button type="button" class="cpchat-x cpchat-close" title="' + esc(t.close) + '" aria-label="' + esc(t.close) + '">✕</button>' +
        '</span>' +
      '</div>' +
      '<div class="cpchat-log" aria-live="polite"></div>' +
      '<form class="cpchat-form">' +
        '<textarea class="cpchat-input" rows="1" maxlength="' + MAX_CHARS + '" placeholder="' + esc(t.ph) + '" aria-label="' + esc(t.ph) + '"></textarea>' +
        '<button type="submit" class="cpchat-send" aria-label="' + esc(t.send) + '" disabled>' + SEND_ICON + '</button>' +
      '</form>' +
      '<p class="cpchat-legal">' + esc(t.legal) + '</p>';
    document.body.appendChild(panel);

    logEl = panel.querySelector('.cpchat-log');
    inputEl = panel.querySelector('.cpchat-input');

    panel.querySelector('.cpchat-close').addEventListener('click', close);
    panel.querySelector('.cpchat-reset').addEventListener('click', function () {
      msgs = []; save(); draw(); node('start'); inputEl.focus();
    });
    panel.querySelector('.cpchat-form').addEventListener('submit', function (e) {
      e.preventDefault();
      var v = inputEl.value.trim().slice(0, MAX_CHARS);
      if (!v || busy) return;
      inputEl.value = ''; inputEl.style.height = 'auto';
      push({ r: 'me', t: v });
      ask(v);
    });
    inputEl.addEventListener('input', function () {
      this.style.height = 'auto';
      this.style.height = Math.min(90, this.scrollHeight) + 'px';
      syncSend();
    });
    inputEl.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        panel.querySelector('.cpchat-form').dispatchEvent(new Event('submit', { cancelable: true }));
      }
    });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && open) close(); });
  }

  function show() {
    if (!panel) return;
    open = true; save();
    panel.hidden = false;
    fab.hidden = true;
    var dot = fab.querySelector('.cpchat-dot'); if (dot) dot.remove();
    try { localStorage.setItem('cp_chat_seen', '1'); } catch (e) {}
    if (!msgs.length) node('start'); else draw();
    if (window.matchMedia('(min-width: 601px)').matches) setTimeout(function () { inputEl.focus(); }, 40);
  }
  function close() {
    open = false; save();
    panel.hidden = true;
    fab.hidden = false;
    fab.focus();
  }

  /* ---- arranque ----------------------------------------------------------- */
  function mount() {
    if (booted) return;
    booted = true;
    var t = T();

    fab = document.createElement('button');
    fab.type = 'button';
    fab.className = 'cpchat-fab';
    fab.setAttribute('aria-label', t.open);
    fab.setAttribute('title', t.title);
    var seen = false;
    try { seen = !!localStorage.getItem('cp_chat_seen'); } catch (e) {}
    fab.innerHTML = BOT_ICON + (seen ? '' : '<span class="cpchat-dot"></span>');
    fab.addEventListener('click', show);
    document.body.appendChild(fab);

    build();
    var had = load();
    if (open) { panel.hidden = false; fab.hidden = true; }
    if (had) draw();
  }

  /* El menú vive en /chat.json. Si no carga, el asistente arranca igual y
     funciona con texto libre — nunca se queda sin widget por un 404. */
  function boot() {
    fetch('/chat.json', { cache: 'no-cache' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) { FLOW = j; })
      .catch(function () { FLOW = null; })
      .then(mount);
  }

  // Los botones de soporte de la app entran por aquí.
  window.CoffeePieChat = {
    open: function () { if (!booted) { mount(); } show(); },
    close: close,
    isOpen: function () { return open; }
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
