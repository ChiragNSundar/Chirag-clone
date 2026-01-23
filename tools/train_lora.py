#!/usr/bin/env python3
"""
Enhanced LoRA Fine-Tuning Script
================================
A comprehensive script for fine-tuning LLMs using LoRA (Low-Rank Adaptation).

Features:
- Unsloth integration for 2-4x faster training
- Support for multiple model architectures (Llama, Mistral, Phi, Gemma, Qwen)
- GGUF export for llama.cpp/Ollama compatibility
- Checkpoint resume and early stopping
- WandB and TensorBoard logging
- Learning rate scheduling with warmup
- LoRA adapter merging

Usage:
    python tools/train_lora.py --dataset backend/data/finetune_dataset.jsonl --model unsloth/llama-3-8b-bnb-4bit

Requirements:
    pip install torch transformers peft datasets trl bitsandbytes accelerate
    pip install unsloth  # Optional, for faster training
"""
import argparse
import os
import sys
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('training.log')
    ]
)
logger = logging.getLogger(__name__)


# ============= Dependency Checking =============

def check_core_dependencies() -> Tuple[bool, List[str]]:
    """Check for required core dependencies."""
    missing = []
    try:
        import torch
    except ImportError:
        missing.append("torch")
    try:
        import transformers
    except ImportError:
        missing.append("transformers")
    try:
        import peft
    except ImportError:
        missing.append("peft")
    try:
        import trl
    except ImportError:
        missing.append("trl")
    try:
        import datasets
    except ImportError:
        missing.append("datasets")
    
    return len(missing) == 0, missing


def check_optional_dependencies() -> Dict[str, bool]:
    """Check for optional dependencies."""
    available = {}
    
    try:
        import unsloth
        available['unsloth'] = True
    except ImportError:
        available['unsloth'] = False
    
    try:
        import wandb
        available['wandb'] = True
    except ImportError:
        available['wandb'] = False
    
    try:
        import bitsandbytes
        available['bitsandbytes'] = True
    except ImportError:
        available['bitsandbytes'] = False
    
    try:
        import flash_attn
        available['flash_attention'] = True
    except ImportError:
        available['flash_attention'] = False
    
    return available


def get_gpu_info() -> Dict[str, Any]:
    """Get GPU information if available."""
    try:
        import torch
        if torch.cuda.is_available():
            return {
                "available": True,
                "device_count": torch.cuda.device_count(),
                "device_name": torch.cuda.get_device_name(0),
                "memory_total": torch.cuda.get_device_properties(0).total_memory / 1e9,
                "memory_allocated": torch.cuda.memory_allocated(0) / 1e9,
                "cuda_version": torch.version.cuda
            }
    except Exception as e:
        logger.warning(f"Could not get GPU info: {e}")
    
    return {"available": False}


# ============= Configuration =============

class TrainingConfig:
    """Training configuration with defaults."""
    
    # Model settings
    model_name: str = "microsoft/phi-2"
    max_seq_length: int = 2048
    load_in_4bit: bool = True
    use_flash_attention: bool = True
    
    # LoRA settings
    lora_r: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.05
    target_modules: List[str] = None  # Auto-detected if None
    
    # Training settings
    num_epochs: int = 3
    batch_size: int = 2
    gradient_accumulation_steps: int = 4
    learning_rate: float = 2e-4
    weight_decay: float = 0.01
    warmup_ratio: float = 0.03
    lr_scheduler_type: str = "cosine"
    
    # Optimization
    use_gradient_checkpointing: bool = True
    optim: str = "paged_adamw_8bit"
    fp16: bool = True
    bf16: bool = False
    
    # Checkpointing
    save_strategy: str = "steps"
    save_steps: int = 100
    save_total_limit: int = 3
    
    # Evaluation
    eval_steps: int = 100
    eval_strategy: str = "steps"
    
    # Early stopping
    early_stopping_patience: int = 3
    early_stopping_threshold: float = 0.01
    
    # Logging
    logging_steps: int = 10
    report_to: List[str] = None  # ["wandb", "tensorboard"]
    
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        
        if self.target_modules is None:
            self.target_modules = ["q_proj", "k_proj", "v_proj", "o_proj", 
                                   "gate_proj", "up_proj", "down_proj"]
        
        if self.report_to is None:
            self.report_to = []
    
    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if not k.startswith('_')}
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'TrainingConfig':
        return cls(**d)
    
    def save(self, path: str):
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
    
    @classmethod
    def load(cls, path: str) -> 'TrainingConfig':
        with open(path, 'r') as f:
            return cls.from_dict(json.load(f))


