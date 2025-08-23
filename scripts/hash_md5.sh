#!/usr/bin/env bash
# Basit MD5 hash üretici (Linux/macOS)
# Kullanım: ./scripts/hash_md5.sh <dosya_yolu>
set -euo pipefail
if [ $# -lt 1 ]; then
  echo "Kullanım: $0 <dosya>" >&2
  exit 1
fi
FILE="$1"
if command -v md5sum >/dev/null 2>&1; then
  md5sum "$FILE" | awk '{print $1}'
elif command -v md5 >/dev/null 2>&1; then
  md5 -q "$FILE"
else
  echo "Ne md5sum ne de md5 komutu bulunamadı." >&2
  exit 2
fi
