
"""
Standalone LoRA Fine-Tuning Script
----------------------------------
This script allows you to fine-tune a model (like Phi-2, TinyLlama, or Mistral) 
on your exported dataset using LoRA (Low-Rank Adaptation).

Usage:
    python tools/train_lora.py --dataset backend/data/finetune_dataset.jsonl --model unsloth/phi-2-bnb-4bit

Requirements:
    pip install torch transformers peft datasets trl bitsandbytes unsloth
"""
import argparse
import os
import sys
import logging
import json

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_dependencies():
    try:
        import torch
        import transformers
        import peft
        import trl
    except ImportError as e:
        logger.error(f"Missing dependency: {e}")
        print("\nPlease install required packages:")
        print("pip install torch transformers peft datasets trl bitsandbytes accelerat")
        sys.exit(1)

def train(dataset_path, model_name, output_dir, epochs=3):
    check_dependencies()
    
    from datasets import load_dataset
    from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments, BitsAndBytesConfig
    from peft import LoraConfig, get_peft_model
    from trl import SFTTrainer
    
    logger.info(f"Loading dataset from {dataset_path}...")
    dataset = load_dataset('json', data_files=dataset_path, split='train')
    
    logger.info(f"Loading model {model_name}...")
    
    # Quantization config for 4-bit loading (efficiency)
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
    )
    
    try:
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            quantization_config=bnb_config,
            device_map="auto",
            trust_remote_code=True
        )
        tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
        tokenizer.pad_token = tokenizer.eos_token
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        return

    # LoRA Configuration
    peft_config = LoraConfig(
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"] # Common for Llama/Mistral/Phi
    )
    
    training_args = TrainingArguments(
        output_dir=output_dir,
        per_device_train_batch_size=2,
        gradient_accumulation_steps=4,
        learning_rate=2e-4,
        logging_steps=10,
        num_train_epochs=epochs,
        save_strategy="epoch",
        fp16=True,
        optim="paged_adamw_8bit"
    )
    
    def formatting_prompts_func(example):
        output_texts = []
        for messages in example['messages']:
            # Convert ChatML format to text
            text = ""
            for msg in messages:
                role = msg['role']
                content = msg['content']
                text += f"<|im_start|>{role}\n{content}<|im_end|>\n"
            text += "<|im_start|>assistant\n"
            output_texts.append(text)
        return output_texts

    logger.info("Starting training...")
    trainer = SFTTrainer(
        model=model,
        train_dataset=dataset,
        peft_config=peft_config,
        dataset_text_field="text", # Ignored by formatting_func but required arg
        max_seq_length=512,
        tokenizer=tokenizer,
        args=training_args,
        formatting_func=formatting_prompts_func,
    )
    
    trainer.train()
    
    logger.info(f"Training complete! Saving to {output_dir}")
    trainer.save_model(output_dir)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Local LoRA Fine-Tuning")
    parser.add_argument("--dataset", type=str, required=True, help="Path to JSONL dataset")
    parser.add_argument("--model", type=str, default="microsoft/phi-2", help="Base model Name (HF)")
    parser.add_argument("--output", type=str, default="./adapters", help="Output directory")
    parser.add_argument("--epochs", type=int, default=3, help="Number of epochs")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.dataset):
        logger.error(f"Dataset not found at {args.dataset}")
        sys.exit(1)
        
    train(args.dataset, args.model, args.output, args.epochs)
