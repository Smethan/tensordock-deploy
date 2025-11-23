#!/bin/bash
set -e

echo "=========================================="
echo "ComfyUI TensorDock Startup"
echo "=========================================="
echo ""

# Background function to download models after ComfyUI setup completes
background_model_downloader() {
    MODELS_FLAG="/workspace/.models_downloaded"
    DOWNLOAD_LOG="/workspace/model_download.log"

    exec > >(tee -a "$DOWNLOAD_LOG") 2>&1

    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Background model downloader started"

    # Wait for ComfyUI setup to complete (indicated by run_gpu.sh existing)
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Waiting for ComfyUI setup to complete..."
    while [ ! -f "/workspace/run_gpu.sh" ]; do
        sleep 2
    done
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ComfyUI setup complete, run_gpu.sh found"

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

        # Run the model downloader
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

# Immediately start the original ComfyUI entrypoint
exec /entrypoint.sh