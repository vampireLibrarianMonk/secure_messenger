from django.urls import re_path

from .consumers import ChatConsumer, VideoSignalingConsumer


websocket_urlpatterns = [
    re_path(r"ws/conversations/(?P<conversation_id>\d+)/$", ChatConsumer.as_asgi()),
    re_path(r"ws/video/conversations/(?P<conversation_id>\d+)/$", VideoSignalingConsumer.as_asgi()),
]
