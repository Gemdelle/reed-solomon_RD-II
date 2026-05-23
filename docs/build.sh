#!/usr/bin/env bash
# Renders Mermaid diagrams via @mermaid-js/mermaid-cli (npx) and builds DOCX + PDF.
# Requires: node/npm, pandoc, soffice (LibreOffice)
set -euo pipefail

DOCS_DIR="$(cd "$(dirname "$0")" && pwd)"
DIAGRAMS_DIR="$DOCS_DIR/diagrams"
OUTPUT_DIR="$DOCS_DIR/informes"
IMG_DIR="$OUTPUT_DIR/img"

mkdir -p "$IMG_DIR"

echo "→ Rendering Mermaid diagrams via @mermaid-js/mermaid-cli..."
for mmd in "$DIAGRAMS_DIR"/*.mmd; do
  name=$(basename "$mmd" .mmd)
  out="$IMG_DIR/$name.png"
  echo "  $name.mmd → img/$name.png"
  npx --yes @mermaid-js/mermaid-cli \
    --input "$mmd" \
    --output "$out" \
    --backgroundColor white \
    --quiet \
    || { echo "  ✗ Failed to render $name"; exit 1; }
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
