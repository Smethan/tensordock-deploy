#!/bin/bash
set -e

echo "=========================================="
echo "ComfyUI TensorDock Startup"
echo "=========================================="
echo ""

cd /workspace/ComfyUI

# Check if models have been downloaded
MODELS_FLAG="/workspace/.models_downloaded"

if [ ! -f "$MODELS_FLAG" ]; then
    echo "📦 First-time setup detected!"
    echo "📥 Downloading models (this will take 15-20 minutes)..."
    echo ""

    # Run the model downloader
    python3 /workspace/download_models.py

    # Create flag file to mark models as downloaded
    touch "$MODELS_FLAG"
    echo ""
    echo "✅ Models downloaded successfully!"
else
    echo "✅ Models already downloaded (skip with: rm /workspace/.models_downloaded)"
fi

# Detect VRAM
if command -v nvidia-smi &> /dev/null; then
    TOTAL_VRAM=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | head -1)
    VRAM_GB=$((TOTAL_VRAM / 1024))
    GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader | head -1)

    echo ""
    echo "=========================================="
    echo "GPU: $GPU_NAME"
    echo "VRAM: ${VRAM_GB}GB"
    echo "=========================================="
    echo ""

    # Determine launch flags based on VRAM
    if [ "$VRAM_GB" -le 12 ]; then
        echo "🚀 Launching ComfyUI with --lowvram mode (≤12GB VRAM)"
        VRAM_FLAG="--lowvram"
    elif [ "$VRAM_GB" -le 16 ]; then
        echo "🚀 Launching ComfyUI with --normalvram mode (12-16GB VRAM)"
        VRAM_FLAG="--normalvram"
    else
        echo "🚀 Launching ComfyUI with high VRAM mode (>16GB VRAM)"
        VRAM_FLAG=""
    fi
else
    echo "⚠️  nvidia-smi not found, launching with default settings"
    VRAM_FLAG=""
fi

echo ""
echo "=========================================="
echo "🌐 Access ComfyUI at:"
echo "   http://localhost:8188"
echo "   or"
echo "   http://$(hostname -I | awk '{print $1}'):8188"
echo ""
echo "Press Ctrl+C to stop"
echo "=========================================="
echo ""

# Start ComfyUI
exec python main.py --listen 0.0.0.0 --port 8188 $VRAM_FLAG --preview-method auto "$@"
