# Moving coffeepie.co from the Namecheap VPS to the SENA server

**Goal.** Free the VPS (209.74.89.188) so it carries only what must not break —
panelesa.com and grupo3p1.co, sites and mail — and move Coffee Pie onto the
self-hosted SENA machine at the office, where the experimental work already
lives next to the RTX 5000.

**Scope.** A new Ubuntu Minimal VM on the SENA Proxmox host serving the static
site, fronting the assistant, and (conditionally — see §6) hosting mail.

Nothing here is destructive to the VPS. The old vhost stays in place and
serving until DNS moves, and stays *configured* for a fortnight after, because
that is the rollback.

---

## 0. Start here: three facts that decide the whole plan

None of the rest is worth building until these are answered. Each has to be
tested **from outside the office network** — a phone on mobile data, or a
shell on the VPS. Testing from inside the office proves nothing: see the
warning at the end of this section.

| # | Question | How to answer it | If the answer is no |
|---|---|---|---|
| 0.1 | Is TCP **80 and 443** reachable from the public internet to the SENA IP? | From the VPS: `nc -vz 206.62.137.22 80` and `443` | No direct hosting. Fall back to a Cloudflare Tunnel (§7) — the site still moves, the ports do not have to open. |
| 0.2 | Is TCP **25** reachable **inbound**, and is outbound 25 unblocked? | Inbound: `nc -vz 206.62.137.22 25`. Outbound, from the VM: `nc -vz gmail-smtp-in.l.google.com 25` | Mail does not move. Keep Namecheap forwarding, or relay (§6). |
| 0.3 | Can you set the **PTR / reverse DNS** for 206.62.137.22? | Ask whoever administers the IP block (SENA network, or their ISP) | Do not self-host outbound mail at all. Relay it (§6). |

**Why the tests must run from outside.** Probing 206.62.137.22 from a machine
on the office LAN answers a different question. A probe of port 80 from here
returns, in 1.3 ms:

```
HTTP/1.1 403 Forbidden
Rejected request from RFC1918 IP to public server address
```

That is the office router refusing to hairpin a LAN client back to its own
public address — not the SENA server, which never saw the packet. A local
"open" or "closed" result is noise either way.

**Current state, measured 2026-08-09** (authoritative, from 8.8.8.8):

- `coffeepie.co` → 209.74.89.188 (the VPS)
- `www.coffeepie.co` → 209.74.89.188
- `api.coffeepie.co` → 209.74.89.188 — resolves, serves nothing; the panel
  backend was never deployed there
- `MX` → `eforward1..5.registrar-servers.com` — **Namecheap email
  forwarding.** Coffee Pie mail has never been on the VPS. Moving the website
  therefore cannot break mail, and "migrating email" here means going from
  forwarding to real self-hosted mailboxes, which is a new capability rather
  than a move.
- `NS` → `dns1/dns2.registrar-servers.com` — Namecheap BasicDNS, records
  edited in the Namecheap panel.

---

## 1. The VM

On the Proxmox host. Ubuntu Minimal 24.04, not a container: mail wants its own
kernel-level isolation, and a VM can be snapshotted and rolled back whole.

- 2 vCPU, 4 GB RAM, 40 GB disk. The site is 169 MB; the headroom is for mail
  spool and logs.
- Static IP on the internal bridge. Write it down — the nginx and firewall
  steps below need it.
- Hostname `web.coffeepie.co` if it will also do mail; the mail hostname must
  match the PTR record eventually.

```bash
apt update && apt install -y nginx git git-lfs rsync certbot python3-certbot-nginx
git lfs install
```

**`git-lfs` is not optional.** The repo keeps its media in LFS, and a clone
without it produces 130-byte text pointers where the images should be. That
already shipped to production once: every image on the site 404-ed in effect
while returning HTTP 200, which is why `scripts/check-lfs-pointers.sh` exists
and why step 2 runs it.

---

## 2. The site

