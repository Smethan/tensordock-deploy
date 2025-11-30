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
import requests

# Load env file if present
from pathlib import Path

def load_env_file(env_path=".env"):
    """Load environment variables from a .env file if it exists."""
    env_file = Path(env_path)
    if env_file.is_file():
        with env_file.open("r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                os.environ.setdefault(key, value)



# Now TENSORDOCK_API_KEY, TENSORDOCK_API_TOKEN, CIVITAI_API_KEY can be in os.environ, from .env or user's environment


class ComfyUIDeployer:
    """Automated ComfyUI deployment on TensorDock."""

    def __init__(self, api_token: str, civitai_key: str = ""):
        """Initialize deployer with API credentials."""
        self.api_token = api_token
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

# Clone the repository
echo "📥 Cloning ComfyUI deployment repository..."
cd /home/user
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
bash deploy.sh -y

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
echo "   cd /home/user/tensordock-deploy && docker compose ps"
echo ""
echo "📝 View logs:"
echo "   cd /home/user/tensordock-deploy && docker compose logs -f"
echo ""
echo "🌐 Access ComfyUI at: http://$(hostname -I | awk '{{print $1}}'):8188"
echo ""
"""
        return script

    # def list_available_gpus(self):
    #     """List available GPU models and locations."""
    #     print("🔍 Fetching available GPUs...")

    #     try:
    #         # The SDK doesn't expose this directly, so we'd need to use requests
    #         # For now, we'll deploy to any available RTX 4090
    #         print("   Looking for RTX 4090...")
    #         return True
    #     except Exception as e:
    #         print(f"❌ Error fetching GPU info: {e}")
    #         return False

    # def deploy_server(self,
    #                  gpu_model: str = "rtx4090-pcie-24gb",
    #                  gpu_count: int = 1,
    #                  vcpus: int = 8,
    #                  ram: int = 32,
    #                  storage: int = 200,
    #                  os: str = "Ubuntu 22.04 LTS") -> Optional[dict]:
    #     """Deploy a new ComfyUI server."""

    #     print(f"\n🚀 Deploying ComfyUI server:")
    #     print(f"   GPU: {gpu_count}x {gpu_model}")
    #     print(f"   vCPUs: {vcpus}")
    #     print(f"   RAM: {ram} GB")
    #     print(f"   Storage: {storage} GB")
    #     print(f"   OS: {os}")
    #     print()

    #     # Generate cloud-init script
    #     print("📝 Generating cloud-init setup script...")
    #     cloudinit_script = self.generate_cloudinit_script()

    #     # Save cloud-init script to temp file for debugging
    #     with open("/tmp/tensordock_cloudinit.sh", "w") as f:
    #         f.write(cloudinit_script)
    #     print(f"   💾 Cloud-init script saved to: /tmp/tensordock_cloudinit.sh")

    #     try:
    #         print("\n⏳ Creating server instance...")

    #         # Deploy VM with cloud-init
    #         # Note: The SDK might not support cloudinit_file parameter directly
    #         # We may need to use raw API calls
    #         result = self.api.virtual_machines.deploy_vm(
    #             name=f"ComfyUI-{int(time.time())}",
    #             gpu_count=gpu_count,
    #             gpu_model=gpu_model,
    #             vcpus=vcpus,
    #             ram=ram,
    #             storage=storage,
    #             operating_system=os,
    #             # The SDK may not support this parameter - need to check
    #             # cloudinit_file=cloudinit_script
    #         )

    #         print("✅ Server deployment initiated!")
    #         print(f"\n📄 Response: {json.dumps(result, indent=2)}")

    #         self.server_info = result
    #         return result

    #     except Exception as e:
    #         print(f"❌ Deployment failed: {e}")
    #         return None

    def deploy_with_raw_api(self,
                           gpu_model: str = "rtx4090-pcie-24gb",
                           gpu_count: int = 1,
                           vcpus: int = 8,
                           ram: int = 32,
                           storage: int = 200,
                           operating_system: str = "ubuntu2404_ml_everything"):
        """Deploy using v2 API."""

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
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        response = requests.get(locations_url, headers=headers)

        if response.status_code != 200:
            print(f"❌ Failed to get locations: {response.text}")
            return None

        locations_data = response.json().get("data", {})
        locations = locations_data.get("locations", [])

        # Find a location with available RTX 4090
        selected_location_id = None
        selected_location_name = None
        selected_gpu_model = None
        location_list = []

        for location in locations:
            location_id = location.get("id")
            city = location.get("city", "Unknown")
            country = location.get("country", "Unknown")
            location_name = f"{city}, {country}"

            # Check GPUs available in this location
            gpus = location.get("gpus", [])
            for gpu in gpus:
                gpu_name = gpu.get("v0Name", "")
                max_count = gpu.get("max_count", 0)
                port_forwarding_available = gpu.get("network_features", {}).get("port_forwarding_available", False)

                if max_count > 0 and ("4090" in gpu_name.lower() or "rtx4090" in gpu_name.lower()) and port_forwarding_available:
                    location_list.append({
                        "id": location_id,
                        "name": location_name,
                        "gpu_model": gpu_name,
                        "max_count": max_count,
                        "price_per_hr": gpu.get('price_per_hr', 'N/A')
                    })
                    print(f"✅ Found RTX 4090 at: {location_name}")
                    

            if len(location_list) > 0 and selected_location_id is None:
                print(f"Found {len(location_list)} locations with RTX 4090:")
                for idx, location in enumerate(location_list, 1):
                    print(f"[{idx}]   {location['name']}: {location['gpu_model']} ({location['max_count']} max) - ${location['price_per_hr']}/hr")
                print(f"Enter the number of the location you want to deploy to (or 'q' to quit):")
                user_input = input("> ").strip()
                if user_input.lower() == 'q':
                    print("Cancelled")
                    return None
                else:
                    selected_location_index = int(user_input) - 1
                    print(f"Selected location: {location_list[selected_location_index]['name']}")
                    print("Are you sure you want to deploy here? (y/n)")
                    user_input = input("> ").strip()
                    if user_input.lower() == 'y':
                        print("Deploying to selected location...")
                        selected_location_id = location_list[selected_location_index]['id']
                        selected_location_name = location_list[selected_location_index]['name']
                        selected_gpu_model = location_list[selected_location_index]['gpu_model']
                        break
                    else:
                        print("Cancelled")
                        continue

        if not selected_location_id:
            print("❌ No RTX 4090 available!")
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
                    "image": operating_system,
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
                    "port_forwards": [
                        {
                            "internal_port": 22,
                            "external_port": 0
                        },
                        {
                            "internal_port": 8080,
                            "external_port": 0
                        },
                        {
                            "internal_port": 8188,
                            "external_port": 0
                        }
                    ],
                    "location_id": selected_location_id,
                    "useDedicatedIp": False,  # Use port forwarding instead
                    "ssh_key": os.environ["SSH_PUB_KEY"]
                    # No cloud-init - will SSH in manually to run setup
                }
            }
        }

        # Save the cloud-init script for manual execution
        with open("/tmp/tensordock_setup.sh", "w") as f:
            f.write(cloudinit_script)
        print(f"   💾 Setup script saved to: /tmp/tensordock_setup.sh")

        response = requests.post(deploy_url, headers=headers, json=payload)

        if response.json().get("data").get("error") is not None or response.json().get("error") is not None or response.status_code >= 400: 
            print(f"❌ Deployment failed: {response.json().get('data').get('status')}")
            print(f"   Response: {response.json()}")
            return None

        result = response.json()
        print("✅ Server created!")
        print(f"\n📄 Server Info:")
        print(json.dumps(result, indent=2))

        self.server_info = result

        # Extract instance data from v2 API response
        instance_data = result.get("data", {})
        instance_id = instance_data.get("id")
        instance_name = instance_data.get("name")
        instance_status = instance_data.get("status")

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
        print(f"   SSH: ssh -p {ssh_port} user@{ssh_host}")

        print("Would you like to run the deployment script now? (y/n)")
        user_input = input("> ").strip()
        if user_input.lower() == 'y':
            print(f"\n🚀 Running deployment script over SSH...")
            self.run_remote_deployment(ssh_host, ssh_port)
        else:
            print("\nDeployment script not run")
            print("You can run the deployment script manually by SSHing into the instance and running the script:")
            print(f"   ssh -p {ssh_port} user@{ssh_host}")
            print(f"   cd /home/user/tensordock-deploy && bash deploy.sh")

        return result

    def _wait_for_ssh_available(self, host: str, port: int, timeout: int = 300) -> bool:
        """Actively poll SSH availability by attempting connections.
        
        Args:
            host: SSH host address
            port: SSH port number
            timeout: Maximum time to wait in seconds
            
        Returns:
            True if SSH becomes available, False if timeout reached
        """
        import subprocess
        import time
        
        start_time = time.time()
        attempt = 0
        
        print(f"   Polling SSH availability at {host}:{port}...")
        
        while time.time() - start_time < timeout:
            attempt += 1
            
            # Attempt SSH connection with a quick timeout
            ssh_test_cmd = [
                "ssh",
                "-p", str(port),
                "-o", "StrictHostKeyChecking=no",
                "-o", "UserKnownHostsFile=/dev/null",
                "-o", "ConnectTimeout=5",
                "-o", "BatchMode=yes",
                "-i", f"{os.path.expanduser('~')}/.ssh/tensordock_key",
                f"user@{host}",
                "echo 'SSH_READY'"
            ]
            
            try:
                result = subprocess.run(
                    ssh_test_cmd,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0 and "SSH_READY" in result.stdout:
                    print(f"\n   ✅ SSH is available after {int(time.time() - start_time)}s (attempt {attempt})")
                    return True
                    
            except (subprocess.TimeoutExpired, Exception) as e:
                # Connection failed, continue polling
                pass
            
            # Exponential backoff: 5s, 10s, 15s, 20s, then 20s intervals
            wait_time = min(5 * (attempt if attempt <= 4 else 4), 20)
            print(f"   SSH not ready yet (attempt {attempt}, waited {int(time.time() - start_time)}s)...", end="\r")
            time.sleep(wait_time)
        
        print(f"\n   ❌ SSH did not become available within {timeout}s")
        return False

    def wait_for_instance(self, instance_id: str, headers: dict, max_wait: int = 300) -> tuple:
        """Wait for instance to be running and return SSH details."""
        import requests
        import time

        instance_url = f"https://dashboard.tensordock.com/api/v2/instances/{instance_id}"
        start_time = time.time()
# EXAMPLE RESPONSE:
#         {
#   "type": "instance",
#   "id": "string",
#   "name": "string",
#   "status": "string",
#   "ipAddress": "string",
#   "portForwards": [
#     {
#       "internal_port": "number",
#       "external_port": "number"
#     }
#   ],
#   "resources": {
#     "vcpu_count": "number",
#     "ram_gb": "number",
#     "storage_gb": "number",
#     "gpus": {
#       "gpu-model-name": {
#         "count": "number",
#         "v0Name": "string"
#       }
#     }
#   },
#   "rateHourly": "number"
# }

        while time.time() - start_time < max_wait:
            response = requests.get(instance_url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                status = data.get("status")

                print(f"   Status: {status}...", end="\r")

                if status == "running":
                    # Get connection details
                    ssh_host = data.get("ipAddress")
                    for port_forward in data.get("portForwards"):
                        if port_forward.get("internal_port") == 22:
                            ssh_port = port_forward.get("external_port")
                            break
                    else:
                        ssh_port = None

                    if ssh_host:
                        print(f"\n   Instance running at {ssh_host}:{ssh_port}")
                        # Actively poll for SSH availability instead of passive wait
                        if self._wait_for_ssh_available(ssh_host, ssh_port, timeout=120):
                            return ssh_host, ssh_port
                        else:
                            print("   ⚠️ Instance running but SSH not available")
                            return None, None

            time.sleep(10)

        return None, None

    def run_remote_deployment(self, host: str, port: int, max_retries: int = 1):
        """SSH into the instance and run the deployment script with reboot handling.
        
        Args:
            host: SSH host address
            port: SSH port number
            max_retries: Maximum number of times to retry after reboot (default: 1)
        """
        import subprocess
        import time

        script_path = "/tmp/tensordock_setup.sh"

        print(f"   Uploading setup script...")

        # Upload the script
        scp_cmd = [
            "scp",
            "-P", str(port),
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-i", f"{os.path.expanduser('~')}/.ssh/tensordock_key",
            script_path,
            f"user@{host}:/home/user/setup.sh"
        ]

        result = subprocess.run(scp_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"   ❌ Failed to upload script: {result.stderr}")
            return

        print(f"   ✅ Script uploaded")
        
        # Deployment loop with reboot handling
        for attempt in range(max_retries + 1):
            if attempt > 0:
                print(f"\n   � Deployment attempt {attempt + 1} (post-reboot continuation)...")
            else:
                print(f"\n   �🚀 Executing deployment (this may take ~10-15 minutes)...")
                print(f"   Follow along with the output:\n")

            # Run the script over SSH with sudo to ensure all commands have root privileges
            ssh_cmd = [
                "ssh",
                "-p", str(port),
                "-o", "StrictHostKeyChecking=no",
                "-o", "UserKnownHostsFile=/dev/null",
                "-o", "ServerAliveInterval=5",
                "-o", "ServerAliveCountMax=3",
                "-i", f"{os.path.expanduser('~')}/.ssh/tensordock_key",
                f"user@{host}",
                "sudo bash /home/user/setup.sh"
            ]

            # Stream output in real-time
            process = subprocess.Popen(ssh_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            
            last_output_time = time.time()
            reboot_detected = False
            
            try:
                for line in process.stdout:
                    print(f"   {line}", end="")
                    last_output_time = time.time()
                    
                    # Check for reboot indicators in output
                    if "rebooting" in line.lower() or "system is going down" in line.lower():
                        print(f"\n   🔄 Reboot detected in script output...")
                        reboot_detected = True
                
                process.wait(timeout=30)  # Wait for process to complete with timeout
                
            except subprocess.TimeoutExpired:
                # Process didn't complete within timeout after last output
                # This might indicate a reboot
                print(f"\n   ⚠️ SSH connection may have been interrupted...")
                reboot_detected = True
            
            # Check exit code
            exit_code = process.returncode if process.returncode is not None else -1
            
            # Handle different exit scenarios
            if exit_code == 0:
                # Clean exit - deployment completed successfully
                print(f"\n\n🎉 Deployment completed successfully!")
                print(f"   ComfyUI should be running at: http://{host}:8188")
                return
                
            elif exit_code == 255 or reboot_detected:
                # SSH disconnect (likely reboot) - exit code 255 is SSH disconnect
                if attempt < max_retries:
                    print(f"\n   🔄 SSH disconnected (likely server reboot)")
                    print(f"   ⏳ Waiting for server to come back online...")
                    
                    # Wait a bit for reboot to initiate
                    time.sleep(10)
                    
                    # Poll for SSH availability with longer timeout for reboot
                    if self._wait_for_ssh_available(host, port, timeout=300):
                        print(f"   ✅ Server is back online, continuing deployment...")
                        # Continue to next iteration to re-execute deployment script
                        continue
                    else:
                        print(f"\n   ❌ Server did not come back online within timeout")
                        print(f"   Manual intervention may be required")
                        return
                else:
                    print(f"\n   ❌ Maximum retry attempts ({max_retries}) reached")
                    print(f"   Deployment may be incomplete")
                    return
            else:
                # Other error
                print(f"\n\n⚠️  Deployment script exited with code {exit_code}")
                print(f"   Check logs: ssh -p {port} -i ~/.ssh/tensordock_key user@{host} 'tail -f /var/log/comfyui-setup.log'")
                return
        
        print(f"\n   ⚠️ Deployment loop completed without success")

    def run_ssh_setup_on_selected_instance(self):
        """List instances and run SSH setup on the selected one."""
        import requests

        print("🔍 Fetching all instances...")

        # v2 API uses Bearer token authentication
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        instances_url = "https://dashboard.tensordock.com/api/v2/instances"
        response = requests.get(instances_url, headers=headers)

        if response.status_code != 200:
            print(f"❌ Failed to fetch instances: {response.text}")
            return

        response_data = response.json()
        instances = response_data.get("data", [])

        if not instances:
            print("📭 No instances found")
            return

        print(f"\n📋 Found {len(instances)} instance(s):\n")

        # Display instances
        instance_details = []
        for idx, instance in enumerate(instances, 1):
            instance_id = instance.get("id")
            response_data = requests.get(f"{instances_url}/{instance_id}", headers=headers)
            instance_data = response_data.json()
            name = instance_data.get("name", "N/A")
            status = instance_data.get("status", "N/A")
            ip_address = instance_data.get("ipAddress", "N/A")
            
            # Find SSH port
            ssh_port = None
            port_forwards = instance_data.get("portForwards", [])
            for port_forward in port_forwards:
                if port_forward.get("internal_port") == 22:
                    ssh_port = port_forward.get("external_port", "N/A")
                    break
            
            gpu_info = ", ".join([f"{count}x {name}" for name, info in instance_data.get("resources", {}).get("gpus", {}).items() for count in [info.get("count", 0)] if count > 0])

            print(f"[{idx}] {name}")
            print(f"    ID: {instance_id}")
            print(f"    Status: {status}")
            print(f"    IP: {ip_address}:{ssh_port}")
            print(f"    GPUs: {gpu_info or 'None'}")
            print()

            instance_details.append({
                "id": instance_id,
                "name": name,
                "ip": ip_address,
                "ssh_port": ssh_port,
                "status": status
            })

        # Ask user to select instance
        print("Enter instance number to run SSH setup on (or 'q' to quit):")
        user_input = input("> ").strip()

        if user_input.lower() == 'q':
            print("Cancelled")
            return

        # Parse selection
        try:
            selection = int(user_input)
            if not (1 <= selection <= len(instance_details)):
                print("❌ Invalid instance number")
                return
        except ValueError:
            print("❌ Invalid input")
            return

        # Get selected instance details
        selected_instance = instance_details[selection - 1]
        
        if selected_instance["status"] != "running":
            print(f"⚠️  Warning: Instance is in '{selected_instance['status']}' state, not 'running'")
            print("Continue anyway? (y/n)")
            confirm = input("> ").strip().lower()
            if confirm != 'y':
                print("Cancelled")
                return

        print(f"\n✅ Selected: {selected_instance['name']}")
        print(f"   IP: {selected_instance['ip']}:{selected_instance['ssh_port']}")
        
        # Confirm
        print("\nThis will run the deployment setup script on this instance. Continue? (y/n)")
        confirm = input("> ").strip().lower()
        if confirm != 'y':
            print("Cancelled")
            return

        # Generate and save the setup script
        print("\n📝 Generating setup script...")
        cloudinit_script = self.generate_cloudinit_script()
        
        with open("/tmp/tensordock_setup.sh", "w") as f:
            f.write(cloudinit_script)
        print(f"   💾 Setup script saved to: /tmp/tensordock_setup.sh")

        # Run the deployment
        print(f"\n🚀 Running SSH deployment on {selected_instance['name']}...")
        self.run_remote_deployment(selected_instance['ip'], selected_instance['ssh_port'])

    def list_and_manage_instances(self):
        """List all instances and allow termination."""
        import requests

        print("🔍 Fetching all instances...")

        # v2 API uses Bearer token authentication
        headers = {
            "Authorization": f"Bearer {self.api_token}",
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
        instances = response_data.get("data", [])
        
       

        if not instances:
            print("📭 No instances found")
            return

        print(f"\n📋 Found {len(instances)} instance(s):\n")

        
        # Display instances
        for idx, instance in enumerate(instances, 1):
            instance_id = instance.get("id")
            response_data = requests.get(f"{instances_url}/{instance_id}", headers=headers)
            instance_data = response_data.json()
            name = instance_data.get("name", "N/A")
            status = instance_data.get("status", "N/A")
            hourly_rate = instance_data.get("rateHourly", "N/A")
            ip_address = instance_data.get("ipAddress", "N/A")
            ssh_port = instance_data.get("portForwards")[0].get("external_port", "N/A")
            gpu_info = ", ".join([f"{count}x {name}" for name, info in instance_data.get("resources", {}).get("gpus", {}).items() for count in [info.get("count", 0)] if count > 0])

            print(f"[{idx}] {name}")
            print(f"    ID: {instance_id}")
            print(f"    Status: {status}")
            print(f"    IP: {ip_address}:{ssh_port}")
            print(f"    GPUs: {gpu_info or 'None'}")
            print(f"    Hourly Rate: {hourly_rate}")
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
        for idx, instance in enumerate(instances_to_delete, 1):
            print(f"   - {instance.get('name')} ({instance.get('id')})")

        confirm = input("\nType 'yes' to confirm: ").strip().lower()
        if confirm != 'yes':
            print("Cancelled")
            return

        # Terminate instances
        print()
        for idx, instance in enumerate(instances_to_delete, 1):
            instance_id = instance.get("id")
            instance_name = instance.get("name")

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
            print(f"   Username: user")
            print(f"   Password: {server.get('password', 'N/A')}")
            print(f"\n🌐 ComfyUI will be available at:")
            print(f"   http://{server.get('ip', 'N/A')}:8188")
            print(f"\n⏱️  Cloud-init setup takes ~10-15 minutes")
            print(f"   Monitor: ssh -p {server.get('port', '22')} user@{server.get('ip', 'N/A')}")
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
    parser.add_argument("--ssh-setup", action="store_true",
                       help="Run SSH setup on an existing instance")

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

    # Call early in script -- before argument parsing or key usage
    load_env_file()

    # Create deployer with credentials from env file
    deployer = ComfyUIDeployer(os.environ["TENSORDOCK_API_TOKEN"], os.environ["CIVITAI_API_KEY"])

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
    elif args.ssh_setup:
        # Run SSH setup on selected instance
        deployer.run_ssh_setup_on_selected_instance()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
