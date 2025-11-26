#!/usr/bin/env python3
"""
TensorDock Automated Server Deployment Script

Deploys a ComfyUI server on TensorDock with:
- 8 vCPUs
- 1x RTX 4090 GPU
- 32GB RAM
- 200GB Storage

Then automatically sets up and runs the ComfyUI Docker container.
"""

import os
import sys
import time
import json
import requests
import argparse
from pathlib import Path
from typing import Dict, Optional

# TensorDock API Configuration
API_BASE_URL = "https://marketplace.tensordock.com/api/v0"
CONSOLE_API_URL = "https://console.tensordock.com/api/v0"

class TensorDockDeployer:
    def __init__(self, api_key: str, api_token: str):
        """Initialize TensorDock deployer with API credentials."""
        self.api_key = api_key
        self.api_token = api_token
        self.headers = {
            "Authorization": f"Bearer {api_key}:{api_token}",
            "Content-Type": "application/json"
        }
        self.server_id = None
        self.server_ip = None
        self.server_port = None
        self.server_password = None

    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None, use_console_api: bool = False) -> Dict:
        """Make API request to TensorDock."""
        base_url = CONSOLE_API_URL if use_console_api else API_BASE_URL
        url = f"{base_url}/{endpoint}"

        try:
            if method == "GET":
                response = requests.get(url, headers=self.headers, params=data)
            elif method == "POST":
                response = requests.post(url, headers=self.headers, json=data)
            elif method == "DELETE":
                response = requests.delete(url, headers=self.headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"❌ API request failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response: {e.response.text}")
            sys.exit(1)

    def get_available_locations(self) -> Dict:
        """Get available GPU locations and pricing."""
        print("🔍 Fetching available GPU locations...")

        # Get stock information
        stock = self._make_request("GET", "client/deploy/hostnodes")

        # Filter for RTX 4090 availability
        rtx_4090_locations = []
        for location in stock.get("hostnodes", []):
            for gpu in location.get("gpu_models", []):
                if "4090" in gpu.get("model", ""):
                    rtx_4090_locations.append({
                        "location": location.get("location", "Unknown"),
                        "hostnode": location.get("hostnode", ""),
                        "gpu_model": gpu.get("model", ""),
                        "gpu_count": gpu.get("amount", 0),
                        "specs": location.get("specs", {})
                    })

        return rtx_4090_locations

    def deploy_server(self,
                     gpu_model: str = "RTX 4090",
                     gpu_count: int = 1,
                     vcpus: int = 8,
                     ram: int = 32,
                     storage: int = 200,
                     os: str = "Ubuntu 22.04 LTS",
                     civitai_api_key: str = "") -> Dict:
        """Deploy a new server with specified specs."""

        print(f"\n🚀 Deploying server with:")
        print(f"   GPU: {gpu_count}x {gpu_model}")
        print(f"   vCPUs: {vcpus}")
        print(f"   RAM: {ram} GB")
        print(f"   Storage: {storage} GB")
        print(f"   OS: {os}")

        # Get available locations first
        locations = self.get_available_locations()

        if not locations:
            print("❌ No RTX 4090 GPUs available!")
            sys.exit(1)

        print(f"\n✅ Found {len(locations)} location(s) with RTX 4090")
        for idx, loc in enumerate(locations, 1):
            print(f"   {idx}. {loc['location']} - {loc['gpu_count']} GPU(s) available")

        # Use first available location
        selected_location = locations[0]
        print(f"\n📍 Deploying to: {selected_location['location']}")

        # Prepare deployment request
        deploy_data = {
            "gpu_model": gpu_model.replace(" ", "_"),
            "gpu_count": gpu_count,
            "vcpus": vcpus,
            "ram": ram,
            "storage": storage,
            "hostnode": selected_location["hostnode"],
            "operating_system": os.replace(" ", "_").replace(".", ""),
            "name": f"ComfyUI-{int(time.time())}"
        }

        print("\n⏳ Creating server instance...")
        result = self._make_request("POST", "client/deploy/single", deploy_data, use_console_api=True)

        self.server_id = result.get("server", {}).get("id")

        if not self.server_id:
            print("❌ Failed to create server!")
            print(f"Response: {json.dumps(result, indent=2)}")
            sys.exit(1)

        print(f"✅ Server created! ID: {self.server_id}")
        return result

    def wait_for_server_ready(self, timeout: int = 300) -> bool:
        """Wait for server to be ready and get connection details."""
        print("\n⏳ Waiting for server to be ready...")

        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # Get server details
                server_info = self._make_request("GET", f"client/get/{self.server_id}", use_console_api=True)

                status = server_info.get("server", {}).get("status", "")

                if status == "running":
                    # Extract connection details
                    self.server_ip = server_info.get("server", {}).get("ip")
                    self.server_port = server_info.get("server", {}).get("port", 22)
                    self.server_password = server_info.get("server", {}).get("password")

                    print(f"\n✅ Server is ready!")
                    print(f"   IP: {self.server_ip}")
                    print(f"   Port: {self.server_port}")
                    print(f"   Username: root")
                    print(f"   Password: {self.server_password}")

                    return True
                else:
                    print(f"   Status: {status} - waiting...")
                    time.sleep(10)

            except Exception as e:
                print(f"   Error checking status: {e}")
                time.sleep(10)

        print(f"❌ Server did not become ready within {timeout} seconds")
        return False

    def setup_and_deploy_comfyui(self, docker_image: str = "electricespeon/comfyui-tensordock:latest"):
        """SSH into server and deploy ComfyUI."""

        print("\n🔧 Setting up ComfyUI on server...")

        # Install sshpass if not available
        try:
            import subprocess
            subprocess.run(["which", "sshpass"], check=True, capture_output=True)
        except:
            print("⚠️  Installing sshpass for automated SSH...")
            os.system("sudo apt-get update && sudo apt-get install -y sshpass")

        # SSH command prefix
        ssh_cmd = f"sshpass -p '{self.server_password}' ssh -o StrictHostKeyChecking=no -p {self.server_port} root@{self.server_ip}"

        # Commands to run on server
        commands = [
            # Update system
            "apt-get update",

            # Clone the deploy repository
            "git clone https://github.com/ElectricEspeon/tensordock-deploy.git /root/comfyui || (cd /root/comfyui && git pull)",

            # Change to directory
            "cd /root/comfyui",

            # Make deploy script executable
            "chmod +x deploy.sh",

            # Run deploy script (will install CUDA, Docker, etc.)
            "DEBIAN_FRONTEND=noninteractive ./deploy.sh",

            # Pull the pre-built Docker image
            f"docker pull {docker_image}",

            # Update docker-compose.yml to use pre-built image
            f"sed -i 's|build: .|image: {docker_image}|g' docker-compose.yml",

            # Start the container
            "docker compose up -d"
        ]

        print("\n📋 Executing deployment commands...")

        for idx, cmd in enumerate(commands, 1):
            print(f"\n[{idx}/{len(commands)}] {cmd[:80]}...")

            full_cmd = f"{ssh_cmd} '{cmd}'"
            result = os.system(full_cmd)

            if result != 0:
                print(f"⚠️  Command exited with code {result}")
                if "deploy.sh" in cmd:
                    print("   (This may require manual intervention)")
            else:
                print(f"✅ Command completed")

        print(f"\n🎉 Deployment complete!")
        print(f"\n🌐 Access ComfyUI at: http://{self.server_ip}:8188")
        print(f"\n🔑 SSH Access: ssh -p {self.server_port} root@{self.server_ip}")
        print(f"   Password: {self.server_password}")

    def save_connection_info(self, filename: str = "server_info.json"):
        """Save server connection information to file."""
        info = {
            "server_id": self.server_id,
            "ip": self.server_ip,
            "port": self.server_port,
            "username": "root",
            "password": self.server_password,
            "comfyui_url": f"http://{self.server_ip}:8188"
        }

        with open(filename, 'w') as f:
            json.dump(info, f, indent=2)

        print(f"\n💾 Connection info saved to: {filename}")

    def delete_server(self):
        """Delete the deployed server."""
        if not self.server_id:
            print("❌ No server ID to delete")
            return

        print(f"\n🗑️  Deleting server {self.server_id}...")

        try:
            result = self._make_request("DELETE", f"client/delete/{self.server_id}", use_console_api=True)
            print("✅ Server deleted successfully")
            return result
        except Exception as e:
            print(f"❌ Failed to delete server: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="TensorDock ComfyUI Deployment Automation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Deploy server and set up ComfyUI
  %(prog)s --api-key YOUR_KEY --api-token YOUR_TOKEN --deploy

  # Deploy with custom Docker image
  %(prog)s --api-key YOUR_KEY --api-token YOUR_TOKEN --deploy --image myuser/comfyui:custom

  # Just check available locations
  %(prog)s --api-key YOUR_KEY --api-token YOUR_TOKEN --check-availability

  # Delete server by ID
  %(prog)s --api-key YOUR_KEY --api-token YOUR_TOKEN --delete SERVER_ID

Environment Variables:
  TENSORDOCK_API_KEY      - Your TensorDock API key
  TENSORDOCK_API_TOKEN    - Your TensorDock API token
        """
    )

    parser.add_argument("--api-key",
                       default=os.getenv("TENSORDOCK_API_KEY"),
                       help="TensorDock API key (or set TENSORDOCK_API_KEY env var)")
    parser.add_argument("--api-token",
                       default=os.getenv("TENSORDOCK_API_TOKEN"),
                       help="TensorDock API token (or set TENSORDOCK_API_TOKEN env var)")

    parser.add_argument("--deploy", action="store_true",
                       help="Deploy a new server and set up ComfyUI")
    parser.add_argument("--check-availability", action="store_true",
                       help="Check available RTX 4090 locations")
    parser.add_argument("--delete", metavar="SERVER_ID",
                       help="Delete a server by ID")

    parser.add_argument("--image", default="electricespeon/comfyui-tensordock:latest",
                       help="Docker image to use (default: electricespeon/comfyui-tensordock:latest)")

    parser.add_argument("--vcpus", type=int, default=8,
                       help="Number of vCPUs (default: 8)")
    parser.add_argument("--ram", type=int, default=32,
                       help="RAM in GB (default: 32)")
    parser.add_argument("--storage", type=int, default=200,
                       help="Storage in GB (default: 200)")

    args = parser.parse_args()

    # Validate credentials
    if not args.api_key or not args.api_token:
        print("❌ Error: API credentials required!")
        print("\nProvide via:")
        print("  1. Command line: --api-key YOUR_KEY --api-token YOUR_TOKEN")
        print("  2. Environment: export TENSORDOCK_API_KEY=... TENSORDOCK_API_TOKEN=...")
        print("\nGet your API credentials at: https://console.tensordock.com/settings")
        sys.exit(1)

    # Create deployer instance
    deployer = TensorDockDeployer(args.api_key, args.api_token)

    # Execute requested action
    if args.check_availability:
        locations = deployer.get_available_locations()
        print(f"\n✅ Found {len(locations)} location(s) with RTX 4090:")
        for loc in locations:
            print(f"\n📍 {loc['location']}")
            print(f"   Hostnode: {loc['hostnode']}")
            print(f"   GPUs Available: {loc['gpu_count']}")

    elif args.delete:
        deployer.server_id = args.delete
        deployer.delete_server()

    elif args.deploy:
        # Deploy server
        deployer.deploy_server(
            vcpus=args.vcpus,
            ram=args.ram,
            storage=args.storage
        )

        # Wait for server to be ready
        if deployer.wait_for_server_ready():
            # Save connection info
            deployer.save_connection_info()

            # Set up and deploy ComfyUI
            deployer.setup_and_deploy_comfyui(docker_image=args.image)
        else:
            print("❌ Server deployment failed")
            sys.exit(1)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
