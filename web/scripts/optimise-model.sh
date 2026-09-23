#!/usr/bin/env bash
# Turn a downloaded 3D model into one a web page can afford.
#
# A model built for a turntable render and a model for eleven figures on a
# pitch are not the same file. The player used here arrived at 22.8 MB —
# 195,928 triangles and four PNG textures worth 16 MB — for something that
# is thirty pixels tall from most cameras on the page. This gets it to
# 761 KB and 14,959 triangles with no visible difference at any distance the
# scene uses.
#
# WHY THESE FLAGS AND NOT THE DEFAULTS:
#
#   --compress false     the default is meshopt, which needs a decoder on the
#                        client. At this size the geometry is not the problem
#                        and a file that any glTF loader opens unaided is
#                        worth more than the last hundred kilobytes.
#   --texture-size 1024  the textures were 73% of the download. At the
#                        distances these render, 1024 is already generous.
#   --texture-compress   PNG is the worst format here. WebP is universally
#     webp               supported and cost nothing in quality at 1024.
#   --simplify-error     0.001 is the gentle setting and still lands under a
#     0.001              megabyte. 0.01 gives 456 KB and 5,909 triangles,
#                        which also looks fine — but the 300 KB saved is not
#                        worth the risk of faceting if anyone zooms in.
#
# The SOURCE lives in data/models/ rather than web/public/, because anything
# under public/ is copied into the static export whether it is referenced or
# not — which would ship the 22 MB original alongside the 761 KB one.
#
# Usage:  bash scripts/optimise-model.sh [source.glb] [out.glb]
set -euo pipefail

SRC="${1:-../data/models/player-source.glb}"
OUT="${2:-public/models/player.glb}"

if [ ! -f "$SRC" ]; then
  echo "no source model at $SRC" >&2
  exit 1
fi

mkdir -p "$(dirname "$OUT")"
npx --yes @gltf-transform/cli@latest optimize "$SRC" "$OUT" \
  --compress false \
  --texture-size 1024 \
  --texture-compress webp \
  --simplify-error 0.001

echo
echo "source: $(du -h "$SRC" | cut -f1)   shipped: $(du -h "$OUT" | cut -f1)"
