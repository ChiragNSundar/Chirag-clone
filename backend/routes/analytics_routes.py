"""
Analytics Routes - API endpoints for analytics dashboard.
"""
from flask import Blueprint, jsonify
from services.analytics_service import get_analytics_service
from services.backup_service import get_backup_service

analytics_bp = Blueprint('analytics', __name__, url_prefix='/api/analytics')


@analytics_bp.route('/dashboard', methods=['GET'])
def get_dashboard():
    """Get analytics dashboard data."""
    analytics = get_analytics_service()
    return jsonify(analytics.get_dashboard_data())


@analytics_bp.route('/suggestions', methods=['GET'])
def get_suggestions():
    """Get training suggestions."""
    analytics = get_analytics_service()
    return jsonify({'suggestions': analytics.get_suggestions()})


@analytics_bp.route('/backup', methods=['POST'])
def create_backup():
    """Create a new backup."""
    backup = get_backup_service()
    result = backup.create_backup()
    return jsonify(result)


@analytics_bp.route('/backups', methods=['GET'])
def list_backups():
    """List all backups."""
    backup = get_backup_service()
    return jsonify({'backups': backup.list_backups()})


@analytics_bp.route('/restore/<backup_name>', methods=['POST'])
def restore_backup(backup_name: str):
    """Restore from a backup."""
    backup = get_backup_service()
    result = backup.restore_backup(backup_name)
    return jsonify(result)


@analytics_bp.route('/export', methods=['GET'])
def export_personality():
    """Export personality to JSON."""
    backup = get_backup_service()
    result = backup.export_personality()
    return jsonify(result)


@analytics_bp.route('/backup/<backup_name>', methods=['DELETE'])
def delete_backup(backup_name: str):
    """Delete a backup."""
    backup = get_backup_service()
    result = backup.delete_backup(backup_name)
    return jsonify(result)
