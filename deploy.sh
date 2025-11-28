#!/bin/bash
# ComfyUI TensorDock One-Command Deploy Script

# Add CUDA path to environment for current script execution
export PATH="/usr/local/cuda-12.8/bin:$PATH"

# Check for root privileges
if [ "$EUID" -ne 0 ]; then
    echo "This script must be run with sudo. Re-running with sudo..."
    exec sudo bash "$0" "$@"
    exit # Should not be reached if exec is successful
fi

# Define state file for post-reboot continuation
STATE_FILE="/var/lib/tensordock-deploy/.reboot_required"

# Check if this is a post-reboot run
if [ -f "$STATE_FILE" ]; then
    echo "🔄 Detected post-reboot run. Cleaning up state and continuing deployment..."
    sudo rm "$STATE_FILE"
    # We'll skip CUDA installation by setting this flag
    SKIP_CUDA_INSTALL=true
else
    SKIP_CUDA_INSTALL=false
fi

# Parse command line arguments
FORCE_YES=false
while [[ $# -gt 0 ]]; do
    case $1 in
        -y|--yes)
            FORCE_YES=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [-y|--yes]"
            echo "  -y, --yes    Automatically accept all prompts"
            exit 1
            ;;
    esac
done

# Function to handle dpkg locks
handle_dpkg_locks() {
    local max_attempts=120  # Try for up to 10 minutes (120 * 5 seconds)
    local attempt=0
    local lock_found=false

    echo "🔒 Checking for existing dpkg locks..."

    # Define common dpkg lock files
    local LOCK_FILES=("/var/lib/dpkg/lock" "/var/lib/dpkg/lock-frontend" "/var/cache/apt/archives/lock")

    while [ $attempt -lt $max_attempts ]; do
        lock_found=false
        for lock_file in "${LOCK_FILES[@]}"; do
            if [ -f "$lock_file" ]; then
                lock_found=true
                echo "⚠️  dpkg lock file found: $lock_file"

                local process_id=$(sudo lsof -t "$lock_file" 2>/dev/null)
                if [ -n "$process_id" ]; then
                    local cmdline=$(ps -p "$process_id" -o comm=)
                    echo "   Process $process_id ($cmdline) is holding the lock."

                    if [[ "$cmdline" == "apt"* || "$cmdline" == "dpkg"* || "$cmdline" == "unattended-upgr"* ]]; then
                        echo "   Waiting for system updates to complete (process $process_id)..."
                        echo "   This is normal Ubuntu security update maintenance"
                    else
                        echo "   Non-APT/DPKG process holding lock. Suggesting cleanup."
                        if [ "$FORCE_YES" = true ]; then
                            echo "   Attempting to kill rogue process $process_id and remove lock (auto-accepted)."
                            sudo kill -9 "$process_id" 2>/dev/null || true
                            sudo rm -f "$lock_file"
                            lock_found=false # Assume cleared for this file
                        else
                            read -p "   Process $process_id ($cmdline) is holding the lock. Kill it and remove lock files? (y/n): " confirm_kill
                            if [ "$confirm_kill" = "y" ] || [ "$confirm_kill" = "Y" ]; then
                                sudo kill -9 "$process_id" 2>/dev/null || true
                                sudo rm -f "$lock_file"
                                lock_found=false
                            fi
                        fi
                    fi
                else
                    echo "   Lock file $lock_file found, but no process is holding it. Removing orphaned lock."
                    if [ "$FORCE_YES" = true ]; then
                        echo "   Removing orphaned lock file (auto-accepted)."
                        sudo rm -f "$lock_file"
                        lock_found=false
                    else
                        read -p "   Lock file $lock_file appears orphaned. Remove it? (y/n): " confirm_remove
                        if [ "$confirm_remove" = "y" ] || [ "$confirm_remove" = "Y" ]; then
                            sudo rm -f "$lock_file"
                            lock_found=false
                        fi
                    fi
                fi
            fi
        done

        if [ "$lock_found" = false ]; then
            echo "✅ No dpkg locks found. Proceeding."
            return 0 # Success
        fi

        attempt=$((attempt + 1))
        if [ $attempt -lt $max_attempts ]; then
            echo "   Retrying in 5 seconds... (Attempt $attempt of $max_attempts)"
            sleep 5
        fi
    done

    echo "❌ Failed to resolve dpkg locks after $max_attempts attempts. Please check manually."
    exit 1
}

# Call the function early in the script
handle_dpkg_locks



echo "=========================================="
echo "ComfyUI Docker Deployment for TensorDock"
echo "=========================================="
echo ""
echo "🔍 Debug: FORCE_YES=$FORCE_YES (should be 'true' if -y was passed)"
echo ""

# ==========================================
# CUDA 12.8 Installation Check
# ==========================================

echo "🔍 Checking CUDA version..."
CUDA_VERSION=""
NEEDS_CUDA_UPGRADE=false

# Check if CUDA is installed and get version
if [ -d "/usr/local/cuda-12.8" ] && command -v nvcc &> /dev/null; then
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
    
    if [ "$FORCE_YES" = true ]; then
        confirm="y"
        echo "Continue with CUDA 12.8 installation? (y/n): y [auto-accepted]"
    else
        read -p "Continue with CUDA 12.8 installation? (y/n): " confirm
    fi

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
    sudo apt-get -o DPkg::Lock::Timeout=120 -y --purge remove nvidia-\* cuda-\* libnvidia-\* || true

    # Step 3: Download CUDA keyring
    echo "📥 Downloading NVIDIA CUDA keyring..."
    wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2404/x86_64/cuda-keyring_1.1-1_all.deb

    # Step 4: Install keyring
    echo "🔑 Installing CUDA keyring..."
    sudo dpkg -i cuda-keyring_1.1-1_all.deb

    # Step 5: Update package lists
    echo "📋 Updating package lists..."
    sudo apt-get -o DPkg::Lock::Timeout=60 update

    # Step 6: Install CUDA 12.8 and drivers
    echo "📦 Installing CUDA 12.8, drivers, and NVIDIA Container Toolkit..."
    echo "   This may take several minutes..."
    sudo DEBIAN_FRONTEND=noninteractive apt-get -o DPkg::Lock::Timeout=120 install -y cuda-toolkit-12-8 nvidia-driver-570-server-open nvidia-container-toolkit

    # Step 6a: Install NVIDIA GPUDirect Storage
    echo "💾 Installing NVIDIA GPUDirect Storage..."
    sudo apt-get install -y nvidia-gds-12-8

    # Configure Docker runtime for NVIDIA
    echo "🐳 Configuring Docker runtime for NVIDIA..."
    sudo nvidia-ctk runtime configure --runtime=docker || true

    # Create state file to indicate reboot is needed
    sudo mkdir -p "$(dirname "$STATE_FILE")"
    sudo touch "$STATE_FILE"

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
    
    if [ "$FORCE_YES" = true ]; then
        reboot_confirm="y"
        echo "Reboot now? (y/n): y [auto-accepted]"
    else
        read -p "Reboot now? (y/n): " reboot_confirm
    fi

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
    echo "⚠️  For your user to run Docker commands without 'sudo' after deployment, you will need to log out and back in."
    echo "   The deployment script will continue without interruption."
    echo ""
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

# ==========================================
# Firewall Configuration (UFW)
# ==========================================

echo ""
echo "=========================================="
echo "🛡️  Configuring Firewall (UFW)"
echo "=========================================="
echo ""

# Install UFW if not already installed
if ! command -v ufw &> /dev/null; then
    echo "📦 Installing UFW..."
    sudo apt-get update
    sudo apt-get install -y ufw
fi

# Set default policies - allow incoming for cloud GPU access
echo "🔒 Setting default firewall policies..."
sudo ufw default allow incoming
sudo ufw default allow outgoing

# Explicitly allow SSH (redundant but ensures it's open)
echo "🔑 Ensuring SSH access..."
sudo ufw allow ssh

# Allow ComfyUI port (8188)
echo "🌐 Allowing ComfyUI port (8188/tcp)..."
sudo ufw allow 8188/tcp

# Enable UFW
echo "🔥 Enabling UFW..."
sudo ufw --force enable

echo "✅ UFW configured and enabled with permissive incoming policy."
echo ""
sudo ufw status verbose
echo ""

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
    if [ "$FORCE_YES" = true ]; then
        api_key=""
        echo "Enter your CivitAI API key (or press Enter to skip): [auto-skipped]"
    else
        read -p "Enter your CivitAI API key (or press Enter to skip): " api_key
    fi
    
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
