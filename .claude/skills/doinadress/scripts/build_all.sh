#!/usr/bin/env bash
# Reconstruiește, în ordine, toate variantele cu familia (cu fețe):
# HTML + web/ + mobile/assets/web, cele 4 APK-uri Kotlin, APK-ul Flutter simplu și apoi APK-ul Flutter complet.
# Rulare (din orice folder): bash .claude/skills/doinadress/scripts/build_all.sh [fișier_log]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
LOG="${1:-/dev/stdout}"
export PYTHONIOENCODING=utf-8
cd "$ROOT"
{
  echo "== build.py";      python src/build.py
  echo "== build_kotlin";  python src/build_kotlin.py
  echo "== build_simplu";  python src/build_simplu.py
  echo "== flutter complet"
  (cd mobile && flutter build apk --release)
  cp mobile/build/app/outputs/flutter-apk/app-release.apk DoinaDress.apk
  echo "== GATA"; ls -la DoinaDress.apk DoinaDress_Simplu.apk kotlin_apk/
} >> "$LOG" 2>&1
