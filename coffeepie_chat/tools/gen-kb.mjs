#!/usr/bin/env node
/* ===========================================================================
   Builds data/chat-kb.json — the ONLY knowledge the web assistant may use.

   ⚠ SECURITY RULE: every source here is something a visitor can already read
   with "View source" on coffeepie.co. Public marketing and legal HTML, the
   public frontend constants, and chat.json. Nothing from the orchestrator, the
   panel backend, the database, Proxmox, .env files or AGENTS.md ever enters
   this file — the assistant cannot leak what it was never given.

   ⚠ PAGE ALLOW-LIST, not a skip-list. The logged-in app pages (panel, machines,
   stream, cart, secure-payment) are deliberately excluded: their copy is UI
   chrome, it describes the control plane, and none of it helps a visitor who is
   asking what this service is. Adding a page here is a conscious act.

   ⚠ WORKFLOW: re-run after editing public copy or chat.json:
        npm run kb
     then rebuild/restart the container so it picks the new file up.
   =========================================================================== */
import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.join(HERE, '..');
const PUB = path.join(ROOT, '..', 'coffeepie_website', 'public');
const OUT = path.join(ROOT, 'data', 'chat-kb.json');

/* Marketing + legal pages only. Anything a signed-in user sees is out. */
const PAGES = [
  'index.html', 'about.html', 'pricing.html', 'api.html', 'tutorials.html',
  'manufacturers.html', 'cloud-providers.html', 'certified-devices.html',
  'investor-portal.html', 'store.html',
  'terms-and-conditions.html', 'privacy-policy.html', 'return-policy.html',
  'shipping-policy.html', 'accessibility.html'
];

const entries = [];
let seq = 0;
function add(e) {
  const text = (e.text || '').replace(/\s+/g, ' ').trim();
  if (text.length < 40) return;                       // too thin to answer anything
  entries.push({ id: e.kind + '-' + ++seq, kind: e.kind, title: (e.title || '').trim(), url: e.url || '', text: text.slice(0, 1400) });
}

