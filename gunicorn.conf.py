import multiprocessing
import os

# Gunicorn configuration
bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"
workers = multiprocessing.cpu_count() * 2 + 1
timeout = 300  # Øg timeout til 5 minutter
worker_class = "sync"
keepalive = 120
