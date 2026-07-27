#!/bin/bash
# ============================================================================
# ¿Hay ficheros que son punteros de Git LFS en vez del medio real?
#
# POR QUÉ EXISTE ESTO
#   .gitattributes manda *.png *.jpg *.svg *.mp4 (y más) a Git LFS. En una
#   máquina CON git-lfs, el checkout sustituye cada puntero por los bytes
#   reales. En una máquina SIN git-lfs, git escribe en disco un fichero de
#   texto de ~130 bytes:
#
#       version https://git-lfs.github.com/spec/v1
#       oid sha256:75fc6f9c…
#       size 111173
#
#   rsync lo copia tal cual, y nginx lo sirve con Content-Type: image/png y
#   200 OK. El navegador recibe un "PNG" que no lo es y pinta una imagen rota.
#
#   Nada en la cadena comprueba jamás que los bytes sean una imagen: ni git, ni
#   rsync, ni nginx, ni un `curl -o /dev/null -w %{http_code}`. Todo dice 200.
#   Por eso esto vivió semanas sin detectarse y parecía aleatorio: sólo el 10 %
#   de los medios está en LFS, así que 9 de cada 10 imágenes funcionaban.
#
# USO
#   ./scripts/check-lfs-pointers.sh                      # el checkout
#   ./scripts/check-lfs-pointers.sh /home/admin/web/coffeepie.co/public_html
#
#   Sale con código 1 si encuentra alguno, para poder encadenarlo:
#       ./scripts/check-lfs-pointers.sh RUTA && rsync -av ORIGEN DESTINO
#   así un despliegue nunca publica punteros.
#
# SI FALLA
#   apt-get install -y git-lfs
#   cd /home/admin/coffeepie && git lfs install
#   git lfs pull --include="coffeepie_website/public/**"
# ============================================================================
set -uo pipefail

DIR="${1:-$(cd "$(dirname "$0")/.." && pwd)/coffeepie_website/public}"

if [ ! -d "$DIR" ]; then
  echo "no existe el directorio: $DIR" >&2
  exit 2
fi

echo "Revisando $DIR…"

# Un puntero LFS siempre empieza por esa línea y pesa poco (~130 bytes).
# Filtrar por tamaño primero hace el escaneo instantáneo aunque haya miles de
# ficheros.
#
# ⚠ El tamaño va en BYTES (-size -2000c), no en kilobytes. `-size -1k` redondea
#   hacia ARRIBA: un fichero de 129 bytes cuenta como 1k, así que `-1k` sólo
#   encontraría ficheros de 0 bytes y el guardián no detectaría nada. Escrito
#   así la primera vez, y una prueba negativa lo destapó.
mapfile -t POINTERS < <(
  find "$DIR" -type f -size -2000c \
       \( -iname '*.png' -o -iname '*.jpg'  -o -iname '*.jpeg' -o -iname '*.webp' \
       -o -iname '*.avif' -o -iname '*.svg' -o -iname '*.gif'  -o -iname '*.mp4'  \
       -o -iname '*.mov'  -o -iname '*.pdf' -o -iname '*.psd'  -o -iname '*.ai' \) \
       -exec grep -l '^version https://git-lfs' {} + 2>/dev/null | sort
)

n=${#POINTERS[@]}

if [ "$n" -eq 0 ]; then
  echo "✓ ningún puntero LFS: todos los medios son ficheros reales."
  exit 0
fi

echo
echo "✗ $n fichero(s) son punteros LFS, no medios reales:"
echo
printf '  %s\n' "${POINTERS[@]#$DIR/}" | head -40
[ "$n" -gt 40 ] && echo "  … y $((n - 40)) más"

echo
echo "Se servirían como 200 OK con ~130 bytes de texto y el navegador"
echo "los pintaría como imágenes rotas. Instala git-lfs y vuelve a bajarlos:"
echo
echo "  apt-get install -y git-lfs"
echo "  cd /home/admin/coffeepie && git lfs install"
echo "  git lfs pull --include=\"coffeepie_website/public/**\""
exit 1
