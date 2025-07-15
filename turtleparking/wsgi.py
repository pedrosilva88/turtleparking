"""
WSGI config for turtleparking project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('POSTGRES_DB', 'turtleparking'),
        'USER': os.environ.get('POSTGRES_USER', 'turtleparkinguser'),
        'PASSWORD': os.environ.get('POSTGRES_PASSWORD', 'yourpassword'),
        'HOST': os.environ.get('POSTGRES_HOST', 'localhost'),
        'PORT': os.environ.get('POSTGRES_PORT', '5432'),
    }
}

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'turtleparking.settings')

application = get_wsgi_application()
