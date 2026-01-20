
"""
Fine-Tuning Service - Prepares datasets and manages fine-tuning jobs.
Exports conversations to JSONL format compatible with OpenAI/Llama training.
"""
import json
import os
import logging
from typing import List, Dict, Any, Optional
from config import Config
from .memory_service import get_memory_service
from .personality_service import get_personality_service

logger = logging.getLogger(__name__)

class FineTuneService:
    """
    Manages dataset preparation and fine-tuning operations.
    """
    
    def __init__(self):
        self.memory = get_memory_service()
        self.personality = get_personality_service()
        self.dataset_path = os.path.join(Config.DATA_DIR, "finetune_dataset.jsonl")
    
    def export_dataset(self, format: str = "chatml") -> str:
        """
        Export training data to a JSONL file.
        
        Args:
            format: 'chatml' (OpenAI/ShareGPT) or 'alpaca'
            
        Returns:
            Path to the exported file
        """
        logger.info(f"Exporting dataset in {format} format...")
        
        # 1. Get Personality System Prompt
        system_prompt = self.personality.get_system_prompt()
        
        # 2. Get All Conversations (from Memory)
        # We need a method in MemoryService to get ALL conversations, not just recent.
        # For now, we'll try to get training examples which are curated.
        training_examples = self.memory.get_all_examples_with_metadata()
        
        data_rows = []
        
        # Add curated training examples
        for ex in training_examples:
            row = {
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": ex['context']},
                    {"role": "assistant", "content": ex['response']}
                ]
            }
            data_rows.append(row)
            
        # Add personality examples (few-shot)
        profile = self.personality.get_profile()
        for ex in profile.response_examples:
            row = {
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": ex.context},
                    {"role": "assistant", "content": ex.response}
                ]
            }
            data_rows.append(row)
            
        # Save to JSONL
        os.makedirs(os.path.dirname(self.dataset_path), exist_ok=True)
        with open(self.dataset_path, 'w', encoding='utf-8') as f:
            for row in data_rows:
                f.write(json.dumps(row, ensure_ascii=False) + '\n')
                
        logger.info(f"Exported {len(data_rows)} rows to {self.dataset_path}")
        return self.dataset_path
    
    def get_dataset_stats(self) -> Dict:
        """Get stats about the current potential dataset."""
        training_count = len(self.memory.get_all_examples_with_metadata())
        personality_count = len(self.personality.get_profile().response_examples)
        
        return {
            "training_examples": training_count,
            "personality_examples": personality_count,
            "total_rows": training_count + personality_count,
            "recommended_epochs": 3 if (training_count + personality_count) > 100 else 5
        }

# Singleton
_finetune_service = None

def get_finetune_service() -> FineTuneService:
    global _finetune_service
    if _finetune_service is None:
        _finetune_service = FineTuneService()
    return _finetune_service
