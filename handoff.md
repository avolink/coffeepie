# Handoff — 2026-07-27

Session on `main`, repo `github.com/avolink/coffeepie`. Everything described here
is committed and pushed. Head at handoff: `9743d3372`.

---

## 1. Objective

Seven things, in the order they came up:

1. **Fix `coffeepie.co/manufacturers`** — production showed a full-screen grey
   "Este contenido está bloqueado" instead of the page.
2. **Make Advanced mode useful** on `machines.html` — the table shipped
   placeholder columns (Tostado / Cuerpo / Perfil) and had no way to create a
   machine.
3. **Switches must not fire on a click** — "mantener encendida" powers a real VM
   off; a stray tap was too cheap.
4. **Reload / back buttons should match the Qt GUI** exactly.
5. **Build an AI assistant** for Coffee Pie, modelled on the one already live on
   panelesa.com, served from our own GPU.
6. **Fix broken images** appearing across the site.
7. **Restore `api.coffeepie.co`** so panel → Proxmox testing can resume against
   the SENA node.

---

## 2. Ending Status

### Done, verified, and live in production
- `/manufacturers` renders. Root cause was **not** the 404 first suspected — see §4.
- All **58 broken media files** restored. `git-lfs` is now installed on the VPS.
- Advanced-mode table, drag-only switches, Qt buttons — deployed via rsync.
- WhatsApp floating bubble removed from 5 pages.

### Done and pushed, NOT yet live
- **The assistant.** The widget is deployed and visible (its launcher shows on
  the site), but the backend container is not running and nginx has no route to
  it, so it falls back to "no pude conectarme". Needs §5.2.
- **WhatsApp removal** — committed and pulled on the VPS, but the rsync to the
  web root never ran (a `sudo cd` failed). Still visible live until §5.1.

### Known broken, not caused by this session
- **`api.coffeepie.co` is down two ways**: `nginx.forcessl.conf` has an
  unconditional `return 301` and is included from `nginx.ssl.conf` too (infinite
  redirect), *and* nothing listens on `:8000` — the panel backend was **never
  deployed to production**. Earlier successful Proxmox tests ran against
  `localhost:8000`. Runbook written: `coffeepie_backend/panel_backend/deploy/VPS-DEPLOY.md`.
- **Repo hygiene**: `graphify-out/graph.json` (75 MB) and the whole AST cache are
  versioned. `graphify-out/.rebuild.lock` is tracked and holds dead PID 35574 —
  it will block the next graphify run until cleared.

### Infrastructure facts established this session
- **One VPS serves everything**: `coffeepie.co`, `api.coffeepie.co`,
  `panelesa.com`, `api.panelesa.com` → **209.74.89.188** (HestiaCP). Coffee Pie's
  own Proxmox is not involved in any of this.
- **The model box** is the SENA Proxmox host; `pct enter 110`, container renamed
  `panelesa-llm` → **`LLM`** because it now serves both sites. Quadro RTX 5000,
  **16 GB**, running `gemma3:12b`, reachable via an existing autossh reverse
  tunnel bound to `172.18.0.1:11434`. Verified alive:
  `api.panelesa.com/v1/chat/health` → `model:"on"`.
- **One GPU, one model.** 8.1 GB (gemma3:12b) + 9 GB (a 14B) > 16 GB, so a
  different model per site makes Ollama evict and reload on alternating
  requests and both sites crawl.

---

## 3. Files and Changes

### Commits (oldest first)
| Commit | What |
|---|---|
| `8e71765a0` | `.download` 404 fix on manufacturers.html (real bug, wrong hypothesis) |
| `9ca838234` | Removed Wix `browser-deprecation` script from all 14 pages — the actual fix |
| `a1436e1b3` | `scripts/check-lfs-pointers.sh` + tutorials.html video path |
| `3abb8c071` | `coffeepie_chat/` — the assistant service |
| `2f67fa30b` | Site: widget, Advanced mode, switches, Qt buttons |
| `2e6b803da` | `panel_backend/deploy/VPS-DEPLOY.md` runbook |
| `9743d3372` | WhatsApp bubble removed from 5 pages |

### New: `coffeepie_chat/` — isolated assistant service
Node 20 / Fastify, **its own container by design**. `panel_backend` holds Proxmox
root credentials, the Supabase service key and the power to delete customer
machines; a public LLM endpoint must not share that process.

