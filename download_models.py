#!/usr/bin/env python3
"""
ComfyUI Model Auto-Downloader for TensorDock - FIXED VERSION
Correct HuggingFace file paths
"""

import os
import sys
import requests
from pathlib import Path
from tqdm import tqdm
from huggingface_hub import hf_hub_download
import json

COMFYUI_BASE = os.environ.get('COMFYUI_PATH', '/workspace/ComfyUI')
MODELS_DIR = os.path.join(COMFYUI_BASE, 'models')
CIVITAI_API_KEY = os.environ.get('CIVITAI_API_KEY', '')

# CORRECTED HUGGINGFACE MODELS with actual file paths
HUGGINGFACE_MODELS = {
    # Wan2.2 I2V Models (fp8_scaled versions) - in I2V subdirectory!
    'diffusion_models': [
        {
            'repo': 'Kijai/WanVideo_comfy_fp8_scaled',
            'files': [
                'I2V/Wan2_2-I2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors',
                'I2V/Wan2_2-I2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors'
            ]
        }
    ],

    # Wan2.2 GGUF Models (quantized for low VRAM)
    'unet': [
        {
            'repo': 'QuantStack/Wan2.2-I2V-A14B-GGUF',
            'files': [
                'HighNoise/Wan2.2-I2V-A14B-HighNoise-Q6_K.gguf',
                'LowNoise/Wan2.2-I2V-A14B-LowNoise-Q6_K.gguf'
            ]
        }
    ],

    # Text Encoder (CLIP/T5)
    'text_encoders': [
        {
            'repo': 'Comfy-Org/Wan_2.1_ComfyUI_repackaged',
            'files': [
                'split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors'
            ]
        }
    ],

    # VAE
    'vae': [
        {
            'repo': 'Comfy-Org/Wan_2.1_ComfyUI_repackaged',
            'files': [
                'split_files/vae/wan_2.1_vae.safetensors'
            ]
        }
    ],

    # LightX2V LoRA (optional but good for faster inference)
    'loras': [
        {
            'repo': 'Kijai/WanVideo_comfy',
            'files': [
                'Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank128_bf16.safetensors'
            ]
        }
    ]
}

# CivitAI Models
CIVITAI_MODELS = {
    'checkpoints': [
        {
            'model_id': 97479,
            'version_id': 1308866,
            'filename': 'furrytoonmix_xlIllustriousV2.safetensors'
        }
    ],
    'loras': [
        {
            'model_id': 1307155,
            'version_id': 2073605,
            'filename': 'NSFW-22-H-e8.safetensors'
        },
        {
            'model_id': 1307155,
            'version_id': 2083303,
            'filename': 'NSFW-22-L-e8.safetensors'
        }
    ]
}

def download_file_with_progress(url, dest_path, headers=None):
    """Download file with progress bar"""
    if headers is None:
        headers = {}

    print(f"  Downloading to: {dest_path}")
    response = requests.get(url, stream=True, headers=headers, allow_redirects=True)
    response.raise_for_status()

    total_size = int(response.headers.get('content-length', 0))

    # Create parent directory if needed
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)

    with open(dest_path, 'wb') as f, tqdm(
        desc=os.path.basename(dest_path),
        total=total_size,
        unit='B',
        unit_scale=True,
        unit_divisor=1024,
    ) as pbar:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
                pbar.update(len(chunk))

def download_from_huggingface(category, repo_info):
    """Download models from HuggingFace"""
    target_dir = os.path.join(MODELS_DIR, category)
    os.makedirs(target_dir, exist_ok=True)

    repo_id = repo_info['repo']
    files = repo_info['files']

    print(f"\n📦 Downloading from {repo_id} to {category}/...")

    for filename in files:
        # The filename might have subdirectories (e.g., "I2V/model.safetensors")
        # We want to save it in the target_dir with just the basename
        basename = os.path.basename(filename)
        target_path = os.path.join(target_dir, basename)

        if os.path.exists(target_path):
            file_size = os.path.getsize(target_path)
            if file_size > 1024 * 1024:  # More than 1MB
                print(f"✓ {basename} already exists ({file_size / (1024**3):.2f} GB)")
                continue
            else:
                print(f"⚠ {basename} exists but is too small, re-downloading...")
                os.remove(target_path)

        try:
            print(f"⬇ Downloading {filename}...")
            downloaded_path = hf_hub_download(
                repo_id=repo_id,
                filename=filename,
                local_dir=target_dir,
                local_dir_use_symlinks=False,
                resume_download=True
            )

            # If the file was downloaded to a subdirectory, move it to the target directory
            if os.path.dirname(downloaded_path) != target_dir:
                final_path = os.path.join(target_dir, basename)
                if downloaded_path != final_path:
                    os.rename(downloaded_path, final_path)
                    print(f"✓ Moved to {final_path}")

            print(f"✓ Downloaded {basename}")
        except Exception as e:
            print(f"✗ Failed to download {filename}: {e}")
            print(f"   Repo: {repo_id}")
            print(f"   File: {filename}")

