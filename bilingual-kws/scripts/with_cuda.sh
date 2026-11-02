#!/usr/bin/env bash
# Reuse the locally installed CUDA 12 libraries, when supplied explicitly.
# A clean `pip install tensorflow[and-cuda]==2.20.0` environment needs no override.
set -euo pipefail
if [[ -n "${KWS_CUDA_SITE:-}" ]]; then
  kws_libs=""
  for kws_dir in "$KWS_CUDA_SITE"/nvidia/*/lib; do
    [[ -d "$kws_dir" ]] && kws_libs="$kws_libs:$kws_dir"
  done
  export LD_LIBRARY_PATH="${kws_libs#:}${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
  # XLA compilation needs CUDA's libdevice and ptxas if enabled.
  if [[ -d "$KWS_CUDA_SITE/nvidia/cuda_nvcc" ]]; then
    export XLA_FLAGS="--xla_gpu_cuda_data_dir=$KWS_CUDA_SITE/nvidia/cuda_nvcc"
  elif [[ -f "$KWS_CUDA_SITE/triton/backends/nvidia/lib/libdevice.10.bc" ]]; then
    # PyTorch's installed Triton ships the matching compiler assets. Build a
    # private CUDA directory layout without modifying the shared environment.
    kws_cuda_root="${KWS_DATA:-/home/fred/bilingual-kws-data}/native/cuda"
    mkdir -p "$kws_cuda_root/nvvm/libdevice" "$kws_cuda_root/bin"
    ln -sf "$KWS_CUDA_SITE/triton/backends/nvidia/lib/libdevice.10.bc" "$kws_cuda_root/nvvm/libdevice/libdevice.10.bc"
    ln -sf "$KWS_CUDA_SITE/triton/backends/nvidia/bin/ptxas" "$kws_cuda_root/bin/ptxas"
    export XLA_FLAGS="--xla_gpu_cuda_data_dir=$kws_cuda_root"
    export PATH="$kws_cuda_root/bin:$PATH"
  fi
fi
exec "$@"
