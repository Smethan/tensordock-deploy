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
    build-essential \
    wget \
    curl \
    git \
    ca-certificates \
    ninja-build \
    && rm -rf /var/lib/apt/lists/*

# Set Python 3.12 as the default python3
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1 \
    && update-alternatives --install /usr/bin/python python /usr/bin/python3.12 1

# Bootstrap pip for Python 3.12
RUN python3.12 -m ensurepip --upgrade && \
    python3.12 -m pip install --upgrade pip setuptools wheel

# Create virtual environment
RUN python3.12 -m venv /workspace/venv

# Activate venv and install core dependencies
ENV PATH="/workspace/venv/bin:$PATH"

# Install PyTorch 2.7.0 with CUDA 12.8 support
RUN pip install --no-cache-dir \
    torch==2.7.0 \
    torchvision \
    torchaudio \
    --index-url https://download.pytorch.org/whl/cu128

# Install Triton
RUN pip install --no-cache-dir -U --pre triton

# Clone ComfyUI
RUN git clone --depth 1 https://github.com/comfyanonymous/ComfyUI.git /workspace/ComfyUI

# Install ComfyUI requirements (this will handle transformers correctly)
RUN pip install --no-cache-dir -r /workspace/ComfyUI/requirements.txt

# Clone ComfyUI Manager
RUN git clone --depth 1 https://github.com/ltdrdata/ComfyUI-Manager.git \
    /workspace/ComfyUI/custom_nodes/comfyui-manager && \
    pip install --no-cache-dir -r /workspace/ComfyUI/custom_nodes/comfyui-manager/requirements.txt

# Build SageAttention from source with multithreading
# Set environment for faster compilation
ENV TORCH_CUDA_ARCH_LIST="8.0 8.6 8.9 9.0 12.0 12.8"
ENV MAX_JOBS="4"

RUN mkdir -p /workspace/.sageattention_build && \
    cd /workspace/.sageattention_build && \
    git clone --depth 1 https://github.com/thu-ml/SageAttention.git . && \
    pip install --no-cache-dir --no-build-isolation .

# Install model downloader dependencies WITHOUT huggingface-hub to avoid conflicts
# We'll install requests and tqdm which are needed, but skip huggingface-hub
# The model downloader will need to be updated to not use huggingface_hub module
RUN pip install --no-cache-dir requests tqdm

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