/* ---- html → text --------------------------------------------------------- */
function textOf(html) {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, ' ')
    .replace(/<style[\s\S]*?<\/style>/gi, ' ')
    .replace(/<svg[\s\S]*?<\/svg>/gi, ' ')
    .replace(/<!--[\s\S]*?-->/g, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/&quot;/g, '"')
    .replace(/&#(\d+);/g, (_, d) => String.fromCharCode(+d))
    .replace(/&[a-z]+;/gi, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}
function attr(html, re) { const m = html.match(re); return m ? m[1].trim() : ''; }
/* <title> and meta content arrive entity-encoded; these strings end up as the
   visible label on a link chip, so "Returns &amp; Refunds" must not ship. */
function deent(s) {
  return String(s)
    .replace(/&nbsp;/g, ' ').replace(/&quot;/g, '"').replace(/&#39;|&apos;/g, "'")
    .replace(/&#(\d+);/g, (_, d) => String.fromCharCode(+d))
    .replace(/&amp;/g, '&')
    .replace(/\s+/g, ' ').trim();
}

/* ---- 1. curated: what Coffee Pie actually is -----------------------------
   Written here, not scraped, so the wording is deliberate and every claim maps
   to something published on the site. This is the block that answers a visitor
   who arrives in a language the Spanish retriever cannot tokenise.            */
const ABOUT = [
  {
    title: 'Coffee Pie — qué es',
    url: '/',
    text: `Coffee Pie® es un servicio de cómputo bajo demanda: en lugar de comprar un computador, alquilas por minutos la potencia que necesitas y la usas desde el navegador o desde una Terminal Codec conectada al televisor o monitor.
      Funciona como un "café internet" pero desde tu casa, oficina o un espacio público con conexión a internet.
      Está construido sobre el sistema QFDM (Sistema de Distribución y Gestión Cuantizada y Fraccionada), patente NC2025/0012723, que reparte servidores reales en porciones llamadas Slices.
      La misión del proyecto es democratizar el acceso al cómputo y reducir la basura electrónica: en lugar de millones de equipos infrautilizados, unos pocos servidores bien aprovechados.`
  },
  {
    title: 'Slices y Créditos — cómo se cobra',
    url: '/pricing.html',
    text: `Un Slice (porción) es la unidad de cómputo: se alquila por tiempo y varios Slices se suman para formar una máquina más potente.
      El consumo se paga con Créditos (Cr). Hay dos formas de obtener Créditos: viendo anuncios, donde el anunciante paga por ti, o comprando paquetes de Créditos.
      El usuario final nunca necesita comprar hardware ni pagar mantenimiento, y puede apagar la máquina cuando no la use para dejar de consumir.`
  },
  {
    title: 'Cómo empezar',
    url: '/pricing.html',
    text: `Crea una cuenta gratuita, elige un plan o empieza con la capa gratuita, y crea tu primera máquina eligiendo el sistema operativo y cuántos Slices quieres.
      La máquina se abre en el navegador. Puedes apagarla, encenderla, cambiarle la capacidad y eliminarla desde tu Panel.
      Para cambiar la capacidad de una máquina hay que apagarla primero, porque el hardware virtual solo se modifica en frío.`
  },
  {
    title: 'Proveedores de cómputo',
    url: '/cloud-providers.html',
    text: `Un Proveedor es un operador de datacenter que aporta servidores a la red QFDM y recibe pagos por los Slices que sirve.
      Los proveedores se clasifican por niveles según redundancia eléctrica y de red, disponibilidad comprometida, refrigeración, seguridad física y uso de energías renovables: a mejor nivel, mejor margen.`
  },
  {
    title: 'Fabricantes y Terminales Codec',
    url: '/manufacturers.html',
    text: `La Terminal Codec es un equipo ARM sencillo, modular, reparable y reciclable que decodifica el video del servidor y conecta los periféricos del usuario.
      Cualquier fabricante puede integrar módulos y accesorios alrededor del servicio. Fabricar terminales para alquilarlas a terceros requiere un acuerdo de regalías de patente para poder conectarse al backend QFDM.`
  },
  {
    title: 'Soporte y contacto',
    url: '/about.html',
    text: `Para casos particulares de tu cuenta, facturación o una máquina que no responde, el canal es el equipo de soporte.
      Desde el Panel de usuario puedes revisar tus máquinas, tu saldo de Créditos y tu facturación.`
  }
];
for (const a of ABOUT) add({ kind: 'servicio', ...a });

/* ---- 2. public frontend constants ---------------------------------------
   Read out of the shipped JS rather than retyped, so the assistant cannot drift
   from what the site itself shows a visitor. If the constants move, the KB moves
   with them on the next `npm run kb`.                                          */
{
  const js = readFileSync(path.join(PUB, 'js', 'cp-machines.js'), 'utf8');
  const num = (re) => { const m = js.match(re); return m ? m[1] : null; };
  const rate = num(/var\s+RATE\s*=\s*(\d+)/);
  const perSlice = js.match(/var\s+PER_SLICE\s*=\s*\{([^}]*)\}/);
  const recPrices = js.match(/var\s+REC_PRICES\s*=\s*\{([^}]*)\}/);

  const bits = [];
  if (perSlice) {
    const o = {};
    for (const kv of perSlice[1].split(',')) {
      const m = kv.match(/(\w+)\s*:\s*([\d.]+)/);
      if (m) o[m[1]] = m[2];
    }
    bits.push(`Cada Slice equivale aproximadamente a ${o.cores || 1} núcleo, ${o.ramGb || 1} GB de RAM, ${o.ssdGb || 0} GB de SSD, ${o.hddGb || 0} GB de disco duro, ${o.vramMb || 0} MB de memoria de video y ${o.mbps || 0} Mbps de red.`);
  }
  if (rate) bits.push(`Tarifa de referencia: ${rate} Cr por minuto por cada Slice.`);
  if (recPrices) {
    const o = {};
    for (const kv of recPrices[1].split(',')) {
      const m = kv.match(/(\w+)\s*:\s*(\d+)/);
      if (m) o[m[1]] = Number(m[2]).toLocaleString('es-CO');
    }
    if (o.minute || o.month || o.year) {
      bits.push(`Recurrencias disponibles por Slice: ${[o.minute && 'por minuto ' + o.minute + ' Cr', o.month && 'mensual ' + o.month + ' Cr', o.year && 'anual ' + o.year + ' Cr'].filter(Boolean).join(', ')}.`);
    }
  }
  /* The operating-system catalog. Visitors ask "can I run Windows?" constantly
     and no marketing page answers it — the list only exists in the shipped JS
     that renders the OS picker, which is public and is the same list the
     product actually offers. Its `min` is the smallest machine each OS will
     run on, which is the other half of that question. */
  const osBlock = js.match(/var\s+OS\s*=\s*\{([\s\S]*?)\n\s*\};/);
  if (osBlock) {
    const offered = [], hidden = [];
    const re = /(\w+)\s*:\s*\{[^}]*label:\s*'([^']+)'[^}]*min:\s*(\d+)([^}]*)\}/g;
    let m;
    while ((m = re.exec(osBlock[1])) !== null) {
      const line = `${m[2]} (desde ${m[3]} ${m[3] === '1' ? 'Slice' : 'Slices'})`;
      (/hidden:\s*true/.test(m[4]) ? hidden : offered).push(line);
    }
    if (offered.length) {
      add({
        kind: 'servicio', title: 'Sistemas operativos disponibles', url: '/pricing.html',
        text: `Puedes crear máquinas con estos sistemas operativos: ${offered.join(', ')}. ` +
              (hidden.length ? `También hay máquinas existentes con ${hidden.join(', ')}. ` : '') +
              `El número de Slices mínimo depende del sistema operativo: Windows necesita más que una distribución Linux ligera. ` +
              `Puedes cambiar la cantidad de Slices después, apagando la máquina primero.`
      });
    }
  }

  if (bits.length) {
    add({ kind: 'servicio', title: 'Qué incluye un Slice y cuánto cuesta', url: '/pricing.html', text: bits.join(' ') });
  } else {
    console.warn('  ⚠ no se pudieron leer las constantes de cp-machines.js — revisa los nombres RATE / PER_SLICE / REC_PRICES');
  }
}