```bash
sudo mkdir -p /opt /var/www/coffeepie.co
sudo git clone https://github.com/avolink/coffeepie.git /opt/coffeepie
cd /opt/coffeepie
bash scripts/check-lfs-pointers.sh          # must print no pointers
sudo rsync -a --delete coffeepie_website/public/ /var/www/coffeepie.co/
sudo chown -R www-data:www-data /var/www/coffeepie.co
```

Deploying is those last two commands after a `git pull`, exactly like the VPS.
The clone and the web root are separate on purpose — the same two-step the VPS
uses, where a `git pull` alone changes nothing live.

### The vhost

`coffeepie.co.nginx.conf` in this directory is **generated** from
`coffeepie_website/firebase.json`, which is the source of truth for the URL
behaviour: 31 rewrites, 20 redirects, cleanUrls, and the cache headers.

```bash
node coffeepie_website/deploy/gen-coffeepie-nginx.mjs
bash coffeepie_website/deploy/verify-nginx-vhost.sh   # 26 checks, real nginx
```

The verifier runs the config in a throwaway nginx container against a fixture
tree and asserts observed behaviour — `/manufacturers` resolves, `/index.html`
redirects to `/` and not to `/index`, `/package.json` is unreachable, the
security headers survive. `nginx -t` alone cannot tell you any of that.

If the assistant is not on this VM, regenerate pointing at it:

```bash
CHAT_UPSTREAM=10.0.0.X:8791 node coffeepie_website/deploy/gen-coffeepie-nginx.mjs
```

Install:

```bash
sudo cp coffeepie_website/deploy/coffeepie.co.nginx.conf /etc/nginx/sites-available/coffeepie.co
sudo ln -sf /etc/nginx/sites-available/coffeepie.co /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

### Prove it before DNS moves

From the VPS or a phone, with no DNS change anywhere:

```bash
curl -sI --resolve coffeepie.co:80:206.62.137.22 http://coffeepie.co/manufacturers
curl -s  --resolve coffeepie.co:80:206.62.137.22 http://coffeepie.co/ | head -5
```

`--resolve` is the whole trick: it sends the right `Host` header to the new
box while the world still goes to the old one. Walk the real nav — `/`,
`/pricing`, `/store`, `/manufacturers`, `/panel`, `/machines` — before
believing the migration.

---

## 3. TLS

Only after DNS points here (§5), because HTTP-01 validation resolves the name
from the public internet.

```bash
sudo certbot --nginx -d coffeepie.co -d www.coffeepie.co
```

Certbot edits the vhost in place to add the `:443` block and the redirect.
**Re-running the generator overwrites those edits** — after any regeneration,
run `sudo certbot --nginx` again (it is idempotent) or keep the TLS block in a
separate include.

To avoid an HTTP-only window at cutover, copy the live cert and key off the
VPS (`/home/admin/conf/web/coffeepie.co/ssl/`) into the VM before flipping
DNS; it stays valid until its expiry regardless of where it is served from,
and certbot takes over renewals afterwards.

---

## 4. The assistant

Moving the site to SENA removes the fragile part of the chat design. On the
VPS the container reached the model through an `autossh` reverse tunnel bound
to the Docker bridge, which needed a Hestia firewall rule to let the bridge
subnet through, and which `docker compose down` would silently kill. On the
SENA side the model (LXC 110, `LLM`, `gemma3:12b` on the RTX 5000) is simply
another host on the internal network.

- Point the chat service at the model directly: `OPENAI_BASE_URL=http://<LLM-CT-IP>:11434/v1`.
- **Delete the tunnel** once the site is cut over — the `autossh` unit, the
  `permitlisten` entry, and the `v-add-firewall-rule` on the VPS. Leaving a
  dead reverse tunnel is a standing hole for no benefit.
- The `/v1/chat` and `/v1/chat/health` proxy lines are already in the
  generated vhost, same origin as the page so there is no CORS preflight.
- Both sites share one GPU, so both must stay on the same model. That
  constraint does not change by moving.

