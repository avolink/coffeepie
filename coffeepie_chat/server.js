/* ===========================================================================
   Coffee Pie® — public web assistant. Entry point.

   This service exists as its OWN container, separate from the panel backend,
   and that separation is the security design, not an accident of packaging.

   The panel backend holds Proxmox root credentials, the Supabase service key
   and the ability to start, resize and delete customer machines. A public
   endpoint that feeds visitor text to a language model has no business sharing
   a process with any of that. Here there is no database driver, no hypervisor
   client and no identity secret to leak — a prompt cannot talk this process
   into reaching something it never imported.

   What it does hold: one static JSON knowledge base built from the PUBLIC
   website, and an HTTP client for whichever model is configured.

   Run locally:  cd coffeepie_chat && npm install && npm run kb && npm run dev
   Deploy:       see README.md (Docker Compose behind the VPS nginx)
   =========================================================================== */

import Fastify from 'fastify';
import cors from '@fastify/cors';
import rateLimit from '@fastify/rate-limit';
import chatRoutes from './routes/chat.js';

const PORT = parseInt(process.env.PORT || '8791', 10);
const ORIGINS = (process.env.ALLOWED_ORIGINS || 'https://coffeepie.co,https://www.coffeepie.co')
  .split(',').map((s) => s.trim()).filter(Boolean);

const app = Fastify({
  logger: { level: process.env.LOG_LEVEL || 'info' },
  bodyLimit: 32 * 1024,          // a chat turn is tiny — cap abuse early
  trustProxy: true               // nginx terminates TLS in front of us
});

await app.register(cors, {
  // CHAT_DEV=1 opens CORS for local work only. In production the widget is
  // served from coffeepie.co, so the allow-list is the whole story.
  origin: process.env.CHAT_DEV === '1' ? true : ORIGINS,
  methods: ['GET', 'POST'],
  allowedHeaders: ['Content-Type']
  // No Authorization header: the assistant is anonymous by design. It never
  // sees a session token, so it can never act on a visitor's behalf.
});

await app.register(rateLimit, {
  max: parseInt(process.env.RATE_LIMIT_MAX || '60', 10),
  timeWindow: '1 minute'
});

app.get('/healthz', async () => ({ ok: true, service: 'coffeepie-chat', ts: new Date().toISOString() }));

await app.register(chatRoutes);

app.setErrorHandler((err, req, reply) => {
  const code = err.statusCode && err.statusCode >= 400 ? err.statusCode : 500;
  if (code >= 500) req.log.error(err);
  reply.code(code).send({ error: code >= 500 ? 'internal' : 'bad_request', message: code >= 500 ? 'Error interno.' : err.message });
});

app.listen({ port: PORT, host: '0.0.0.0' })
  .then(() => app.log.info(`Coffee Pie chat listening on :${PORT}`))
  .catch((err) => { app.log.error(err); process.exit(1); });
