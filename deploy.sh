#!/bin/bash
# ComfyUI TensorDock One-Command Deploy Script

set -e

echo "=========================================="
echo "ComfyUI Docker Deployment for TensorDock"
echo "=========================================="
echo ""

# ==========================================
# CUDA 12.8 Installation Check
# ==========================================

echo "🔍 Checking CUDA version..."
CUDA_VERSION=""
NEEDS_CUDA_UPGRADE=false

# Check if CUDA is installed and get version
if command -v nvcc &> /dev/null; then
    CUDA_VERSION=$(nvcc --version | grep "release" | sed -n 's/.*release \([0-9]\+\.[0-9]\+\).*/\1/p')
    echo "✅ CUDA $CUDA_VERSION detected"

    # Check if we need to upgrade (anything less than 12.8)
    if [ "$(printf '%s\n' "12.8" "$CUDA_VERSION" | sort -V | head -n1)" != "12.8" ]; then
        NEEDS_CUDA_UPGRADE=true
        echo "⚠️  CUDA $CUDA_VERSION is installed, but CUDA 12.8 is required"
    else
        echo "✅ CUDA 12.8 or higher is installed"
    fi
else
    echo "⚠️  CUDA not detected"
    NEEDS_CUDA_UPGRADE=true
fi

# Install or upgrade to CUDA 12.8 if needed
if [ "$NEEDS_CUDA_UPGRADE" = true ]; then
    echo ""
    echo "=========================================="
    echo "📦 CUDA 12.8 Installation Required"
    echo "=========================================="
    echo ""
    echo "This script will:"
    echo "  1. Download NVIDIA CUDA repository keyring"
    echo "  2. Remove existing NVIDIA drivers and CUDA installations"
    echo "  3. Install CUDA 12.8 and compatible drivers (570)"
    echo "  4. Install NVIDIA Container Toolkit"
    echo "  5. Reboot the system"
    echo ""
    echo "⚠️  WARNING: This will remove existing NVIDIA drivers!"
    echo ""
    read -p "Continue with CUDA 12.8 installation? (y/n): " confirm

    if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
        echo "❌ Installation cancelled. CUDA 12.8 is required to run this setup."
        exit 1
    fi

    echo ""
    echo "🔧 Starting CUDA 12.8 installation..."
    echo ""
    # Step 1: Remove hold status from NVIDIA packages
    echo "🔓 Removing hold status from NVIDIA packages..."
    sudo apt-mark unhold nvidia\* libnvidia\* cuda\*|| true

    # Step 2: Purge old NVIDIA installations
    echo "🗑️  Removing old NVIDIA drivers and CUDA installations..."
    sudo apt --purge remove nvidia-\* cuda-\* libnvidia-\* -y || true

    # Step 3: Download CUDA keyring
    echo "📥 Downloading NVIDIA CUDA keyring..."
    wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2404/x86_64/cuda-keyring_1.1-1_all.deb

    # Step 4: Install keyring
    echo "🔑 Installing CUDA keyring..."
    sudo dpkg -i cuda-keyring_1.1-1_all.deb

    # Step 5: Update package lists
    echo "📋 Updating package lists..."
    sudo apt update

    # Step 6: Install CUDA 12.8 and drivers
    echo "📦 Installing CUDA 12.8, drivers, and NVIDIA Container Toolkit..."
    echo "   This may take several minutes..."
    sudo apt install -y cuda-drivers-570 cuda-toolkit-12-8 nvidia-driver-570-server nvidia-container-toolkit

    # Step 6a: Install NVIDIA GPUDirect Storage
    echo "💾 Installing NVIDIA GPUDirect Storage..."
    sudo apt install -y nvidia-gds-12-8

    # Configure Docker runtime for NVIDIA
    echo "🐳 Configuring Docker runtime for NVIDIA..."
    sudo nvidia-ctk runtime configure --runtime=docker || true

    echo ""
    echo "=========================================="
    echo "✅ CUDA 12.8 Installation Complete!"
    echo "=========================================="
    echo ""
    echo "⚠️  SYSTEM REBOOT REQUIRED"
    echo ""
    echo "After reboot, run this script again to complete deployment:"
    echo "  bash deploy.sh"
    echo ""
    read -p "Reboot now? (y/n): " reboot_confirm

    if [ "$reboot_confirm" = "y" ] || [ "$reboot_confirm" = "Y" ]; then
        echo "🔄 Rebooting system..."
        sudo reboot
    else
        echo "⚠️  Please reboot manually and run this script again."
        exit 0
    fi
fi

echo ""
echo "✅ CUDA 12.8 is ready!"
echo ""

# ==========================================
# Docker Installation (Official Method)
# ==========================================

