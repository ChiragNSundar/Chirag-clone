"""
Proactive Routes - API endpoints for managing proactive message schedules.
"""
from flask import Blueprint, request, jsonify
from services.scheduler_service import get_scheduler_service

proactive_bp = Blueprint('proactive', __name__, url_prefix='/api/autopilot')


@proactive_bp.route('/schedules', methods=['GET'])
def list_schedules():
    """Get all proactive message schedules."""
    platform = request.args.get('platform')
    
    try:
        scheduler = get_scheduler_service()
        
        if not scheduler.is_available():
            return jsonify({
                'error': 'Scheduler not available. Install APScheduler.',
                'available': False
            }), 503
        
        schedules = scheduler.list_schedules(platform)
        stats = scheduler.get_stats()
        
        return jsonify({
            'schedules': schedules,
            'stats': stats,
            'available': True
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@proactive_bp.route('/schedules', methods=['POST'])
def create_schedule():
    """
    Create a new proactive message schedule.
    
    JSON body:
    - platform: 'discord' or 'telegram'
    - target_id: User/channel ID
    - target_name: Display name
    - message_type: Type of message
    - trigger_type: 'cron', 'interval', or 'once'
    - cron_expression: For cron trigger (default: '0 9 * * *')
    - interval_hours: For interval trigger
    - run_at: ISO datetime for one-time
    - custom_message: Optional custom template
    """
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'Request body required'}), 400
    
    required = ['platform', 'target_id', 'target_name', 'message_type']
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({'error': f'Missing required fields: {", ".join(missing)}'}), 400
    
    try:
        scheduler = get_scheduler_service()
        
        if not scheduler.is_available():
            return jsonify({'error': 'Scheduler not available'}), 503
        
        schedule = scheduler.create_schedule(
            platform=data['platform'],
            target_id=data['target_id'],
            target_name=data['target_name'],
            message_type=data['message_type'],
            trigger_type=data.get('trigger_type', 'cron'),
            cron_expression=data.get('cron_expression', '0 9 * * *'),
            interval_hours=data.get('interval_hours', 24),
            run_at=data.get('run_at'),
            custom_message=data.get('custom_message'),
            active=data.get('active', True)
        )
        
        return jsonify({
            'success': True,
            'schedule': schedule,
            'message': f'Schedule created for {data["target_name"]}'
        })
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@proactive_bp.route('/schedules/<schedule_id>', methods=['GET'])
def get_schedule(schedule_id: str):
    """Get a specific schedule."""
    try:
        scheduler = get_scheduler_service()
        schedule = scheduler.get_schedule(schedule_id)
        
        if not schedule:
            return jsonify({'error': 'Schedule not found'}), 404
        
        return jsonify(schedule)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@proactive_bp.route('/schedules/<schedule_id>', methods=['PUT'])
def update_schedule(schedule_id: str):
    """Update a schedule."""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'Request body required'}), 400
    
    try:
        scheduler = get_scheduler_service()
        schedule = scheduler.update_schedule(schedule_id, **data)
        
        if not schedule:
            return jsonify({'error': 'Schedule not found'}), 404
        
        return jsonify({
            'success': True,
            'schedule': schedule
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@proactive_bp.route('/schedules/<schedule_id>', methods=['DELETE'])
def delete_schedule(schedule_id: str):
    """Delete a schedule."""
    try:
        scheduler = get_scheduler_service()
        deleted = scheduler.delete_schedule(schedule_id)
        
        if not deleted:
            return jsonify({'error': 'Schedule not found'}), 404
        
        return jsonify({
            'success': True,
            'message': 'Schedule deleted'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@proactive_bp.route('/schedules/<schedule_id>/trigger', methods=['POST'])
def trigger_schedule(schedule_id: str):
    """Manually trigger a schedule now."""
    try:
        scheduler = get_scheduler_service()
        triggered = scheduler.trigger_now(schedule_id)
        
        if not triggered:
            return jsonify({'error': 'Schedule not found'}), 404
        
        return jsonify({
            'success': True,
            'message': 'Schedule triggered'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@proactive_bp.route('/schedules/<schedule_id>/pause', methods=['POST'])
def pause_schedule(schedule_id: str):
    """Pause a schedule."""
    try:
        scheduler = get_scheduler_service()
        paused = scheduler.pause_schedule(schedule_id)
        
        if not paused:
            return jsonify({'error': 'Schedule not found'}), 404
        
        return jsonify({
            'success': True,
            'message': 'Schedule paused'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@proactive_bp.route('/schedules/<schedule_id>/resume', methods=['POST'])
def resume_schedule(schedule_id: str):
    """Resume a paused schedule."""
    try:
        scheduler = get_scheduler_service()
        resumed = scheduler.resume_schedule(schedule_id)
        
        if not resumed:
            return jsonify({'error': 'Schedule not found'}), 404
        
        return jsonify({
            'success': True,
            'message': 'Schedule resumed'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@proactive_bp.route('/message-types', methods=['GET'])
def get_message_types():
    """Get available message types."""
    try:
        scheduler = get_scheduler_service()
        types = scheduler.get_message_types()
        return jsonify(types)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@proactive_bp.route('/stats', methods=['GET'])
def get_stats():
    """Get scheduler statistics."""
    try:
        scheduler = get_scheduler_service()
        
        if not scheduler.is_available():
            return jsonify({
                'available': False,
                'error': 'Scheduler not available'
            })
        
        stats = scheduler.get_stats()
        stats['available'] = True
        return jsonify(stats)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
