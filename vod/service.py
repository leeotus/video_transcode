import uuid
from pathlib import Path
from werkzeug.utils import secure_filename

from base import VOD_TMP_DIR
from db.video_repository import video_repository
from vod.tasks import transcode_video_task


def create_video_upload(file_storage, display_name: str | None = None):
    if file_storage is None:
        raise ValueError("file is required")

    video_id = str(uuid.uuid4())
    original_name = file_storage.filename or "upload.mp4"
    safe_name = secure_filename(original_name) or "upload.mp4"
    user_display_name = display_name or original_name

    work_dir = Path(VOD_TMP_DIR) / video_id
    work_dir.mkdir(parents=True, exist_ok=True)
    source_path = str(work_dir / safe_name)
    file_storage.save(source_path)

    repo = video_repository()
    payload = repo.upsert(
        video_id,
        {
            "video_id": video_id,
            "display_name": user_display_name,
            "original_name": original_name,
            "source_path": source_path,
            "status": "uploaded",
            "progress": {"cover": "pending", "hdr": "pending", "sdr": "pending"},
        },
    )

    task = transcode_video_task.delay(video_id, source_path, original_name, user_display_name)
    payload = repo.upsert(video_id, {"status": "queued", "task_id": task.id})
    return payload


def find_video(video_id: str):
    return video_repository().find_by_id(video_id)


def get_stream(video_id: str, profile: str):
    if profile not in ("hdr", "sdr"):
        raise ValueError("profile must be 'hdr' or 'sdr'")

    video = video_repository().find_by_id(video_id)
    if not video:
        return None

    stream = video.get("streams", {}).get(profile)
    if not stream:
        return {
            "video_id": video_id,
            "profile": profile,
            "status": video.get("status"),
            "ready": False,
        }

    return {
        "video_id": video_id,
        "profile": profile,
        "status": video.get("status"),
        "ready": True,
        "stream": stream,
    }
