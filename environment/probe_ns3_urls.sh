#!/usr/bin/env bash
set -euo pipefail
echo "=== nsnam releases page ==="
curl -fsSL -o /tmp/ns3page.html -w "http_code=%{http_code}\n" https://www.nsnam.org/releases/ || echo "releases page failed"
if [[ -f /tmp/ns3page.html ]]; then
  grep -oE 'ns-3\.[0-9]+|ns-allinone-[0-9.]+' /tmp/ns3page.html | sort -u | tail -30 || true
fi
echo "=== URL probes ==="
urls=(
  "https://www.nsnam.org/releases/ns-allinone-3.47.tar.bz2"
  "https://www.nsnam.org/release/ns-allinone-3.47.tar.bz2"
  "https://www.nsnam.org/releases/ns-3-47/ns-3.47.tar.bz2"
  "https://www.nsnam.org/releases/ns-3-47/ns-allinone-3.47.tar.bz2"
  "https://gitlab.com/nsnam/ns-3-dev/-/archive/ns-3.47/ns-3-dev-ns-3.47.tar.bz2"
  "https://gitlab.com/nsnam/ns-3-dev/-/archive/ns-3.47/ns-3-dev-ns-3.47.tar.gz"
  "https://github.com/nsnam/ns-3-dev-git/archive/refs/tags/ns-3.47.tar.gz"
  "https://github.com/nsnam/ns-3-dev/archive/refs/tags/ns-3.47.tar.gz"
)
for u in "${urls[@]}"; do
  echo "URL=$u"
  code=$(curl -fsSIL --max-time 25 -o /tmp/hdr.txt -w "%{http_code}" "$u" || echo "ERR")
  echo "  http_code=$code"
  if [[ -f /tmp/hdr.txt ]]; then
    grep -iE 'HTTP/|content-length|content-type|location' /tmp/hdr.txt | head -12 || true
  fi
  echo "---"
done
