// Coffee Pie — Panel browser-streaming launcher.
// Gates the header stream icon by account tier (from the JWT, injected by the
// Supabase custom access token hook as app_metadata.tier):
//   • Big_Package → full color, enabled, clickable.
//   • any other   → grayscale, dimmed, locked, click explains the requirement.
// The thumbnail is the user's LAST session preview when the backend can supply
// one, otherwise a guaranteed default image (the icon is never empty).
// Vanilla JS. Requires cp-panel-auth.js (window.cpPanelAuth).
(function () {
    'use strict';

    var DEFAULT_THUMB = '/assets/stream-default.svg';
    var STREAM_TIER = 'big_package';   // compared case-insensitively

    function ready(fn) {
        if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', fn);
        else fn();
    }

    function tr(es) {
        try {
            if (window.CoffeePieLang && window.CoffeePieLang.get() !== 'es') {
                var t = window.CoffeePieLang.translate(es, window.CoffeePieLang.get());
                if (t) return t;
            }
        } catch (e) { /* fall back to Spanish */ }
        return es;
    }

    function toast(msg) {
        if (typeof window.showToast === 'function') window.showToast(msg);
        else console.log('[CP stream]', msg);
    }

    function auth() { return window.cpPanelAuth || {}; }
    function tier() { return (auth().tier ? auth().tier() : 'free'); }
    function enabled() { return String(tier()).toLowerCase() === STREAM_TIER; }

    // ── Last-session thumbnail (best-effort; default on any failure) ──────
    // When the backend exposes GET {API}/stream/thumbnail returning an image
    // (or a JSON {url}), we swap it in. Until then this quietly no-ops and the
    // default image stays — so the icon always has a picture.
    function loadThumbnail() {
        var img = document.getElementById('cp-stream-thumb');
        if (!img || !auth().api || !auth().token || !auth().token()) return;
        fetch(auth().api + '/stream/thumbnail', {
            headers: { 'Authorization': 'Bearer ' + auth().token() }
        }).then(function (r) {
            if (!r.ok) throw new Error('no thumb');
            var ct = r.headers.get('content-type') || '';
            if (ct.indexOf('application/json') !== -1) {
                return r.json().then(function (j) { if (j && j.url) img.src = j.url; });
            }
            return r.blob().then(function (b) { img.src = URL.createObjectURL(b); });
        }).catch(function () { /* keep default */ });
    }

    // ── Click behaviour ──────────────────────────────────────────────────
    window.openBrowserStream = function () {
        if (!enabled()) {
            toast(tr('El acceso por navegador requiere el Paquete Grande. Los demás paquetes usan el Terminal Codec.'));
            return;
        }
        // Big_Package: open the browser session. The live desktop view is the
        // next build phase; for now signal intent honestly rather than faking a
        // stream. (Will navigate to /stream once the session view exists.)
        toast(tr('Preparando tu sesión en el navegador…'));
    };

    // ── Apply enabled/disabled visual state ──────────────────────────────
    function applyState() {
        var btn = document.getElementById('cp-stream-btn');
        var lock = document.getElementById('cp-stream-lock');
        var img = document.getElementById('cp-stream-thumb');
        if (!btn) return;
        var on = enabled();
        btn.disabled = false; // still clickable so disabled users get the explainer
        btn.style.cursor = on ? 'pointer' : 'not-allowed';
        btn.style.opacity = on ? '1' : '0.55';
        btn.style.boxShadow = on ? '0 0 0 2px rgba(193,139,68,0.55)' : 'none';
        if (img) img.style.filter = on ? 'none' : 'grayscale(1)';
        if (lock) lock.style.display = on ? 'none' : 'block';
        btn.setAttribute('aria-disabled', on ? 'false' : 'true');
        btn.title = on
            ? tr('Abrir sesión en el navegador')
            : tr('Requiere Paquete Grande');
    }

    ready(function () {
        applyState();
        if (enabled()) loadThumbnail();
        // Re-localize the title if the language changes.
        window.addEventListener('cplangchange', applyState);
    });
})();
