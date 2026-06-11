// Coffee Pie — Panel auth gate.
// Classic login in front of the user panel:
//   • Clicking any "Panel de Usuario" / "/panel" link opens a login modal.
//   • Credentials are checked against panel_backend (/auth/login → Supabase test DB).
//   • Wrong creds are rejected; correct creds store a token and open /panel.
//   • /panel itself is gated: no valid token → bounced back to the login.
//
// Works regardless of how/when the header is injected (event delegation on
// document). Vanilla JS only. API base auto-detects localhost for QA.
(function () {
    'use strict';

    var isLocal = /^(localhost|127\.0\.0\.1)$/.test(location.hostname);
    var API = isLocal ? 'http://localhost:8000' : 'https://api.coffeepie.co';
    var TOKEN_KEY = 'cp_panel_token';

    // ── Translation helper ───────────────────────────────────────────────
    function t(key) {
        try {
            var lang = window.CoffeePieLang && window.CoffeePieLang.get ? window.CoffeePieLang.get() : 'es';
            var translated = window.CoffeePieLang && window.CoffeePieLang.translate
                ? window.CoffeePieLang.translate(key, lang)
                : null;
            return translated || key;
        } catch (e) { return key; }
    }

    function token() { return sessionStorage.getItem(TOKEN_KEY); }
    function setToken(t) { sessionStorage.setItem(TOKEN_KEY, t); }
    function clearToken() { sessionStorage.removeItem(TOKEN_KEY); }

    // Treat a token as valid only if it's a JWT that hasn't expired.
    function tokenValid() {
        var t = token();
        if (!t) return false;
        try {
            var p = JSON.parse(atob(t.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')));
            return !p.exp || p.exp * 1000 > Date.now();
        } catch (e) { return false; }
    }

    function isPanelLink(el) {
        var a = el && el.closest && el.closest('a, button, [role="link"]');
        if (!a) return false;
        // Exclude cart links — cart should never trigger the login gate.
        if (a.getAttribute && a.getAttribute('data-testid') === 'cart-link') return false;
        if (a.getAttribute && (a.getAttribute('href') === '/cart' || a.getAttribute('href') === '/cart/')) return false;
        var href = a.getAttribute && a.getAttribute('href');
        return (href === '/panel' || href === '/panel/') ||
               (a.getAttribute && a.getAttribute('data-testid') === 'user-panel-link') ||
               (a.classList && a.classList.contains('user-panel-header-link'));
    }

    // ── Modal ────────────────────────────────────────────────────────────
    var modal;
    function buildModal() {
        if (modal) return modal;
        var css = ''
            + '.cpg-bg{display:none;position:fixed;inset:0;background:rgba(0,0,0,.85);z-index:2147483647;justify-content:center;align-items:center;font-family:Arial,Helvetica,sans-serif;}'
            + '.cpg-bg.show{display:flex;}'
            + '.cpg{background:#1a1a1a;padding:42px 36px;border-radius:16px;width:380px;max-width:92vw;border:1px solid #333;text-align:center;}'
            + '.cpg h2{color:#c18b44;margin:0 0 6px;font-size:20px;}'
            + '.cpg p{color:#888;margin:0 0 22px;font-size:13px;}'
            + '.cpg input{width:100%;box-sizing:border-box;padding:13px;margin-bottom:13px;background:#222;border:1px solid #444;border-radius:8px;color:#fff;font-size:15px;}'
            + '.cpg input:focus{border-color:#c18b44;outline:none;}'
            + '.cpg .cpg-btn{width:100%;padding:13px;background:#c18b44;color:#111;border:none;border-radius:8px;font-size:15px;font-weight:bold;cursor:pointer;margin-top:6px;}'
            + '.cpg .cpg-btn:disabled{opacity:.5;cursor:not-allowed;}'
            + '.cpg .cpg-cancel{color:#888;text-decoration:underline;cursor:pointer;font-size:13px;margin-top:14px;display:inline-block;}'
            + '.cpg .cpg-err{color:#ff6b6b;font-size:13px;margin-top:10px;min-height:16px;}';
        var st = document.createElement('style'); st.textContent = css; document.head.appendChild(st);

        modal = document.createElement('div'); modal.className = 'cpg-bg';
        modal.innerHTML =
            '<div class="cpg">' +
            '<h2>Coffee Pie</h2><p class="cpg-subtitle">' + t('Accede a tu Panel de Usuario') + '</p>' +
            '<input class="cpg-email" type="email" placeholder="' + t('Correo') + '" autocomplete="username">' +
            '<input class="cpg-pass" type="password" placeholder="' + t('Contraseña') + '" autocomplete="current-password">' +
            '<div class="cpg-err"></div>' +
            '<button class="cpg-btn cpg-submit">' + t('Iniciar Sesión') + '</button>' +
            '<span class="cpg-cancel">' + t('Cancelar') + '</span>' +
            '</div>';
        document.body.appendChild(modal);

        var email = modal.querySelector('.cpg-email');
        var pass = modal.querySelector('.cpg-pass');
        var err = modal.querySelector('.cpg-err');
        var submit = modal.querySelector('.cpg-submit');

        function doLogin() {
            var e = email.value.trim(), p = pass.value;
            if (!e || !p) { err.textContent = t('Ingresa correo y contraseña.'); return; }
            err.textContent = ''; submit.textContent = t('Entrando…'); submit.disabled = true;
            fetch(API + '/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email: e, password: p })
            })
            .then(function (r) { return r.json().then(function (b) { return { ok: r.ok, body: b }; }); })
            .then(function (res) {
                submit.textContent = t('Iniciar Sesión'); submit.disabled = false;
                if (res.ok && res.body.access_token) {
                    setToken(res.body.access_token);
                    close();
                    location.href = '/panel';
                } else {
                    err.textContent = t('Credenciales inválidas.');
                }
            })
            .catch(function () {
                submit.textContent = t('Iniciar Sesión'); submit.disabled = false;
                err.textContent = t('No se pudo conectar al servidor.') + ' (' + API + ')';
            });
        }

        submit.onclick = doLogin;
        pass.onkeydown = function (ev) { if (ev.key === 'Enter') doLogin(); };
        modal.querySelector('.cpg-cancel').onclick = close;
        modal.onclick = function (ev) { if (ev.target === modal) close(); };
        return modal;
    }

    function open() { buildModal().classList.add('show'); modal.querySelector('.cpg-email').focus(); }
    function close() { if (modal) modal.classList.remove('show'); }

    // ── Intercept panel-link clicks anywhere on the page ─────────────────
    document.addEventListener('click', function (ev) {
        if (!isPanelLink(ev.target)) return;
        if (tokenValid()) return; // already logged in → let the link proceed
        ev.preventDefault();
        ev.stopPropagation();
        open();
    }, true);

    // ── Gate the /panel page itself ──────────────────────────────────────
    function gatePanelPage() {
        var onPanel = /^\/panel\/?$/.test(location.pathname);
        if (!onPanel) return;
        if (!tokenValid()) {
            // Direct access without a session → send home and prompt login.
            sessionStorage.setItem('cp_post_login', '/panel');
            location.replace('/');
            return;
        }
        // Wire logout if the panel has a logout control.
        document.addEventListener('click', function (ev) {
            var b = ev.target.closest && ev.target.closest('.panel-logout-button');
            if (b) { ev.preventDefault(); clearToken(); location.href = '/'; }
        }, true);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', gatePanelPage);
    } else {
        gatePanelPage();
    }

    // Expose the token for the data-loader (cp-panel-data.js).
    window.cpPanelAuth = { token: token, valid: tokenValid, api: API, logout: function () { clearToken(); } };
})();
