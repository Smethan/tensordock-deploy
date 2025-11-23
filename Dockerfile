FROM nextdiffusionai/comfyui-sageattention:cuda12.8

# Set working directory
WORKDIR /workspace

# Install additional dependencies
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Ensure ComfyUI exists and set it as the working directory
# ENV COMFYUI_PATH=/workspace/ComfyUI
# RUN if [ ! -d "$COMFYUI_PATH" ]; then \
#     git clone https://github.com/comfyanonymous/ComfyUI.git $COMFYUI_PATH; \
#     fi

WORKDIR $COMFYUI_PATH

# Install additional Python packages for model downloading
RUN pip install --no-cache-dir \
    requests \
    tqdm \
    huggingface-hub

# Copy the model downloader script
COPY download_models.py /workspace/download_models.py
RUN chmod +x /workspace/download_models.py

# Install custom nodes
# RUN mkdir -p custom_nodes && \
#     cd custom_nodes && \
#     # ComfyUI Manager
#     if [ ! -d "ComfyUI-Manager" ]; then \
#     git clone https://github.com/ltdrdata/ComfyUI-Manager.git; \
#     fi && \
#     # WanVideo Wrapper
#     if [ ! -d "ComfyUI-WanVideoWrapper" ]; then \
#     git clone https://github.com/kijai/ComfyUI-WanVideoWrapper.git; \
#     fi && \
#     # VideoHelper Suite
#     if [ ! -d "ComfyUI-VideoHelperSuite" ]; then \
#     git clone https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git; \
#     fi && \
#     # GGUF support
#     if [ ! -d "ComfyUI-GGUF" ]; then \
#     git clone https://github.com/city96/ComfyUI-GGUF.git; \
#     fi && \
#     cd ..

# # Create directories for models and outputs
# RUN mkdir -p models/checkpoints models/diffusion_models models/unet \
#     models/vae models/text_encoders models/loras output

# Copy entrypoint script
COPY entrypoint.sh /workspace/entrypoint.sh
RUN chmod +x /workspace/entrypoint.sh

# Setup venv for ComfyUI
# RUN pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
# RUN pip install -r requirements.txt

# Expose ComfyUI port
EXPOSE 8188

# Set entrypoint
ENTRYPOINT ["/workspace/entrypoint.sh"]
