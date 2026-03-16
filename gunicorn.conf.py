import os

# Workers — override with WEB_CONCURRENCY env var.
# Default to 2 (safe for Railway / small containers); for VPS use 2*CPU+1.
workers = int(os.environ.get("WEB_CONCURRENCY", 2))

bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"
timeout = 120

# Periodically recycle workers to prevent memory leaks
max_requests = 1000
max_requests_jitter = 50

# Logging to stdout/stderr (captured by container runtime)
accesslog = "-"
errorlog = "-"
loglevel = "warning"

# Trust X-Forwarded-For from reverse proxy (Railway / nginx)
forwarded_allow_ips = "*"
proxy_allow_ips = "*"
