#!/usr/bin/env bash
# Regenerates the social preview image and the PNG icons with headless Chrome/Chromium.
set -Eeuo pipefail
cd "$(dirname "$0")/.."
CHROME="${CHROME:-$(command -v google-chrome || command -v chromium || command -v chromium-browser || true)}"
[[ -n "$CHROME" ]] || { echo "Chrome or Chromium is required (set CHROME=/path/to/chrome)." >&2; exit 1; }

shot() { # shot <html-file> <output.png> <width> <height>
  local src="$1"
  [[ "$src" = /* ]] || src="$PWD/$src"
  "$CHROME" --headless=new --disable-gpu --hide-scrollbars --force-device-scale-factor=1 \
    --default-background-color=00000000 --window-size="$3,$4" --screenshot="$2" "file://$src" >/dev/null 2>&1
}

shot scripts/og-image.html public/og-image.png 1200 630
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
for size in 180 32; do
  cat > "$tmp/icon.html" <<HTML
<!doctype html><html><body style="margin:0;background:transparent">
$(sed "s|<svg |<svg width=\"$size\" height=\"$size\" |" public/favicon.svg)
</body></html>
HTML
  shot "$tmp/icon.html" "$tmp/icon-$size.png" "$size" "$size"
done
cp "$tmp/icon-180.png" public/apple-touch-icon.png
# favicon.ico: an ICO container holding the 32x32 PNG (supported by all current browsers).
python3 - "$tmp/icon-32.png" public/favicon.ico <<'PY'
import struct, sys
png = open(sys.argv[1], "rb").read()
header = struct.pack("<HHH", 0, 1, 1)
entry = struct.pack("<BBBBHHII", 32, 32, 0, 0, 1, 32, len(png), 6 + 16)
open(sys.argv[2], "wb").write(header + entry + png)
PY
echo "Generated public/og-image.png, public/apple-touch-icon.png, public/favicon.ico"