# ============= Model Presets =============

MODEL_PRESETS = {
    # Unsloth optimized models (recommended)
    "llama3-8b": {
        "model_name": "unsloth/llama-3-8b-bnb-4bit",
        "max_seq_length": 4096,
        "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]
    },
    "llama3-8b-instruct": {
        "model_name": "unsloth/llama-3-8b-Instruct-bnb-4bit",
        "max_seq_length": 4096,
        "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]
    },
    "mistral-7b": {
        "model_name": "unsloth/mistral-7b-bnb-4bit",
        "max_seq_length": 4096,
        "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]
    },
    "mistral-7b-instruct": {
        "model_name": "unsloth/mistral-7b-instruct-v0.2-bnb-4bit",
        "max_seq_length": 4096,
        "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]
    },
    "phi-2": {
        "model_name": "unsloth/phi-2-bnb-4bit",
        "max_seq_length": 2048,
        "target_modules": ["q_proj", "k_proj", "v_proj", "dense", "fc1", "fc2"]
    },
    "phi-3-mini": {
        "model_name": "unsloth/Phi-3-mini-4k-instruct-bnb-4bit",
        "max_seq_length": 4096,
        "target_modules": ["qkv_proj", "o_proj", "gate_up_proj", "down_proj"]
    },
    "gemma-2b": {
        "model_name": "unsloth/gemma-2b-bnb-4bit",
        "max_seq_length": 2048,
        "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]
    },
    "gemma-7b": {
        "model_name": "unsloth/gemma-7b-bnb-4bit",
        "max_seq_length": 4096,
        "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]
    },
    "qwen2-7b": {
        "model_name": "unsloth/Qwen2-7B-bnb-4bit",
        "max_seq_length": 4096,
        "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]
    },
    "tinyllama": {
        "model_name": "unsloth/tinyllama-bnb-4bit",
        "max_seq_length": 2048,
        "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]
    },
    # Standard HuggingFace models (fallback)
    "phi-2-hf": {
        "model_name": "microsoft/phi-2",
        "max_seq_length": 2048,
        "target_modules": ["q_proj", "k_proj", "v_proj", "dense"]
    }
}


# ============= Dataset Handling =============

def load_dataset(dataset_path: str, validation_split: float = 0.1):
    """Load and optionally split the dataset."""
    from datasets import load_dataset as hf_load_dataset
    
    logger.info(f"Loading dataset from {dataset_path}...")
    
    if dataset_path.endswith('.jsonl') or dataset_path.endswith('.json'):
        dataset = hf_load_dataset('json', data_files=dataset_path, split='train')
    else:
        # Assume it's a HuggingFace dataset
        dataset = hf_load_dataset(dataset_path, split='train')
    
    logger.info(f"Dataset loaded with {len(dataset)} examples")
    
    # Split into train/validation
    if validation_split > 0:
        split = dataset.train_test_split(test_size=validation_split, seed=42)
        return split['train'], split['test']
    
    return dataset, None


