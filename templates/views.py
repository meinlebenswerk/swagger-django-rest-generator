"""
Do not modify this file. It is generated from the Swagger specification.

"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import mixins, viewsets

from .serializers import *
from . import api_implementation as implemented_handlers


def findHandler(name):
    handler = getattr(implemented_handlers, name, None)
    if handler is not None and callable(handler):
        return handler
    return None


def verifyToken(token):
    return False

