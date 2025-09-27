import os
import django
from django.core.asgi import get_asgi_application

# Set Django settings module first
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'investor_platform.settings')

# Configure Django before importing anything else
django.setup()

# Now import channels routing (after Django is configured)
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import chat.routing

# Get the Django ASGI application first
django_asgi_app = get_asgi_application()

# Create the protocol router
application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(
        URLRouter(
            chat.routing.websocket_urlpatterns
        )
    ),
})