if ! command -v docker &> /dev/null; then
    echo "=========================================="
    echo "📦 Installing Docker Engine"
    echo "=========================================="
    echo ""

    # Uninstall old/conflicting packages
    echo "🗑️  Removing any conflicting packages..."
    for pkg in docker.io docker-doc docker-compose docker-compose-v2 podman-docker containerd runc; do
        sudo apt-get remove -y $pkg 2>/dev/null || true
    done

    # Update and install prerequisites
    echo "📋 Installing prerequisites..."
    sudo apt-get update
    sudo apt-get install -y ca-certificates curl

    # Create keyrings directory
    sudo install -m 0755 -d /etc/apt/keyrings

    # Add Docker's official GPG key
    echo "🔑 Adding Docker GPG key..."
    sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    sudo chmod a+r /etc/apt/keyrings/docker.asc

    # Add Docker repository
    echo "📦 Adding Docker repository..."
    echo "Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Signed-By: /etc/apt/keyrings/docker.asc" | sudo tee /etc/apt/sources.list.d/docker.sources > /dev/null

    # Update package index
    sudo apt-get update

    # Install Docker Engine, CLI, containerd, and plugins
    echo "🐳 Installing Docker Engine and components..."
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

    # Create docker group (may already exist)
    sudo groupadd docker 2>/dev/null || true

    # Add current user to docker group
    echo "👤 Adding user to docker group..."
    sudo usermod -aG docker $USER

    # Enable Docker to start on boot
    echo "🚀 Enabling Docker service..."
    sudo systemctl enable docker.service
    sudo systemctl enable containerd.service

    # Start Docker service
    sudo systemctl start docker

    echo ""
    echo "✅ Docker installed successfully!"
    echo ""
    echo "⚠️  IMPORTANT: You need to log out and back in for group changes to take effect."
    echo "   After relogging, run this script again to complete deployment."
    echo ""
    read -p "Would you like to activate Docker for this session with 'newgrp docker'? (y/n): " newgrp_confirm

    if [ "$newgrp_confirm" = "y" ] || [ "$newgrp_confirm" = "Y" ]; then
        echo "🔄 Activating docker group and continuing deployment..."
        echo ""
        # Use newgrp to activate group and re-run the script
        exec sg docker "$0 $@"
    else
        echo "Please log out and back in, then run: bash deploy.sh"
        exit 0
    fi
fi

# Verify Docker Compose is available (should be installed as plugin)
if ! docker compose version &> /dev/null; then
    echo "⚠️  Docker Compose plugin not found. This is unexpected."
    echo "   Attempting to verify Docker installation..."
    docker --version
    exit 1
fi

echo "✅ Docker Engine is installed and ready"
echo ""

# Check if NVIDIA Container Toolkit is installed
if ! docker run --rm --gpus all nvidia/cuda:12.8.0-base-ubuntu22.04 nvidia-smi &> /dev/null; then
    echo "⚠️  NVIDIA Container Toolkit not detected. Installing..."


    # Install nvidia-container-toolkit
    sudo apt-get update
    sudo apt-get install -y nvidia-container-toolkit

    # Configure Docker runtime
    sudo nvidia-ctk runtime configure --runtime=docker

    # Restart Docker
    sudo systemctl restart docker

    echo "✅ NVIDIA Container Toolkit installed."
fi

# Check for CivitAI API key
echo ""
echo "CivitAI API Key Setup (optional)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "CivitAI API key is needed to download NSFW models."
echo "Get your API key at: https://civitai.com/user/account"
echo ""

if [ -f .env ]; then
    echo "✅ .env file already exists."
    source .env
    if [ -n "$CIVITAI_API_KEY" ]; then
        echo "✅ CivitAI API key found in .env"
    else
        echo "⚠️  No CivitAI API key in .env (NSFW models will be skipped)"
    fi
else
    read -p "Enter your CivitAI API key (or press Enter to skip): " api_key
    if [ -n "$api_key" ]; then
        echo "CIVITAI_API_KEY=$api_key" > .env
        echo "✅ API key saved to .env"
    else
        echo "CIVITAI_API_KEY=" > .env
        echo "⚠️  Skipping CivitAI API key (NSFW models won't download)"
    fi
fi

# Create data directory
echo ""
echo "📁 Creating persistent data directory..."
mkdir -p comfyui-data

# Build and start
echo ""
echo "🚀 Building and starting ComfyUI..."
echo ""

docker compose up -d --build

echo ""
echo "=========================================="
echo "✨ Deployment Complete!"
echo "=========================================="
echo ""
echo "📊 Status:"
docker compose ps

echo ""
echo "📝 View logs:"
echo "   docker compose logs -f"
echo ""
echo "🌐 Access ComfyUI at:"
echo "   http://localhost:8188"
if command -v hostname &> /dev/null; then
    IP=$(hostname -I | awk '{print $1}')
    echo "   http://$IP:8188"
fi
echo ""
echo "⚠️  First launch will download models (~15-20 minutes)"
echo "   Watch progress with: docker compose logs -f"
echo ""
echo "🛑 To stop:"
echo "   docker compose down"
echo ""
echo "=========================================="
