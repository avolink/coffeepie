/* ===========================================================================
   Knowledge base + retrieval for the public web assistant.

   The KB is a static file generated from the PUBLIC frontend (tools/gen-kb.mjs).
   This module is deliberately the assistant's ONLY door to information: it reads
   one JSON file and does string matching. It imports no database client, no auth,
   no filesystem walking and no network — so there is no code path from a chat
   message to anything private.
   =========================================================================== */

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const KB_PATH = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'data', 'chat-kb.json');

let KB = { generated: null, entries: [] };
try {
  KB = JSON.parse(readFileSync(KB_PATH, 'utf8'));
} catch (e) {
  // A missing KB is not fatal: the assistant degrades to "no entiendo" plus the
  // support hand-off, which is safe. It must never take the site down.
  KB = { generated: null, entries: [] };
}

/* Accent-folding tokenizer. The site copy is Spanish; the UI offers 12
   languages, so the character classes have to survive Cyrillic, Greek, Arabic,
   Devanagari and CJK rather than silently dropping a whole query to empty. */
export function tokens(s) {
  return String(s == null ? '' : s)
    .toLowerCase()
    .normalize('NFD').replace(/[̀-ͯ]/g, '')        // drop combining accents
    .replace(/[^a-z0-9Ͱ-ϿЀ-ӿ؀-ۿऀ-ॿ぀-ヿ一-鿿가-힯]+/gi, ' ')
    .split(' ')
    .filter((t) => t.length > 1 && !STOP.has(t));
}

const STOP = new Set((
  'de la el los las un una unos unas y o u a en con por para del al que se su sus lo es son ser esta este estos estas mi me te ' +
  'como cual cuales donde cuando quien porque pero si no ni mas muy ya hay tiene tienen puedo puede pueden quiero quisiera necesito ' +
  'sobre tras hacia desde hasta entre segun durante sin bajo ante cada todo toda todos todas otro otra otros otras ' +
  'about over into from than then there here what which whose whom into onto ' +
  'the of and or to in on for with a an is are be this that i you my your we our it its do does can could would should please ' +
  'e em para com por que os as um uma nao sim ' +
  'le les des du au aux et ou pour dans avec je vous nous est sont quel quelle quels quelles combien comment ' +
  'der die das und oder ein eine ist sind wie was wo wann wer'
).split(' '));

/* The site content is Spanish; visitors arrive in other languages. Without this
   bridge an English question retrieves nothing and every answer falls through to
   support. Domain vocabulary only — this is not a translator. */
const SYN = {
  // the product itself
  computer: 'computador maquina', pc: 'computador maquina', machine: 'maquina', machines: 'maquina',
  vm: 'maquina virtual', desktop: 'escritorio computador', cloud: 'nube',
  slice: 'slice porcion', slices: 'slice porcion', core: 'nucleo', cores: 'nucleo',
  ram: 'ram memoria', memory: 'memoria ram', storage: 'almacenamiento disco', disk: 'disco almacenamiento',
  gpu: 'gpu grafica', vram: 'vram grafica',
  // money
  credit: 'credito', credits: 'credito creditos', cr: 'credito',
  price: 'precio', prices: 'precio', pricing: 'precio planes', cost: 'precio costo',
  preco: 'precio', prix: 'precio', preis: 'precio',
  free: 'gratis gratuita gratuito', gratuit: 'gratis', gratis: 'gratis',
  plan: 'plan paquete', plans: 'plan paquete', package: 'paquete plan', packages: 'paquete plan',
  subscription: 'suscripcion', pay: 'pago pagar', payment: 'pago', billing: 'facturacion pago',
  ads: 'anuncios publicidad', ad: 'anuncio publicidad', advertising: 'publicidad anuncios',
  token: 'token cofp', cofp: 'token cofp', blockchain: 'blockchain token',
  // who you are
  provider: 'proveedor', providers: 'proveedor', datacenter: 'datacenter centro datos',
  manufacturer: 'fabricante', manufacturers: 'fabricante', hardware: 'hardware terminal',
  terminal: 'terminal codec', codec: 'terminal codec', investor: 'inversionista',
  // using it
  os: 'sistema operativo', windows: 'windows', linux: 'linux', debian: 'debian', ubuntu: 'ubuntu',
  stream: 'streaming transmision', streaming: 'streaming transmision', latency: 'latencia ping',
  ping: 'ping latencia', connection: 'conexion', internet: 'internet conexion',
  account: 'cuenta', login: 'sesion cuenta ingreso', signup: 'registro cuenta', register: 'registro cuenta',
  password: 'contrasena', support: 'soporte ayuda', help: 'ayuda soporte', aide: 'ayuda',
  api: 'api', docs: 'documentacion', documentation: 'documentacion',
  // commerce
  buy: 'comprar', purchase: 'comprar compra', acheter: 'comprar', comprar: 'comprar',
  store: 'tienda', shop: 'tienda', cart: 'carrito', shipping: 'envio', delivery: 'entrega envio',
  refund: 'reembolso devolucion', warranty: 'garantia', guarantee: 'garantia',
  privacy: 'privacidad', terms: 'terminos condiciones', security: 'seguridad',
  // the patent / model
  qfdm: 'qfdm', patent: 'patente', open: 'abierto', opensource: 'codigo abierto',
  environment: 'ambiental medio ambiente', waste: 'residuos basura electronica', ewaste: 'residuos electronicos'
};
/* A Map, not the object literal: a query containing "constructor" would
   otherwise look up Object.prototype. */