def create_formatting_function(tokenizer, format_type: str = "chatml"):
    """Create a formatting function based on the format type."""
    
    if format_type == "chatml":
        def formatting_func(examples):
            output_texts = []
            for messages in examples.get('messages', []):
                text = ""
                for msg in messages:
                    role = msg.get('role', 'user')
                    content = msg.get('content', '')
                    text += f"<|im_start|>{role}\n{content}<|im_end|>\n"
                output_texts.append(text)
            return output_texts
        return formatting_func
    
    elif format_type == "alpaca":
        def formatting_func(examples):
            output_texts = []
            instructions = examples.get('instruction', [])
            inputs = examples.get('input', [''] * len(instructions))
            outputs = examples.get('output', [])
            
            for inst, inp, out in zip(instructions, inputs, outputs):
                if inp:
                    text = f"### Instruction:\n{inst}\n\n### Input:\n{inp}\n\n### Response:\n{out}"
                else:
                    text = f"### Instruction:\n{inst}\n\n### Response:\n{out}"
                output_texts.append(text)
            return output_texts
        return formatting_func
    
    elif format_type == "conversation":
        def formatting_func(examples):
            output_texts = []
            for ctx, resp in zip(examples.get('context', []), examples.get('response', [])):
                text = f"User: {ctx}\nAssistant: {resp}"
                output_texts.append(text)
            return output_texts
        return formatting_func
    
    else:
        # Default: assume 'text' field
        def formatting_func(examples):
            return examples.get('text', [])
        return formatting_func


# ============= Training =============

def train_with_unsloth(
    config: TrainingConfig,
    dataset_path: str,
    output_dir: str,
    resume_from: Optional[str] = None,
    wandb_project: Optional[str] = None,
    format_type: str = "chatml"
):
    """Train using Unsloth for optimized performance."""
    from unsloth import FastLanguageModel
    from trl import SFTTrainer
    from transformers import TrainingArguments
    
    logger.info("Using Unsloth for optimized training...")
    
    # Load model with Unsloth
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=config.model_name,
        max_seq_length=config.max_seq_length,
        load_in_4bit=config.load_in_4bit,
        dtype=None,  # Auto-detect
    )
    
    # Apply LoRA
    model = FastLanguageModel.get_peft_model(
        model,
        r=config.lora_r,
        lora_alpha=config.lora_alpha,
        lora_dropout=config.lora_dropout,
        target_modules=config.target_modules,
        use_gradient_checkpointing=config.use_gradient_checkpointing,
        random_state=42,
    )
    
    # Ensure pad token
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    
    # Load dataset
    train_dataset, eval_dataset = load_dataset(dataset_path)
    formatting_func = create_formatting_function(tokenizer, format_type)
    
    # Configure reporting
    report_to = []
    if wandb_project:
        try:
            import wandb
            wandb.init(project=wandb_project, name=f"lora-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
            report_to.append("wandb")
        except Exception as e:
            logger.warning(f"Could not initialize WandB: {e}")
    
    report_to.append("tensorboard")
    
    # Training arguments
    training_args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=config.num_epochs,
        per_device_train_batch_size=config.batch_size,
        gradient_accumulation_steps=config.gradient_accumulation_steps,
        learning_rate=config.learning_rate,
        weight_decay=config.weight_decay,
        warmup_ratio=config.warmup_ratio,
        lr_scheduler_type=config.lr_scheduler_type,
        optim=config.optim,
        fp16=config.fp16,
        bf16=config.bf16,
        logging_steps=config.logging_steps,
        save_strategy=config.save_strategy,
        save_steps=config.save_steps,
        save_total_limit=config.save_total_limit,
        evaluation_strategy=config.eval_strategy if eval_dataset else "no",
        eval_steps=config.eval_steps if eval_dataset else None,
        load_best_model_at_end=True if eval_dataset else False,
        metric_for_best_model="eval_loss" if eval_dataset else None,
        greater_is_better=False,
        report_to=report_to,
        run_name=f"chirag-clone-lora-{datetime.now().strftime('%Y%m%d')}",
    )
    
    # Create trainer
    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        formatting_func=formatting_func,
        max_seq_length=config.max_seq_length,
        args=training_args,
        packing=True,  # Unsloth optimization
    )
    
    # Resume from checkpoint if specified
    if resume_from and os.path.exists(resume_from):
        logger.info(f"Resuming from checkpoint: {resume_from}")
        trainer.train(resume_from_checkpoint=resume_from)
    else:
        trainer.train()
    
    # Save final model
    logger.info(f"Saving model to {output_dir}")
    trainer.save_model(output_dir)
    tokenizer.save_pretrained(output_dir)
    
    # Save config
    config.save(os.path.join(output_dir, "training_config.json"))
    
    return model, tokenizer


