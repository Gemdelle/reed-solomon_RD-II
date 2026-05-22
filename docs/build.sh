#!/usr/bin/env bash
# Renders Mermaid diagrams via kroki.io and builds DOCX + PDF.
# Requires: curl, pandoc, soffice (LibreOffice)
set -euo pipefail

DOCS_DIR="$(cd "$(dirname "$0")" && pwd)"
DIAGRAMS_DIR="$DOCS_DIR/diagrams"
OUTPUT_DIR="$DOCS_DIR/informes"
IMG_DIR="$OUTPUT_DIR/img"

mkdir -p "$IMG_DIR"

echo "→ Rendering diagrams via kroki.io..."
for mmd in "$DIAGRAMS_DIR"/*.mmd; do
  name=$(basename "$mmd" .mmd)
  out="$IMG_DIR/$name.png"
  echo "  $name.mmd → img/$name.png"
  curl -sf -X POST "https://kroki.io/mermaid/png" \
    -H "Content-Type: text/plain" \
    --data-binary "@$mmd" \
    -o "$out" || { echo "  ✗ Failed to render $name (check internet)"; exit 1; }
done

echo "→ Building DOCX..."
pandoc "$DOCS_DIR/arquitectura_src.md" \
  --resource-path="$OUTPUT_DIR" \
  --toc \
  --highlight-style tango \
  -o "$OUTPUT_DIR/arquitectura.docx"

echo "→ Building PDF..."
soffice --headless --convert-to pdf \
  "$OUTPUT_DIR/arquitectura.docx" \
  --outdir "$OUTPUT_DIR" 2>/dev/null

echo "✓ Done — output in docs/informes/"
ls -lh "$OUTPUT_DIR"/*.docx "$OUTPUT_DIR"/*.pdf
