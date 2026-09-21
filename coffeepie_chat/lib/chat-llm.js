/* ===========================================================================
   The assistant's language-model backend — one small adapter, two wire formats.

   routes/chat.js owns every guardrail: what context the model may see, the
   injection pre-filter, the leak post-filter and the link allow-list. None of
   that depends on WHICH model answers, so the model is a config choice, not an
   architectural one:

     CHAT_PROVIDER=openai      (default) → any OpenAI-compatible /chat/completions
     CHAT_PROVIDER=anthropic             → api.anthropic.com, Claude

   The default is the generic one because Coffee Pie serves its own model: the
   Quadro RTX 5000 in the SENA box, reached over a reverse SSH tunnel. Ollama,
   llama.cpp's server, vLLM and LM Studio all speak this format.

     CHAT_PROVIDER=openai
     CHAT_BASE_URL=http://172.18.0.1:11434/v1
     CHAT_MODEL=qwen2.5:14b-instruct-q4_K_M
     CHAT_API_KEY=            (empty: a local server asks for no key)

   Switching backends is an .env edit and a container restart — no code change
   and, crucially, no guardrail change. That matters most with a small
   self-hosted model, which is far likelier than Claude to wander off the
   "answer only from the context" rule; the output filters are what catch it.
   =========================================================================== */

const TIMEOUT_MS = parseInt(process.env.CHAT_TIMEOUT_MS || '30000', 10);
/* A 14B on one GPU is slower than a hosted API — 30 s by default, not 15.
   The route falls back to a knowledge-base answer on timeout, so a slow model
   degrades the reply, never the page. */

/* The provider's own words on a failure — "model not found", "requires more
   system memory than is available", a refused connection. Without this the
   operator sees a bare fallback and has to guess. It goes to the container log
   only; the visitor always gets the neutral knowledge-base answer. */
async function errText(res) {
  try {
    const body = await res.text();
    const j = JSON.parse(body);
    const m = j?.error?.message || j?.error || j?.message || body;
    return String(typeof m === 'string' ? m : JSON.stringify(m)).slice(0, 200);
  } catch (e) { return ''; }
}

export const provider = () => (process.env.CHAT_PROVIDER || 'openai').toLowerCase();
export const model = () =>
  process.env.CHAT_MODEL || (provider() === 'anthropic' ? 'claude-haiku-4-5' : 'local-model');

/* A local server needs no key, so "configured" cannot just mean "key present". */
export function llmConfigured() {
  return provider() === 'anthropic' ? !!process.env.ANTHROPIC_API_KEY : !!process.env.CHAT_BASE_URL;
}

async function callAnthropic(system, messages, maxTokens) {
  const res = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      'x-api-key': process.env.ANTHROPIC_API_KEY,
      'anthropic-version': '2023-06-01'
    },
    body: JSON.stringify({ model: model(), max_tokens: maxTokens, temperature: 0.2, system, messages }),
    signal: AbortSignal.timeout(TIMEOUT_MS)
  });
  if (!res.ok) return { ok: false, status: res.status, detail: await errText(res) };
  const data = await res.json();
  const text = (data.content || []).filter((c) => c.type === 'text').map((c) => c.text).join('\n').trim();
  const u = data.usage || {};
  return { ok: true, text, usage: { in: u.input_tokens || 0, out: u.output_tokens || 0 } };
}

/* OpenAI-compatible: the system prompt is the first message, and the reply is
   choices[0].message.content. Everything else is the same shape. */
async function callOpenAICompatible(system, messages, maxTokens) {
  const base = (process.env.CHAT_BASE_URL || '').replace(/\/+$/, '');
  const headers = { 'content-type': 'application/json' };
  if (process.env.CHAT_API_KEY) headers.authorization = 'Bearer ' + process.env.CHAT_API_KEY;
  const res = await fetch(base + '/chat/completions', {
    method: 'POST',
    headers,
    body: JSON.stringify({
      model: model(), max_tokens: maxTokens, temperature: 0.2, stream: false,
      messages: [{ role: 'system', content: system }, ...messages]
    }),
    signal: AbortSignal.timeout(TIMEOUT_MS)
  });
  if (!res.ok) return { ok: false, status: res.status, detail: await errText(res) };
  const data = await res.json();
  const text = ((data.choices || [])[0]?.message?.content || '').trim();
  const u = data.usage || {};   // same numbers, different field names than Anthropic
  return { ok: true, text, usage: { in: u.prompt_tokens || 0, out: u.completion_tokens || 0 } };
}

/* Returns the answer text, or null on any failure — the caller falls back to a
   knowledge-base answer, so a model outage is never a site outage.

   `onUsage` receives {in, out} token counts. Both wire formats report them; a
   local server that doesn't simply reports zeros, which is honest — tokens on
   our own GPU cost nothing. */
export async function complete({ system, messages, maxTokens = 400, log, onUsage }) {
  if (!llmConfigured()) return null;
  const r = provider() === 'anthropic'
    ? await callAnthropic(system, messages, maxTokens)
    : await callOpenAICompatible(system, messages, maxTokens);
  if (!r.ok) {
    if (log) log.warn({ status: r.status, provider: provider(), model: model(), detail: r.detail || '' }, 'chat: model call failed');
    return null;
  }
  if (onUsage && r.usage) onUsage(r.usage);
  return r.text || null;
}
