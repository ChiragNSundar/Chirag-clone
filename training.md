# 🧠 Local Fine-Tuning Guide

This guide explains how to fine-tune a local Large Language Model (LLM) on your own data (conversations, facts, journals) to create a personalized "Digital Twin" model.

---

## 🏗️ Architecture

The training pipeline consists of two stages:

1. **Dataset Generation**: The backend exports your "Brain" (Core Memories + Personality) into a standard training format (`.jsonl`).
2. **LoRA Training**: A standalone script uses **Low-Rank Adaptation (LoRA)** to fine-tune a base model (like Llama 3 or Phi-3) efficiently.

```mermaid
graph LR
    Brain[Brain (Memory/Personality)] -->|Export| Dataset[dataset.jsonl]
    Dataset -->|Train| Script[train_lora.py]
    Base[Base Model (e.g. Llama-3)] --> Script
    Script -->|Save| Adapter[LoRA Adapters]
    Adapter -->|Merge/Convert| GGUF[Model.gguf]
    GGUF -->|Load| Ollama[Ollama Service]
```

---

## 📋 Prerequisites

### Hardware

* **NVIDIA GPU**: Required for optimized training (Unsloth).
  * **8GB VRAM**: Sufficient for Phi-3, Gemma-2b, or Llama-3-8b (4-bit).
  * **16GB+ VRAM**: Recommended for faster training and larger batch sizes.
* **System RAM**: 16GB minimum.

### Software

* **Python 3.10+** (Separate environment recommended).
* **Ollama**: For running the final model.

### Permissions
* **Admin Role**: You must be an Admin/Owner to export training data (v3.1+).

---

## 🚀 Step 1: Export Training Data

First, you need to extract the dataset from the running application.

### Via API

Run this command to trigger an export:

```bash
# Export to ChatML format (optimized for Llama 3 / Phi-3)
# NOTE: Requires Admin Authentication (Bearer Token)
curl -X POST "http://localhost:8000/api/finetune/export" \
     -H "Authorization: Bearer <ADMIN_JWT_TOKEN>" \
     -H "Content-Type: application/json" \
     -d '{"format": "chatml", "quality_filter": true, "deduplicate": true}'
```

The file will be saved to: `backend/data/finetune_dataset.jsonl`.

### Customizing the Export

You can adjust parameters in the JSON payload:

* `"include_system": true` -Bakes your personality system prompt into every example.
* `"validation_split": 0.1` - Reserves 10% of data for validation.

---

## 🏋️ Step 2: Run Training

We utilize **Unsloth**, which makes training 2-4x faster and uses nearly 70% less VRAM.

### 1. Setup Environment

Create a dedicated environment for training to avoid conflicts with the backend:

```bash
# Create venv
python -m venv venv-train
source venv-train/bin/activate  # or venv-train\Scripts\activate on Windows

# Install dependencies (Unsloth + PyTorch)
pip install "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git"
pip install --no-deps "xformers<0.0.26" "trl<0.9.0" peft accelerate bitsandbytes
```

*(Note: Windows users may need [specific installation steps for bitsandbytes](https://github.com/idank/bitsandbytes-windows))*

### 2. Execute Training Script

The script `tools/train_lora.py` handles everything.

#### Example: Train Llama 3 (8B)

```bash
python tools/train_lora.py \
    --dataset backend/data/finetune_dataset.jsonl \
    --preset llama3-8b \
    --epochs 3 \
    --batch-size 2 \
    --output adapters/chirag-v1
```

#### Example: Train Phi-3 (Fast & Lightweight)

```bash
python tools/train_lora.py \
    --dataset backend/data/finetune_dataset.jsonl \
    --preset phi-3-mini \
    --epochs 5 \
    --output adapters/chirag-mini-v1
```

### Key Arguments

* `--preset`: Selects base model and config (see script for list: `llama3-8b`, `mistral-7b`, `phi-3-mini`).
* `--lora-r`: Rank of LoRA adapters (default 16). Higher = 'smarter' but slower/larger.
* `--resume-from`: Path to a checkpoint directory to resume training.

---

## 📦 Step 3: Export & Integration

Once training is complete, you need to convert the model to GGUF format to run it with Ollama.

### 1. Convert to GGUF

The script can handle this automatically if you have `llama.cpp` tools installed, or use Unsloth's built-in export:

```bash
python tools/train_lora.py \
    --model adapters/chirag-v1 \
    --export-gguf \
    --gguf-quantization q4_k_m
```

This will produce a file like `adapters/chirag-v1/model-q4_k_m.gguf`.

### 2. Register with Ollama

Create a Modelfile for your new model:

```dockerfile
FROM ./adapters/chirag-v1/model-q4_k_m.gguf

TEMPLATE """<|im_start|>system
{{ .System }}<|im_end|>
<|im_start|>user
{{ .Prompt }}<|im_end|>
<|im_start|>assistant
"""

PARAMETER stop "<|im_start|>"
PARAMETER stop "<|im_end|>"
PARAMETER temperature 0.7
SYSTEM "You are Chirag, a helpful AI assistant."
```

Then create the model:

```bash
ollama create chirag-v1 -f Modelfile
```

### 3. Use in Chirag Clone

Update your `.env` file to point to your new local model:

```bash
# .env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=chirag-v1
```

Restart the backend, and you are now chatting with your fine-tuned digital twin!