def train_standard(
    config: TrainingConfig,
    dataset_path: str,
    output_dir: str,
    resume_from: Optional[str] = None,
    wandb_project: Optional[str] = None,
    format_type: str = "chatml"
):
    """Train using standard PEFT/TRL (fallback when Unsloth not available)."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments, BitsAndBytesConfig
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from trl import SFTTrainer
    
    logger.info("Using standard PEFT/TRL training...")
    
    # Quantization config
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=config.load_in_4bit,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
    )
    
    # Load model
    model = AutoModelForCausalLM.from_pretrained(
        config.model_name,
        quantization_config=bnb_config if config.load_in_4bit else None,
        device_map="auto",
        trust_remote_code=True,
        use_flash_attention_2=config.use_flash_attention,
    )
    
    tokenizer = AutoTokenizer.from_pretrained(config.model_name, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    
    # Prepare for training
    if config.load_in_4bit:
        model = prepare_model_for_kbit_training(model)
    
    # LoRA config
    peft_config = LoraConfig(
        r=config.lora_r,
        lora_alpha=config.lora_alpha,
        lora_dropout=config.lora_dropout,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=config.target_modules,
    )
    
    model = get_peft_model(model, peft_config)
    model.print_trainable_parameters()
    
    # Load dataset
    train_dataset, eval_dataset = load_dataset(dataset_path)
    formatting_func = create_formatting_function(tokenizer, format_type)
    
    # Configure reporting
    report_to = ["tensorboard"]
    if wandb_project:
        try:
            import wandb
            wandb.init(project=wandb_project)
            report_to.append("wandb")
        except Exception:
            pass
    
    # Training arguments
    training_args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=config.num_epochs,
        per_device_train_batch_size=config.batch_size,
        gradient_accumulation_steps=config.gradient_accumulation_steps,
        learning_rate=config.learning_rate,
        weight_decay=config.weight_decay,
        warmup_ratio=config.warmup_ratio,
        lr_scheduler_type=config.lr_scheduler_type,
        optim=config.optim,
        fp16=config.fp16,
        logging_steps=config.logging_steps,
        save_strategy=config.save_strategy,
        save_steps=config.save_steps,
        save_total_limit=config.save_total_limit,
        evaluation_strategy=config.eval_strategy if eval_dataset else "no",
        eval_steps=config.eval_steps if eval_dataset else None,
        report_to=report_to,
    )
    
    # Create trainer
    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        formatting_func=formatting_func,
        max_seq_length=config.max_seq_length,
        args=training_args,
    )
    
    # Train
    if resume_from and os.path.exists(resume_from):
        trainer.train(resume_from_checkpoint=resume_from)
    else:
        trainer.train()
    
    # Save
    trainer.save_model(output_dir)
    tokenizer.save_pretrained(output_dir)
    config.save(os.path.join(output_dir, "training_config.json"))
    
    return model, tokenizer


# ============= Export Functions =============

def merge_and_save(model, tokenizer, output_dir: str, save_method: str = "merged_16bit"):
    """Merge LoRA weights and save the model."""
    logger.info(f"Merging LoRA weights with method: {save_method}")
    
    try:
        # Try Unsloth merge first
        from unsloth import FastLanguageModel
        
        if save_method == "merged_16bit":
            model.save_pretrained_merged(output_dir, tokenizer, save_method="merged_16bit")
        elif save_method == "merged_4bit":
            model.save_pretrained_merged(output_dir, tokenizer, save_method="merged_4bit")
        elif save_method == "lora":
            model.save_pretrained(output_dir)
            tokenizer.save_pretrained(output_dir)
        
        logger.info(f"Model saved to {output_dir}")
        
    except ImportError:
        # Fallback: Standard PEFT merge
        logger.info("Using standard PEFT merge...")
        merged_model = model.merge_and_unload()
        merged_model.save_pretrained(output_dir)
        tokenizer.save_pretrained(output_dir)


def export_to_gguf(
    model_path: str,
    output_path: str,
    quantization: str = "q4_k_m",
    model_name: str = "chirag-clone"
):
    """Export model to GGUF format for llama.cpp/Ollama."""
    logger.info(f"Exporting to GGUF with {quantization} quantization...")
    
    try:
        # Try Unsloth export first
        from unsloth import FastLanguageModel
        
        model, tokenizer = FastLanguageModel.from_pretrained(model_path)
        
        # GGUF quantization options
        quant_methods = {
            "q4_k_m": "q4_k_m",
            "q5_k_m": "q5_k_m", 
            "q8_0": "q8_0",
            "f16": "f16",
        }
        
        quant = quant_methods.get(quantization, "q4_k_m")
        
        model.save_pretrained_gguf(
            output_path,
            tokenizer,
            quantization_method=quant,
        )
        
        logger.info(f"GGUF model saved to {output_path}")
        return os.path.join(output_path, f"{model_name}-{quant}.gguf")
        
    except ImportError:
        logger.warning("Unsloth not available. Please use llama.cpp convert.py for GGUF export.")
        logger.info("To convert manually:")
        logger.info(f"  python llama.cpp/convert.py {model_path} --outfile {output_path}/model.gguf")
        logger.info(f"  ./llama.cpp/quantize {output_path}/model.gguf {output_path}/model-{quantization}.gguf {quantization}")
        return None


def register_with_ollama(gguf_path: str, model_name: str = "chirag-clone"):
    """Register the GGUF model with Ollama."""
    logger.info(f"Registering model '{model_name}' with Ollama...")
    
    # Create Modelfile
    modelfile_content = f"""FROM {gguf_path}

