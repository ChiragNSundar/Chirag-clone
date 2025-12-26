"""
Backup Service - Handle data backup and export/import.
"""
import os
import json
import shutil
from datetime import datetime
from typing import Dict, Optional
from config import Config


class BackupService:
    """Service for backing up and restoring clone data."""
    
    def __init__(self):
        self.backup_dir = os.path.join(Config.DATA_DIR, 'backups')
        os.makedirs(self.backup_dir, exist_ok=True)
    
    def create_backup(self, name: Optional[str] = None) -> Dict:
        """
        Create a backup of all clone data.
        
        Returns:
            Dict with backup info
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = name or f'backup_{timestamp}'
        backup_path = os.path.join(self.backup_dir, backup_name)
        
        try:
            os.makedirs(backup_path, exist_ok=True)
            
            files_backed_up = []
            
            # Backup personality profile
            personality_file = os.path.join(Config.DATA_DIR, 'personality_profile.json')
            if os.path.exists(personality_file):
                shutil.copy(personality_file, os.path.join(backup_path, 'personality_profile.json'))
                files_backed_up.append('personality_profile.json')
            
            # Backup analytics
            analytics_file = os.path.join(Config.DATA_DIR, 'analytics.json')
            if os.path.exists(analytics_file):
                shutil.copy(analytics_file, os.path.join(backup_path, 'analytics.json'))
                files_backed_up.append('analytics.json')
            
            # Backup ChromaDB (copy entire directory)
            chroma_dir = Config.CHROMA_DB_PATH
            if os.path.exists(chroma_dir):
                backup_chroma = os.path.join(backup_path, 'chroma_db')
                shutil.copytree(chroma_dir, backup_chroma)
                files_backed_up.append('chroma_db/')
            
            # Create metadata file
            metadata = {
                'created_at': datetime.now().isoformat(),
                'name': backup_name,
                'files': files_backed_up
            }
            with open(os.path.join(backup_path, 'metadata.json'), 'w') as f:
                json.dump(metadata, f, indent=2)
            
            return {
                'success': True,
                'backup_name': backup_name,
                'files_backed_up': files_backed_up,
                'path': backup_path
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def list_backups(self) -> list:
        """List all available backups."""
        backups = []
        
        if not os.path.exists(self.backup_dir):
            return backups
        
        for name in os.listdir(self.backup_dir):
            backup_path = os.path.join(self.backup_dir, name)
            if os.path.isdir(backup_path):
                metadata_file = os.path.join(backup_path, 'metadata.json')
                if os.path.exists(metadata_file):
                    with open(metadata_file, 'r') as f:
                        metadata = json.load(f)
                    backups.append({
                        'name': name,
                        'created_at': metadata.get('created_at'),
                        'files': metadata.get('files', [])
                    })
        
        # Sort by date descending
        backups.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        return backups
    
    def restore_backup(self, backup_name: str) -> Dict:
        """
        Restore from a backup.
        
        Args:
            backup_name: Name of the backup to restore
            
        Returns:
            Dict with restore result
        """
        backup_path = os.path.join(self.backup_dir, backup_name)
        
        if not os.path.exists(backup_path):
            return {'success': False, 'error': 'Backup not found'}
        
        try:
            files_restored = []
            
            # Restore personality profile
            personality_backup = os.path.join(backup_path, 'personality_profile.json')
            if os.path.exists(personality_backup):
                shutil.copy(personality_backup, os.path.join(Config.DATA_DIR, 'personality_profile.json'))
                files_restored.append('personality_profile.json')
            
            # Restore analytics
            analytics_backup = os.path.join(backup_path, 'analytics.json')
            if os.path.exists(analytics_backup):
                shutil.copy(analytics_backup, os.path.join(Config.DATA_DIR, 'analytics.json'))
                files_restored.append('analytics.json')
            
            # Restore ChromaDB
            chroma_backup = os.path.join(backup_path, 'chroma_db')
            if os.path.exists(chroma_backup):
                if os.path.exists(Config.CHROMA_DB_PATH):
                    shutil.rmtree(Config.CHROMA_DB_PATH)
                shutil.copytree(chroma_backup, Config.CHROMA_DB_PATH)
                files_restored.append('chroma_db/')
            
            return {
                'success': True,
                'files_restored': files_restored,
                'message': 'Backup restored. Please restart the server.'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def export_personality(self) -> Dict:
        """Export personality to a shareable JSON file."""
        from services.personality_service import get_personality_service
        from services.memory_service import get_memory_service
        
        personality = get_personality_service()
        memory = get_memory_service()
        
        profile = personality.get_profile()
        stats = memory.get_training_stats()
        
        export_data = {
            'exported_at': datetime.now().isoformat(),
            'personality': {
                'name': profile.name,
                'tone_markers': profile.tone_markers,
                'typing_quirks': profile.typing_quirks,
                'emoji_patterns': profile.emoji_patterns,
                'facts': profile.facts,
                'avg_message_length': profile.avg_message_length,
                'vocabulary_sample': dict(list(profile.vocabulary.items())[:100])
            },
            'training_stats': stats,
            'sample_responses': profile.response_examples[:20]
        }
        
        export_file = os.path.join(Config.DATA_DIR, 'personality_export.json')
        with open(export_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        return {
            'success': True,
            'file': export_file,
            'data': export_data
        }
    
    def delete_backup(self, backup_name: str) -> Dict:
        """Delete a backup."""
        backup_path = os.path.join(self.backup_dir, backup_name)
        
        if not os.path.exists(backup_path):
            return {'success': False, 'error': 'Backup not found'}
        
        try:
            shutil.rmtree(backup_path)
            return {'success': True, 'message': f'Backup {backup_name} deleted'}
        except Exception as e:
            return {'success': False, 'error': str(e)}


# Singleton
_backup_service = None

def get_backup_service() -> BackupService:
    """Get the singleton backup service."""
    global _backup_service
    if _backup_service is None:
        _backup_service = BackupService()
    return _backup_service
