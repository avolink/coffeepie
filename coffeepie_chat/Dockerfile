# Coffee Pie chat image. node:20-slim (Debian/glibc): LTS, matches package.json
# engines >=20, and avoids the npm "Exit handler never called" flakiness seen on
# node:*-alpine. ~200 MB, small enough for the VPS disk budget.
FROM node:20-slim

ENV NODE_ENV=production
WORKDIR /app

# Prod deps from the lockfile, for a reproducible build.
COPY package.json package-lock.json* ./
RUN npm ci --omit=dev --no-audit --no-fund

COPY server.js ./
COPY lib ./lib
COPY routes ./routes
COPY tools ./tools
COPY data ./data
# ^ data/chat-kb.json — the assistant's knowledge base, generated from the
#   PUBLIC site by tools/gen-kb.mjs. Regenerate + rebuild when public copy
#   changes, otherwise the container keeps answering from the old site.

USER node
EXPOSE 8791

# Healthcheck through node itself — slim has no curl or wget.
HEALTHCHECK --interval=30s --timeout=3s --retries=3 CMD \
  node -e "require('http').get('http://127.0.0.1:8791/healthz',r=>process.exit(r.statusCode===200?0:1)).on('error',()=>process.exit(1))"

CMD ["node", "server.js"]
