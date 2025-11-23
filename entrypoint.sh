#!/bin/bash
set -e

echo "=========================================="
echo "ComfyUI TensorDock Startup"
echo "ComfyUI Triton SageAttention Edition"
echo "=========================================="
echo ""

# Activate virtual environment
VENV_DIR="/workspace/venv"
if [ -f "$VENV_DIR/bin/activate" ]; then
    source "$VENV_DIR/bin/activate"
    echo "✅ Virtual environment activated"
else
    echo "❌ Virtual environment not found at $VENV_DIR"
    exit 1
fi

# Verify GPU availability
echo "🔍 Checking GPU availability..."
python3 - <<'PYCODE'
import torch, sys
try:
    if torch.cuda.is_available() and torch.cuda.device_count() > 0:
        print(f"✅ GPU detected: {torch.cuda.get_device_name(0)}")
        print(f"   CUDA Version: {torch.version.cuda}")
        print(f"   Torch Version: {torch.__version__}")
    else:
        print("❌ No GPU detected! ComfyUI requires a GPU.")
        sys.exit(1)
except Exception as e:
    print(f"❌ CUDA initialization failed: {e}")
    sys.exit(1)
PYCODE

if [ $? -ne 0 ]; then
    echo "⚠️ GPU check failed. Exiting..."
    exit 1
fi
echo ""

# Background function to download models after ComfyUI starts
background_model_downloader() {
    MODELS_FLAG="/workspace/.models_downloaded"
    DOWNLOAD_LOG="/workspace/model_download.log"

    exec > >(tee -a "$DOWNLOAD_LOG") 2>&1

    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Background model downloader started"

    # Wait for ComfyUI to be listening on port 8188
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Waiting for ComfyUI to start on port 8188..."
    for i in {1..60}; do
        if netstat -tuln 2>/dev/null | grep -q ":8188 " || ss -tuln 2>/dev/null | grep -q ":8188 "; then
            echo "[$(date '+%Y-%m-%d %H:%M:%S')] ComfyUI is now listening on port 8188"
            break
        fi
        sleep 2
    done

    # Additional 5 second grace period to ensure ComfyUI is fully initialized
    sleep 5

    # Check if models need to be downloaded
    if [ ! -f "$MODELS_FLAG" ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting model download..."
        echo "📦 First-time setup detected!"
        echo "📥 Downloading models in background (this will take 15-20 minutes)..."
        echo ""

        # Run the model downloader with venv python
        cd /workspace
        python3 /workspace/download_models.py

        # Create flag file to mark models as downloaded
        touch "$MODELS_FLAG"
        echo ""
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ Models downloaded successfully!"
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ Models already downloaded (skip with: rm /workspace/.models_downloaded)"
    fi
}

# Launch model downloader in background
background_model_downloader &
DOWNLOADER_PID=$!

echo "📥 Model downloader started in background (PID: $DOWNLOADER_PID)"
echo "📋 Check download progress: tail -f /workspace/model_download.log"
echo ""

echo "🚀 Starting ComfyUI with SageAttention..."
echo "   Access at: http://localhost:8188"
echo ""

# Run ComfyUI using the installer's generated script
# The run_comfyui.sh script includes:
# - Python from venv
# - --use-sage-attention flag
# - --fast flag
# - --listen 0.0.0.0 --port 8188 (we'll add these)

cd /workspace/ComfyUI
exec python3 main.py \
    --use-sage-attention \
    --fast \
    --listen 0.0.0.0 \
    --port 8188