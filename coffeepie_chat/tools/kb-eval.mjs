#!/usr/bin/env node
/* ===========================================================================
   Retrieval smoke test — does a real visitor question land on the right entry?

   Run after regenerating the KB:  node tools/kb-eval.mjs
   It exercises the retriever alone (no model, no network), which is the half of
   the assistant that decides whether an answer is even possible. A question in
   the "should miss" list that starts matching means the floor has drifted and
   the bot will begin answering things the site cannot support.
   =========================================================================== */
import { retrieve, kbSize } from '../lib/chat-kb.js';

const HIT = [
  ['cuánto cuesta', /precio|plan|slice|cr[eé]dito/i],
  ['qué es un slice', /slice/i],
  ['cómo consigo créditos', /cr[eé]dito|anuncio|precio/i],
  ['puedo usar windows', /coffee|slice|servicio|m[aá]quina|tienda/i],
  ['cómo empiezo a usar el servicio', /empezar|servicio|coffee|plan/i],
  ['quiero ser proveedor', /proveedor|cloud/i],
  ['fabricar terminales', /fabricante|manufacturer|terminal/i],
  ['política de reembolso', /reembolso|refund|devoluci/i],
  ['cómo protegen mis datos', /privacidad|privacy|datos/i],
  ['envíos y transporte', /env[ií]o|shipping/i],
  ['qué es QFDM', /qfdm|coffee|servicio/i],
  ['how much does it cost', /precio|plan|slice|cr[eé]dito/i],
  ['what is a slice', /slice/i],
  ['become a provider', /proveedor|cloud/i]
];

/* Questions the public site genuinely cannot answer. These must return nothing,
   so the route can say "no entiendo" instead of dressing up a coincidence. */
const MISS = [
  'receta de paella',
  'quién ganó el mundial de 1998',
  'escribe un poema sobre el mar'
];

/* Known-weak: a bag-of-words retriever cannot separate these from a real
   question, and the scores say so. "cuál es la capital de Mongolia" scores 2.5
   because "capital" appears once (high IDF) in the investor copy; "how much
   does it cost" also scores 2.5, because "precio" appears everywhere (low IDF).
   Same number, opposite intent — no floor can split them.

   That is fine, and it is why the guard is layered: a weak hit reaches the
   model with irrelevant context, and rule 1 of the system prompt ("only answer
   from CONTEXTO, otherwise say exactly …") turns it into the same "no entiendo"
   the visitor would have got anyway. The cost is one wasted model call, not a
   wrong answer. Listed here so the behaviour is measured rather than assumed —
   if one of these ever starts scoring high, that IS a regression. */
const WEAK = [
  ['cuál es la capital de Mongolia', 3.2]
];

let pass = 0, fail = 0;
console.log(`KB: ${kbSize} entradas\n`);
console.log('— deben acertar —');
for (const [q, re] of HIT) {
  const r = retrieve(q, 3);
  const top = r[0];
  const ok = !!top && re.test(top.entry.title + ' ' + top.entry.text);
  ok ? pass++ : fail++;
  console.log(`${ok ? 'ok  ' : 'FAIL'}  ${q.padEnd(34)} → ${top ? top.entry.title.slice(0, 46) + '  (' + top.score.toFixed(1) + ')' : '(sin resultados)'}`);
}
console.log('\n— deben fallar —');
for (const q of MISS) {
  const r = retrieve(q, 3);
  const ok = r.length === 0;
  ok ? pass++ : fail++;
  console.log(`${ok ? 'ok  ' : 'FAIL'}  ${q.padEnd(34)} → ${r.length ? r[0].entry.title.slice(0, 46) + '  (' + r[0].score.toFixed(1) + ')' : '(sin resultados)'}`);
}
console.log('\n— débiles: sólo el prompt las detiene, vigilamos que no suban —');
for (const [q, ceiling] of WEAK) {
  const r = retrieve(q, 3);
  const score = r.length ? r[0].score : 0;
  const ok = score < ceiling;                 // must stay weak, not disappear
  ok ? pass++ : fail++;
  console.log(`${ok ? 'ok  ' : 'FAIL'}  ${q.padEnd(34)} → ${score.toFixed(1)} (techo ${ceiling})`);
}

console.log(`\n${pass} ok, ${fail} fail`);
process.exit(fail ? 1 : 0);
