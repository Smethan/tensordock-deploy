FROM nvidia/cuda:12.8.0-devel-ubuntu22.04

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Set working directory
WORKDIR /workspace

# Install system dependencies including Python 3.12
RUN apt-get update && apt-get install -y \
    software-properties-common \
    && add-apt-repository ppa:deadsnakes/ppa \
    && apt-get update && apt-get install -y \
    python3.12 \
    python3.12-venv \
    python3.12-dev \
    python3-pip \
    build-essential \
    wget \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set Python 3.12 as the default python3
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1 \
    && update-alternatives --install /usr/bin/python python /usr/bin/python3.12 1

# Upgrade pip for Python 3.12
RUN python3.12 -m pip install --upgrade pip setuptools wheel

# Copy the Python installer script
COPY comfyui_triton_sageattention.py /workspace/comfyui_triton_sageattention.py
RUN chmod +x /workspace/comfyui_triton_sageattention.py

# Run the installer in non-interactive mode
# This will:
# - Create virtual environment at /workspace/venv
# - Install build tools
# - Detect CUDA and install PyTorch
# - Install Triton
# - Clone ComfyUI to /workspace/ComfyUI
# - Install SageAttention and custom nodes
# - Create run_comfyui.sh script
RUN python3.12 /workspace/comfyui_triton_sageattention.py \
    --install \
    --non-interactive \
    --base-path /workspace \
    --verbose

# Install additional Python packages for model downloading
RUN /workspace/venv/bin/pip install --no-cache-dir \
    requests \
    tqdm \
    huggingface-hub

# Copy the model downloader script
COPY download_models.py /workspace/download_models.py
RUN chmod +x /workspace/download_models.py

# Copy entrypoint script
COPY entrypoint.sh /workspace/entrypoint.sh
RUN chmod +x /workspace/entrypoint.sh

# Expose ComfyUI port
EXPOSE 8188

# Set entrypoint
ENTRYPOINT ["/workspace/entrypoint.sh"]