Keep `coffeepie_chat` a separate container from anything with database or
hypervisor access; `test/no-private-imports.test.js` enforces it.

---

## 5. DNS cutover

1. **24 hours ahead**, drop the TTL on `coffeepie.co` and `www` to 300 in the
   Namecheap panel. Everything below depends on this — at the default TTL a
   bad cutover is stuck for hours.
2. Verify §2 with `--resolve`. Do not skip it.
3. Flip the A records for `coffeepie.co` and `www` to 206.62.137.22.
   **Leave MX alone** (§6). Leave `api.coffeepie.co` alone — it is broken
   today and moving it changes nothing.
4. Watch: `watch -n5 'curl -sI https://coffeepie.co | head -1'`, and the VM's
   `tail -f /var/log/nginx/access.log` to see real traffic arrive.
5. Issue the cert (§3) if you did not pre-seed it.

**Rollback** is putting the A records back. Which only works if you did step 1,
and if the VPS vhost is untouched — so do not delete anything there for two
weeks. Keep the TTL low for that fortnight too; borrowed hardware earns a
shorter leash than a paid VPS.

---

## 6. Mail — read before doing anything

Self-hosting mail on an office connection is the highest-risk item here and
the one with the least to gain, because Coffee Pie mail costs nothing today.
Three things have to be true, and 0.3 is usually the one that is not:

- inbound 25 reachable, or no mail arrives;
- outbound 25 allowed, or nothing you send leaves;
- a PTR record for 206.62.137.22 matching the mail hostname. Gmail and
  Outlook reject or spam-file mail from an IP with no matching reverse DNS,
  and an institutional range typically also sits on Spamhaus' PBL.

**Recommended split**, which is what panelesa already does on the VPS:

- **Inbound**: real mailboxes on the VM (Postfix + Dovecot), MX pointed at
  it — only if 0.2 says inbound 25 is reachable.
- **Outbound**: relay through SMTP2GO rather than sending direct. The
  reputation, SPF alignment and DKIM signing are theirs, the PTR problem stops
  mattering, and there is already an account.

**If 0.2 or 0.3 fails, do not move mail.** Namecheap forwarding keeps working
untouched while the website moves — the A records and the MX records are
independent. That is a legitimate end state, not a failure.

Sequence mail *after* the website is cut over and stable. Two migrations at
once share one blast radius.

---

## 7. If the ports cannot open

If 0.1 fails — likely on an institutional network — the site still moves. Run
a Cloudflare Tunnel: `cloudflared` on the VM makes an outbound connection, so
nothing has to be forwarded and no inbound port opens.

What changes: DNS becomes a CNAME to the tunnel instead of an A record;
Cloudflare terminates TLS, so skip §3 and certbot entirely; the vhost keeps
its `:80` block exactly as generated, which is why it is generated HTTP-only.

What it costs: Cloudflare sees the plaintext traffic, and the site depends on
a third party the VPS did not need. For a static marketing site, that is a
reasonable trade. It would be a worse one for mail — tunnels do not carry SMTP.

---

## 8. Decommission, two weeks later

Once traffic has been on SENA long enough to trust:

- Remove the coffeepie.co vhost and web root from the VPS.
- Remove the chat container, the autossh tunnel unit and its firewall rule
  from the VPS (§4).
- Leave `api.coffeepie.co` pointing at the VPS or repoint it — decide when
  the panel backend actually gets deployed somewhere.
- Raise the DNS TTL back to something ordinary.

---

## Open items this document does not resolve

- **The three checks in §0.** Everything is gated on them and none can be run
  from here.
- **`api.coffeepie.co`** serves nothing on either host. The panel backend has
  never been deployed; `machines.html` talking to a real hypervisor still
  depends on it. Out of scope here, tracked in `handoff.md` §5.3.
- **The VPS still has an unpublished change.** The WhatsApp-bubble removal was
  pulled but never rsynced to the web root, so it is not live. Publish it
  there — the VPS serves the site until cutover.
