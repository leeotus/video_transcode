from db.video_repository import video_repository


def upsert_video(video_id: str, updates: dict):
    return video_repository().upsert(video_id, updates)


def get_video(video_id: str):
    return video_repository().find_by_id(video_id)