```
server.js                      Fastify bootstrap, CORS allow-list, :8791
routes/chat.js                 all guardrails; imports ONLY lib/*
lib/chat-kb.js                 retrieval; reads one static JSON, no network
lib/chat-llm.js                provider adapter (openai-compatible | anthropic)
data/chat-kb.json              generated, 57 entries — COMMITTED so the VPS needs no Node
tools/gen-kb.mjs               builds the KB from the public site
tools/kb-eval.mjs              retrieval smoke test, 18/18
tools/chat-probe.mjs           run INSIDE the container to test the model path
test/no-private-imports.test.js  fails the build if a DB/hypervisor/auth import appears
test/chat.test.js              guardrail unit tests
Dockerfile, docker-compose.yml, .env.example, deploy/nginx-chat.conf, README.md
```

**Dependency map (established empirically, not from the graph):**
- `routes/chat.js` → `lib/chat-kb.js`, `lib/chat-llm.js`. Nothing else. Enforced by test.
- `lib/chat-kb.js` → `data/chat-kb.json` only.
- `tools/gen-kb.mjs` → `../coffeepie_website/public/` (page allow-list) **and**
  `public/js/cp-machines.js`, which it parses for `PER_SLICE`, `RATE`,
  `REC_PRICES` and the **OS catalog**. If those constant names change, the KB
  silently loses that content — the generator warns but does not fail.
- `public/chat.json` is read by **both** the widget and `gen-kb.mjs`. One file so
  the menu and the retrievable text cannot drift.

### Website changes
| File | Change |
|---|---|
| `public/js/cp-chat.js` | new — widget; API base is **same-origin** in prod |
| `public/css/cp-chat.css` | new — uses `var(--cp-*, fallback)` so it works on Wix pages that define no tokens |
| `public/chat.json` | new — guided menu (Spanish only, see §4) |
| `public/footer.js` | injects the widget site-wide; **only script every Wix page loads** |
| `public/js/cp-switch.js` | new — drag-to-toggle, both switch skins, 7 switches |
| `public/js/cp-machines.js` | Advanced table columns, apply-tick, auth modal, support buttons open the chat |
| `public/js/cp-panel-auth.js` | new `reauth()` — step-up auth; keeps Supabase keys in one file |
| `public/machines.html` | table columns + dark theme + new-machine row + Qt buttons + chat tags |
| `public/panel.html` | chat tags |
| `public/assets/machines/Back_Button.png` | new — copied from the Qt GUI, md5-identical |
| `scripts/check-lfs-pointers.sh` | new — deploy guard |

### Graph status
`graphify-out/` was built **18 July** (2,805 files) and is stale. It contains
`cp-machines.js`, `cp-panel-auth.js`, `panel_backend/app/main.py` — but **not**
`coffeepie_chat/*`, `cp-chat.js`, `cp-switch.js` or `check-lfs-pointers.sh`.
Rebuild before relying on it (`graphify update .` from WSL, AST-only, ~30 min);
clear the stale lock first.

---

## 4. Failed Paths and Tests

Recorded because each cost real time and would cost it again.

**The `.download` 404 was the wrong root cause.** `/manufacturers` looked like a
missing-asset problem. It was Wix's `browser-deprecation` script: it probes
ES2017 with `new Function()`, our CSP has no `'unsafe-eval'`, the throw is caught
and read as "old browser", and it then wipes `#SITE_CONTAINER` and overlays an
iframe that `frame-src` also blocks. A deploy was spent on the wrong fix. The
lesson: **prove it with a controlled A/B**, which is what finally isolated it.

**Only that page broke because of MIME, not code.** The other 13 pages reference
`..._<page>.download` variants served with no `Content-Type`, so `nosniff` makes
Chrome refuse them. They were safe *by accident*. All 14 tags removed.

**`curl -w '%{http_code}'` is not an image check.** LFS pointers return **200 OK**
with `Content-Type: image/png` and 130 bytes of text. This produced a confident
and wrong "the images are fixed". Check magic bytes: `89504e47` = PNG,
`76657273` = `vers…` = pointer.

**My first LFS guard silently passed.** `find -size -1k` rounds **up**, so a
129-byte file counts as 1k and only 0-byte files matched. A negative test — feed
it a real pointer, demand a non-zero exit — caught it. Now `-size -2000c`.
The same bug had been in an ad-hoc check earlier, which is why I wrongly told the
user their local copies were all real; two (`images/hero-video.mp4`,
`images/logo.png`) were pointers and were restored with `git lfs checkout`.

**A global `str.replace` turned a 1-hunk edit into 40.** Removing the WhatsApp
block, I "tidied" the gap with `'\n\n\n' → '\n\n'`, which collapsed blank lines
across the whole document. Caught by counting diff hunks — a single-block removal
must produce exactly one. Reverted all 5 files and redid it.

