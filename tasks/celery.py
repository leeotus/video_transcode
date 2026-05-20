from celery import Celery

from base import CELERY_BROKER_URL, CELERY_RESULT_BACKEND

celery_app = Celery(
    "video_transcode",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=["vod.tasks"],
)

celery_app.conf.update(
    task_track_started=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=False,
)
