#!/bin/bash

# Skift til appens mappe
cd /home/site/wwwroot
echo "✅ Skiftet til app mappen: /home/site/wwwroot"

# Tilføj . mappen til PYTHONPATH
export PYTHONPATH=$PYTHONPATH:/home/site/wwwroot
echo "✅ PYTHONPATH er sat til: $PYTHONPATH"

# Tjek om gunicorn.conf.py findes
if [ ! -f "gunicorn.conf.py" ]; then
    echo "❌ gunicorn.conf.py ikke fundet - opretter standard konfiguration..."
    cat > gunicorn.conf.py << EOL
import multiprocessing

# Gunicorn configuration
bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"
workers = multiprocessing.cpu_count() * 2 + 1
timeout = 300  # Øg timeout til 5 minutter
worker_class = "sync"
keepalive = 120
EOL
fi

# Start Gunicorn med config fil og wsgi entry point
echo "✅ Starter Gunicorn med gunicorn.conf.py og wsgi entry point..."
exec gunicorn --config gunicorn.conf.py wsgi:app