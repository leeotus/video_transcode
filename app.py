from flask import Flask, jsonify, request, stream_with_context, Response
from base import *
import logging
import signal
from storage.file_uploader import FileUploader, generate_presigned_url
from minio.error import S3Error
from transcode import *
from vod.service import create_video_upload, find_video, get_stream

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.Logger(__name__)

app = Flask(__name__)

@app.after_request
def add_cors_headers(response):
  response.headers["Access-Control-Allow-Origin"] = "*"
  response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
  response.headers["Access-Control-Allow-Headers"] = "Content-Type"
  response.headers["Access-Control-Expose-Headers"] = "Content-Type"
  return response

@app.get("/heal")
def health():
  return jsonify({"status": "ok"})

@app.post("/api/videos")
def upload_vod_video():
  file_storage = request.files.get("file")
  display_name = request.form.get("name") or request.form.get("display_name")
  try:
    payload = create_video_upload(file_storage, display_name)
  except ValueError as exc:
    return jsonify({"error": str(exc)}), 400
  except Exception as exc:
    logger.exception("create VOD upload failed")
    return jsonify({"error": str(exc)}), 500
  return jsonify(payload), 202

@app.get("/api/videos/<video_id>")
def get_vod_video(video_id: str):
  try:
    payload = find_video(video_id)
  except Exception as exc:
    logger.exception("get VOD video failed")
    return jsonify({"error": str(exc)}), 500
  if not payload:
    return jsonify({"error": "video not found"}), 404
  return jsonify(payload)

@app.get("/api/videos/<video_id>/streams/<profile>")
def get_vod_stream(video_id: str, profile: str):
  try:
    payload = get_stream(video_id, profile.lower())
  except ValueError as exc:
    return jsonify({"error": str(exc)}), 400
  except Exception as exc:
    logger.exception("get VOD stream failed")
    return jsonify({"error": str(exc)}), 500
  if not payload:
    return jsonify({"error": "video not found"}), 404
  if not payload.get("ready"):
    return jsonify(payload), 202
  return jsonify(payload)

# Legacy realtime upload API. Kept for compatibility during migration.
@app.post("/video/<path:object_name>")
def upload_video(object_name: str):
  bucket = request.args.get("bucket", DEFAULT_BUCKET)
  client = FileUploader()
  client.create_bucket(bucket)

  length = request.content_length if request.content_length is not None else -1
  part_size = 10 * 1024 * 1024 if length == -1 else 0

  try:
    res = client.upload_from_stream(
      bucket_name=bucket,
      object_name=object_name,
      data_stream=request.stream,
      length=length,
      part_size=part_size,
      content_type=request.content_type or "application/octet-stream",
    )
  except ValueError as exc:
    logger.exception("invalid upload request")
    return jsonify({"error": str(exc)}), 400
  except S3Error as exc:
    logger.exception("upload failed")
    return jsonify({"error": str(exc)}), 502
  except RuntimeError as exc:
    logger.exception("storage client error")
    return jsonify({"error": str(exc)}), 500

  return jsonify({"bucket": res.bucket_name, "object": res.object_name})

# Legacy realtime stream API. Will be removed after VOD HLS frontend migration.
@app.get("/video/<path:object_name>/stream")
def get_video_stream(object_name: str):
    bucket = request.args.get("bucket", DEFAULT_BUCKET)
    profile = request.args.get("profile", "hdr").lower()
    dst_width = int(request.args.get("width", DEFAULT_DST_WIDTH))
    dst_height = int(request.args.get("height", DEFAULT_DST_HEIGHT))

    if profile not in ("hdr", "sdr"):
        return jsonify({"error": "profile must be 'hdr' or 'sdr'"}), 400

    # example: http://minio:9000/videos/demo.mp4?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=...
    input_url = generate_presigned_url(bucket, object_name)
    try:
        probe_info = ffprobe_impl(input_url)
        input_video_info = get_video_info(probe_info)
        out_kwargs = build_realtime_output_kwargs(
            input_video_info, profile, dst_width, dst_height
        )
    except Exception as exc:
        logger.exception("probe/build output args failed")
        return jsonify({"error": str(exc)}), 400

    process = spawn_ffmpeg_stream(input_url, out_kwargs)

    def generate():
        try:
            while True:
                chunk = process.stdout.read(STREAM_CHUNK_SIZE)
                if not chunk:
                    break
                yield chunk
        finally:
            if process.poll() is None:
                process.send_signal(signal.SIGTERM)
            stderr = (
                process.stderr.read().decode("utf-8", errors="ignore")
                if process.stderr
                else ""
            )
            return_code = process.wait()
            if return_code not in (0, -signal.SIGTERM) and stderr:
                logger.error("ffmpeg stream failed: %s", stderr)

    headers = {
      "Content-Type": "video/mp4",
      "Cache-Control": "no-store",
      "X-Accel-Buffering": "no",
    }
    return Response(stream_with_context(generate()), headers=headers, direct_passthrough=True)

if __name__ == "__main__":
    app.run(
        host=os.getenv("FLASK_HOST", "0.0.0.0"),
        port=int(os.getenv("FLASK_PORT", "5000")),
        debug=True,
    )
