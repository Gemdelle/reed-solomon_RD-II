#!/usr/bin/env bash
# Converts icon.svg → icon.png (Linux), icon.icns (macOS), icon.ico (Windows).
# Requires: inkscape  (or rsvg-convert as fallback for PNG)
#           icnsutils  (for ICNS — apt: icnsutils)
#           imagemagick  (for ICO)
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SVG="$DIR/icon.svg"

echo "==> Generating icon.png (512x512)..."
if command -v inkscape &>/dev/null; then
  inkscape --export-filename="$DIR/icon.png" --export-width=512 --export-height=512 "$SVG"
elif command -v rsvg-convert &>/dev/null; then
  rsvg-convert -w 512 -h 512 -o "$DIR/icon.png" "$SVG"
elif command -v magick &>/dev/null; then
  magick -background none -size 512x512 "$SVG" "$DIR/icon.png"
elif command -v convert &>/dev/null; then
  convert -background none -size 512x512 "$SVG" "$DIR/icon.png"
else
  echo "ERROR: install inkscape, rsvg-convert, or imagemagick" && exit 1
fi

echo "==> Generating icon.icns (macOS)..."
if command -v png2icns &>/dev/null; then
  for size in 16 32 128 256 512; do
    inkscape --export-filename="/tmp/icon_${size}.png" --export-width=$size --export-height=$size "$SVG" 2>/dev/null \
      || rsvg-convert -w $size -h $size -o "/tmp/icon_${size}.png" "$SVG"
  done
  png2icns "$DIR/icon.icns" /tmp/icon_16.png /tmp/icon_32.png /tmp/icon_128.png /tmp/icon_256.png /tmp/icon_512.png
  rm -f /tmp/icon_*.png
else
  echo "SKIP: install icnsutils (png2icns) for macOS icon"
fi

echo "==> Generating icon.ico (Windows)..."
if command -v magick &>/dev/null; then
  magick "$DIR/icon.png" -resize 256x256 "$DIR/icon.ico"
elif command -v convert &>/dev/null; then
  convert "$DIR/icon.png" -resize 256x256 "$DIR/icon.ico"
else
  echo "SKIP: install imagemagick for Windows icon"
fi

echo "==> Done."
ls -lh "$DIR"/icon.*