**Assumed a second SSH tunnel was needed.** Wrong: both sites share one VPS, and
panelesa's tunnel already terminates there. What *is* needed is a firewall rule,
because Hestia's `-P INPUT DROP` and the existing ACCEPT rule is scoped to
`172.18.0.0/16` while this container sits on `172.19.0.0/16`.

**Assumed `api.coffeepie.co` served the panel backend.** It serves nothing.

**`/healthz` vs `/health`.** panelesa's API uses the former; `panel_backend` uses
the latter. Told the user the wrong one more than once.

**Chained `apt-get update && apt-get install`.** A pre-existing broken Docker repo
(stray `\` in `docker.list`) made `update` exit non-zero, so the install never
ran and `git lfs` appeared "not a git command".

### Verification that did work
- Controlled A/B with the production CSP toggled — isolated the deprecation bug.
- `tools/kb-eval.mjs` — 18/18, incl. a "known-weak" bucket that asserts a
  bag-of-words retriever *stays* weak rather than pretending it can improve.
- `npm test` in `coffeepie_chat` — 16/16.
- Negative tests on the LFS guard.
- Browser-pane DOM assertions for every UI change.
  ⚠ The pane **never composites frames** here: screenshots always fail, and CSS
  transitions do not advance. Read animated values with transitions disabled.

---

## 5. Following Steps

### 5.1 Finish what is already pushed (5 minutes)
Ownership first — earlier steps ran as `root` inside `admin`'s home, which is why
git now refuses with "dubious ownership":
```bash
sudo chown -R admin:admin /home/admin/coffeepie
git config --global --unset-all safe.directory      # drop the bad trailing-slash entry
cd /home/admin/coffeepie && git pull
rsync -av coffeepie_website/public/ /home/admin/web/coffeepie.co/public_html/
```
That publishes the WhatsApp removal. (`sudo cd` can never work — `cd` is a shell
builtin.)

### 5.2 Bring the assistant up
```bash
cd /home/admin/coffeepie/coffeepie_chat
cp .env.example .env          # choose CHAT_MODEL — see the GPU note in §2
docker compose up -d --build  # never `down` first: it deletes the bridge and kills the tunnel
```
Then the **mandatory** firewall rule (the existing one only covers panelesa's subnet):
```bash
v-add-firewall-rule ACCEPT 172.19.0.0/16 11434 TCP coffeepie-chat-llm
docker compose exec chat node tools/chat-probe.mjs
```
Then paste `coffeepie_chat/deploy/nginx-chat.conf` into Hestia → Web →
**coffeepie.co** → Nginx Additional directives. Verify:
`curl -s https://coffeepie.co/v1/chat/health` → `{"ok":true,"kb":57,"model":"on"}`.

### 5.3 Restore `api.coffeepie.co` and resume Proxmox testing
Full runbook: `coffeepie_backend/panel_backend/deploy/VPS-DEPLOY.md`. Order:
1. Make the forcessl rule scheme-aware (do not just delete the include — Hestia
   regenerates vhosts). A 502 afterwards is progress.
2. venv + `.env` + `systemctl enable --now coffeepie-panel` (systemd, not Docker).
3. nginx `proxy_pass` → `127.0.0.1:8000`, **with `Upgrade`/`Connection` headers** —
   `stream_routes.py` relays websockets to Proxmox `vncwebsocket`; without them
   the panel works and streaming dies far from the cause.
4. Chain test, then create a VM and watch `journalctl -u coffeepie-panel -f`.

⚠ **`NODE_CRED_ENC_KEY` must be the key that encrypted.** The Proxmox root
password for `206.62.137.22` is Fernet-encrypted in Supabase, almost certainly
with the QA default from `app/auth/node_credentials.py`. A fresh key in
production makes it undecryptable, and it surfaces as "Proxmox rejected the
credentials". Carry the key over, or re-register the node.

### 5.4 Backlog
- **Assistant menu is Spanish-only.** Answers are translated (the route pins the
  language for the model) and panel chrome is es/en, but `chat.json` buttons are
  not. Largest visible gap on a 12-language site.
- **Merge the two assistants?** Discussed and *deliberately declined*: cross-site
  answers would read unprofessional. Revisit only if maintaining two copies of
  the guardrails becomes painful — and then share the code, not the process.
- **Repo hygiene**: 75 MB `graph.json` + AST cache are versioned; `.rebuild.lock`
  is tracked and stale.
- **Docker apt repo** has a stray `\` in `/etc/apt/sources.list.d/docker.list`.
- **Language**: the `coffeepie_chat` README and this session's commit messages
  were written in **Spanish**, against the standing preference for English in
  reports/commits/comments. Normalise if that still holds.
