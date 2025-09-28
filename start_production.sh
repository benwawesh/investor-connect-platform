#!/bin/bash
cd /var/www/investor-connect-platform
source venv/bin/activate
gunicorn --bind 0.0.0.0:8080 --workers 3 investor_platform.wsgi:application
