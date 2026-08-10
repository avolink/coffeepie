#!/usr/bin/env node
/* ===========================================================================
   Generates deploy/coffeepie.co.nginx.conf from firebase.json — a COMPLETE
   nginx vhost (not a snippet) for the Ubuntu Minimal VM on the SENA server,
   so it serves coffeepie.co with the same behaviour the site has today:
   cleanUrls, the redirect table, the rewrite table, and the cache headers.

   The VPS runs HestiaCP, which owns its vhosts and only lets you paste extra
   directives into a template. The SENA VM is plain nginx with no panel, so
   here we emit the whole `server {}` block and drop it in sites-available.

   Re-run whenever firebase.json's hosting rules change:
     node coffeepie_website/deploy/gen-coffeepie-nginx.mjs
   then, on the VM:  sudo nginx -t && sudo systemctl reload nginx

   Design notes
   ------------
   - HTTP-only on purpose. `certbot --nginx` rewrites this file in place to
     add the :443 block and the redirect once the cert exists. Emitting a
     :443 block up front is the classic chicken-and-egg: nginx refuses to
     start when ssl_certificate points at a file that is not there yet, and
     then the HTTP-01 challenge that would create it cannot be served.
   - No Content-Security-Policy. Deliberate: a CSP is what blanked
     /manufacturers in production (the Wix deprecation bundle needs eval, and
     the policy denied it, so the script wiped #SITE_CONTAINER). firebase.json
     does not define one either. If a CSP is ever added, ship it as
     Content-Security-Policy-Report-Only first and read the reports.
   - nginx's `rewrite` always takes a regex, so every firebase source becomes
     one: literals are escaped, `*` becomes `[^/]*`, and Firebase's `:param`
     placeholders become capture groups that the destination refers to as $1,
     $2 ... (only /productos/:slug* uses this today).
   - Ordering matters and is not cosmetic:
       hide rules -> redirects -> cleanUrls 301 -> rewrite table -> locations
     Redirects must precede the cleanUrls 301 or `/index.html` would land on
     `/index` instead of `/`. The cleanUrls 301 must precede the rewrite
     table so it only ever sees the client's original URL, never an
     internally-rewritten target (which has to serve, not redirect).
   =========================================================================== */

import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SITE = path.join(HERE, '..');
const fb = JSON.parse(readFileSync(path.join(SITE, 'firebase.json'), 'utf8')).hosting;

// Where the VM serves from, and where the assistant listens. Both are
// referenced by the runbook (deploy/SENA-MIGRATION.md) — keep them in step.
const ROOT = process.env.SITE_ROOT || '/var/www/coffeepie.co';
// 127.0.0.1 assumes the assistant container sits on the same VM. It does not
// have to: on the SENA side it may already be running next to the model, in
// which case regenerate with CHAT_UPSTREAM=10.x.x.x:8791 and the proxy_pass
// follows. Keep it an IP:port — nginx resolves names once at startup and then
// caches the answer forever, which is a bad trade for a container address.
const CHAT_UPSTREAM = process.env.CHAT_UPSTREAM || '127.0.0.1:8791';

