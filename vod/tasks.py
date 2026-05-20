import logging
import shutil
from pathlib import Path

from base import VOD_BUCKET, VOD_TMP_DIR
from tasks.celery import celery_app
from vod.hls import extract_cover, probe_video, transcode_hls
from db.video_repository import video_repository
from storage.vod_storage import vod_storage

logger = logging.getLogger(__name__)


def _profile_stream_payload(video_id: str, profile: str, uploaded_files: list[dict]):
    prefix = f"videos/{video_id}/{profile}"
    playlist_object = f"{prefix}/index.m3u8"
    playlist = next((item for item in uploaded_files if item["object"] == playlist_object), None)
    return {
        "profile": profile,
        "type": "hls",
        "bucket": VOD_BUCKET,
        "prefix": prefix,
        "playlist_object": playlist_object,
        "playlist_url": playlist["url"] if playlist else None,
        "files": uploaded_files,
    }


@celery_app.task(name="vod.transcode_video", bind=True)
def transcode_video_task(self, video_id: str, source_path: str, original_name: str, display_name: str):
    work_dir = Path(VOD_TMP_DIR) / video_id
    cover_path = work_dir / "cover.jpg"
    hdr_dir = work_dir / "hdr"
    sdr_dir = work_dir / "sdr"

    try:
        repo = video_repository()
        storage = vod_storage()

        repo.upsert(
            video_id,
            {
                "status": "processing",
                "task_id": self.request.id,
                "progress": {"cover": "pending", "hdr": "pending", "sdr": "pending"},
            },
        )

        probe_info, video_info = probe_video(source_path)
        metadata = {
            "format": probe_info.get("format", {}),
            "video": video_info,
        }
        repo.upsert(video_id, {"metadata": metadata})

        extract_cover(source_path, str(cover_path))
        cover_result = storage.upload_file(str(cover_path), f"videos/{video_id}/cover.jpg", "image/jpeg")
        repo.upsert(
            video_id,
            {
                "cover": {
                    "bucket": VOD_BUCKET,
                    "object": f"videos/{video_id}/cover.jpg",
                    "url": cover_result["url"],
                },
                "progress": {"cover": "ready", "hdr": "pending", "sdr": "pending"},
            },
        )

        transcode_hls(source_path, str(hdr_dir), "hdr")
        hdr_files = storage.upload_directory(str(hdr_dir), f"videos/{video_id}/hdr")
        hdr_stream = _profile_stream_payload(video_id, "hdr", hdr_files)
        repo.upsert(
            video_id,
            {
                "streams.hdr": hdr_stream,
                "progress": {"cover": "ready", "hdr": "ready", "sdr": "pending"},
            },
        )

        transcode_hls(source_path, str(sdr_dir), "sdr")
        sdr_files = storage.upload_directory(str(sdr_dir), f"videos/{video_id}/sdr")
        sdr_stream = _profile_stream_payload(video_id, "sdr", sdr_files)
        payload = repo.upsert(
            video_id,
            {
                "status": "ready",
                "streams.sdr": sdr_stream,
                "progress": {"cover": "ready", "hdr": "ready", "sdr": "ready"},
            },
        )
        logger.info("VOD transcode ready: %s", video_id)
        return payload

    except Exception as exc:
        logger.exception("VOD transcode failed: %s", video_id)
        repo.upsert(
            video_id,
            {
                "status": "failed",
                "error": str(exc),
            },
        )
        raise

    finally:
        if work_dir.exists():
            shutil.rmtree(work_dir, ignore_errors=True)
