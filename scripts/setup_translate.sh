#!/usr/bin/env bash
# Coffee Pie - LibreTranslate Setup
# Starts LibreTranslate locally on port 5050.
# Requires: Docker (or Python 3.10+ with pip for alt install).

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; NC='\033[0m'
log()  { printf "${GREEN}[setup]${NC} %s\n" "$*"; }
warn() { printf "${CYAN}[warn]${NC}  %s\n" "$*"; }
err()  { printf "${RED}[err]${NC}   %s\n" "$*"; exit 1; }

CONTAINER_NAME="coffeepie-libretranslate"
LIBRETRANSLATE_PORT="${LIBRETRANSLATE_PORT:-5050}"
LIBRETRANSLATE_TAG="${LIBRETRANSLATE_TAG:-latest}"

# ---- Docker path ----
use_docker() {
    if ! command -v docker &>/dev/null; then
        warn "Docker not found. Trying alternative install..."
        use_pip_standalone
        return
    fi

    # Check if already running
    if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        log "LibreTranslate container already running on port ${LIBRETRANSLATE_PORT}"
        return
    fi

    # Remove stopped container if exists
    docker rm -f "${CONTAINER_NAME}" 2>/dev/null || true

    log "Pulling LibreTranslate image (tag: ${LIBRETRANSLATE_TAG})..."
    docker pull "libretranslate/libretranslate:${LIBRETRANSLATE_TAG}"

    log "Starting LibreTranslate on http://localhost:${LIBRETRANSLATE_PORT} ..."
    docker run -d \
        --name "${CONTAINER_NAME}" \
        --restart unless-stopped \
        -p "${LIBRETRANSLATE_PORT}:5050" \
        "libretranslate/libretranslate:${LIBRETRANSLATE_TAG}" \
        --host 0.0.0.0 \
        --load-only en,pt,fr,de,ja,ko,zh,ru,ar,hi

    log "Waiting for LibreTranslate to be ready..."
    for i in $(seq 1 60); do
        if curl -s "http://localhost:${LIBRETRANSLATE_PORT}/languages" > /dev/null 2>&1; then
            log "LibreTranslate is ready!"
            return
        fi
        sleep 3
    done
    err "LibreTranslate did not start within 3 minutes. Check: docker logs ${CONTAINER_NAME}"
}

# ---- pip + argostranslate alt path ----
use_pip_standalone() {
    log "Installing argostranslate via pip (offline-capable, no Docker needed)..."

    if ! python3 -m pip --version &>/dev/null; then
        log "Installing pip..."
        python3 -m ensurepip --user 2>/dev/null || \
            python3 -m ensurepip 2>/dev/null || \
            err "Cannot install pip. Install Python 3.10+ with pip first."
    fi

    python3 -m pip install --user argostranslate 2>/dev/null || \
        python3 -m pip install argostranslate 2>/dev/null || \
        err "Failed to install argostranslate"

    log "Installing language packages (this downloads ~200MB per language pair)..."
    python3 -c "
import argostranslate.package
import argostranslate.translate
argostranslate.package.update_package_index()
available = argostranslate.package.get_available_packages()
targets = ['en','pt','fr','de','ja','ko','zh','ru','ar','hi']
for pkg in available:
    if pkg.from_code == 'es' and pkg.to_code in targets:
        print(f'  Installing es->{pkg.to_code} ...')
        argostranslate.package.install_from_path(pkg.download())
print('All language packages installed.')
"
    log "Argos Translate ready (offline mode, no server needed)."
    log "Run: python3 scripts/translate.py"
}

# ---- Main ----
echo ""
printf "${CYAN}"
echo "  ☕ Coffee Pie Translation Setup"
echo "  ==============================="
printf "${NC}"
echo ""

use_docker

echo ""
log "Setup complete. You can now run:  python3 scripts/translate.py"
