#!/usr/bin/env python3
"""
TensorDock Automated ComfyUI Deployment

Uses TensorDock Python SDK to deploy a ComfyUI server with cloud-init automation.

Installation:
    pip install tensordock requests

Usage:
    export TENSORDOCK_API_KEY="your_key"
    export TENSORDOCK_API_TOKEN="your_token"
    export CIVITAI_API_KEY="your_civitai_key"  # Optional

    python tensordock_auto_deploy.py --deploy
"""

import os
import sys
import time
import json
import argparse
from typing import Optional

try:
    from tensordock import TensorDockAPI
except ImportError:
    print("❌ TensorDock SDK not installed!")
    print("   Install with: pip install tensordock")
    sys.exit(1)


class ComfyUIDeployer:
    """Automated ComfyUI deployment on TensorDock."""

    def __init__(self, api_key: str, api_token: str, civitai_key: str = ""):
        """Initialize deployer with API credentials."""
        self.api = TensorDockAPI(api_key=api_key, api_token=api_token)
        self.civitai_key = civitai_key
        self.server_info = None

    def generate_cloudinit_script(self) -> str:
        """Generate cloud-init script for automated ComfyUI setup."""

        # Escape the API key for safe bash variable assignment
        civitai_key_safe = self.civitai_key.replace("'", "'\\''")

        script = f"""#!/bin/bash
set -e

# Redirect all output to log file
exec > >(tee -a /var/log/comfyui-setup.log)
exec 2>&1

echo "=========================================="
echo "ComfyUI TensorDock Cloud-Init Setup"
echo "=========================================="
echo "Started: $(date)"
echo ""

# Update system
echo "📦 Updating system packages..."
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get upgrade -y

# Install git
echo "📦 Installing git..."
apt-get install -y git

# Clone the repository
echo "📥 Cloning ComfyUI deployment repository..."
cd /root
if [ -d "tensordock-deploy" ]; then
    rm -rf tensordock-deploy
fi
git clone https://github.com/Smethan/tensordock-deploy.git
cd tensordock-deploy

# Create .env file with secrets
echo "🔐 Setting up environment variables..."
cat > .env << 'ENVEOF'
CIVITAI_API_KEY={civitai_key_safe}
COMFYUI_PATH=/workspace/ComfyUI
NVIDIA_VISIBLE_DEVICES=all
NVIDIA_DRIVER_CAPABILITIES=compute,utility
ENVEOF

echo "✅ Environment configured"
echo ""

# Make deploy script executable
chmod +x deploy.sh

# Run the deploy script (installs CUDA, Docker, builds image, starts container)
echo "🚀 Running deployment script..."
echo "   This will install CUDA 12.8, Docker, and build ComfyUI..."
echo ""

# Run deploy.sh non-interactively
export DEBIAN_FRONTEND=noninteractive
bash deploy.sh

echo ""
echo "=========================================="
echo "✅ Cloud-Init Setup Complete!"
echo "=========================================="
echo "Finished: $(date)"
echo ""
echo "📋 Check logs:"
echo "   cat /var/log/comfyui-setup.log"
echo ""
echo "📊 ComfyUI status:"
echo "   cd /root/tensordock-deploy && docker compose ps"
echo ""
echo "📝 View logs:"
echo "   cd /root/tensordock-deploy && docker compose logs -f"
echo ""
echo "🌐 Access ComfyUI at: http://$(hostname -I | awk '{{print $1}}'):8188"
echo ""
"""
        return script

    def list_available_gpus(self):
        """List available GPU models and locations."""
        print("🔍 Fetching available GPUs...")

        try:
            # The SDK doesn't expose this directly, so we'd need to use requests
            # For now, we'll deploy to any available RTX 4090
            print("   Looking for RTX 4090...")
            return True
        except Exception as e:
            print(f"❌ Error fetching GPU info: {e}")
            return False

    def deploy_server(self,
                     gpu_model: str = "rtx4090-pcie-24gb",
                     gpu_count: int = 1,
                     vcpus: int = 8,
                     ram: int = 32,
                     storage: int = 200,
                     os: str = "Ubuntu 22.04 LTS") -> Optional[dict]:
        """Deploy a new ComfyUI server."""

        print(f"\n🚀 Deploying ComfyUI server:")
        print(f"   GPU: {gpu_count}x {gpu_model}")
        print(f"   vCPUs: {vcpus}")
        print(f"   RAM: {ram} GB")
        print(f"   Storage: {storage} GB")
        print(f"   OS: {os}")
        print()

        # Generate cloud-init script
        print("📝 Generating cloud-init setup script...")
        cloudinit_script = self.generate_cloudinit_script()

        # Save cloud-init script to temp file for debugging
        with open("/tmp/tensordock_cloudinit.sh", "w") as f:
            f.write(cloudinit_script)
        print(f"   💾 Cloud-init script saved to: /tmp/tensordock_cloudinit.sh")

        try:
            print("\n⏳ Creating server instance...")

            # Deploy VM with cloud-init
            # Note: The SDK might not support cloudinit_file parameter directly
            # We may need to use raw API calls
            result = self.api.virtual_machines.deploy_vm(
                name=f"ComfyUI-{int(time.time())}",
                gpu_count=gpu_count,
                gpu_model=gpu_model,
                vcpus=vcpus,
                ram=ram,
                storage=storage,
                operating_system=os,
                # The SDK may not support this parameter - need to check
                # cloudinit_file=cloudinit_script
            )

            print("✅ Server deployment initiated!")
            print(f"\n📄 Response: {json.dumps(result, indent=2)}")

            self.server_info = result
            return result

        except Exception as e:
            print(f"❌ Deployment failed: {e}")
            return None

    def deploy_with_raw_api(self,
                           gpu_model: str = "rtx4090-pcie-24gb",
                           gpu_count: int = 1,
                           vcpus: int = 8,
                           ram: int = 32,
                           storage: int = 200,
                           os: str = "Ubuntu 22.04 LTS"):
        """Deploy using v2 API (supports cloud-init)."""

        import requests

        print(f"\n🚀 Deploying with v2 API (supports cloud-init):")
        print(f"   GPU: {gpu_count}x {gpu_model}")
        print(f"   vCPUs: {vcpus}")
        print(f"   RAM: {ram} GB")
        print(f"   Storage: {storage} GB")
        print()

        # Generate cloud-init
        cloudinit_script = self.generate_cloudinit_script()

        # First, get available locations
        print("📍 Finding available location with RTX 4090...")
        locations_url = "https://dashboard.tensordock.com/api/v2/locations"

        # v2 API uses Bearer token authentication
        headers = {
            "Authorization": f"Bearer {self.api.api_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        response = requests.get(locations_url, headers=headers)

        if response.status_code != 200:
            print(f"❌ Failed to get locations: {response.text}")
            return None

        locations_data = response.json()
        locations = locations_data.get("locations", [])

        # Find a location with available RTX 4090
        selected_location_id = None
        selected_location_name = None
        selected_gpu_model = None

        for location in locations:
            location_id = location.get("id")
            city = location.get("city", "Unknown")
            country = location.get("country", "Unknown")
            location_name = f"{city}, {country}"

            # Check GPUs available in this location
            gpus = location.get("gpus", [])
            for gpu in gpus:
                gpu_name = gpu.get("name", "")
                max_count = gpu.get("max_count", 0)

                if max_count > 0 and ("4090" in gpu_name.lower() or "rtx4090" in gpu_name.lower()):
                    selected_location_id = location_id
                    selected_location_name = location_name
                    selected_gpu_model = gpu_name
                    print(f"✅ Found RTX 4090 at: {location_name}")
                    print(f"   Location ID: {location_id}")
                    print(f"   GPU: {gpu_name}")
                    print(f"   Max available: {max_count}")
                    print(f"   Price: ${gpu.get('price_per_hour', 'N/A')}/hr")
                    break

            if selected_location_id:
                break

        if not selected_location_id:
            print("❌ No RTX 4090 available!")
            print("\n📋 Available locations (first 3):")
            for location in locations[:3]:
                location_name = f"{location.get('city', 'Unknown')}, {location.get('country', 'Unknown')}"
                gpus = location.get("gpus", [])
                available_gpus = [f"{gpu['name']} ({gpu['max_count']} max)" for gpu in gpus if gpu.get('max_count', 0) > 0]
                print(f"   {location_name}: {', '.join(available_gpus) if available_gpus else 'No GPUs available'}")
            return None

        # Deploy the server using v2 API
        print("\n⏳ Creating server instance...")
        print(f"   Using GPU model: {selected_gpu_model}")

        deploy_url = "https://dashboard.tensordock.com/api/v2/instances"

        # v2 API uses JSON:API format
        payload = {
            "data": {
                "type": "virtualmachine",
                "attributes": {
                    "name": f"ComfyUI-{int(time.time())}",
                    "type": "virtualmachine",
                    "image": "ubuntu2404",  # Ubuntu 24.04 LTS
                    "resources": {
                        "vcpu_count": vcpus,
                        "ram_gb": ram,
                        "storage_gb": storage,
                        "gpus": {
                            selected_gpu_model: {
                                "count": gpu_count
                            }
                        }
                    },
                    "location_id": selected_location_id,
                    "useDedicatedIp": False,  # Use port forwarding instead
                    "ssh_key": open('/home/smethan/.ssh/id_ed25519.pub').readline().strip()
                    # No cloud-init - will SSH in manually to run setup
                }
            }
        }

        # Save the cloud-init script for manual execution
        with open("/tmp/tensordock_setup.sh", "w") as f:
            f.write(cloudinit_script)
        print(f"   💾 Setup script saved to: /tmp/tensordock_setup.sh")

        response = requests.post(deploy_url, headers=headers, json=payload)

        if response.status_code not in [200, 201]:
            print(f"❌ Deployment failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return None

        result = response.json()
        print("✅ Server created!")
        print(f"\n📄 Server Info:")
        print(json.dumps(result, indent=2))

        self.server_info = result

        # Extract instance data from v2 API response
        instance_data = result.get("data", {})
        instance_id = instance_data.get("id")
        attributes = instance_data.get("attributes", {})
        instance_name = attributes.get("name")
        instance_status = attributes.get("status")

        print(f"\n🎉 Instance created!")
        print(f"   Instance ID: {instance_id}")
        print(f"   Name: {instance_name}")
        print(f"   Initial Status: {instance_status}")

        # Save server info
        with open("server_info.json", 'w') as f:
            json.dump(result, f, indent=2)
        print(f"   💾 Response saved to: server_info.json")

        # Wait for instance to be running and get connection details
        print(f"\n⏳ Waiting for instance to be ready...")
        ssh_host, ssh_port = self.wait_for_instance(instance_id, headers)

        if not ssh_host:
            print("❌ Failed to get instance connection details")
            return result

        print(f"\n✅ Instance is ready!")
        print(f"   SSH: ssh -p {ssh_port} root@{ssh_host}")

        # SSH in and run the deployment script
        print(f"\n🚀 Running deployment script over SSH...")
        self.run_remote_deployment(ssh_host, ssh_port, cloudinit_script)

        return result

    def wait_for_instance(self, instance_id: str, headers: dict, max_wait: int = 300) -> tuple:
        """Wait for instance to be running and return SSH details."""
        import requests
        import time

        instance_url = f"https://dashboard.tensordock.com/api/v2/instances/{instance_id}"
        start_time = time.time()

        while time.time() - start_time < max_wait:
            response = requests.get(instance_url, headers=headers)
            if response.status_code == 200:
                data = response.json().get("data", {})
                attributes = data.get("attributes", {})
                status = attributes.get("status")

                print(f"   Status: {status}...", end="\r")

                if status == "running":
                    # Get connection details
                    ssh_host = attributes.get("ip_address")
                    ssh_port = attributes.get("ssh_port", 22)

                    if ssh_host:
                        print(f"\n   Instance running at {ssh_host}:{ssh_port}")
                        # Wait a bit more for SSH to be fully ready
                        print("   Waiting for SSH to be ready...")
                        time.sleep(30)
                        return ssh_host, ssh_port

            time.sleep(10)

        return None, None

    def run_remote_deployment(self, host: str, port: int, setup_script: str):
        """SSH into the instance and run the deployment script."""
        import subprocess

        # Save setup script to temp file
        script_path = "/tmp/tensordock_remote_setup.sh"
        with open(script_path, "w") as f:
            f.write(setup_script)

        print(f"   Uploading setup script...")

        # Upload the script
        scp_cmd = [
            "scp",
            "-P", str(port),
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-i", "/home/smethan/.ssh/id_ed25519",
            script_path,
            f"root@{host}:/root/setup.sh"
        ]

        result = subprocess.run(scp_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"   ❌ Failed to upload script: {result.stderr}")
            return

        print(f"   ✅ Script uploaded")
        print(f"\n   🚀 Executing deployment (this will take ~10-15 minutes)...")
        print(f"   Follow along with the output:\n")

        # Run the script over SSH
        ssh_cmd = [
            "ssh",
            "-p", str(port),
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-i", "/home/smethan/.ssh/id_ed25519",
            f"root@{host}",
            "bash /root/setup.sh"
        ]

        # Stream output in real-time
        process = subprocess.Popen(ssh_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

        for line in process.stdout:
            print(f"   {line}", end="")

        process.wait()

        if process.returncode == 0:
            print(f"\n\n🎉 Deployment completed successfully!")
            print(f"   ComfyUI should be running at: http://{host}:8188")
        else:
            print(f"\n\n⚠️  Deployment script exited with code {process.returncode}")
            print(f"   Check logs: ssh -p {port} -i /home/smethan/.ssh/id_ed25519 root@{host} 'tail -f /var/log/comfyui-setup.log'")

    def list_and_manage_instances(self):
        """List all instances and allow termination."""
        import requests

        print("🔍 Fetching all instances...")

        # v2 API uses Bearer token authentication
        headers = {
            "Authorization": f"Bearer {self.api.api_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        instances_url = "https://dashboard.tensordock.com/api/v2/instances"
        response = requests.get(instances_url, headers=headers)

        if response.status_code != 200:
            print(f"❌ Failed to fetch instances: {response.text}")
            return

        response_data = response.json()
        print(response.content)

        # Handle different response formats
        data = response_data.get("data", [])
        if isinstance(data, dict):
            # Format: {"data": {"instances": [...]}}
            instances = data.get("instances", [])
        else:
            # Format: {"data": [...]}
            instances = data

        if not instances:
            print("📭 No instances found")
            return

        print(f"\n📋 Found {len(instances)} instance(s):\n")

        # Display instances
        for idx, instance in enumerate(instances, 1):
            instance_id = instance.get("id")
            attributes = instance.get("attributes", {})
            name = attributes.get("name", "N/A")
            status = attributes.get("status", "N/A")
            created = attributes.get("created_at", "N/A")
            ip_address = attributes.get("ip_address", "N/A")
            ssh_port = attributes.get("ssh_port", "N/A")

            # Get GPU info
            resources = attributes.get("resources", {})
            gpus = resources.get("gpus", {})
            gpu_info = ", ".join([f"{count}x {name}" for name, info in gpus.items() for count in [info.get("count", 0)] if count > 0])

            print(f"[{idx}] {name}")
            print(f"    ID: {instance_id}")
            print(f"    Status: {status}")
            print(f"    IP: {ip_address}:{ssh_port}")
            print(f"    GPUs: {gpu_info or 'None'}")
            print(f"    Created: {created}")
            print()

        # Ask user which to terminate
        print("Enter instance numbers to terminate (comma-separated), or 'q' to quit:")
        user_input = input("> ").strip()

        if user_input.lower() == 'q':
            print("Cancelled")
            return

        # Parse selections
        try:
            selections = [int(x.strip()) for x in user_input.split(",")]
        except ValueError:
            print("❌ Invalid input")
            return

        # Confirm
        instances_to_delete = []
        for idx in selections:
            if 1 <= idx <= len(instances):
                instance = instances[idx - 1]
                instances_to_delete.append(instance)

        if not instances_to_delete:
            print("No valid instances selected")
            return

        print(f"\n⚠️  You are about to terminate {len(instances_to_delete)} instance(s):")
        for instance in instances_to_delete:
            print(f"   - {instance.get('attributes', {}).get('name')} ({instance.get('id')})")

        confirm = input("\nType 'yes' to confirm: ").strip().lower()
        if confirm != 'yes':
            print("Cancelled")
            return

        # Terminate instances
        print()
        for instance in instances_to_delete:
            instance_id = instance.get("id")
            instance_name = instance.get("attributes", {}).get("name")

            print(f"🗑️  Terminating {instance_name}...")

            delete_url = f"https://dashboard.tensordock.com/api/v2/instances/{instance_id}"
            response = requests.delete(delete_url, headers=headers)

            if response.status_code in [200, 204]:
                print(f"   ✅ Terminated successfully")
            else:
                print(f"   ❌ Failed: {response.text}")

        print(f"\n✅ Done!")

    def save_connection_info(self, server_info: dict, filename: str = "server_info.json"):
        """Save server connection information."""

        with open(filename, 'w') as f:
            json.dump(server_info, f, indent=2)

        print(f"\n💾 Connection info saved to: {filename}")

        # Print connection details if available
        if "server" in server_info:
            server = server_info["server"]
            print(f"\n🔑 Connection Details:")
            print(f"   IP: {server.get('ip', 'N/A')}")
            print(f"   Port: {server.get('port', '22')}")
            print(f"   Username: root")
            print(f"   Password: {server.get('password', 'N/A')}")
            print(f"\n🌐 ComfyUI will be available at:")
            print(f"   http://{server.get('ip', 'N/A')}:8188")
            print(f"\n⏱️  Cloud-init setup takes ~10-15 minutes")
            print(f"   Monitor: ssh -p {server.get('port', '22')} root@{server.get('ip', 'N/A')}")
            print(f"   Check logs: tail -f /var/log/comfyui-setup.log")


def main():
    parser = argparse.ArgumentParser(
        description="TensorDock ComfyUI Automated Deployment",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment Variables:
  TENSORDOCK_API_KEY      - Your TensorDock API key
  TENSORDOCK_API_TOKEN    - Your TensorDock API token
  CIVITAI_API_KEY         - Your CivitAI API key (optional)

Examples:
  # Deploy ComfyUI server
  python tensordock_auto_deploy.py --deploy

  # Deploy with custom specs
  python tensordock_auto_deploy.py --deploy --vcpus 16 --ram 64 --storage 500

  # List all instances and optionally terminate them
  python tensordock_auto_deploy.py --list

Get API keys at: https://marketplace.tensordock.com/api
        """
    )

    parser.add_argument("--deploy", action="store_true",
                       help="Deploy a new ComfyUI server")
    parser.add_argument("--list", action="store_true",
                       help="List all instances and optionally terminate them")

    parser.add_argument("--gpu-model", default="rtx4090-pcie-24gb",
                       help="GPU model (default: rtx4090-pcie-24gb)")
    parser.add_argument("--gpu-count", type=int, default=1,
                       help="Number of GPUs (default: 1)")
    parser.add_argument("--vcpus", type=int, default=8,
                       help="vCPUs (default: 8)")
    parser.add_argument("--ram", type=int, default=32,
                       help="RAM in GB (default: 32)")
    parser.add_argument("--storage", type=int, default=200,
                       help="Storage in GB (default: 200)")

    args = parser.parse_args()

    # Get credentials from environment
    api_key = os.getenv("TENSORDOCK_API_KEY")
    api_token = os.getenv("TENSORDOCK_API_TOKEN")
    civitai_key = os.getenv("CIVITAI_API_KEY", "")

    if not api_key or not api_token:
        print("❌ Error: TensorDock API credentials required!")
        print("\nSet environment variables:")
        print("  export TENSORDOCK_API_KEY='your_key'")
        print("  export TENSORDOCK_API_TOKEN='your_token'")
        print("\nGet credentials at: https://marketplace.tensordock.com/api")
        sys.exit(1)

    # Create deployer
    deployer = ComfyUIDeployer(api_key, api_token, civitai_key)

    if args.deploy:
        # Deploy new instance
        deployer.deploy_with_raw_api(
            gpu_model=args.gpu_model,
            gpu_count=args.gpu_count,
            vcpus=args.vcpus,
            ram=args.ram,
            storage=args.storage
        )
    elif args.list:
        # List and manage instances
        deployer.list_and_manage_instances()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
