#!/usr/bin/env node
/* ===========================================================================
   Does the model actually answer, from where the service actually runs?

     docker compose exec chat node tools/chat-probe.mjs

   Necessary because the route swallows model failures on purpose: if the model
   is unreachable the visitor still gets a knowledge-base answer, so in
   production the ONLY symptom of a broken tunnel is that replies stop being
   paraphrased. This prints the resolved config, reachability, latency, tokens,
   and on failure the provider's own words — "model 'x' not found", "requires
   more system memory", a refused connection.

   Run it inside the container, not on the host: the whole point is to test the
   path the container has. The VPS is shared with panelesa and the SENA tunnel
   is already bound to panelesa's compose gateway (172.18.0.1), so what this
   really checks is whether this container can cross to that bridge.
   =========================================================================== */
import { complete, llmConfigured, provider, model } from '../lib/chat-llm.js';
import { kbSize, kbGenerated, retrieve } from '../lib/chat-kb.js';

const log = { warn: (o, m) => console.error('  ↳', m, JSON.stringify(o)), info: () => {} };

console.log('Coffee Pie chat — sonda\n');
console.log('  proveedor      ', provider());
console.log('  modelo         ', model());
console.log('  base URL       ', process.env.CHAT_BASE_URL || '(n/a)');
console.log('  timeout        ', (process.env.CHAT_TIMEOUT_MS || '30000') + ' ms');
console.log('  configurado    ', llmConfigured() ? 'sí' : 'NO — respondería sólo desde la base de conocimiento');
console.log('  base conocim.  ', kbSize + ' entradas, generada ' + (kbGenerated || '(desconocido)'));

const hits = retrieve('cuánto cuesta un slice', 2);
console.log('  recuperación   ', hits.length ? `ok — "${hits[0].entry.title}" (${hits[0].score.toFixed(1)})` : 'SIN RESULTADOS — revisa data/chat-kb.json');

if (!llmConfigured()) {
  console.log('\nSin modelo configurado: no hay nada más que sondear.');
  process.exit(1);
}

console.log('\nLlamando al modelo…');
const t0 = Date.now();
let usage = null;
const out = await complete({
  system: 'Responde en español, en una sola frase corta.',
  messages: [{ role: 'user', content: 'Di exactamente: la sonda funciona.' }],
  maxTokens: 40, log, onUsage: (u) => { usage = u; }
});
const ms = Date.now() - t0;

if (out === null) {
  console.log(`\n✗ el modelo no respondió (${ms} ms). El motivo del proveedor va arriba.`);
  console.log('  Comprobaciones habituales:');
  console.log('   · ¿vive el túnel?      ss -ltnp | grep 11434        (en el VPS)');
  console.log('   · ¿responde Ollama?    curl -s 127.0.0.1:11434/api/tags | head -c 200');
  console.log('   · ¿ve el contenedor al bridge de panelesa? CHAT_BASE_URL debe ser 172.18.0.1, no 127.0.0.1');
  console.log('   · si no cruza entre bridges: añade -R 172.19.0.1:11434 al túnel + permitlisten (README)');
  process.exit(1);
}

console.log(`\n✓ respuesta en ${ms} ms`);
console.log('  texto  ', JSON.stringify(out.slice(0, 120)));
console.log('  tokens ', usage ? `${usage.in} entrada / ${usage.out} salida` : '(el servidor no los reporta — normal en local)');
if (ms > 20000) console.log('\n  ⚠ más de 20 s. Con CHAT_TIMEOUT_MS=30000 vas justo: considera un modelo menor o subir el timeout.');
