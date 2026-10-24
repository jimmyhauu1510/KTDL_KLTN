#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"
export UV_CACHE_DIR="${UV_CACHE_DIR:-$project_dir/.cache/uv}"
venv_path="${VIETFIN_VENV:-$project_dir/.venv}"
tessdata_path="${VIETFIN_TESSDATA:-$project_dir/data/tessdata}"
command -v uv >/dev/null || { echo 'Cần uv để cài dependencies có kiểm tra hash.' >&2; exit 1; }
command -v tesseract >/dev/null || { echo 'Cần cài tesseract-ocr và fonts-dejavu-core từ trình quản lý gói hệ điều hành.' >&2; exit 1; }
if [ ! -x "$venv_path/bin/python" ]; then
    uv venv "$venv_path" --python python3.12
fi
uv pip install --python "$venv_path/bin/python" --require-hashes -r requirements.lock
uv pip install --python "$venv_path/bin/python" -e . --no-deps
mkdir -p "$tessdata_path"
if [ ! -f "$tessdata_path/vie.traineddata" ]; then
    curl --fail --location --proto '=https' --tlsv1.2 \
      https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/4.1.0/vie.traineddata \
      -o "$tessdata_path/vie.traineddata"
fi
echo "79df64caf7bcfb2a27df5042ecb6121e196eada34da774956995747636d5bfa1  $tessdata_path/vie.traineddata" | sha256sum -c -
uv pip check --python "$venv_path/bin/python"
VIETFIN_TESSDATA="$tessdata_path" "$venv_path/bin/python" -m pytest -q
echo "Cài đặt hoàn tất. Chạy: VIETFIN_TESSDATA='$tessdata_path' '$venv_path/bin/vietfin' serve"
