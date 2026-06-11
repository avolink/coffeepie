// Coffee Pie — Panel data binding (Proveedores tab: nodes).
// Replaces the client-side-only node table with real backend persistence:
//   • On load: GET /nodes → render the table from the database.
//   • "Guardar Nodo": POST /nodes → row persists (survives refresh).
//   • Delete: DELETE /nodes/{id}.
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
                '<button class="node-action-btn delete" onclick="deleteNode(\'' + esc(n.id) + '\')" title="Eliminar">' +
                '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>' +
                '</button></div></td>';
        }

        function renderNodes(nodes) {
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

        // ── Override the inline, DOM-only handlers with real persistence ──
        window.saveNode = function () {
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

            fetch(API + '/nodes', { method: 'POST', headers: authHeaders(true), body: JSON.stringify(body) })
                .then(function (r) { return r.json().then(function (b) { return { ok: r.ok, status: r.status, body: b }; }); })
                .then(function (res) {
                    if (res.ok) {
                        toast('Nodo "' + name + '" registrado en la base de datos.');
                        if (typeof window.closeNodeModal === 'function') window.closeNodeModal();
                        loadNodes();
                    } else if (res.status === 403) {
                        toast('Tu cuenta no tiene rol de Proveedor.');
                    } else {
                        toast('Error al registrar: ' + (res.body.detail || ('HTTP ' + res.status)));
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

        // Editing is not persisted server-side yet — be honest instead of lying.
        window.editNode = function () {
            toast('La edición de nodos estará disponible próximamente.');
        };

        loadNodes();
    });
})();
