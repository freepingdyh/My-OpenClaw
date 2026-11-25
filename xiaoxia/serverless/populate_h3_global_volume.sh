#!/usr/bin/env bash
set -euo pipefail

# Populate exactly the four MiniMax H3 files Xiaoxia uses.
# Run this from a temporary RunPod Pod with xiaoxia-models Global Volume attached.
# On a Pod, Global Volume is normally /workspace, or /workspace-global when a
# Network Volume is attached at the same time.

if [[ -d /workspace-global ]]; then
  VOLUME_ROOT=/workspace-global
elif [[ -d /workspace ]]; then
  VOLUME_ROOT=/workspace
else
  echo "[H3_POPULATE] no Global Volume mount found at /workspace or /workspace-global" >&2
  exit 2
fi

DEST="${VOLUME_ROOT}/h3_models"
mkdir -p "${DEST}/diffusion_models" "${DEST}/text_encoders" "${DEST}/vae"

download_and_verify() {
  local rel="$1"
  local sha="$2"
  local url="https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/${rel}"
  local out="${DEST}/${rel}"

  if [[ -f "${out}" ]]; then
    current="$(sha256sum "${out}" | awk '{print $1}')"
    if [[ "${current}" == "${sha}" ]]; then
      echo "[H3_POPULATE] already verified: ${rel}"
      return 0
    fi
    echo "[H3_POPULATE] existing file checksum mismatch; redownloading: ${rel}"
    rm -f "${out}"
  fi

  echo "[H3_POPULATE] downloading: ${rel}"
  curl --fail --location --retry 8 --retry-delay 5 --continue-at -     --output "${out}" "${url}"

  current="$(sha256sum "${out}" | awk '{print $1}')"
  if [[ "${current}" != "${sha}" ]]; then
    echo "[H3_POPULATE] SHA256 mismatch for ${rel}" >&2
    echo "expected=${sha}" >&2
    echo "actual=${current}" >&2
    exit 3
  fi
  echo "[H3_POPULATE] verified: ${rel}"
}

download_and_verify   "diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors"   "e889202c41dafb67b10d67b97f0d8541508036a6090af23425a5c2615d03c47a"

download_and_verify   "text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"   "35a88d51044231fe332301d7a62aa81e3f2cba62febeb446e2c1e3e0ef76f2c6"

download_and_verify   "vae/minimax_h3_video_vae_int8_convrot.safetensors"   "52a2c8c73583c86e4f41cdcce3a6ad0ea562987bc0bf3d60a0cef5f5c8e60c0e"

download_and_verify   "vae/minimax_h3_audio_vae_fp32.safetensors"   "8e505d95dd1561d47abd43d4238fd40d9bb1ae9e147ed0a4cba778d76ae4db48"

echo
echo "[H3_POPULATE] complete"
du -sh "${DEST}" || true
find "${DEST}" -maxdepth 2 -type f -printf "%p  %s bytes\n" | sort