const SYN_MAP = new Map(Object.entries(SYN));
function expand(list) {
  const out = new Set(list);
  for (const t of list) {
    const s = SYN_MAP.get(t) || SYN_MAP.get(t.replace(/[sx]$/, '')) || SYN_MAP.get(t.replace(/es$/, ''));
    if (s) for (const w of s.split(' ')) out.add(w);
  }
  return [...out];
}

/* Inverse document frequency, computed once — a term in every entry ("coffee",
   "pie") must not outweigh a rare, discriminating one ("QFDM", "Sunshine"). */
const DF = new Map();
for (const e of KB.entries) {
  for (const t of new Set(tokens(e.title + ' ' + e.text))) DF.set(t, (DF.get(t) || 0) + 1);
}
const N = Math.max(1, KB.entries.length);
function idf(t) { return Math.log(1 + N / (1 + (DF.get(t) || 0))); }

/* Truncated stem: "compra"/"comprar"/"compras" collapse to "compr". Crude, but
   it is what lets a question phrased as a verb find copy written as a noun
   without dragging a stemmer onto the box. */
const pre = (t) => t.slice(0, 5);

/* Precomputed per-entry token sets — retrieval runs on every message. */
const INDEX = KB.entries.map((e) => {
  const ti = tokens(e.title), bo = tokens(e.text);
  return {
    entry: e,
    title: new Set(ti), body: new Set(bo),
    titleP: new Set(ti.map(pre)), bodyP: new Set(bo.map(pre))
  };
});

export const kbSize = KB.entries.length;
export const kbGenerated = KB.generated;

/* The curated public summary. Used as general context when a question matches
   nothing specific — it is what lets a visitor writing in Japanese or Arabic
   still get "what is this, what does it cost, how do I start", since the
   retriever indexes Spanish and those scripts share no tokens with it. */
export function summary() {
  return KB.entries.filter((e) => e.kind === 'empresa' || e.kind === 'servicio');
}

/* Top-k entries for a query. Returns [] when nothing clears the floor, which is
   the signal that the question is outside what the site can answer. */
export function retrieve(query, k = 4) {
  const q0 = [...new Set(tokens(query))];
  const q = expand(q0);
  if (!q.length) return [];
  const scored = [];
  for (const row of INDEX) {
    let s = 0, hit = 0, exact = 0;
    for (const t of q) {
      const p = pre(t);
      const full = row.title.has(t) ? 2.2 : row.body.has(t) ? 1 : 0;
      const w = full || (row.titleP.has(p) ? 1.1 : row.bodyP.has(p) ? 0.5 : 0);   // inexact = half credit
      if (!w) continue;
      if (full) exact++;
      hit++;
      s += idf(t) * w;
    }
    // A stem alone never makes a match: "cuéntame un chiste" shares five letters
    // with "cuenta" and nothing else. Prefixes may only reinforce a real hit.
    if (!exact) continue;
    // Reward covering more of the question, measured against what the visitor
    // actually typed — otherwise every expanded synonym dilutes its own query.
    s *= 0.5 + 0.5 * Math.min(1, hit / q0.length);
    s *= KIND_W[row.entry.kind] || 1;
    scored.push({ score: s, hit, entry: row.entry });
  }
  scored.sort((a, b) => b.score - a.score);
  if (!scored.length || scored[0].score < FLOOR) return [];   // nothing on the site answers this
  // Diversity: four near-identical plan rows would crowd out the page that
  // actually explains the topic, so cap how many of one kind can fill the slots.
  const out = [], used = {};
  for (const r of scored) {
    const n = used[r.entry.kind] || 0;
    if (n >= (KIND_CAP[r.entry.kind] || k)) continue;
    used[r.entry.kind] = n + 1;
    out.push(r);
    if (out.length === k) break;
  }
  return out;
}

const FLOOR = 2.2;                                 // below this it is word coincidence, not a match
const KIND_W = { servicio: 1.25, flujo: 1.1 };     // "how the service works" is usually the answer wanted
const KIND_CAP = { plan: 2, pagina: 3 };
