// Coffee Pie — "Mis Máquinas" (machines.html) behaviour.
// VanillaJS clone of the QML frontend (Home_Screen / StackViewBasic2 /
// Basic_OS_Selection / Basic_Machine_Properties_Selection / Contextual_Menu /
// StackViewAdvanced). Big_Package tier only.
//
// Real backend contract (panel_backend app/api/vms_routes.py):
//   POST   {api}/vms                      → create (status 'creating', async provision)
//   GET    {api}/vms/me                   → my machines
//   POST   {api}/vms/{id}/start|stop|shutdown|reboot
//   PATCH  {api}/vms/{id}/specs           → resize Slices (machine must be off)
//   DELETE {api}/vms/{id}
//   POST   {api}/stream/session?vm_id=    → stream MY machine (noVNC handoff)
// If /vms/* is unreachable the page falls back to a clearly-labelled demo
// dataset so look & behaviour stay exercisable; streaming stays real.
(function () {
    'use strict';

    // ── QFDM catalog ─────────────────────────────────────────────────────
    // 1 Slice ("Porción") = 1 vCore + 1 GiB RAM. Uniform base rate per Slice;
    // each OS has a MINIMUM Slice count — that's why the selector shows
    // "Desde N Cr/min" (N = minSlices × rate). Per-slice recurrence prices
    // follow the QML: minute 30 Cr, month 500'000 Cr, year 6'000'000 Cr.
    var RATE = 30;
    var REC_PRICES = { minute: 30, month: 500000, year: 6000000 };
    var REC_UNITS = { minute: 'Cr/min', month: 'Cr/mes', year: 'Cr/año' };
    var OS = {
        win11:   { label: 'Windows 11',          icon: 'W11_Icon.png',         min: 6 },
        win10:   { label: 'Windows 10',          icon: 'W10_Icon.png',         min: 4 },
        steamos: { label: 'Steam OS',            icon: 'Steam_OS_Icon.png',    min: 4 },
        mint:    { label: 'Linux Mint',          icon: 'Linux_Mint_Icon.png',  min: 2 },
        bodhi:   { label: 'Bodhi Linux',         icon: 'Bodhi_Linux_Icon.png', min: 1 },
        docker:  { label: 'Ubuntu Server Docker', icon: 'Docker_OS_Icon.png',  min: 1 },
        // present for existing machines, not offered in the selector
        debian:  { label: 'Debian',    icon: 'Debian_Icon.png',  min: 1, hidden: true },
        arch:    { label: 'Arch Linux', icon: 'Manjaro_Icon.png', min: 1, hidden: true },
        centos:  { label: 'CentOS',    icon: 'Cent_OS_Icon.png', min: 1, hidden: true }
    };
    var OS_DIR = '/assets/machines/os/';
    // Per-Slice physical mapping (from the reference: 4 Slices = 4 Wh, 4
    // cores, 4 GB RAM, 32 GB SSD, 500 GB HDD, 500 MB VRAM, 32 Mbps, 12 MPX/s)
    var PER_SLICE = { wh: 1, cores: 1, ramGb: 1, ssdGb: 8, hddGb: 125, vramMb: 125, mbps: 8, mpxs: 3 };

    var STATE_LABEL = {
        creating: 'Creando...', created: 'Creado', running: 'Corriendo',
        stopped: 'Detenida', error: 'Error'
    };

    function osKey(raw) {
        var s = String(raw || '').toLowerCase();
        if (/win.*11|windows 11/.test(s)) return 'win11';
        if (/win.*10|windows 10|win/.test(s)) return 'win10';
        if (/steam/.test(s)) return 'steamos';
        if (/bodhi/.test(s)) return 'bodhi';
        if (/mint/.test(s)) return 'mint';
        if (/docker|ubuntu/.test(s)) return 'docker';
        if (/debian/.test(s)) return 'debian';
        if (/arch|manjaro/.test(s)) return 'arch';
        if (/cent/.test(s)) return 'centos';
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
        clearTimeout(toastT); toastT = setTimeout(function () { el.classList.remove('show'); }, 3600);
    }
    function notify(msg) {
        toast(msg);
        try {
            if (window.Notification && Notification.permission === 'granted') {
                new Notification('Coffee Pie', { body: msg, icon: '/assets/machines/Coffee_Pie_Logo.png' });
            }
        } catch (e) { /* toast already shown */ }
    }
    function esc(s) {
        return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
        });
    }
    function cssEsc(s) { return String(s).replace(/["\\]/g, '\\$&'); }

    // ── State ────────────────────────────────────────────────────────────
    var machines = [];
    var credits = 0;
    var machinesDemo = false;   // /vms/* unreachable → demo dataset
    var currentVm = null;       // machine bound to the open context menu
    var pollTimer = null;

    // create-flow state
    var chosenOs = null;
    var chosenRec = 'minute';

    function DEMO() {
        return [
            mk('Mi Máquina Personal', 'win10', 8), mk('Mi Workstation', 'win11', 16),
            mk('Production DB', 'debian', 2), mk('Mint', 'mint', 4), mk('Arch Pentesting', 'arch', 1)
        ];
        function mk(name, key, slices) {
            return {
                id: 'demo-' + Math.random().toString(36).slice(2, 8),
                vmid: 100 + Math.floor(Math.random() * 900),
                name: name, os: key, osLabel: osInfo(key).label, rate: slices * RATE,
                state: 'created', slices: slices, recurrence: 'minute'
            };
        }
    }

    function normalize(v) {
        var key = osKey(v.os || (v.specs ? v.specs.so : ''));
        var st = String(v.status || 'created').toLowerCase();
        if (!STATE_LABEL[st]) st = /run/.test(st) ? 'running' : 'created';
        return {
            id: v.id != null ? v.id : v.vmid,
            vmid: v.vmid,
            name: v.name || 'Mi Máquina',
            os: key, osLabel: osInfo(key).label,
            rate: v.credits_for_minutes != null ? v.credits_for_minutes : (v.slices || 1) * RATE,
            state: st, error: v.error_detail || null,
            slices: v.slices || (v.specs && v.specs.cpu) || 1,
            recurrence: v.recurrence || 'minute',
            node: v.node || null
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
                machinesDemo = false;
                return res.data.map(normalize);
            }
            throw new Error('unavailable');
        }).catch(function () {
            machinesDemo = true;
            return machines.length && machines[0] && String(machines[0].id).indexOf('demo-') === 0
                ? machines : DEMO();
        });
    }

    function loadCredits() {
        try {
            var c = A.claims ? A.claims() : null;
            var am = c && c.app_metadata;
            if (am && am.credits != null) { credits = Number(am.credits); return Promise.resolve(); }
        } catch (e) { /* fall through */ }
        credits = 1000000;      // display placeholder until the Cr wallet endpoint lands
        return Promise.resolve();
    }

    // ── Views ────────────────────────────────────────────────────────────
    function showView(name) {
        ['viewHome', 'viewOS', 'viewSlices'].forEach(function (v) {
            $(v).classList.toggle('active', v === 'view' + name);
        });
        window.scrollTo(0, 0);
    }

    // ── Render: header ───────────────────────────────────────────────────
    function renderHeader() {
        $('acctType').textContent = tierLabel();
        var cEl = $('acctCredits');
        cEl.textContent = fmt(credits);
        cEl.classList.toggle('neg', credits < 0);
        $('demoChip').style.display = machinesDemo ? 'block' : 'none';
    }

    // ── Render: card grid (Básico) ───────────────────────────────────────
    function cardHTML(m) {
        var info = osInfo(m.os);
        var label = m.state === 'error' && m.error ? 'Error' : (STATE_LABEL[m.state] || m.state);
        return '' +
        '<div class="card vm" data-id="' + esc(m.id) + '" data-state="' + esc(m.state) + '">' +
            '<span class="runbadge"></span>' +
            '<button class="cardmenu" title="Opciones"><span></span><span></span><span></span></button>' +
            '<div>' +
              '<input class="name" value="' + esc(m.name) + '" spellcheck="false">' +
              '<div class="status" title="' + esc(m.error || '') + '">' + esc(label) + '</div>' +
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

    function renderAll() { renderHeader(); renderGrid(); renderAdvanced(); }

    // ── Creation-status polling → "Creando..." → notification ───────────
    function pollCreating() {
        if (pollTimer) return;
        pollTimer = setInterval(function () {
            var pending = machines.some(function (m) { return m.state === 'creating'; });
            if (!pending) { clearInterval(pollTimer); pollTimer = null; return; }
            var before = {};
            machines.forEach(function (m) { before[m.id] = m.state; });
            loadMachines().then(function (list) {
                machines = list; renderAll();
                machines.forEach(function (m) {
                    if (before[m.id] === 'creating' && m.state === 'created') {
                        notify('La máquina ha sido creada, ya puedes empezar a usarla');
                    }
                    if (before[m.id] === 'creating' && m.state === 'error') {
                        toast(m.error || 'La creación de la máquina falló.');
                    }
                });
                if (!machines.some(function (m) { return m.state === 'creating'; })) {
                    clearInterval(pollTimer); pollTimer = null;
                }
            });
        }, 3000);
    }

    // ── View: OS selection ───────────────────────────────────────────────
    function renderOsCards() {
        $('osCards').innerHTML = Object.keys(OS).filter(function (k) { return !OS[k].hidden; })
            .map(function (k) {
                var o = OS[k];
                return '<button class="oscard" data-os="' + k + '">' +
                    '<span class="t">' + esc(o.label) + '</span>' +
                    '<span class="plaque"><img src="' + OS_DIR + o.icon + '" alt="' + esc(o.label) + '"></span>' +
                    '<span class="price">Desde ' + fmt(o.min * RATE) + ' Cr/min</span>' +
                '</button>';
            }).join('');
    }

    // ── View: recurrence + slices ────────────────────────────────────────
    function sliceCount() { return parseInt($('sliceRange').value, 10) || 1; }

    function renderSliceInfo() {
        var n = sliceCount();
        var recTotal = n * REC_PRICES[chosenRec];
        var head = n + (n === 1 ? ' Porción te costará: ' : ' Porciones te costarán: ') +
                   fmt(recTotal) + ' ' + REC_UNITS[chosenRec];
        $('specList').innerHTML =
            '<div class="head">' + esc(head) + '</div>' +
            (n * PER_SLICE.wh) + ' Wh Consumo Eléctrico<br>' +
            (n * PER_SLICE.cores) + ' Núcleos Lógicos<br>' +
            (n * PER_SLICE.ramGb) + ' GB RAM<br>' +
            (n * PER_SLICE.ssdGb) + ' GB SSD<br>' +
            (n * PER_SLICE.hddGb) + ' GB HDD<br>' +
            (n * PER_SLICE.vramMb) + ' MB VRAM<br>' +
            (n * PER_SLICE.mbps) + ' Mbps Ancho de Banda<br>' +
            (n * PER_SLICE.mpxs) + ' MPX/s Resolución/Tasa Refresco';
    }

    function openSlices(osK) {
        chosenOs = osK;
        chosenRec = 'minute';
        var o = osInfo(osK);
        $('chosenOsIcon').src = OS_DIR + o.icon;
        var r = $('sliceRange');
        r.min = o.min; r.value = o.min;
        Array.prototype.forEach.call(document.querySelectorAll('.recbox'), function (b) {
            b.classList.toggle('sel', b.getAttribute('data-rec') === 'minute');
        });
        renderSliceInfo();
        showView('Slices');
    }

    function createMachine() {
        var n = sliceCount();
        var btn = $('btnContinuar');
        if (window.Notification && Notification.permission === 'default') {
            try { Notification.requestPermission(); } catch (e) { /* toast fallback */ }
        }
        if (machinesDemo) {
            machines.push({
                id: 'demo-' + Math.random().toString(36).slice(2, 8), vmid: null,
                name: 'Mi Máquina', os: chosenOs, osLabel: osInfo(chosenOs).label,
                rate: n * RATE, state: 'creating', slices: n, recurrence: chosenRec
            });
            renderAll(); showView('Home');
            var demoId = machines[machines.length - 1].id;
            setTimeout(function () {
                var m = byId(demoId);
                if (m) { m.state = 'created'; renderAll(); notify('La máquina ha sido creada, ya puedes empezar a usarla'); }
            }, 5000);
            return;
        }
        btn.disabled = true;
        req('POST', '/vms', { name: 'Mi Máquina', os: chosenOs, slices: n, recurrence: chosenRec })
            .then(function (res) {
                btn.disabled = false;
                if (res.ok && res.data && res.data.id) {
                    machines.push(normalize(res.data));
                    renderAll(); showView('Home');
                    toast('Creando tu máquina en el nodo más cercano…');
                    pollCreating();
                } else if (res.status === 403) {
                    toast((res.data && res.data.detail) || 'Requiere el Paquete Grande.');
                } else {
                    toast((res.data && res.data.detail) || 'No se pudo crear la máquina.');
                }
            })
            .catch(function () { btn.disabled = false; toast('No se pudo conectar al servidor. (' + api() + ')'); });
    }

    // ── Launch: stream MY machine ────────────────────────────────────────
    function launch(m) {
        if (m.state === 'creating') { toast('La máquina aún se está creando…'); return; }
        if (m.state === 'error') { toast(m.error || 'Esta máquina tuvo un error al crearse.'); return; }
        if (!api() || !token()) { toast('Sesión no válida.'); return; }
        toast('Preparando “' + m.name + '” en el navegador…');
        var q = String(m.id).indexOf('demo-') === 0 ? '' : ('?vm_id=' + encodeURIComponent(m.id));
        req('POST', '/stream/session' + q).then(function (res) {
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
    function action(m, cfg) {
        if (machinesDemo || String(m.id).indexOf('demo-') === 0) {
            cfg.demoLocal && cfg.demoLocal();
            renderAll(); toast(cfg.okMsg + ' (demo)');
            return Promise.resolve(true);
        }
        return req(cfg.method, cfg.path, cfg.body).then(function (res) {
            if (res.ok || res.status === 204) {
                return loadMachines().then(function (list) { machines = list; renderAll(); toast(cfg.okMsg); return true; });
            }
            toast((res.data && res.data.detail) || 'La acción falló.'); return false;
        }).catch(function () { toast('No se pudo conectar al servidor.'); return false; });
    }

    function startVM(m) { return action(m, { method: 'POST', path: '/vms/' + m.id + '/start', okMsg: 'Máquina iniciada',
        demoLocal: function () { m.state = 'running'; } }); }
    function stopVM(m) { return action(m, { method: 'POST', path: '/vms/' + m.id + '/stop', okMsg: 'Máquina detenida',
        demoLocal: function () { m.state = 'stopped'; } }); }
    function shutdownVM(m) { return action(m, { method: 'POST', path: '/vms/' + m.id + '/shutdown', okMsg: 'Máquina apagada',
        demoLocal: function () { m.state = 'stopped'; } }); }
    function rebootVM(m) { return action(m, { method: 'POST', path: '/vms/' + m.id + '/reboot', okMsg: 'Máquina reiniciada',
        demoLocal: function () { m.state = 'running'; } }); }
    function deleteVM(m) { return action(m, { method: 'DELETE', path: '/vms/' + m.id, okMsg: 'Máquina eliminada',
        demoLocal: function () { machines = machines.filter(function (x) { return x.id !== m.id; }); } }); }
    function cloneVM(m) {
        // Duplicating = creating a sibling with the same OS/slices/recurrence.
        if (machinesDemo || String(m.id).indexOf('demo-') === 0) {
            var c = JSON.parse(JSON.stringify(m)); c.id = 'demo-' + Math.random().toString(36).slice(2, 8);
            c.name = m.name + ' (copia)'; c.state = 'created'; machines.push(c);
            renderAll(); toast('Máquina duplicada (demo)');
            return Promise.resolve(true);
        }
        return req('POST', '/vms', { name: m.name + ' (copia)', os: m.os, slices: m.slices, recurrence: m.recurrence })
            .then(function (res) {
                if (res.ok && res.data && res.data.id) {
                    machines.push(normalize(res.data)); renderAll();
                    toast('Duplicando la máquina…'); pollCreating(); return true;
                }
                toast((res.data && res.data.detail) || 'No se pudo duplicar.'); return false;
            });
    }

    // ── Context menu ─────────────────────────────────────────────────────
    function openCtx(m) {
        currentVm = m;
        $('ctxKeepOn').checked = m.state === 'running';
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
            if (credits <= 0 && !machinesDemo) { toast('Saldo insuficiente para duplicar.'); return; }
            cloneVM(currentVm); closeCtx();
        });
        $('ctxSnap').addEventListener('click', function () {
            closeCtx(); toast('Snapshots estarán disponibles próximamente.');
        });
        $('ctxEdit').addEventListener('click', function () {
            var m = currentVm; closeCtx();
            if (m) openResize(m);
        });
        $('ctxDelete').addEventListener('click', function () {
            if (!currentVm) return;
            if (confirm('¿Seguro que deseas eliminar “' + currentVm.name + '”?')) deleteVM(currentVm);
            closeCtx();
        });
        $('ctxMenu').addEventListener('click', function (e) { if (e.target === this) closeCtx(); });
    }

    // ── Resize ("descargar RAM") ─────────────────────────────────────────
    var resizeVmRef = null;
    function renderRzInfo() {
        var n = parseInt($('rzRange').value, 10) || 1;
        $('rzInfo').innerHTML = n + (n === 1 ? ' Porción' : ' Porciones') + ' → ' +
            n + ' Núcleos · ' + n + ' GB RAM · ' + fmt(n * RATE) + ' Cr/min';
    }
    function openResize(m) {
        if (m.state === 'running') {
            toast('Apaga la máquina para modificar sus Porciones (el hardware virtual solo cambia en frío).');
            return;
        }
        if (m.state === 'creating') { toast('La máquina aún se está creando…'); return; }
        resizeVmRef = m;
        var r = $('rzRange');
        r.min = osInfo(m.os).min; r.value = m.slices;
        renderRzInfo();
        $('resizeModal').classList.add('open');
    }
    function closeResize() { $('resizeModal').classList.remove('open'); resizeVmRef = null; }

    function wireResize() {
        $('rzRange').addEventListener('input', renderRzInfo);
        $('rzDec').addEventListener('click', function () { var r = $('rzRange'); r.value = Math.max(+r.min, +r.value - 1); renderRzInfo(); });
        $('rzInc').addEventListener('click', function () { var r = $('rzRange'); r.value = Math.min(+r.max, +r.value + 1); renderRzInfo(); });
        $('rzCancel').addEventListener('click', closeResize);
        $('resizeModal').addEventListener('click', function (e) { if (e.target === this) closeResize(); });
        $('rzSave').addEventListener('click', function () {
            if (!resizeVmRef) return;
            var m = resizeVmRef, n = parseInt($('rzRange').value, 10) || 1;
            closeResize();
            if (machinesDemo || String(m.id).indexOf('demo-') === 0) {
                m.slices = n; m.rate = n * RATE; renderAll(); toast('Porciones actualizadas (demo)');
                return;
            }
            toast('Aplicando ' + n + ' Porciones…');
            req('PATCH', '/vms/' + m.id + '/specs', { slices: n }).then(function (res) {
                if (res.ok) {
                    loadMachines().then(function (l) { machines = l; renderAll(); toast('Porciones actualizadas: ' + n); });
                } else {
                    toast((res.data && res.data.detail) || 'No se pudo redimensionar.');
                }
            }).catch(function () { toast('No se pudo conectar al servidor.'); });
        });
    }

    // ── Grid / table event delegation ────────────────────────────────────
    function byId(id) { return machines.filter(function (m) { return String(m.id) === String(id); })[0]; }

    function wireGrid() {
        $('grid').addEventListener('click', function (e) {
            if (e.target.closest('#newTile')) { showView('OS'); return; }
            var card = e.target.closest('.card.vm'); if (!card) return;
            var m = byId(card.getAttribute('data-id')); if (!m) return;
            if (e.target.closest('.cardmenu')) { openCtx(m); return; }
            if (e.target.closest('.osicon')) { launch(m); return; }
        });
        $('grid').addEventListener('keydown', function (e) {
            if (e.key === 'Enter' && e.target.classList.contains('name')) {
                e.preventDefault(); e.target.blur();
                var card = e.target.closest('.card.vm'); var m = byId(card.getAttribute('data-id'));
                if (m) { m.name = e.target.value.trim() || m.name; renderAdvanced(); toast('Nombre actualizado.'); }
            }
        });
        $('advBody').addEventListener('click', function (e) {
            var row = e.target.closest('tr'); if (!row) return;
            var qty = row.querySelector('.qty'); if (!qty) return;
            var n = parseInt(qty.textContent, 10) || 1;
            if (e.target.classList.contains('inc')) qty.textContent = Math.min(256, n + 1);
            if (e.target.classList.contains('dec')) qty.textContent = Math.max(1, n - 1);
        });
    }

    // ── Create-flow wiring ───────────────────────────────────────────────
    function wireCreateFlow() {
        $('osCards').addEventListener('click', function (e) {
            var c = e.target.closest('.oscard'); if (!c) return;
            openSlices(c.getAttribute('data-os'));
        });
        $('osBack').addEventListener('click', function () { showView('Home'); });
        $('slBack').addEventListener('click', function () { showView('OS'); });

        Array.prototype.forEach.call(document.querySelectorAll('.recbox'), function (b) {
            b.addEventListener('click', function () {
                chosenRec = b.getAttribute('data-rec');
                Array.prototype.forEach.call(document.querySelectorAll('.recbox'), function (x) {
                    x.classList.toggle('sel', x === b);
                });
                renderSliceInfo();
            });
        });
        $('sliceRange').addEventListener('input', renderSliceInfo);
        $('sliceDec').addEventListener('click', function () {
            var r = $('sliceRange'); r.value = Math.max(+r.min, +r.value - 1); renderSliceInfo();
        });
        $('sliceInc').addEventListener('click', function () {
            var r = $('sliceRange'); r.value = Math.min(+r.max, +r.value + 1); renderSliceInfo();
        });
        $('btnContinuar').addEventListener('click', createMachine);
    }

    // ── Recargar Saldo: pasarelas de pago + ads-for-credits ─────────────
    // The gateways are the paid top-up path; the honey button is the
    // watch-ads path (Coffee Pie's ad inventory — spaces sold to agencies
    // and ad platforms). Rewards here update the DISPLAYED balance only
    // until the Cr wallet endpoint lands (billing engine pending).
    var AD_SECONDS = 5;         // demo ad length (production standard: 30)
    var AD_REWARD = 500;
    var adTimer = null;

    function openPay() { $('payModal').classList.add('open'); }
    function closePay() { $('payModal').classList.remove('open'); }

    function openAds() {
        closePay();
        $('adsModal').classList.add('open');
        var n = AD_SECONDS;
        $('adCount').textContent = n;
        $('adClaim').disabled = true;
        $('adMsg').textContent = 'Mira el anuncio completo y gana Créditos gratis';
        clearInterval(adTimer);
        adTimer = setInterval(function () {
            n -= 1;
            $('adCount').textContent = n > 0 ? n : '✓';
            if (n <= 0) {
                clearInterval(adTimer); adTimer = null;
                $('adClaim').disabled = false;
                $('adMsg').textContent = '¡Anuncio completado!';
            }
        }, 1000);
    }
    function closeAds() {
        clearInterval(adTimer); adTimer = null;
        $('adsModal').classList.remove('open');
    }

    function wirePayAds() {
        // Triggers: Saldo label/value, and Recargar Saldo in the main menu.
        $('saldoRow').addEventListener('click', openPay);
        $('payClose').addEventListener('click', closePay);
        $('payModal').addEventListener('click', function (e) { if (e.target === this) closePay(); });
        $('payModal').addEventListener('click', function (e) {
            var gw = e.target.closest('.gw');
            if (gw) toast('Recargas con ' + gw.getAttribute('data-gw') + ' estarán disponibles próximamente.');
        });
        $('honeyBtn').addEventListener('click', openAds);
        $('adsClose').addEventListener('click', closeAds);
        $('adsModal').addEventListener('click', function (e) { if (e.target === this) closeAds(); });
        $('adClaim').addEventListener('click', function () {
            credits += AD_REWARD;
            renderHeader();
            closeAds();
            notify('+' + fmt(AD_REWARD) + ' Cr añadidos a tu Saldo');
        });
    }

    // ── Toolbar / nav ────────────────────────────────────────────────────
    function wireToolbar() {
        $('advToggle').addEventListener('change', function () {
            $('grid').style.display = this.checked ? 'none' : 'grid';
            $('advanced').style.display = this.checked ? 'block' : 'none';
        });
        $('search').addEventListener('input', renderGrid);
        $('btnReload').addEventListener('click', refresh);
        Array.prototype.forEach.call(document.querySelectorAll('#btnHelp, [data-help]'), function (b) {
            b.addEventListener('click', function () { toast('Soporte: soporte@coffeepie.co'); });
        });
        $('btnNav').addEventListener('click', function () { $('navMenu').classList.add('open'); });
        $('navMenu').addEventListener('click', function (e) { if (e.target === this) this.classList.remove('open'); });
        $('navClose').addEventListener('click', function () { $('navMenu').classList.remove('open'); });
        $('navRecharge').addEventListener('click', function () {
            $('navMenu').classList.remove('open'); openPay();
        });
        $('navAccount').addEventListener('click', function () { location.href = '/panel'; });
        $('navConfig').addEventListener('click', function () { location.href = '/panel'; });
        $('navSupport').addEventListener('click', function () { toast('Soporte: soporte@coffeepie.co'); });
        $('navLogout').addEventListener('click', function () {
            if (A.logout) A.logout(); location.href = '/';
        });
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') {
                closeCtx(); closeResize(); closePay(); closeAds();
                $('navMenu').classList.remove('open');
            }
        });
    }

    function refresh() {
        return Promise.all([loadMachines(), loadCredits()]).then(function (r) {
            machines = r[0]; renderAll();
            if (machines.some(function (m) { return m.state === 'creating'; })) pollCreating();
        });
    }

    // ── Boot ─────────────────────────────────────────────────────────────
    function boot() {
        if (!A.valid || !A.valid()) {
            sessionStorage.setItem('cp_post_login', '/machines.html');
            location.replace('/panel');
            return;
        }
        renderOsCards();
        wireCtx(); wireResize(); wireGrid(); wireCreateFlow(); wirePayAds(); wireToolbar();

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
