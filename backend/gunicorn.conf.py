"""
Gunicorn Configuration for Production Deployment
Run with: gunicorn -c gunicorn.conf.py app:app
"""
import multiprocessing

# Server socket
bind = "0.0.0.0:5000"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "geventwebsocket.gunicorn.workers.GeventWebSocketWorker"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 100

# Timeouts
timeout = 120
graceful_timeout = 30
keepalive = 5

# Security
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "chirag-clone"

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# Hooks
def on_starting(server):
    """Called just before the master process is initialized."""
    pass

def on_reload(server):
    """Called to recycle workers during a reload via SIGHUP."""
    pass

def worker_int(worker):
    """Called when a worker receives SIGINT or SIGQUIT."""
    pass

def worker_abort(worker):
    """Called when a worker receives SIGABRT."""
    pass

def pre_fork(server, worker):
    """Called just before a worker is forked."""
    pass

def post_fork(server, worker):
    """Called just after a worker has been forked."""
    pass

def post_worker_init(worker):
    """Called just after a worker has initialized."""
    pass

def worker_exit(server, worker):
    """Called just after a worker has been exited."""
    pass

def nworkers_changed(server, new_value, old_value):
    """Called when the number of workers has been changed."""
    pass

def on_exit(server):
    """Called just before exiting Gunicorn."""
    pass