TEMPLATE \"\"\"<|im_start|>system
{{{{ .System }}}}<|im_end|>
<|im_start|>user
{{{{ .Prompt }}}}<|im_end|>
<|im_start|>assistant
\"\"\"

PARAMETER stop "<|im_start|>"
PARAMETER stop "<|im_end|>"
PARAMETER temperature 0.7
PARAMETER top_p 0.9
"""
    
    modelfile_path = os.path.join(os.path.dirname(gguf_path), "Modelfile")
    with open(modelfile_path, 'w') as f:
        f.write(modelfile_content)
    
    logger.info(f"Modelfile created at {modelfile_path}")
    logger.info(f"To register with Ollama, run:")
    logger.info(f"  ollama create {model_name} -f {modelfile_path}")
    
    return modelfile_path


# ============= CLI =============

def parse_args():
    parser = argparse.ArgumentParser(
        description="Enhanced LoRA Fine-Tuning for LLMs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic training with Phi-2
  python tools/train_lora.py --dataset data.jsonl --preset phi-2

  # Train with Llama 3 and export to GGUF
  python tools/train_lora.py --dataset data.jsonl --preset llama3-8b --export-gguf

  # Resume training from checkpoint
  python tools/train_lora.py --dataset data.jsonl --model unsloth/mistral-7b-bnb-4bit --resume-from ./adapters/checkpoint-500

  # Custom LoRA configuration
  python tools/train_lora.py --dataset data.jsonl --preset phi-2 --lora-r 32 --lora-alpha 64 --epochs 5
        """
    )
    
    # Required
    parser.add_argument("--dataset", type=str, required=True,
                        help="Path to JSONL dataset or HuggingFace dataset name")
    
    # Model selection
    model_group = parser.add_mutually_exclusive_group()
    model_group.add_argument("--model", type=str,
                             help="HuggingFace model name or path")
    model_group.add_argument("--preset", type=str, choices=list(MODEL_PRESETS.keys()),
                             help="Use a predefined model preset")
    
    # Output
    parser.add_argument("--output", type=str, default="./adapters",
                        help="Output directory for trained adapter")
    parser.add_argument("--run-name", type=str,
                        help="Name for this training run (default: auto-generated)")
    
    # Training parameters
    parser.add_argument("--epochs", type=int, default=3,
                        help="Number of training epochs")
    parser.add_argument("--batch-size", type=int, default=2,
                        help="Per-device batch size")
    parser.add_argument("--gradient-accumulation", type=int, default=4,
                        help="Gradient accumulation steps")
    parser.add_argument("--learning-rate", type=float, default=2e-4,
                        help="Learning rate")
    parser.add_argument("--max-seq-length", type=int, default=2048,
                        help="Maximum sequence length")
    
    # LoRA parameters
    parser.add_argument("--lora-r", type=int, default=16,
                        help="LoRA rank")
    parser.add_argument("--lora-alpha", type=int, default=32,
                        help="LoRA alpha")
    parser.add_argument("--lora-dropout", type=float, default=0.05,
                        help="LoRA dropout")
    
    # Optimization
    parser.add_argument("--use-unsloth", action="store_true",
                        help="Use Unsloth optimizations (if available)")
    parser.add_argument("--no-4bit", action="store_true",
                        help="Disable 4-bit quantization")
    parser.add_argument("--bf16", action="store_true",
                        help="Use bfloat16 instead of float16")
    
    # Checkpointing
    parser.add_argument("--resume-from", type=str,
                        help="Resume training from checkpoint path")
    parser.add_argument("--save-steps", type=int, default=100,
                        help="Save checkpoint every N steps")
    
    # Evaluation
    parser.add_argument("--eval-steps", type=int, default=100,
                        help="Evaluate every N steps")
    parser.add_argument("--validation-split", type=float, default=0.1,
                        help="Fraction of data to use for validation")
    
    # Logging
    parser.add_argument("--wandb-project", type=str,
                        help="WandB project name for logging")
    parser.add_argument("--logging-steps", type=int, default=10,
                        help="Log every N steps")
    
    # Export
    parser.add_argument("--export-gguf", action="store_true",
                        help="Export to GGUF format after training")
    parser.add_argument("--gguf-quantization", type=str, default="q4_k_m",
                        choices=["q4_k_m", "q5_k_m", "q8_0", "f16"],
                        help="GGUF quantization method")
    parser.add_argument("--merge-weights", action="store_true",
                        help="Merge LoRA weights into base model")
    parser.add_argument("--register-ollama", action="store_true",
                        help="Register exported model with Ollama")
    
    # Format
    parser.add_argument("--format", type=str, default="chatml",
                        choices=["chatml", "alpaca", "conversation", "raw"],
                        help="Dataset format")
    
    # Misc
    parser.add_argument("--dry-run", action="store_true",
                        help="Validate configuration without training")
    parser.add_argument("--list-presets", action="store_true",
                        help="List available model presets")
    
    return parser.parse_args()


