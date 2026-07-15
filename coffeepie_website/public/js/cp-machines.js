// Coffee Pie — "Mis Máquinas" (machines.html) behaviour.
// VanillaJS clone of the QML frontend (Home_Screen / StackViewBasic2 /
// Contextual_Menu / StackViewAdvanced). Big_Package tier only.
//
// Data + actions target the documented VM REST contract used by the QML
// Python client (vmsutilities.py):
//   GET    {api}/vms/me
//   GET    {api}/vms/{id}/status
//   POST   {api}/vms/{id}/start|stop|shutdown|reboot
//   POST   {api}/vms/clone/{id}          POST {api}/vms/clone-with-specs
//   POST   {api}/snapshots/Snapshot/create
//   DELETE {api}/vms/{id}
// When the backend doesn't (yet) expose these, the page falls back to a
// clearly-labelled demo dataset so the look & behaviour are fully
// exercisable now. The LAUNCH action always uses the real, working
// /stream/session broker.
(function () {
    'use strict';

    // ── OS catalog (icon + indicative Cr/min) ────────────────────────────
    var OS = {
        bodhi:   { label: 'Bodhi Linux',  icon: 'Bodhi_Linux_Icon.png', rate: 30 },
        win10:   { label: 'Windows 10',   icon: 'W10_Icon.png',         rate: 60 },
        win11:   { label: 'Windows 11',   icon: 'W11_Icon.png',         rate: 70 },
        debian:  { label: 'Debian',       icon: 'Debian_Icon.png',      rate: 25 },
        mint:    { label: 'Linux Mint',   icon: 'Linux_Mint_Icon.png',  rate: 30 },
        arch:    { label: 'Arch Linux',   icon: 'Manjaro_Icon.png',     rate: 30 },
        centos:  { label: 'CentOS',       icon: 'Cent_OS_Icon.png',     rate: 25 },
        steamos: { label: 'SteamOS',      icon: 'Steam_OS_Icon.png',    rate: 80 },
        docker:  { label: 'Docker',       icon: 'Docker_OS_Icon.png',   rate: 20 }
    };
    var OS_DIR = '/assets/machines/os/';

    function osKey(raw) {
        var s = String(raw || '').toLowerCase();
        if (/win.*11|windows 11/.test(s)) return 'win11';
        if (/win.*10|windows 10|win/.test(s)) return 'win10';
        if (/bodhi/.test(s)) return 'bodhi';
        if (/mint/.test(s)) return 'mint';
        if (/debian/.test(s)) return 'debian';
        if (/arch|manjaro/.test(s)) return 'arch';
        if (/cent/.test(s)) return 'centos';
        if (/steam/.test(s)) return 'steamos';
        if (/docker/.test(s)) return 'docker';
        if (/linux/.test(s)) return 'bodhi';
        return 'bodhi';
    }
    function osInfo(key) { return OS[key] || OS.bodhi; }

    // ── Auth handle ──────────────────────────────────────────────────────
    var A = window.cpPanelAuth || {};
    function api() { return A.api || ''; }
    function token() { return A.token ? A.token() : ''; }
    function tierRaw() { return String(A.tier ? A.tier() : 'free').toLowerCase(); }
    function isBig() { return tierRaw() === 'big_package'; }

    function tierLabel() {
        var t = tierRaw();
        if (t === 'big_package') return 'Paquete Grande';
        if (t === 'medium_package') return 'Paquete Medio';
        if (t === 'small_package') return 'Paquete Pequeño';
        if (t === 'free' || !t) return 'Gratis';
        return t.replace(/_/g, ' ').replace(/\b\w/g, function (c) { return c.toUpperCase(); });
    }

    // ── Small helpers ────────────────────────────────────────────────────
    var $ = function (id) { return document.getElementById(id); };
    function fmt(n) {
        var s = String(Math.round(Number(n) || 0));
        return s.replace(/\B(?=(\d{3})+(?!\d))/g, "'");
    }
    var toastT;
    function toast(msg) {
        var el = $('toast'); if (!el) return;
        el.textContent = msg; el.classList.add('show');
        clearTimeout(toastT); toastT = setTimeout(function () { el.classList.remove('show'); }, 3200);
    }

    // ── State ────────────────────────────────────────────────────────────
    var machines = [];
    var credits = 0;
    var demoMode = false;
    var currentVm = null;      // machine bound to the open context menu
    var advanced = false;

    function DEMO() {
        // Mirrors the reference "Avanzado" dataset so both views look real.
        return [
            mk('Mi Máquina Personal', 'win10', 8),
            mk('Mi Workstation', 'win11', 16),
            mk('Production DB', 'debian', 2),
            mk('Mint', 'mint', 4),
            mk('Arch Pentesting', 'arch', 1)
        ];
        function mk(name, key, slices) {
            var info = osInfo(key);
            return {
                id: 'demo-' + Math.random().toString(36).slice(2, 8),
                vmid: 100 + Math.floor(Math.random() * 900),
                name: name, os: key, osLabel: info.label, rate: info.rate,
                status: 'Creado', running: false, slices: slices,
                specs: { cpu: slices, memory: slices * 1024, storage: 40, so: key }
            };
        }
    }

    function normalize(v) {
        var key = osKey(v.specs ? v.specs.so : (v.os || v.so));
        var info = osInfo(key);
        return {
            id: v.id != null ? v.id : v.vmid,
            vmid: v.vmid != null ? v.vmid : v.id,
            name: v.name || 'Mi Máquina',
            os: key, osLabel: info.label,
            rate: v.credits_for_minutes != null ? v.credits_for_minutes : info.rate,
            status: v.status || 'Creado',
            running: /run/i.test(v.status || ''),
            slices: (v.specs && v.specs.cpu) || v.slices || 1,
            specs: v.specs || { cpu: 1, memory: 1024, storage: 40, so: key }
        };
    }

    // ── REST adapter ─────────────────────────────────────────────────────
    function req(method, path, body) {
        var opts = { method: method, headers: { 'Authorization': 'Bearer ' + token() } };
        if (body !== undefined) { opts.headers['Content-Type'] = 'application/json'; opts.body = JSON.stringify(body); }
        return fetch(api() + path, opts).then(function (r) {
            return r.text().then(function (txt) {
                var data; try { data = txt ? JSON.parse(txt) : {}; } catch (e) { data = { detail: txt }; }
                return { ok: r.ok, status: r.status, data: data };
            });
        });
    }

    function loadMachines() {
        return req('GET', '/vms/me').then(function (res) {
            if (res.ok && Array.isArray(res.data)) {
                demoMode = false;
                return res.data.map(normalize);
            }
            throw new Error('unavailable');
        }).catch(function () {
            demoMode = true;
            return DEMO();
        });
    }

    function loadCredits() {
        // Prefer an explicit credits claim; else the (real) COFP balance is a
        // different currency, so fall back to a demo Cr balance for the clone.
        try {
            var c = A.claims ? A.claims() : null;
            var am = c && c.app_metadata;
            if (am && am.credits != null) { credits = Number(am.credits); return Promise.resolve(); }
        } catch (e) {}
        return req('GET', '/vms/credits').then(function (res) {
            if (res.ok && res.data && res.data.credits != null) credits = Number(res.data.credits);
            else { credits = 1000000; demoMode = true; }
        }).catch(function () { credits = 1000000; demoMode = true; });
    }

    // ── Render: header ───────────────────────────────────────────────────
    function renderHeader() {
        $('acctType').textContent = tierLabel();
        var cEl = $('acctCredits');
        cEl.textContent = fmt(credits);
        cEl.classList.toggle('neg', credits < 0);
        $('demoChip').style.display = demoMode ? 'block' : 'none';
    }

    // ── Render: card grid (Básico) ───────────────────────────────────────
    function cardHTML(m) {
        var info = osInfo(m.os);
        return '' +
        '<div class="card vm" data-id="' + esc(m.id) + '" data-running="' + m.running + '">' +
            '<span class="runbadge"></span>' +
            '<button class="cardmenu" title="Opciones"><span></span><span></span><span></span></button>' +
            '<div>' +
              '<input class="name" value="' + esc(m.name) + '" spellcheck="false">' +
              '<div class="status">' + esc(m.status) + '</div>' +
            '</div>' +
            '<button class="osicon" title="Abrir en el navegador">' +
              '<img src="' + OS_DIR + info.icon + '" alt="' + esc(info.label) + '">' +
            '</button>' +
            '<div class="footer"><span class="osname">' + esc(m.osLabel) + '</span>' +
              '<span class="rate">' + fmt(m.rate) + ' Cr/min</span></div>' +
        '</div>';
    }

    function renderGrid() {
        var grid = $('grid');
        var q = ($('search').value || '').trim().toLowerCase();
        var list = q ? machines.filter(function (m) {
            return (m.name + ' ' + m.osLabel).toLowerCase().indexOf(q) !== -1;
        }) : machines;

        var html = '<button class="card newtile" id="newTile" title="Nueva Máquina">' +
                   '<img src="/assets/machines/New_Machine_Button.png" alt="Nueva Máquina"></button>';
        html += list.map(cardHTML).join('');
        if (!list.length && q) html += '<div class="empty">No hay máquinas que coincidan con “' + esc(q) + '”.</div>';
        grid.innerHTML = html;
    }

    // ── Render: advanced table (Avanzado) ────────────────────────────────
    function renderAdvanced() {
        var body = $('advBody');
        body.innerHTML = machines.map(function (m) {
            return '' +
            '<tr data-id="' + esc(m.id) + '">' +
              '<td class="check"><input type="checkbox"></td>' +
              '<td><input class="tname" value="' + esc(m.name) + '" spellcheck="false"></td>' +
              '<td><div class="stepper"><button class="dec">–</button><span class="qty">1</span><button class="inc">+</button></div></td>' +
              '<td class="os">' + esc(m.osLabel) + '</td>' +
              '<td>' + esc(m.slices) + '</td>' +
              '<td>Medio</td><td>Redondo</td><td>Suave</td>' +
            '</tr>';
        }).join('');
    }

    function esc(s) {
        return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
        });
    }

    function renderAll() { renderHeader(); renderGrid(); renderAdvanced(); }

    // ── Launch: the REAL, working streaming broker ───────────────────────
    function launch(m) {
        if (!api() || !token()) { toast('Sesión no válida.'); return; }
        toast('Preparando “' + m.name + '” en el navegador…');
        req('POST', '/stream/session').then(function (res) {
            if (res.ok && res.data && res.data.session_id) {
                res.data.vm_name = res.data.vm_name || m.name;
                sessionStorage.setItem('cp_stream_session', JSON.stringify(res.data));
                location.href = '/stream.html';
            } else if (res.status === 403) {
                toast('El acceso por navegador requiere el Paquete Grande.');
            } else {
                toast((res.data && res.data.detail) || 'No se pudo iniciar la sesión.');
            }
        }).catch(function () { toast('No se pudo conectar al servidor. (' + api() + ')'); });
    }

    // ── VM actions (real endpoint, demo fallback) ────────────────────────
    // `demoLocal` mutates local state so the clone behaves when the backend
    // route is absent; `okMsg`/`path`/`method` drive the real call.
    function action(m, cfg) {
        if (demoMode || String(m.id).indexOf('demo-') === 0) {
            cfg.demoLocal && cfg.demoLocal();
            renderAll(); toast(cfg.okMsg + ' (demo)');
            return Promise.resolve(true);
        }
        return req(cfg.method, cfg.path, cfg.body).then(function (res) {
            if (res.ok) {
                cfg.onOk && cfg.onOk(res.data);
                return loadMachines().then(function (list) { machines = list; renderAll(); toast(cfg.okMsg); return true; });
            }
            if (res.status === 404) { toast('Acción no disponible aún en este backend.'); return false; }
            toast((res.data && res.data.detail) || 'La acción falló.'); return false;
        }).catch(function () { toast('No se pudo conectar al servidor.'); return false; });
    }

    function startVM(m) { return action(m, { method: 'POST', path: '/vms/' + m.id + '/start', okMsg: 'Máquina iniciada',
        demoLocal: function () { m.running = true; m.status = 'running'; } }); }
    function stopVM(m) { return action(m, { method: 'POST', path: '/vms/' + m.id + '/stop', okMsg: 'Máquina detenida',
        demoLocal: function () { m.running = false; m.status = 'stopped'; } }); }
    function shutdownVM(m) { return action(m, { method: 'POST', path: '/vms/' + m.id + '/shutdown', okMsg: 'Máquina apagada',
        demoLocal: function () { m.running = false; m.status = 'stopped'; } }); }
    function rebootVM(m) { return action(m, { method: 'POST', path: '/vms/' + m.id + '/reboot', okMsg: 'Máquina reiniciada',
        demoLocal: function () { m.running = true; m.status = 'running'; } }); }
    function snapshotVM(m) { return action(m, { method: 'POST',
        path: '/snapshots/Snapshot/create?vm_id=' + encodeURIComponent(m.id) + '&description=' + encodeURIComponent('Snapshot desde el panel'),
        okMsg: 'Snapshot creado' }); }
    function cloneVM(m) { return action(m, { method: 'POST', path: '/vms/clone/' + m.id, okMsg: 'Máquina duplicada',
        demoLocal: function () {
            var c = JSON.parse(JSON.stringify(m)); c.id = 'demo-' + Math.random().toString(36).slice(2, 8);
            c.name = m.name + ' (copia)'; c.running = false; c.status = 'Creado'; machines.push(c);
        } }); }
    function deleteVM(m) { return action(m, { method: 'DELETE', path: '/vms/' + m.id, okMsg: 'Máquina eliminada',
        demoLocal: function () { machines = machines.filter(function (x) { return x.id !== m.id; }); } }); }

    // ── Context menu ─────────────────────────────────────────────────────
    function openCtx(m) {
        currentVm = m;
        $('ctxKeepOn').checked = !!m.running;
        $('ctxMenu').classList.add('open');
    }
    function closeCtx() { $('ctxMenu').classList.remove('open'); currentVm = null; }

    function wireCtx() {
        $('ctxKeepOn').addEventListener('change', function () {
            if (!currentVm) return;
            (this.checked ? startVM : shutdownVM)(currentVm);
        });
        $('ctxStart').addEventListener('click', function () { currentVm && startVM(currentVm); closeCtx(); });
        $('ctxStop').addEventListener('click', function () { currentVm && stopVM(currentVm); closeCtx(); });
        $('ctxReboot').addEventListener('click', function () { currentVm && rebootVM(currentVm); closeCtx(); });
        $('ctxClone').addEventListener('click', function () {
            if (!currentVm) return;
            if (credits <= 0 && !demoMode) { toast('Saldo insuficiente para duplicar.'); return; }
            cloneVM(currentVm); closeCtx();
        });
        $('ctxSnap').addEventListener('click', function () { currentVm && snapshotVM(currentVm); closeCtx(); });
        $('ctxEdit').addEventListener('click', function () {
            var m = currentVm; closeCtx();
            var card = m && document.querySelector('.card.vm[data-id="' + cssEsc(m.id) + '"] .name');
            if (card) { card.focus(); card.select(); toast('Renombra la máquina y presiona Enter.'); }
        });
        $('ctxDelete').addEventListener('click', function () {
            if (!currentVm) return;
            if (confirm('¿Seguro que deseas eliminar “' + currentVm.name + '”?')) deleteVM(currentVm);
            closeCtx();
        });
        $('ctxMenu').addEventListener('click', function (e) { if (e.target === this) closeCtx(); });
    }
    function cssEsc(s) { return String(s).replace(/["\\]/g, '\\$&'); }

    // ── OS picker (new machine) ──────────────────────────────────────────
    var pickOs = null;
    function openPicker() {
        if (!isBig()) { toast('Crear máquinas requiere el Paquete Grande.'); return; }
        if (credits <= 0 && !demoMode) { toast('Saldo insuficiente para crear una máquina.'); return; }
        pickOs = null;
        var host = $('oses');
        host.innerHTML = Object.keys(OS).map(function (k) {
            var o = OS[k];
            return '<div class="os" data-os="' + k + '"><img src="' + OS_DIR + o.icon + '" alt="' + esc(o.label) + '">' +
                   '<span class="n">' + esc(o.label) + '</span><span class="c">' + o.rate + ' Cr/min</span></div>';
        }).join('');
        $('osCreate').disabled = true;
        $('osPicker').classList.add('open');
    }
    function closePicker() { $('osPicker').classList.remove('open'); }

    function wirePicker() {
        $('oses').addEventListener('click', function (e) {
            var el = e.target.closest('.os'); if (!el) return;
            Array.prototype.forEach.call(this.querySelectorAll('.os'), function (o) { o.classList.remove('sel'); });
            el.classList.add('sel'); pickOs = el.getAttribute('data-os'); $('osCreate').disabled = false;
        });
        $('osCancel').addEventListener('click', closePicker);
        $('osPicker').addEventListener('click', function (e) { if (e.target === this) closePicker(); });
        $('osCreate').addEventListener('click', function () {
            if (!pickOs) return;
            var info = osInfo(pickOs);
            var specs = { so: pickOs, cpu: 2, memory: 2048, storage: 40, name: 'Mi Máquina' };
            closePicker();
            if (demoMode) {
                machines.push({
                    id: 'demo-' + Math.random().toString(36).slice(2, 8), vmid: 100 + Math.floor(Math.random() * 900),
                    name: 'Mi Máquina', os: pickOs, osLabel: info.label, rate: info.rate,
                    status: 'Creado', running: false, slices: 2, specs: specs
                });
                renderAll(); toast('Máquina creada (demo)');
                return;
            }
            toast('Creando máquina…');
            req('POST', '/vms/clone-with-specs', specs).then(function (res) {
                if (res.ok) { loadMachines().then(function (l) { machines = l; renderAll(); toast('Máquina creada'); }); }
                else if (res.status === 404) toast('Creación no disponible aún en este backend.');
                else toast((res.data && res.data.detail) || 'No se pudo crear la máquina.');
            }).catch(function () { toast('No se pudo conectar al servidor.'); });
        });
    }

    // ── Grid / table event delegation ────────────────────────────────────
    function wireGrid() {
        $('grid').addEventListener('click', function (e) {
            if (e.target.closest('#newTile')) { openPicker(); return; }
            var card = e.target.closest('.card.vm'); if (!card) return;
            var m = byId(card.getAttribute('data-id')); if (!m) return;
            if (e.target.closest('.cardmenu')) { openCtx(m); return; }
            if (e.target.closest('.osicon')) { launch(m); return; }
        });
        // Rename commit
        $('grid').addEventListener('keydown', function (e) {
            if (e.key === 'Enter' && e.target.classList.contains('name')) {
                e.preventDefault(); e.target.blur();
                var card = e.target.closest('.card.vm'); var m = byId(card.getAttribute('data-id'));
                if (m) { m.name = e.target.value.trim() || m.name; renderAdvanced(); toast('Nombre actualizado.'); }
            }
        });
        // Advanced steppers
        $('advBody').addEventListener('click', function (e) {
            var row = e.target.closest('tr'); if (!row) return;
            var qty = row.querySelector('.qty'); if (!qty) return;
            var n = parseInt(qty.textContent, 10) || 1;
            if (e.target.classList.contains('inc')) qty.textContent = Math.min(256, n + 1);
            if (e.target.classList.contains('dec')) qty.textContent = Math.max(1, n - 1);
        });
    }
    function byId(id) { return machines.filter(function (m) { return String(m.id) === String(id); })[0]; }

    // ── Toolbar / nav ────────────────────────────────────────────────────
    function wireToolbar() {
        $('advToggle').addEventListener('change', function () {
            advanced = this.checked;
            $('grid').style.display = advanced ? 'none' : 'grid';
            $('advanced').style.display = advanced ? 'block' : 'none';
        });
        $('search').addEventListener('input', renderGrid);
        $('btnReload').addEventListener('click', refresh);
        $('btnHelp').addEventListener('click', function () { toast('Soporte: soporte@coffeepie.co'); });
        $('btnNav').addEventListener('click', function () { $('navMenu').classList.add('open'); });
        $('navMenu').addEventListener('click', function (e) { if (e.target === this) this.classList.remove('open'); });
        $('navReload').addEventListener('click', function (e) { e.preventDefault(); $('navMenu').classList.remove('open'); refresh(); });
        $('navLogout').addEventListener('click', function (e) {
            e.preventDefault(); if (A.logout) A.logout(); location.href = '/';
        });
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') { closeCtx(); closePicker(); $('navMenu').classList.remove('open'); }
        });
    }

    function refresh() {
        return Promise.all([loadMachines(), loadCredits()]).then(function (r) {
            machines = r[0]; renderAll();
        });
    }

    // ── Boot ─────────────────────────────────────────────────────────────
    function boot() {
        if (!A.valid || !A.valid()) {
            sessionStorage.setItem('cp_post_login', '/machines.html');
            location.replace('/panel');   // /panel gate bounces to login
            return;
        }
        wireCtx(); wirePicker(); wireGrid(); wireToolbar();

        if (!isBig()) {
            renderHeader();
            $('gate').style.display = 'block';
            document.querySelector('.toolbar').style.display = 'none';
            $('grid').style.display = 'none';
            return;
        }
        refresh();
    }

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
    else boot();
})();
