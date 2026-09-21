#!/usr/bin/env bash
# ============================================================================
# Smoke-tests deploy/coffeepie.co.nginx.conf against a real nginx in a
# throwaway container, using a fixture tree instead of the 169 MB public/.
#
#   bash coffeepie_website/deploy/verify-nginx-vhost.sh
#
# `nginx -t` only parses the file. It cannot tell you that /manufacturers
# resolves, that /index.html redirects to / rather than to /index, or that
# package.json is unreachable — and those are exactly the things that break
# a migration. So this asserts observed status codes and Location headers.
#
# Run it after every regeneration, before copying anything to the server.
# ============================================================================
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONF="$HERE/coffeepie.co.nginx.conf"
IMAGE="nginx:alpine"
NAME="coffeepie-vhost-check"
PORT=8899

[ -f "$CONF" ] && : || { echo "missing $CONF — run gen-coffeepie-nginx.mjs first"; exit 1; }

FIX="$(mktemp -d)"
cleanup() { docker rm -f "$NAME" >/dev/null 2>&1; rm -rf "$FIX"; }
trap cleanup EXIT

# Fixture: one file per behaviour the vhost claims to implement.
mkdir -p "$FIX/tools" "$FIX/products"
echo 'home'          > "$FIX/index.html"
echo 'manufacturers' > "$FIX/manufacturers.html"
echo 'pricing'       > "$FIX/pricing.html"
echo 'cart'          > "$FIX/cart.html"
echo 'notfound'      > "$FIX/404.html"
echo 'robots'        > "$FIX/robots.txt"
echo '<urlset/>'     > "$FIX/sitemap.xml"
echo 'secret'        > "$FIX/package.json"
echo 'secret'        > "$FIX/tools/build.py"
echo 'app'           > "$FIX/app.js"
# mktemp -d is 0700 and nginx's worker runs as an unprivileged user, so
# without this every request is a 403 that looks like a config bug.
chmod -R a+rX "$FIX"

docker rm -f "$NAME" >/dev/null 2>&1
docker run -d --name "$NAME" -p "127.0.0.1:$PORT:80" \
  -v "$CONF:/etc/nginx/conf.d/coffeepie.conf:ro" \
  -v "$FIX:/var/www/coffeepie.co:ro" \
  "$IMAGE" >/dev/null || { echo "could not start $IMAGE"; exit 1; }

# nginx -t inside the same container: syntax first, behaviour after.
if ! docker exec "$NAME" nginx -t >/dev/null 2>&1; then
  echo "FAIL nginx -t:"; docker exec "$NAME" nginx -t; exit 1
fi
echo "ok   nginx -t"

for _ in $(seq 1 30); do
  curl -s -o /dev/null -m 1 -H 'Host: coffeepie.co' "http://127.0.0.1:$PORT/" && break
  sleep 0.2
done

fails=0
# check <label> <path> <expected-status> [expected-Location]
check() {
  local label="$1" path="$2" want="$3" wantloc="${4:-}"
  local out code loc
  out=$(curl -s -i -m 5 -H 'Host: coffeepie.co' "http://127.0.0.1:$PORT$path")
  code=$(printf '%s' "$out" | head -1 | awk '{print $2}')
  loc=$(printf '%s' "$out" | tr -d '\r' | awk -F': ' 'tolower($1)=="location"{print $2}')
  if [ "$code" != "$want" ]; then
    echo "FAIL $label: $path -> $code (want $want)"; fails=$((fails+1)); return
  fi
  if [ -n "$wantloc" ] && [ "$loc" != "$wantloc" ]; then
    echo "FAIL $label: $path -> Location '$loc' (want '$wantloc')"; fails=$((fails+1)); return
  fi
  echo "ok   $label: $path -> $code${wantloc:+ -> $wantloc}"
}

echo "--- serving"
check "root"              /                 200
check "clean url"         /manufacturers    200
check "clean url"         /pricing          200

echo "--- redirects (firebase 'redirects')"
check "es->en"            /fabricantes      301 /manufacturers
check "es->en"            /precios          301 /pricing
check "typo"              /princing         301 /pricing
check "index"             /index.html       301 /
check "param"             /productos/abc    301 /products/abc
check "carrito"           /carrito          301 /cart

echo "--- cleanUrls 301 (.html is not a public URL)"
check "html 301"          /manufacturers.html 301 /manufacturers

echo "--- blocked (firebase 'ignore')"
check "package.json"      /package.json     404
check "tools/"            /tools/build.py   404
check "dotfile"           /.env             404

echo "--- content types / caching"
check "robots"            /robots.txt       200
check "sitemap"           /sitemap.xml      200
check "missing"           /nope             404

# hdr <path> <header-name> — asserts the header is present and non-empty.
hdr() {
  local path="$1" name="$2" got
  got=$(curl -s -i -m 5 -H 'Host: coffeepie.co' "http://127.0.0.1:$PORT$path" \
        | tr -d '\r' | awk -F': ' -v n="$name" 'tolower($1)==n{print $2; exit}')
  if [ -z "$got" ]; then
    echo "FAIL header: $path has no $name"; fails=$((fails+1))
  else
    echo "ok   header: $path $name: $got"
  fi
}
hdr /app.js         cache-control
hdr /               cache-control
hdr /manufacturers  cache-control

# nginx discards inherited add_header inside any location that declares one,
# so the security headers have to be re-stated per location. Assert that in
# the three that set Cache-Control, or the whole site quietly loses them.
echo "--- security headers survive the per-location add_header trap"
hdr /               x-content-type-options
hdr /manufacturers  x-content-type-options
hdr /app.js         x-content-type-options
hdr /app.js         referrer-policy
hdr /robots.txt     x-content-type-options

echo
if [ "$fails" -eq 0 ]; then echo "PASS — vhost behaves like firebase.json"; else echo "$fails FAILING checks"; fi
exit "$fails"