function reEscape(s) {
  return s.replace(/[.+()[\]^$\\{}|?]/g, '\\$&');
}
function nginxQuote(s) {
  return '"' + String(s).replace(/\\/g, '\\\\').replace(/"/g, '\\"') + '"';
}

/* Firebase source -> { regex, params[] }.
   `:name*` swallows slashes (a whole trailing path), `:name` stops at the
   next segment boundary, and a bare `*` is a wildcard within one segment. */
function toRegex(source) {
  const params = [];
  let out = '';
  const re = /:([A-Za-z0-9_]+)(\*?)|\*/g;
  let last = 0, m;
  while ((m = re.exec(source)) !== null) {
    out += reEscape(source.slice(last, m.index));
    if (m[1]) {
      params.push(m[1]);
      out += m[2] ? '(.*)' : '([^/]+)';
    } else {
      out += '[^/]*';
    }
    last = m.index + m[0].length;
  }
  out += reEscape(source.slice(last));
  return { regex: '^' + out + '$', params };
}

/* Destination with :name placeholders swapped for the capture groups that
   the source produced, in the order the source declared them. */
function toTarget(destination, params) {
  let out = destination;
  params.forEach((name, i) => {
    out = out.split(':' + name).join('$' + (i + 1));
  });
  return out;
}

/* The firebase.json "**" header block. These have to be repeated inside every
   location that declares an add_header of its own: nginx does NOT merge
   add_header across levels — a single one in a location silently discards the
   whole inherited set. Emitting them once at server scope only protects the
   locations that add nothing, which is the opposite of what you want, since
   the locations that DO add something are the ones serving HTML and scripts. */
const SECURITY_HEADERS = [
  ['X-Content-Type-Options', 'nosniff'],
  ['X-Frame-Options', 'SAMEORIGIN'],
  ['Referrer-Policy', 'strict-origin-when-cross-origin'],
  ['Strict-Transport-Security', 'max-age=31536000; includeSubDomains'],
  ['Permissions-Policy', 'camera=(), microphone=(), geolocation=(self)'],
];
function sec(indent) {
  return SECURITY_HEADERS.map(([k, v]) => `${indent}add_header ${k} "${v}" always;`).join('\n');
}

function ruleLines(rules, flag) {
  return rules
    .map((r) => {
      const { regex, params } = toRegex(r.source);
      return `\trewrite ${nginxQuote(regex)} ${nginxQuote(toTarget(r.destination, params))} ${flag};`;
    })
    .join('\n');
}

const redirLines = ruleLines(fb.redirects, 'permanent');
const rewriteLines = ruleLines(fb.rewrites, 'last');

/* firebase.json "ignore" — these must not be publicly servable just because
   root points at the whole public/ tree. Globs are translated by hand rather
   than mechanically: the list is short and the failure mode of getting one
   wrong (exposing a source file) is worse than the duplication. */
const archiveExt = 'zip|rar|7z|tar|gz';

const conf = `# ============================================================================
# GENERATED FILE — do not hand-edit. Source of truth is coffeepie_website/firebase.json.
# Regenerate:  node coffeepie_website/deploy/gen-coffeepie-nginx.mjs
# ============================================================================
# ${fb.rewrites.length} rewrites and ${fb.redirects.length} redirects ported from firebase.json.
#
# Install on the SENA VM:
#   sudo cp coffeepie.co.nginx.conf /etc/nginx/sites-available/coffeepie.co
#   sudo ln -sf /etc/nginx/sites-available/coffeepie.co /etc/nginx/sites-enabled/
#   sudo rm -f /etc/nginx/sites-enabled/default
#   sudo nginx -t && sudo systemctl reload nginx
#
# TLS is NOT configured here. After DNS points at this host, run:
#   sudo certbot --nginx -d coffeepie.co -d www.coffeepie.co
# which edits this file in place to add :443 and the http->https redirect.
# Re-running the generator overwrites those edits — re-run certbot after.

server {
\tlisten 80;
\tlisten [::]:80;
\tserver_name coffeepie.co www.coffeepie.co;

\troot ${ROOT};
\tindex index.html;
\tcharset utf-8;

\t# Emit "Location: /pricing", not "Location: http://coffeepie.co/pricing".
\t# nginx builds absolute redirects from the scheme it thinks it is serving,
\t# which is wrong the moment anything fronts it — a tunnel, or certbot's
\t# :443 block proxying internally — and an http:// Location on an https
\t# page is a downgrade the browser has to be talked out of. Relative
\t# redirects cannot get the scheme or the host wrong.
\tabsolute_redirect off;

\t# Wix-era exports are heavy; 169 MB of assets over a self-hosted uplink.
\tgzip on;
\tgzip_vary on;
\tgzip_proxied any;
\tgzip_comp_level 6;
\tgzip_min_length 1024;
\tgzip_types text/plain text/css application/json application/javascript application/xml text/xml image/svg+xml;

\t# Uploads are not a thing here, but the assistant POSTs JSON.
\tclient_max_body_size 1m;

# ---- 1) never serve these, whatever the URL says (firebase "ignore") ----
\tlocation ~ /\\.(?!well-known/) { return 404; }        # dotfiles, keep ACME
\tlocation ~ ^/(node_modules|tools)/ { return 404; }
\tlocation ~ ^/(package\\.json|package-lock\\.json|firebase\\.json|firebase-debug\\.log)$ { return 404; }
\tlocation ~* \\.(${archiveExt}|py)$ { return 404; }

# ---- 1b) security headers (firebase.json "headers", the ** entry).
#          Repeated in every location below that sets Cache-Control — nginx
#          discards inherited add_header the moment a location declares one.
#          No CSP on purpose — see the header of the generator for why.
#          HSTS is inert over plain HTTP and takes effect once certbot has
#          added the TLS block. ----
${sec('\t')}

# ---- 2) explicit redirects, before cleanUrls (see generator header) ----
${redirLines}

# ---- 3) cleanUrls parity: a direct .html request 301s to the bare form ----
\tif ($request_uri ~ ^(.+)\\.html(\\?.*)?$) {
\t\treturn 301 $1$2;
\t}

# ---- 4) internal rewrite table (URL bar unchanged) ----
${rewriteLines}

# ---- 5) the assistant. Same origin as the page on purpose: no CORS
#         preflight, one less round trip, one less thing to misconfigure.
#         On this host the chat container reaches the model over the SENA
#         internal bridge, so the autossh tunnel the VPS needed is gone. ----
\tlocation = /v1/chat {
\t\tproxy_pass         http://${CHAT_UPSTREAM};
\t\tproxy_http_version 1.1;
\t\tproxy_set_header   Host              $host;
\t\tproxy_set_header   X-Real-IP         $remote_addr;
\t\tproxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
\t\tproxy_set_header   X-Forwarded-Proto $scheme;
\t\t# A cold prompt on one GPU is slow. The service gives up at
\t\t# CHAT_TIMEOUT_MS (30s) and answers from the KB instead, so nginx has to
\t\t# outlast it or the visitor gets a 504 instead of that graceful fallback.
\t\tproxy_read_timeout 45s;
\t\tproxy_send_timeout 45s;
\t\t# The route is anonymous by design; same origin means the browser would
\t\t# now attach session cookies. Strip them so that stays true.
\t\tproxy_set_header   Cookie        "";
\t\tproxy_set_header   Authorization "";
\t}
\tlocation = /v1/chat/health {
\t\tproxy_pass       http://${CHAT_UPSTREAM};
\t\tproxy_set_header Host $host;
\t\tproxy_set_header Cookie "";
\t\taccess_log       off;
\t}

# ---- 6) cache headers (firebase.json "headers") ----
\tlocation ~* \\.(jpg|jpeg|gif|png|webp|avif|svg)$ {
\t\ttry_files $uri =404;
\t\tadd_header Cache-Control "public, max-age=2592000, immutable";
${sec('\t\t')}
\t}
\tlocation ~* \\.(woff|woff2|ttf|otf|eot)$ {
\t\ttry_files $uri =404;
\t\tadd_header Cache-Control "public, max-age=31536000, immutable";
\t\tadd_header Access-Control-Allow-Origin "*";
${sec('\t\t')}
\t}
\tlocation ~* \\.(js|css)$ {
\t\ttry_files $uri =404;
\t\tadd_header Cache-Control "public, max-age=604800";
${sec('\t\t')}
\t}
\tlocation ~* \\.html$ {
\t\ttry_files $uri =404;
\t\tadd_header Cache-Control "public, max-age=3600, must-revalidate";
${sec('\t\t')}
\t}
\t# Explicit Content-Type: these are served to crawlers, and nosniff above
\t# means a wrong or missing type is fatal rather than merely untidy.
\tlocation ~ ^/(sitemap|en_en-sitemap)\\.xml$ {
\t\ttry_files $uri =404;
\t\tdefault_type application/xml;
\t\tadd_header Cache-Control "public, max-age=86400";
${sec('\t\t')}
\t}
\tlocation = /robots.txt {
\t\ttry_files $uri =404;
\t\tdefault_type text/plain;
\t\tadd_header Cache-Control "public, max-age=86400";
${sec('\t\t')}
\t}

# ---- 7) extensionless resolution: /foo -> foo.html, / -> index.html.
#         This is the HTML path — "/" and every clean URL land here, not in
#         the \\.html$ location above (the URI has no extension by then), so
#         the HTML cache policy has to be repeated. ----
\tlocation / {
\t\ttry_files $uri $uri.html $uri/index.html $uri/ =404;
\t\tadd_header Cache-Control "public, max-age=3600, must-revalidate";
${sec('\t\t')}
\t}

\terror_page 404 /404.html;
\tlocation = /404.html { internal; }
}
`;

mkdirSync(HERE, { recursive: true });
const out = path.join(HERE, 'coffeepie.co.nginx.conf');
writeFileSync(out, conf, 'utf8');
console.log(
  `wrote ${path.relative(path.join(SITE, '..'), out)} ` +
  `(${fb.rewrites.length} rewrites, ${fb.redirects.length} redirects)`
);
