import multiprocessing
import os

# Workers — override with WEB_CONCURRENCY env var
workers = int(os.environ.get("WEB_CONCURRENCY", multiprocessing.cpu_count() * 2 + 1))

bind = "0.0.0.0:8000"
timeout = 120

# Periodically recycle workers to prevent memory leaks
max_requests = 1000
max_requests_jitter = 50

# Logging to stdout/stderr (captured by Docker)
accesslog = "-"
errorlog = "-"
loglevel = "warning"

# Trust X-Forwarded-For from nginx
forwarded_allow_ips = "*"
proxy_allow_ips = "*"
