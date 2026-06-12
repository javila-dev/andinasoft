import os

bind = os.getenv('GUNICORN_BIND', '0.0.0.0:8000')
workers = int(os.getenv('GUNICORN_WORKERS', '3'))
timeout = int(os.getenv('GUNICORN_TIMEOUT', '120'))
graceful_timeout = int(os.getenv('GUNICORN_GRACEFUL_TIMEOUT', '30'))
keepalive = int(os.getenv('GUNICORN_KEEPALIVE', '5'))