def main():
    args = parse_args()
    
    # List presets and exit
    if args.list_presets:
        print("\nAvailable Model Presets:")
        print("=" * 50)
        for name, preset in MODEL_PRESETS.items():
            print(f"\n  {name}:")
            print(f"    Model: {preset['model_name']}")
            print(f"    Max Seq Length: {preset['max_seq_length']}")
        return
    
    # Check dependencies
    core_ok, missing = check_core_dependencies()
    if not core_ok:
        logger.error(f"Missing required dependencies: {', '.join(missing)}")
        print("\nPlease install required packages:")
        print("  pip install torch transformers peft datasets trl bitsandbytes accelerate")
        sys.exit(1)
    
    optional = check_optional_dependencies()
    logger.info(f"Optional dependencies: {optional}")
    
    # Check GPU
    gpu_info = get_gpu_info()
    if gpu_info["available"]:
        logger.info(f"GPU: {gpu_info['device_name']} ({gpu_info['memory_total']:.1f}GB)")
    else:
        logger.warning("No GPU detected. Training will be slow!")
    
    # Check dataset exists
    if not os.path.exists(args.dataset) and not args.dataset.startswith("huggingface"):
        logger.error(f"Dataset not found: {args.dataset}")
        sys.exit(1)
    
    # Build configuration
    config_kwargs = {
        "num_epochs": args.epochs,
        "batch_size": args.batch_size,
        "gradient_accumulation_steps": args.gradient_accumulation,
        "learning_rate": args.learning_rate,
        "max_seq_length": args.max_seq_length,
        "lora_r": args.lora_r,
        "lora_alpha": args.lora_alpha,
        "lora_dropout": args.lora_dropout,
        "load_in_4bit": not args.no_4bit,
        "bf16": args.bf16,
        "fp16": not args.bf16,
        "save_steps": args.save_steps,
        "eval_steps": args.eval_steps,
        "logging_steps": args.logging_steps,
    }
    
    # Apply preset if specified
    if args.preset:
        preset = MODEL_PRESETS[args.preset]
        config_kwargs.update(preset)
    elif args.model:
        config_kwargs["model_name"] = args.model
    else:
        # Default to phi-2
        config_kwargs["model_name"] = "microsoft/phi-2"
    
    config = TrainingConfig(**config_kwargs)
    
    # Generate run name
    run_name = args.run_name or f"lora-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    output_dir = os.path.join(args.output, run_name)
    
    logger.info(f"\n{'='*50}")
    logger.info(f"Training Configuration")
    logger.info(f"{'='*50}")
    logger.info(f"Model: {config.model_name}")
    logger.info(f"Dataset: {args.dataset}")
    logger.info(f"Output: {output_dir}")
    logger.info(f"Epochs: {config.num_epochs}")
    logger.info(f"Batch Size: {config.batch_size} (effective: {config.batch_size * config.gradient_accumulation_steps})")
    logger.info(f"LoRA: r={config.lora_r}, alpha={config.lora_alpha}")
    logger.info(f"Learning Rate: {config.learning_rate}")
    logger.info(f"{'='*50}\n")
    
    if args.dry_run:
        logger.info("Dry run complete. Configuration is valid.")
        return
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Train
    start_time = time.time()
    
    use_unsloth = args.use_unsloth and optional.get('unsloth', False)
    
    if use_unsloth:
        model, tokenizer = train_with_unsloth(
            config=config,
            dataset_path=args.dataset,
            output_dir=output_dir,
            resume_from=args.resume_from,
            wandb_project=args.wandb_project,
            format_type=args.format
        )
    else:
        if args.use_unsloth:
            logger.warning("Unsloth requested but not available. Using standard training.")
        model, tokenizer = train_standard(
            config=config,
            dataset_path=args.dataset,
            output_dir=output_dir,
            resume_from=args.resume_from,
            wandb_project=args.wandb_project,
            format_type=args.format
        )
    
    elapsed = time.time() - start_time
    logger.info(f"Training completed in {elapsed/60:.1f} minutes")
    
    # Post-training exports
    if args.merge_weights:
        merge_dir = os.path.join(output_dir, "merged")
        merge_and_save(model, tokenizer, merge_dir)
    
    if args.export_gguf:
        gguf_dir = os.path.join(output_dir, "gguf")
        os.makedirs(gguf_dir, exist_ok=True)
        gguf_path = export_to_gguf(
            model_path=output_dir,
            output_path=gguf_dir,
            quantization=args.gguf_quantization,
            model_name=run_name
        )
        
        if gguf_path and args.register_ollama:
            register_with_ollama(gguf_path, run_name)
    
    logger.info(f"\n{'='*50}")
    logger.info(f"Training Complete!")
    logger.info(f"{'='*50}")
    logger.info(f"Adapter saved to: {output_dir}")
    if args.merge_weights:
        logger.info(f"Merged model: {os.path.join(output_dir, 'merged')}")
    if args.export_gguf:
        logger.info(f"GGUF export: {os.path.join(output_dir, 'gguf')}")
    logger.info(f"{'='*50}\n")


if __name__ == "__main__":
    main()