def download_from_civitai(category, model_info):
    """Download models from CivitAI"""
    target_dir = os.path.join(MODELS_DIR, category)
    os.makedirs(target_dir, exist_ok=True)

    model_id = model_info['model_id']
    version_id = model_info.get('version_id')
    filename = model_info['filename']

    target_path = os.path.join(target_dir, filename)

    if os.path.exists(target_path):
        file_size = os.path.getsize(target_path)
        if file_size > 1024 * 1024:
            print(f"✓ {filename} already exists ({file_size / (1024**3):.2f} GB)")
            return
        else:
            print(f"⚠ {filename} exists but is too small, re-downloading...")
            os.remove(target_path)

    # Build download URL
    if version_id:
        url = f"https://civitai.com/api/download/models/{version_id}"
    else:
        url = f"https://civitai.com/api/download/models/{model_id}"

    # Add API key if available
    headers = {}
    if CIVITAI_API_KEY:
        headers['Authorization'] = f'Bearer {CIVITAI_API_KEY}'

    try:
        print(f"\n📦 Downloading {filename} from CivitAI...")
        download_file_with_progress(url, target_path, headers)
        print(f"✓ Downloaded {filename}")
    except Exception as e:
        print(f"✗ Failed to download {filename}: {e}")
        if "NSFW" in filename or "nsfw" in filename.lower():
            print("⚠ This appears to be an NSFW model.")
            print("   Make sure CIVITAI_API_KEY is set: export CIVITAI_API_KEY='your_key'")
            print("   Get your API key at: https://civitai.com/user/account")

def main():
    """Main download orchestrator"""
    print("=" * 70)
    print("ComfyUI Model Auto-Downloader - FIXED VERSION")
    print("=" * 70)

    if not os.path.exists(COMFYUI_BASE):
        print(f"❌ ComfyUI directory not found at {COMFYUI_BASE}")
        print("   Set COMFYUI_PATH environment variable if needed")
        sys.exit(1)

    print(f"\n📁 ComfyUI: {COMFYUI_BASE}")
    print(f"📁 Models directory: {MODELS_DIR}")
    print(f"🔑 CivitAI API Key: {'Set ✓' if CIVITAI_API_KEY else 'Not set (limits NSFW downloads)'}")

    # Download HuggingFace models
    print("\n" + "=" * 70)
    print("DOWNLOADING FROM HUGGINGFACE")
    print("=" * 70)

    for category, repos in HUGGINGFACE_MODELS.items():
        for repo_info in repos:
            download_from_huggingface(category, repo_info)

    # Download CivitAI models
    if CIVITAI_MODELS:
        print("\n" + "=" * 70)
        print("DOWNLOADING FROM CIVITAI")
        print("=" * 70)

        for category, models in CIVITAI_MODELS.items():
            for model_info in models:
                download_from_civitai(category, model_info)

    print("\n" + "=" * 70)
    print("✨ Model download complete!")
    print("=" * 70)

    # Print storage summary
    print("\n📊 Storage usage by category:")
    for category in ['checkpoints', 'diffusion_models', 'unet', 'vae', 'text_encoders', 'loras']:
        cat_path = os.path.join(MODELS_DIR, category)
        if os.path.exists(cat_path):
            total_size = sum(
                os.path.getsize(os.path.join(dirpath, filename))
                for dirpath, _, filenames in os.walk(cat_path)
                for filename in filenames
            )
            if total_size > 0:
                print(f"   {category}: {total_size / (1024**3):.2f} GB")

if __name__ == "__main__":
    main()