/* ---- 3. public pages: meta description + <h2> sections -------------------
   The site is a Wix export, so two kinds of rubbish come along with the real
   copy and both actively hurt retrieval: the newsletter block repeated at the
   foot of every page (identical text on 10 pages destroys its own IDF), and
   layout blocks that are pure glyphs — a comparison table of ✔ and ✗ carries no
   words to match on but does carry a heading that looks meaningful.            */
const NOISE_HEADING = /^\s*(cont[aá]ctanos|suscr[ií]bete|newsletter|s[ií]guenos|follow us)/i;
function letterRatio(s) {
  const letters = (s.match(/[\p{L}]/gu) || []).length;
  return s.length ? letters / s.length : 0;
}

const seen = new Set();
for (const file of PAGES) {
  const full = path.join(PUB, file);
  if (!existsSync(full)) { console.warn('  ⚠ falta ' + file); continue; }
  const html = readFileSync(full, 'utf8');
  const url = '/' + file;
  const title = deent(attr(html, /<title>([^<]*)<\/title>/i)).replace(/\s*\|\s*Coffee\s*Pie.*$/i, '').trim();
  const desc = deent(attr(html, /<meta\s+name=["']description["']\s+content=["']([^"']*)["']/i));
  if (desc) add({ kind: 'pagina', title, url, text: title + '. ' + desc });

  // one entry per <h2> section, so retrieval lands on the relevant part of a
  // long page instead of its first paragraph
  const body = html.slice(html.indexOf('<body'));
  const parts = body.split(/<h2\b/i);
  for (let i = 1; i < parts.length; i++) {
    const chunk = '<h2' + parts[i];
    const end = chunk.indexOf('</h2>');
    const heading = textOf(chunk.slice(0, end < 0 ? 400 : end + 5));
    if (!heading || heading.length > 120) continue;
    if (NOISE_HEADING.test(heading)) continue;
    const txt = textOf(chunk).slice(0, 1400);
    if (txt.length < 120) continue;            // a stub cannot answer anything
    if (letterRatio(txt) < 0.5) continue;      // glyph grid, not prose
    // The Wix export repeats whole blocks; a duplicate body adds nothing but
    // dilutes IDF, so keep the first occurrence only.
    const key = txt.slice(0, 160);
    if (seen.has(key)) continue;
    seen.add(key);
    add({ kind: 'pagina', title: (title ? title + ' — ' : '') + heading, url, text: txt });
  }
}

/* ---- 4. chat.json — the guided-flow copy, also searchable as free text ---- */
{
  // Served publicly at /chat.json and fetched by the widget — one file, so the
  // menu the visitor clicks and the text the assistant can retrieve cannot drift.
  const p = path.join(PUB, 'chat.json');
  if (existsSync(p)) {
    const flow = JSON.parse(readFileSync(p, 'utf8'));
    for (const [key, node] of Object.entries(flow)) {
      if (!node || typeof node !== 'object' || !node.text) continue;
      add({ kind: 'flujo', title: node.title || key, url: (node.links && node.links[0] && node.links[0].url) || '', text: node.text });
    }
  }
}

mkdirSync(path.dirname(OUT), { recursive: true });
writeFileSync(OUT, JSON.stringify({ generated: new Date().toISOString(), entries }, null, 0));
const kb = Buffer.byteLength(JSON.stringify(entries));
console.log(`chat-kb: ${entries.length} entradas (${(kb / 1024).toFixed(0)} KB) → data/chat-kb.json`);
const byKind = entries.reduce((a, e) => ((a[e.kind] = (a[e.kind] || 0) + 1), a), {});
console.log('  ' + Object.entries(byKind).map(([k, n]) => `${k}: ${n}`).join(' · '));
