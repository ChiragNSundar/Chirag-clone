"""
Enhanced Fine-Tuning Service - Prepares datasets and manages fine-tuning jobs.

Features:
- Export conversations to JSONL format (ChatML, Alpaca, ShareGPT)
- Data quality filtering
- Deduplication
- Dataset statistics and analysis
- Train/validation splitting
"""
import json
import os
import re
import logging
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from collections import Counter
from dataclasses import dataclass
from config import Config
from .memory_service import get_memory_service
from .personality_service import get_personality_service

logger = logging.getLogger(__name__)


@dataclass
class DatasetStats:
    """Statistics about the dataset."""
    total_examples: int
    training_examples: int
    personality_examples: int
    avg_input_length: float
    avg_output_length: float
    max_input_length: int
    max_output_length: int
    sources: Dict[str, int]
    token_estimate: int
    recommended_epochs: int
    quality_score: float


class FineTuneService:
    """
    Enhanced service for dataset preparation and fine-tuning operations.
    
    Provides:
    - Multi-format export (ChatML, Alpaca, ShareGPT, raw)
    - Quality filtering and deduplication
    - Dataset statistics and analysis
    - Train/validation splitting
    """
    
    # Minimum quality thresholds
    MIN_RESPONSE_LENGTH = 10
    MIN_CONTEXT_LENGTH = 5
    MAX_RESPONSE_LENGTH = 4000
    
    def __init__(self):
        self.memory = get_memory_service()
        self.personality = get_personality_service()
        self.dataset_path = os.path.join(Config.DATA_DIR, "finetune_dataset.jsonl")
        self.train_path = os.path.join(Config.DATA_DIR, "train_dataset.jsonl")
        self.val_path = os.path.join(Config.DATA_DIR, "val_dataset.jsonl")
    
    def export_dataset(
        self,
        format: str = "chatml",
        include_system: bool = True,
        deduplicate: bool = True,
        quality_filter: bool = True,
        validation_split: float = 0.1,
        shuffle: bool = True
    ) -> Dict[str, Any]:
        """
        Export training data to JSONL file(s).
        
        Args:
            format: 'chatml' (OpenAI/ShareGPT), 'alpaca', or 'raw'
            include_system: Include system prompt in each example
            deduplicate: Remove near-duplicate examples
            quality_filter: Filter out low-quality examples
            validation_split: Fraction for validation set (0 to disable)
            shuffle: Shuffle data before splitting
            
        Returns:
            Dict with paths and statistics
        """
        logger.info(f"Exporting dataset in {format} format...")
        
        # 1. Get system prompt
        system_prompt = self.personality.get_system_prompt() if include_system else ""
        
        # 2. Collect all examples
        all_examples = self._collect_all_examples()
        logger.info(f"Collected {len(all_examples)} raw examples")
        
        # 3. Quality filtering
        if quality_filter:
            all_examples = self._filter_quality(all_examples)
            logger.info(f"After quality filter: {len(all_examples)} examples")
        
        # 4. Deduplication
        if deduplicate:
            all_examples = self._deduplicate(all_examples)
            logger.info(f"After deduplication: {len(all_examples)} examples")
        
        # 5. Shuffle
        if shuffle:
            import random
            random.shuffle(all_examples)
        
        # 6. Format conversion
        formatted_data = []
        for ex in all_examples:
            formatted = self._format_example(ex, format, system_prompt)
            if formatted:
                formatted_data.append(formatted)
        
        # 7. Train/validation split
        if validation_split > 0 and len(formatted_data) > 10:
            split_idx = int(len(formatted_data) * (1 - validation_split))
            train_data = formatted_data[:split_idx]
            val_data = formatted_data[split_idx:]
            
            self._save_jsonl(train_data, self.train_path)
            self._save_jsonl(val_data, self.val_path)
            self._save_jsonl(formatted_data, self.dataset_path)
            
            logger.info(f"Saved {len(train_data)} train, {len(val_data)} val examples")
            
            return {
                "success": True,
                "format": format,
                "total_examples": len(formatted_data),
                "train_examples": len(train_data),
                "val_examples": len(val_data),
                "train_path": self.train_path,
                "val_path": self.val_path,
                "full_path": self.dataset_path
            }
        else:
            self._save_jsonl(formatted_data, self.dataset_path)
            logger.info(f"Saved {len(formatted_data)} examples to {self.dataset_path}")
            
            return {
                "success": True,
                "format": format,
                "total_examples": len(formatted_data),
                "path": self.dataset_path
            }
    
    def _collect_all_examples(self) -> List[Dict[str, Any]]:
        """Collect examples from all sources."""
        examples = []
        
        # From memory service (training examples)
        try:
            training_examples = self.memory.get_all_examples_with_metadata()
            for ex in training_examples:
                examples.append({
                    "context": ex.get('context', ''),
                    "response": ex.get('response', ''),
                    "source": ex.get('source', 'memory')
                })
        except Exception as e:
            logger.warning(f"Could not get training examples: {e}")
        
        # From personality service (response examples)
        try:
            profile = self.personality.get_profile()
            for ex in profile.response_examples:
                examples.append({
                    "context": ex.context,
                    "response": ex.response,
                    "source": "personality"
                })
        except Exception as e:
            logger.warning(f"Could not get personality examples: {e}")
        
        return examples
    
    def _filter_quality(self, examples: List[Dict]) -> List[Dict]:
        """Filter out low-quality examples."""
        filtered = []
        
        for ex in examples:
            context = ex.get('context', '').strip()
            response = ex.get('response', '').strip()
            
            # Skip empty or too short
            if len(context) < self.MIN_CONTEXT_LENGTH:
                continue
            if len(response) < self.MIN_RESPONSE_LENGTH:
                continue
            
            # Skip too long
            if len(response) > self.MAX_RESPONSE_LENGTH:
                continue
            
            # Skip obvious garbage (high non-ascii ratio)
            non_ascii_ratio = sum(1 for c in response if ord(c) > 127) / max(len(response), 1)
            if non_ascii_ratio > 0.5:
                continue
            
            # Skip if just repeated characters
            if len(set(response)) < 5:
                continue
            
            # Skip common bot refusals (optional - can be enabled for specific datasets)
            # refusal_patterns = ["I cannot", "I can't", "As an AI"]
            # if any(p.lower() in response.lower() for p in refusal_patterns):
            #     continue
            
            filtered.append(ex)
        
        return filtered
    
    def _deduplicate(self, examples: List[Dict], threshold: float = 0.9) -> List[Dict]:
        """Remove near-duplicate examples using content hashing."""
        seen_hashes = set()
        unique = []
        
        for ex in examples:
            # Create normalized hash
            content = f"{ex.get('context', '').lower().strip()}|{ex.get('response', '').lower().strip()}"
            content = re.sub(r'\s+', ' ', content)  # Normalize whitespace
            
            # Use first N characters for fuzzy matching
            content_key = content[:500]
            content_hash = hashlib.md5(content_key.encode()).hexdigest()
            
            if content_hash not in seen_hashes:
                seen_hashes.add(content_hash)
                unique.append(ex)
        
        return unique
    
    def _format_example(
        self,
        example: Dict,
        format: str,
        system_prompt: str
    ) -> Optional[Dict]:
        """Format a single example for the specified format."""
        context = example.get('context', '').strip()
        response = example.get('response', '').strip()
        
        if not context or not response:
            return None
        
        if format == "chatml":
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": context})
            messages.append({"role": "assistant", "content": response})
            return {"messages": messages}
        
        elif format == "alpaca":
            return {
                "instruction": context,
                "input": "",
                "output": response
            }
        
        elif format == "sharegpt":
            conversations = []
            if system_prompt:
                conversations.append({"from": "system", "value": system_prompt})
            conversations.append({"from": "human", "value": context})
            conversations.append({"from": "gpt", "value": response})
            return {"conversations": conversations}
        
        elif format == "raw":
            text = f"User: {context}\nAssistant: {response}"
            if system_prompt:
                text = f"System: {system_prompt}\n{text}"
            return {"text": text}
        
        else:
            # Default to ChatML
            return {
                "messages": [
                    {"role": "user", "content": context},
                    {"role": "assistant", "content": response}
                ]
            }
    
    def _save_jsonl(self, data: List[Dict], path: str):
        """Save data to JSONL file."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            for row in data:
                f.write(json.dumps(row, ensure_ascii=False) + '\n')
    
    def get_dataset_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics about the current dataset."""
        all_examples = self._collect_all_examples()
        
        if not all_examples:
            return {
                "training_examples": 0,
                "personality_examples": 0,
                "total_rows": 0,
                "recommended_epochs": 5,
                "message": "No training data available"
            }
        
        # Count by source
        sources = Counter(ex.get('source', 'unknown') for ex in all_examples)
        
        # Length statistics
        input_lengths = [len(ex.get('context', '')) for ex in all_examples]
        output_lengths = [len(ex.get('response', '')) for ex in all_examples]
        
        avg_input = sum(input_lengths) / len(input_lengths) if input_lengths else 0
        avg_output = sum(output_lengths) / len(output_lengths) if output_lengths else 0
        
        # Token estimate (rough: 4 chars per token)
        total_chars = sum(input_lengths) + sum(output_lengths)
        token_estimate = total_chars // 4
        
        # Quality score (0-1)
        quality_filtered = self._filter_quality(all_examples)
        quality_score = len(quality_filtered) / len(all_examples) if all_examples else 0
        
        # Recommended epochs based on dataset size
        if len(all_examples) < 50:
            recommended_epochs = 5
        elif len(all_examples) < 200:
            recommended_epochs = 3
        elif len(all_examples) < 1000:
            recommended_epochs = 2
        else:
            recommended_epochs = 1
        
        return {
            "total_examples": len(all_examples),
            "training_examples": sources.get('memory', 0) + sources.get('training', 0),
            "personality_examples": sources.get('personality', 0),
            "sources": dict(sources),
            "avg_input_length": round(avg_input, 1),
            "avg_output_length": round(avg_output, 1),
            "max_input_length": max(input_lengths) if input_lengths else 0,
            "max_output_length": max(output_lengths) if output_lengths else 0,
            "token_estimate": token_estimate,
            "quality_score": round(quality_score, 2),
            "recommended_epochs": recommended_epochs,
            "total_rows": len(all_examples)
        }
    
    def analyze_dataset(self) -> Dict[str, Any]:
        """Deep analysis of the dataset for insights."""
        all_examples = self._collect_all_examples()
        
        if not all_examples:
            return {"error": "No data to analyze"}
        
        # Response length distribution
        response_lengths = [len(ex.get('response', '')) for ex in all_examples]
        length_buckets = {
            "short (< 50 chars)": sum(1 for l in response_lengths if l < 50),
            "medium (50-200 chars)": sum(1 for l in response_lengths if 50 <= l < 200),
            "long (200-500 chars)": sum(1 for l in response_lengths if 200 <= l < 500),
            "very long (500+ chars)": sum(1 for l in response_lengths if l >= 500)
        }
        
        # Common words in responses (basic analysis)
        all_words = []
        for ex in all_examples:
            words = re.findall(r'\b\w+\b', ex.get('response', '').lower())
            all_words.extend(words)
        
        # Filter common stop words
        stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 
                      'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
                      'would', 'could', 'should', 'may', 'might', 'must', 'can',
                      'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from',
                      'or', 'and', 'but', 'if', 'then', 'so', 'than', 'that', 'this',
                      'it', 'its', 'i', 'you', 'we', 'they', 'me', 'my', 'your'}
        
        filtered_words = [w for w in all_words if w not in stop_words and len(w) > 2]
        word_freq = Counter(filtered_words).most_common(20)
        
        # Quality analysis
        quality_issues = {
            "too_short": sum(1 for ex in all_examples if len(ex.get('response', '')) < 10),
            "too_long": sum(1 for ex in all_examples if len(ex.get('response', '')) > 2000),
            "empty_context": sum(1 for ex in all_examples if len(ex.get('context', '').strip()) < 5),
            "duplicates": len(all_examples) - len(self._deduplicate(all_examples))
        }
        
        return {
            "total_examples": len(all_examples),
            "length_distribution": length_buckets,
            "top_words": word_freq,
            "quality_issues": quality_issues,
            "estimated_training_time_minutes": len(all_examples) * 0.1  # Rough estimate
        }
    
    def preview_export(self, format: str = "chatml", limit: int = 5) -> List[Dict]:
        """Preview what the exported data will look like."""
        system_prompt = self.personality.get_system_prompt()
        examples = self._collect_all_examples()[:limit]
        
        return [
            self._format_example(ex, format, system_prompt)
            for ex in examples
            if self._format_example(ex, format, system_prompt)
        ]


# Singleton
_finetune_service = None


def get_finetune_service() -> FineTuneService:
    global _finetune_service
    if _finetune_service is None:
        _finetune_service = FineTuneService()
    return _finetune_service
