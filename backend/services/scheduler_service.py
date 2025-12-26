"""
Scheduler Service - Background job scheduling for proactive messages.
Uses APScheduler for timed message sending.
"""
import os
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from config import Config

# APScheduler import with fallback
try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.date import DateTrigger
    from apscheduler.triggers.interval import IntervalTrigger
    HAS_APSCHEDULER = True
except ImportError:
    HAS_APSCHEDULER = False
    print("APScheduler not installed. Proactive messaging disabled. Install with: pip install APScheduler")


class SchedulerService:
    """Service for managing proactive message schedules."""
    
    MESSAGE_TYPES = {
        'good_morning': {
            'name': 'Good Morning',
            'description': 'AI-generated morning greeting',
            'prompt': 'Generate a warm, personalized good morning message.'
        },
        'check_in': {
            'name': 'Check In',
            'description': 'Casual check-in message',
            'prompt': 'Generate a casual check-in message asking how someone is doing.'
        },
        'motivation': {
            'name': 'Motivation',
            'description': 'Motivational message',
            'prompt': 'Generate an encouraging, motivational message.'
        },
        'good_night': {
            'name': 'Good Night',
            'description': 'Evening/night message',
            'prompt': 'Generate a warm good night message.'
        },
        'random': {
            'name': 'Random',
            'description': 'Random conversation starter',
            'prompt': 'Generate a random, interesting conversation starter.'
        },
        'custom': {
            'name': 'Custom',
            'description': 'Custom message template',
            'prompt': None
        }
    }
    
    def __init__(self):
        self.scheduler = None
        self.schedules: Dict[str, Dict] = {}
        self.schedules_path = os.path.join(Config.DATA_DIR, "schedules.json")
        self._message_callback: Optional[Callable] = None
        self._initialized = False
        
        if HAS_APSCHEDULER:
            self._init_scheduler()
    
    def _init_scheduler(self):
        """Initialize the APScheduler."""
        try:
            self.scheduler = BackgroundScheduler(
                timezone='UTC',
                job_defaults={
                    'coalesce': True,
                    'max_instances': 1
                }
            )
            self._load_schedules()
            self.scheduler.start()
            self._initialized = True
            print("Scheduler service initialized")
        except Exception as e:
            print(f"Scheduler init error: {e}")
            self._initialized = False
    
    def _load_schedules(self):
        """Load schedules from JSON file."""
        if os.path.exists(self.schedules_path):
            try:
                with open(self.schedules_path, 'r', encoding='utf-8') as f:
                    self.schedules = json.load(f)
                
                # Re-register active schedules
                for schedule_id, schedule in self.schedules.items():
                    if schedule.get('active', True):
                        self._register_job(schedule_id, schedule)
                        
            except Exception as e:
                print(f"Error loading schedules: {e}")
                self.schedules = {}
    
    def _save_schedules(self):
        """Save schedules to JSON file."""
        os.makedirs(os.path.dirname(self.schedules_path), exist_ok=True)
        with open(self.schedules_path, 'w', encoding='utf-8') as f:
            json.dump(self.schedules, f, indent=2, ensure_ascii=False)
    
    def _register_job(self, schedule_id: str, schedule: Dict):
        """Register a job with APScheduler."""
        if not self.scheduler:
            return
        
        try:
            # Remove existing job if any
            try:
                self.scheduler.remove_job(schedule_id)
            except:
                pass
            
            trigger_type = schedule.get('trigger_type', 'cron')
            
            if trigger_type == 'cron':
                trigger = CronTrigger.from_crontab(schedule.get('cron_expression', '0 9 * * *'))
            elif trigger_type == 'interval':
                trigger = IntervalTrigger(
                    hours=schedule.get('interval_hours', 24)
                )
            elif trigger_type == 'once':
                run_time = datetime.fromisoformat(schedule.get('run_at'))
                trigger = DateTrigger(run_date=run_time)
            else:
                return
            
            self.scheduler.add_job(
                self._execute_schedule,
                trigger=trigger,
                id=schedule_id,
                args=[schedule_id],
                replace_existing=True
            )
            
        except Exception as e:
            print(f"Error registering job {schedule_id}: {e}")
    
    def _execute_schedule(self, schedule_id: str):
        """Execute a scheduled message."""
        schedule = self.schedules.get(schedule_id)
        if not schedule:
            return
        
        print(f"Executing schedule: {schedule_id}")
        
        # Update last run time
        schedule['last_run'] = datetime.now().isoformat()
        schedule['run_count'] = schedule.get('run_count', 0) + 1
        self._save_schedules()
        
        # Call the message callback if registered
        if self._message_callback:
            try:
                self._message_callback(schedule)
            except Exception as e:
                print(f"Schedule callback error: {e}")
    
    def set_message_callback(self, callback: Callable):
        """
        Set the callback function for sending messages.
        
        The callback should accept a schedule dict with:
        - platform: 'discord' or 'telegram'
        - target_id: User/channel ID
        - message_type: Type of message to generate
        - custom_message: Optional custom message template
        """
        self._message_callback = callback
    
    def create_schedule(
        self,
        platform: str,
        target_id: str,
        target_name: str,
        message_type: str,
        trigger_type: str = 'cron',
        cron_expression: str = '0 9 * * *',
        interval_hours: int = 24,
        run_at: Optional[str] = None,
        custom_message: Optional[str] = None,
        active: bool = True
    ) -> Dict:
        """
        Create a new proactive message schedule.
        
        Args:
            platform: 'discord' or 'telegram'
            target_id: User ID or channel ID
            target_name: Display name for the target
            message_type: Type from MESSAGE_TYPES
            trigger_type: 'cron', 'interval', or 'once'
            cron_expression: Cron expression (for cron trigger)
            interval_hours: Hours between messages (for interval trigger)
            run_at: ISO datetime for one-time run
            custom_message: Custom message template
            active: Whether schedule is active
            
        Returns:
            Schedule metadata including ID
        """
        if not HAS_APSCHEDULER:
            raise RuntimeError("APScheduler not installed")
        
        if message_type not in self.MESSAGE_TYPES:
            raise ValueError(f"Invalid message type: {message_type}")
        
        if platform not in ['discord', 'telegram']:
            raise ValueError(f"Invalid platform: {platform}")
        
        schedule_id = str(uuid.uuid4())[:8]
        
        schedule = {
            'id': schedule_id,
            'platform': platform,
            'target_id': target_id,
            'target_name': target_name,
            'message_type': message_type,
            'trigger_type': trigger_type,
            'cron_expression': cron_expression,
            'interval_hours': interval_hours,
            'run_at': run_at,
            'custom_message': custom_message,
            'active': active,
            'created_at': datetime.now().isoformat(),
            'last_run': None,
            'run_count': 0
        }
        
        self.schedules[schedule_id] = schedule
        self._save_schedules()
        
        if active:
            self._register_job(schedule_id, schedule)
        
        return schedule
    
    def update_schedule(
        self,
        schedule_id: str,
        **kwargs
    ) -> Optional[Dict]:
        """Update an existing schedule."""
        if schedule_id not in self.schedules:
            return None
        
        schedule = self.schedules[schedule_id]
        
        # Update allowed fields
        allowed_fields = [
            'message_type', 'trigger_type', 'cron_expression',
            'interval_hours', 'run_at', 'custom_message', 'active', 'target_name'
        ]
        
        for field in allowed_fields:
            if field in kwargs:
                schedule[field] = kwargs[field]
        
        schedule['updated_at'] = datetime.now().isoformat()
        self._save_schedules()
        
        # Re-register or remove job
        if schedule.get('active', True):
            self._register_job(schedule_id, schedule)
        else:
            try:
                self.scheduler.remove_job(schedule_id)
            except:
                pass
        
        return schedule
    
    def delete_schedule(self, schedule_id: str) -> bool:
        """Delete a schedule."""
        if schedule_id not in self.schedules:
            return False
        
        # Remove from scheduler
        try:
            if self.scheduler:
                self.scheduler.remove_job(schedule_id)
        except:
            pass
        
        del self.schedules[schedule_id]
        self._save_schedules()
        return True
    
    def list_schedules(self, platform: Optional[str] = None) -> List[Dict]:
        """Get list of all schedules, optionally filtered by platform."""
        schedules = list(self.schedules.values())
        
        if platform:
            schedules = [s for s in schedules if s.get('platform') == platform]
        
        # Sort by created_at
        schedules.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        
        return schedules
    
    def get_schedule(self, schedule_id: str) -> Optional[Dict]:
        """Get a specific schedule."""
        return self.schedules.get(schedule_id)
    
    def trigger_now(self, schedule_id: str) -> bool:
        """Manually trigger a schedule immediately."""
        if schedule_id not in self.schedules:
            return False
        
        self._execute_schedule(schedule_id)
        return True
    
    def pause_schedule(self, schedule_id: str) -> bool:
        """Pause a schedule."""
        return self.update_schedule(schedule_id, active=False) is not None
    
    def resume_schedule(self, schedule_id: str) -> bool:
        """Resume a paused schedule."""
        return self.update_schedule(schedule_id, active=True) is not None
    
    def get_message_types(self) -> Dict:
        """Get available message types."""
        return self.MESSAGE_TYPES
    
    def is_available(self) -> bool:
        """Check if scheduler service is available."""
        return HAS_APSCHEDULER and self._initialized
    
    def get_stats(self) -> Dict:
        """Get scheduler statistics."""
        total = len(self.schedules)
        active = sum(1 for s in self.schedules.values() if s.get('active', True))
        
        by_platform = {}
        by_type = {}
        
        for schedule in self.schedules.values():
            platform = schedule.get('platform', 'unknown')
            msg_type = schedule.get('message_type', 'unknown')
            
            by_platform[platform] = by_platform.get(platform, 0) + 1
            by_type[msg_type] = by_type.get(msg_type, 0) + 1
        
        total_runs = sum(s.get('run_count', 0) for s in self.schedules.values())
        
        return {
            'total_schedules': total,
            'active_schedules': active,
            'by_platform': by_platform,
            'by_type': by_type,
            'total_runs': total_runs,
            'scheduler_running': self.scheduler.running if self.scheduler else False
        }
    
    def shutdown(self):
        """Shutdown the scheduler."""
        if self.scheduler:
            self.scheduler.shutdown(wait=False)


# Singleton instance
_scheduler_service = None

def get_scheduler_service() -> SchedulerService:
    """Get the singleton scheduler service instance."""
    global _scheduler_service
    if _scheduler_service is None:
        _scheduler_service = SchedulerService()
    return _scheduler_service
