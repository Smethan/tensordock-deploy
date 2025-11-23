# ComfyUI Docker with SageAttention for TensorDock

Dockerized ComfyUI setup based on `nextdiffusionai/comfyui-sageattention:cuda12.8` with automatic model downloading and TensorDock optimization.

## Features

- **Base Image**: `nextdiffusionai/comfyui-sageattention:cuda12.8` with CUDA 12.8 and SageAttention
- **Auto Model Download**: Downloads all required models on first launch (HuggingFace + CivitAI)
- **Custom Nodes Pre-installed**:
  - ComfyUI-Manager
  - ComfyUI-WanVideoWrapper
  - ComfyUI-VideoHelperSuite
  - ComfyUI-GGUF
- **VRAM Auto-Detection**: Automatically uses optimal launch flags based on GPU VRAM
- **Persistent Storage**: Models and outputs persist across container restarts
- **One-Command Deploy**: Simple `docker-compose up` to get running

## Quick Start (One Command Deploy)

### Prerequisites

1. **TensorDock Instance** with:
   - Docker and Docker Compose installed
   - NVIDIA GPU with CUDA support
   - NVIDIA Container Toolkit installed

2. **Clone this repo** to your TensorDock instance:
   ```bash
   git clone <your-repo-url>
   cd <repo-directory>
   ```

### Deploy

**Option 1: Without CivitAI API Key** (skips NSFW models)
```bash
docker-compose up -d
```

**Option 2: With CivitAI API Key** (downloads all models including NSFW)
```bash
export CIVITAI_API_KEY="your_civitai_api_key_here"
docker-compose up -d
```

Get your CivitAI API key at: https://civitai.com/user/account

### First Launch

The first time you run the container, it will:
1. Download all models from HuggingFace (~15-20 minutes)
2. Download CivitAI models if API key is provided
3. Start ComfyUI automatically

**Watch the logs:**
```bash
docker-compose logs -f
```

**Access ComfyUI:**
- Local: http://localhost:8188
- TensorDock: http://YOUR_INSTANCE_IP:8188

## Usage

### Start ComfyUI
```bash
docker-compose up -d
```

### Stop ComfyUI
```bash
docker-compose down
```

### View Logs
```bash
docker-compose logs -f
```

### Force Re-download Models
```bash
rm ./comfyui-data/.models_downloaded
docker-compose restart
```

### Update ComfyUI or Custom Nodes
```bash
docker-compose exec comfyui bash
cd /workspace/ComfyUI
git pull
cd custom_nodes/ComfyUI-Manager
git pull
# etc...
```

## Directory Structure

```
.
├── Dockerfile                  # Docker image definition
├── docker-compose.yml          # One-command deployment config
├── entrypoint.sh              # Startup script with VRAM detection
├── download_models.py         # Model downloader script
└── comfyui-data/              # Persistent data (created on first run)
    ├── models/                # Downloaded models
    ├── output/                # Generated outputs
    ├── custom_nodes/          # Custom nodes
    └── .models_downloaded     # Flag file
```

## Models Downloaded

### HuggingFace Models
- **Wan2.2 I2V Models** (fp8_scaled):
  - Wan2_2-I2V-A14B-HIGH
  - Wan2_2-I2V-A14B-LOW
- **GGUF Models** (quantized for low VRAM):
  - Wan2.2-I2V-A14-BHighNoise-Q6_K
  - Wan2.2-I2V-A14B-LowNoise-Q6_K
- **Text Encoders**: umt5_xxl_fp8
- **VAE**: wan_2.1_vae
- **LoRAs**: LightX2V (high/low noise)

### CivitAI Models (requires API key)
- FurryToonMix XL Illustrious V2 (checkpoint)
- NSFW-22-H-e8 (LoRA)
- NSFW-22-L-e8 (LoRA)

## VRAM Optimization

The container automatically detects your GPU's VRAM and launches ComfyUI with appropriate flags:

- **≤12GB VRAM**: `--lowvram` mode
- **12-16GB VRAM**: `--normalvram` mode
- **>16GB VRAM**: Default (high performance) mode

## Troubleshooting

### Port 8188 Already in Use
```bash
# Change port in docker-compose.yml
ports:
  - "8189:8188"  # Use 8189 instead
```

### NVIDIA GPU Not Detected
```bash
# Verify NVIDIA Container Toolkit
docker run --rm --gpus all nvidia/cuda:12.8.0-base-ubuntu22.04 nvidia-smi

# If fails, install NVIDIA Container Toolkit:
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
    sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

### Models Not Downloading
```bash
# Check logs for errors
docker-compose logs -f

# Manually run model downloader
docker-compose exec comfyui python3 /workspace/download_models.py
```

### CivitAI Models Failing
Make sure your API key is set:
```bash
export CIVITAI_API_KEY="your_key"
docker-compose up -d
```

## Manual Build (Alternative to docker-compose)

```bash
# Build the image
docker build -t comfyui-tensordock .

# Run with GPU support
docker run -d \
  --gpus all \
  -p 8188:8188 \
  -v $(pwd)/comfyui-data/models:/workspace/ComfyUI/models \
  -v $(pwd)/comfyui-data/output:/workspace/ComfyUI/output \
  -e CIVITAI_API_KEY="your_key" \
  --shm-size 8g \
  --name comfyui \
  comfyui-tensordock
```

## Customization

### Add More Models

Edit `download_models.py` and add to the dictionaries:

```python
HUGGINGFACE_MODELS = {
    'checkpoints': [
        {
            'repo': 'username/repo',
            'files': ['model.safetensors']
        }
    ]
}

CIVITAI_MODELS = {
    'loras': [
        {
            'model_id': 12345,
            'version_id': 67890,
            'filename': 'my_lora.safetensors'
        }
    ]
}
```

Then rebuild and restart:
```bash
docker-compose down
docker-compose build
rm ./comfyui-data/.models_downloaded
docker-compose up -d
```

### Change Launch Arguments

Edit `entrypoint.sh` and modify the final line:
```bash
exec python main.py --listen 0.0.0.0 --port 8188 $VRAM_FLAG --preview-method auto --your-custom-args "$@"
```

## Performance Tips

1. **Use SageAttention**: Already included in base image (20-30% speedup)
2. **GGUF Models**: Use GGUF quantized models for lower VRAM systems
3. **Shared Memory**: Already set to 8GB in docker-compose.yml
4. **Persistent Volumes**: Models are cached, no re-download needed

## Credits

- Base Image: [NextDiffusionAI ComfyUI SageAttention](https://hub.docker.com/r/nextdiffusionai/comfyui-sageattention)
- Models: Kijai's WanVideo repositories
- CivitAI: Community models

## License

This Docker setup is provided as-is. Check individual model licenses on HuggingFace and CivitAI.
