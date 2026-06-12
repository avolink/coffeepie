// Coffee Pie — Panel data binding (Proveedores tab: nodes).
// Replaces the client-side-only node table with real backend persistence:
//   • On load: GET /nodes → render the table from the database.
//   • "Guardar Nodo": POST /nodes → row persists (survives refresh).
//   • Edit (pencil): fills the modal from cache, PATCH /nodes/{id}.
//   • Delete: DELETE /nodes/{id}.
//   • Same-IP warning (non-blocking): typing an IP another node already uses
//     shows a hint — duplicates are legal (NAT'd domestic nodes) but usually
//     a typo for datacenter providers.
// Overrides the inline saveNode/deleteNode globals AFTER the inline script ran
// (functions resolve at click time), so the Wix export needs no surgery.
// Requires cp-panel-auth.js (token + API base). Vanilla JS only.
(function () {
    'use strict';

    function ready(fn) {
        if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', fn);
        else fn();
    }

    ready(function () {
        if (!window.cpPanelAuth || !/^\/panel\/?$/.test(location.pathname)) return;
        var API = window.cpPanelAuth.api;

        function authHeaders(json) {
            var h = { 'Authorization': 'Bearer ' + window.cpPanelAuth.token() };
            if (json) h['Content-Type'] = 'application/json';
            return h;
        }
        function toast(msg) {
            if (typeof window.showToast === 'function') window.showToast(msg);
            else console.log('[CP]', msg);
        }

        var HYPERVISOR_LABELS = { proxmox: 'Proxmox VE', esxi: 'VMware ESXi', hyperv: 'Hyper-V', xen: 'XenServer', kvm: 'KVM / libvirt' };

        function esc(s) {
            return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
                return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
            });
        }

        function rowHTML(n) {
            var ssdTB = (n.ssd_gb / 1000).toFixed(n.ssd_gb >= 1000 ? 1 : 0);
            var gpuGB = (n.gpu_vram_mb / 1000).toFixed(n.gpu_vram_mb >= 1000 ? 1 : 0);
            var hv = HYPERVISOR_LABELS[n.hypervisor] || n.hypervisor;
            var statusLabel = n.status === 'maintenance' ? 'En Mantenimiento' : (n.status === 'offline' ? 'Offline' : 'Activo');
            var statusClass = n.status === 'maintenance' ? 'maintenance' : (n.status === 'offline' ? 'offline' : 'active');
            return '' +
                '<td data-label="Nodo"><strong style="color:var(--cp-text);">' + esc(n.name) + '</strong>' +
                '<div style="font-size:11px;color:var(--cp-text-muted);margin-top:2px;">' + esc(n.location) + '</div></td>' +
                '<td data-label="IP Pública"><code style="background:rgba(255,255,255,0.05);padding:3px 8px;border-radius:4px;font-size:12px;">' + esc(n.public_ip) + '</code></td>' +
                '<td data-label="Recursos"><div style="font-size:12px;">' + n.vcores + ' vCores | ' + n.ram_gb + ' GB RAM</div>' +
                '<div style="font-size:12px;">' + ssdTB + ' TB SSD | ' + gpuGB + ' GB GPU</div></td>' +
                '<td data-label="Hipervisor"><span class="tag">' + esc(hv) + '</span></td>' +
                '<td data-label="Estado"><span class="node-status ' + statusClass + '">' + statusLabel + '</span></td>' +
                '<td data-label="Mantenimiento"><span class="node-maint none">—</span></td>' +
                '<td data-label="Acciones"><div style="display:flex;gap:6px;">' +
                '<button class="node-action-btn edit" onclick="editNode(\'' + esc(n.id) + '\')" title="Editar">' +
                '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>' +
                '</button>' +
                '<button class="node-action-btn delete" onclick="deleteNode(\'' + esc(n.id) + '\')" title="Eliminar">' +
                '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>' +
                '</button></div></td>';
        }

        var nodeCache = {};   // id → node, source of truth for the edit modal

        function renderNodes(nodes) {
            nodeCache = {};
            nodes.forEach(function (n) { nodeCache[n.id] = n; });
            var tbody = document.getElementById('nodesTableBody');
            if (!tbody) return;
            tbody.innerHTML = '';
            nodes.forEach(function (n) {
                var tr = document.createElement('tr');
                tr.setAttribute('data-node-id', n.id);
                tr.innerHTML = rowHTML(n);
                tbody.appendChild(tr);
            });
            if (typeof window.updateProviderStats === 'function') window.updateProviderStats();
            if (typeof window.populateMaintenanceSelect === 'function') window.populateMaintenanceSelect();
        }

        function loadNodes() {
            fetch(API + '/nodes', { headers: authHeaders(false) })
                .then(function (r) {
                    if (r.status === 403) return [];           // not a provider → empty table
                    if (!r.ok) throw new Error('HTTP ' + r.status);
                    return r.json();
                })
                .then(renderNodes)
                .catch(function (e) { toast('No se pudieron cargar los nodos (' + e.message + ')'); });
        }

        // ── Same-IP hint under the IP field (non-blocking: NAT'd domestic
        // nodes legitimately share a public IP, but for a datacenter it's
        // almost always a typo — exactly how N104 got N103's IP) ──────────
        function ipWarningEl() {
            var el = document.getElementById('cpIpDupWarning');
            if (!el) {
                var input = document.getElementById('modalNodeIP');
                if (!input) return null;
                el = document.createElement('div');
                el.id = 'cpIpDupWarning';
                el.style.cssText = 'display:none;font-size:12px;color:var(--cp-warning,#ffb400);margin-top:6px;';
                input.parentNode.appendChild(el);
            }
            return el;
        }
        function checkDupIP() {
            var el = ipWarningEl();
            if (!el) return;
            var ip = document.getElementById('modalNodeIP').value.trim();
            var editId = (document.getElementById('editNodeId') || {}).value || '';
            var holder = null;
            Object.keys(nodeCache).forEach(function (id) {
                if (id !== editId && ip && nodeCache[id].public_ip === ip) holder = nodeCache[id].name;
            });
            if (holder) {
                el.textContent = '⚠ El nodo "' + holder + '" ya usa esta IP. ¿Misma máquina/router, o un error de tipeo?';
                el.style.display = 'block';
            } else {
                el.style.display = 'none';
            }
        }
        var ipInput = document.getElementById('modalNodeIP');
        if (ipInput) ipInput.addEventListener('input', checkDupIP);

        // ── Override the inline, DOM-only handlers with real persistence ──
        window.saveNode = function () {
            var editId = (document.getElementById('editNodeId') || {}).value || '';
            var name = document.getElementById('modalNodeName').value.trim();
            var ip = document.getElementById('modalNodeIP').value.trim();
            var location = document.getElementById('modalNodeLocation').value.trim();
            if (!name) { toast('Ingresa un nombre para el nodo'); return; }
            if (!ip) { toast('Ingresa la IP pública del nodo'); return; }
            if (!location) { toast('Ingresa la ubicación del Datacenter'); return; }

            var body = {
                name: name,
                public_ip: ip,
                vcores: parseInt(document.getElementById('modalNodeCores').value) || 0,
                ram_gb: parseInt(document.getElementById('modalNodeRAM').value) || 0,
                ssd_gb: parseInt(document.getElementById('modalNodeSSD').value) || 0,
                gpu_vram_mb: parseInt(document.getElementById('modalNodeGPU').value) || 0,
                hypervisor: document.getElementById('modalNodeHypervisor').value,
                location: location
            };

            var url = editId ? API + '/nodes/' + encodeURIComponent(editId) : API + '/nodes';
            var method = editId ? 'PATCH' : 'POST';
            fetch(url, { method: method, headers: authHeaders(true), body: JSON.stringify(body) })
                .then(function (r) { return r.json().then(function (b) { return { ok: r.ok, status: r.status, body: b }; }); })
                .then(function (res) {
                    if (res.ok) {
                        toast(editId ? 'Nodo "' + name + '" actualizado.' : 'Nodo "' + name + '" registrado en la base de datos.');
                        if (typeof window.closeNodeModal === 'function') window.closeNodeModal();
                        loadNodes();
                    } else if (res.status === 403) {
                        toast('Tu cuenta no tiene rol de Proveedor.');
                    } else if (res.status === 404) {
                        toast('Nodo no encontrado (¿eliminado en otra sesión?).');
                        loadNodes();
                    } else {
                        toast((editId ? 'Error al actualizar: ' : 'Error al registrar: ') + (res.body.detail || ('HTTP ' + res.status)));
                    }
                })
                .catch(function () { toast('No se pudo conectar al servidor (' + API + ').'); });
        };

        window.deleteNode = function (id) {
            if (!confirm('¿Eliminar este nodo?')) return;
            fetch(API + '/nodes/' + encodeURIComponent(id), { method: 'DELETE', headers: authHeaders(false) })
                .then(function (r) {
                    if (r.status === 204) { toast('Nodo eliminado.'); loadNodes(); }
                    else if (r.status === 404) { toast('Nodo no encontrado (¿ya eliminado?).'); loadNodes(); }
                    else { toast('Error al eliminar (HTTP ' + r.status + ').'); }
                })
                .catch(function () { toast('No se pudo conectar al servidor.'); });
        };

        // Edit: fill the modal from the cache (not DOM-scraping, which loses
        // precision — the table rounds SSD to TB and GPU to GB) and let
        // saveNode() PATCH instead of POST via the editNodeId hidden field.
        window.editNode = function (id) {
            var n = nodeCache[id];
            if (!n) { toast('Nodo no encontrado — recarga la página.'); return; }
            document.getElementById('nodeModalTitle').textContent = 'Editar Nodo';
            document.getElementById('editNodeId').value = id;
            document.getElementById('modalNodeName').value = n.name;
            document.getElementById('modalNodeIP').value = n.public_ip;
            document.getElementById('modalNodeCores').value = n.vcores;
            document.getElementById('modalNodeRAM').value = n.ram_gb;
            document.getElementById('modalNodeSSD').value = n.ssd_gb;
            document.getElementById('modalNodeGPU').value = n.gpu_vram_mb;
            document.getElementById('modalNodeHypervisor').value = n.hypervisor;
            document.getElementById('modalNodeLocation').value = n.location;
            document.getElementById('modalNodeSaveBtn').textContent = 'Actualizar Nodo';
            checkDupIP();
            document.getElementById('nodeModal').style.display = 'flex';
            document.body.style.overflow = 'hidden';
        };

        // Re-evaluate the IP hint when the blank "Registrar Nodo" modal opens
        // (programmatic value resets don't fire the 'input' listener).
        var _openAdd = window.openAddNodeModal;
        if (typeof _openAdd === 'function') {
            window.openAddNodeModal = function () { _openAdd(); checkDupIP(); };
        }

        // ── Stat cards ───────────────────────────────────────────────────
        // Format a COFP amount with apostrophe thousands separators (panel style:
        // "100'000"), trimming trailing-zero decimals.
        function fmtCOFP(v) {
            var n = parseFloat(v); if (isNaN(n)) return v;
            var dec = Math.round((n - Math.trunc(n)) * 100) / 100;
            var intPart = Math.trunc(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, "'");
            return dec ? intPart + '.' + String(dec).split('.')[1] : intPart;
        }
        function setText(id, txt) { var el = document.getElementById(id); if (el) el.textContent = txt; }

        // LIVE: bound to real DB data via GET /cofp/provider/summary.
        function bindProviderSummary() {
            fetch(API + '/cofp/provider/summary', { headers: authHeaders(false) })
                .then(function (r) { return r.ok ? r.json() : null; })
                .then(function (s) {
                    if (!s) return;
                    setText('provTokensEarned', fmtCOFP(s.cofp_this_month));
                    // Sub-label: rough COP at the governance base rate (0.29 COP/COFP).
                    var cop = Math.round(parseFloat(s.cofp_this_month) * 0.29);
                    var sub = document.querySelector('#provTokensEarned + .stat-change');
                    if (sub) sub.textContent = 'COFP · ≈ ' + cop.toLocaleString('es-CO') + ' COP (base)';
                    // Top-of-panel COFP balance.
                    setText('coffee-balance-value', fmtCOFP(s.cofp_balance));
                    var cur = document.getElementById('coffee-balance-currency');
                    if (cur) cur.textContent = 'COFP';
                })
                .catch(function () { /* leave existing values on failure */ });
            // provActiveNodes is kept live by updateProviderStats() (counts rendered rows).
        }

        // DEMO: capacity/utilization cards have no data source yet — that data
        // lives in the DC-Agent, not in panel_backend. Mark them honestly so QA
        // doesn't mistake placeholders for live numbers.
        function markDemoStats() {
            ['provTotalSlices', 'provBusySlices', 'provAvailableSlices',
             'provUnavailableSlices', 'provHostedVMs', 'provAvgUptime'].forEach(function (id) {
                var el = document.getElementById(id);
                if (!el || el.dataset.cpDemo) return;
                el.dataset.cpDemo = '1';
                el.title = 'Dato de demostración — pendiente de integración con el DC-Agent';
                el.style.opacity = '0.55';
                var tag = document.createElement('span');
                tag.textContent = ' demo';
                tag.style.cssText = 'font-size:9px;vertical-align:super;color:var(--cp-warning,#ffb400);letter-spacing:.5px;';
                el.appendChild(tag);
            });
        }

        // ── Other tabs (invoices, API keys, licenses, withdrawals, segments) ──
        function fmtInt(n) { return Number(n).toLocaleString('es-CO').replace(/,/g, "'"); }
        function fmtDate(s) { return s ? String(s).slice(0, 10) : '—'; }

        function getJSON(path) {
            return fetch(API + path, { headers: authHeaders(false) })
                .then(function (r) { return r.ok ? r.json() : []; })
                .catch(function () { return []; });
        }
        function fill(id, rows, rowHtml, emptyCols) {
            var tb = document.getElementById(id);
            if (!tb) return;
            if (!rows.length) {
                tb.innerHTML = '<tr><td colspan="' + (emptyCols || 6) +
                    '" style="text-align:center;color:var(--cp-text-muted);padding:18px;">Sin registros</td></tr>';
                return;
            }
            tb.innerHTML = rows.map(rowHtml).join('');
        }

        var INVOICE_ST = { paid: ['Pagada', 'paid'], pending: ['Pendiente', 'pending'], rejected: ['Pago Rechazado', 'rejected'] };
        var LICENSE_ST = { active: ['Activa', 'active'], expired: ['Expirada', 'expired'], suspended: ['Suspendida', 'pending'] };
        function stPill(map, k, cls) {
            var m = map[k] || [k, '']; return '<span class="' + cls + ' ' + m[1] + '">' + m[0] + '</span>';
        }

        function bindInvoices() {
            getJSON('/panel/invoices').then(function (rows) {
                fill('invoiceTableBody', rows, function (r) {
                    return '<tr>' +
                        '<td data-label="Factura N.º">' + esc(r.invoice_number) + '</td>' +
                        '<td data-label="Fecha">' + fmtDate(r.issued_on) + '</td>' +
                        '<td data-label="Concepto">' + esc(r.concept) + '</td>' +
                        '<td data-label="Monto COP" class="invoice-amount">$' + fmtInt(r.amount_cop) + ' COP</td>' +
                        '<td data-label="Créditos" class="invoice-amount">' + fmtInt(r.credits) + ' Cr</td>' +
                        '<td data-label="Estado">' + stPill(INVOICE_ST, r.status, 'invoice-status') + '</td>' +
                        '<td data-label="Descargar"><a href="#" onclick="return false;" style="color:var(--cp-accent);">PDF</a></td>' +
                        '</tr>';
                }, 7);
            });
        }
        function bindApiKeys() {
            getJSON('/panel/apikeys').then(function (rows) {
                fill('apiKeysTableBody', rows, function (r) {
                    return '<tr>' +
                        '<td data-label="Nombre">' + esc(r.name) + '</td>' +
                        '<td data-label="Clave API"><code style="font-size:12px;">' + esc(r.masked_key) + '</code></td>' +
                        '<td data-label="Entorno"><span class="tag">' + esc(r.environment) + '</span></td>' +
                        '<td data-label="Creada">' + fmtDate(r.created_at) + '</td>' +
                        '<td data-label="Último Uso">' + fmtDate(r.last_used) + '</td>' +
                        '<td data-label="Acciones"><a href="#" onclick="return false;" style="color:var(--cp-danger,#e66);">Revocar</a></td>' +
                        '</tr>';
                }, 6);
            });
        }
        function bindLicenses() {
            getJSON('/panel/licenses').then(function (rows) {
                fill('licensesTableBody', rows, function (r) {
                    return '<tr>' +
                        '<td data-label="Clave de Licencia"><code style="font-size:12px;">' + esc(r.license_key) + '</code></td>' +
                        '<td data-label="Terminales">' + fmtInt(r.terminals) + '</td>' +
                        '<td data-label="Tipo">' + esc(r.plan_type) + '</td>' +
                        '<td data-label="Inicio">' + fmtDate(r.start_date) + '</td>' +
                        '<td data-label="Expiración">' + fmtDate(r.expiration) + '</td>' +
                        '<td data-label="Estado">' + stPill(LICENSE_ST, r.status, 'invoice-status') + '</td>' +
                        '<td data-label="Acciones"><a href="#" onclick="return false;" style="color:var(--cp-accent);">Renovar</a></td>' +
                        '</tr>';
                }, 7);
            });
        }
        function bindWithdrawals() {
            getJSON('/panel/withdrawals').then(function (rows) {
                var label = document.getElementById('withdrawalCountLabel');
                if (label) label.textContent = rows.length + ' retiro' + (rows.length !== 1 ? 's' : '');
                fill('withdrawalsTableBody', rows, function (r) {
                    return '<tr>' +
                        '<td data-label="ID Retiro">#' + esc(String(r.created_at).slice(0, 10).replace(/-/g, '')) + '</td>' +
                        '<td data-label="Fecha">' + fmtDate(r.created_at) + '</td>' +
                        '<td data-label="Tokens Quemados" class="invoice-amount">' + fmtInt(Math.round(parseFloat(r.cofp_burned))) + ' COFP</td>' +
                        '<td data-label="Monto Recibido" class="invoice-amount">' + fmtInt(r.cop_received) + ' COP</td>' +
                        '<td data-label="Concepto">' + esc(r.concept) + '</td>' +
                        '<td data-label="Estado">' + stPill(INVOICE_ST, r.status, 'invoice-status') + '</td>' +
                        '</tr>';
                }, 6);
            });
        }
        function bindSegments() {
            getJSON('/panel/segments').then(function (rows) {
                var el = document.getElementById('segmentsList');
                if (!el) return;
                if (!rows.length) { el.innerHTML = '<div style="color:var(--cp-text-muted);padding:12px;">Sin segmentos</div>'; return; }
                el.innerHTML = rows.map(function (s) {
                    var meta = [s.industry, s.role, (s.age_min + '-' + s.age_max + ' años'), s.region].filter(Boolean).join(' · ');
                    return '<div class="campaign-item" style="border-left:3px solid var(--cp-accent);">' +
                        '<div class="campaign-info">' +
                        '<div class="campaign-name">' + esc(s.name) + '</div>' +
                        '<div class="campaign-meta" style="font-size:12px;color:var(--cp-text-muted);">' + esc(meta) + '</div>' +
                        '</div>' +
                        '<div class="campaign-stat"><strong>' + fmtInt(s.size_estimate) + '</strong><span style="font-size:11px;color:var(--cp-text-muted);"> alcance</span></div>' +
                        '</div>';
                }).join('');
            });
        }

        // ── Withdrawal request: burn COFP for real via POST /cofp/withdraw ──
        // Replaces the inline DOM-only mock. The server is authoritative on
        // balance (400 on insufficient COFP), so no client-side max check —
        // the inline one misparses decimal balances anyway.

        // The input's max is the per-withdrawal settlement cap, NOT the balance.
        // The inline syncWithdrawMax() scraped the rendered balance string for
        // it — grabbing the 25'000'000 placeholder before the live balance
        // arrived. Earnings run far past that (1 COFP = 1 slice·min ⇒ a 20-node
        // rack ≈ 221M COFP/month). Keep in sync with MAX_WITHDRAWAL_COFP in
        // app/cofp/ledger.py, which enforces the real rule.
        var WITHDRAW_CAP = 100000000;
        // Floor (≈ 31'900 COP at tier2): each payout is a real bank transfer
        // with a fixed cost — dust withdrawals would be net-negative. Keep in
        // sync with MIN_WITHDRAWAL_COFP in app/cofp/ledger.py.
        var WITHDRAW_MIN = 100000;
        var wdAmountInput = document.getElementById('withdrawAmount');
        if (wdAmountInput) {
            wdAmountInput.max = WITHDRAW_CAP;
            wdAmountInput.min = WITHDRAW_MIN;
            // The Wix-export prefill is 1000 — below the floor; lift it.
            if ((parseInt(wdAmountInput.value) || 0) < WITHDRAW_MIN) {
                wdAmountInput.value = WITHDRAW_MIN;
                if (typeof window.updateWithdrawalPreview === 'function') window.updateWithdrawalPreview();
            }
        }
        window.syncWithdrawMax = function () {
            var i = document.getElementById('withdrawAmount');
            if (i) { i.max = WITHDRAW_CAP; i.min = WITHDRAW_MIN; }
        };
        window.requestWithdrawal = function () {
            var amount = parseInt(document.getElementById('withdrawAmount').value) || 0;
            var concept = document.getElementById('withdrawConcept').value.trim();
            if (!amount || amount < 1) { toast('Ingresa una cantidad válida de tokens'); return; }
            if (amount < WITHDRAW_MIN) {
                toast('El retiro mínimo es ' + fmtInt(WITHDRAW_MIN) + ' COFP (≈ ' +
                    fmtInt(Math.floor(WITHDRAW_MIN * 0.319)) + ' COP) — los costos de la ' +
                    'transferencia bancaria se comerían un monto menor.');
                return;
            }
            if (!concept) { toast('Ingresa un concepto para el retiro'); return; }

            var tier = window.PROVIDER_TIER || 'tier1';
            fetch(API + '/cofp/withdraw', {
                method: 'POST', headers: authHeaders(true),
                body: JSON.stringify({ cofp_amount: String(amount), tier: tier, concept: concept })
            })
                .then(function (r) { return r.json().then(function (b) { return { ok: r.ok, status: r.status, body: b }; }); })
                .then(function (res) {
                    if (res.ok) {
                        toast('Retiro solicitado: ' + res.body.cofp_burned + ' COFP → ' +
                            fmtInt(res.body.payout_cop) + ' COP (tasa ' + res.body.effective_rate_cop +
                            '). Transferencia estimada en 24-72h.');
                        document.getElementById('withdrawAmount').value = String(WITHDRAW_MIN);
                        document.getElementById('withdrawConcept').value = '';
                        if (typeof window.updateWithdrawalPreview === 'function') window.updateWithdrawalPreview();
                        bindWithdrawals();        // re-render history from the DB
                        bindProviderSummary();    // balance went down — refetch
                    } else if (res.status === 400) {
                        toast('Retiro rechazado: ' + (res.body.detail || 'datos inválidos'));
                    } else if (res.status === 403) {
                        toast('Tu cuenta no tiene rol de Proveedor o Contribuidor.');
                    } else {
                        toast('Error al solicitar el retiro: ' + (res.body.detail || ('HTTP ' + res.status)));
                    }
                })
                .catch(function () { toast('No se pudo conectar al servidor (' + API + ').'); });
        };

        loadNodes();
        bindProviderSummary();
        markDemoStats();
        bindInvoices();
        bindApiKeys();
        bindLicenses();
        bindWithdrawals();
        bindSegments();
    });
})();
