import copy
import logging
import os
from pathlib import Path

import ffmpeg

from base import VOD_DEFAULT_HEIGHT, VOD_DEFAULT_WIDTH, VOD_HLS_TIME
from converter import add_hdr_x265_params, add_x264_params, convert_hdr2sdr, video_color_params, video_corp, video_rescale
from etc.config import product_info
from transcode import BASE_CONF, ffprobe_impl
from utils import check_hdr_video, get_video_info

logger = logging.getLogger(__name__)


def probe_video(input_file: str):
    probe_info = ffprobe_impl(input_file)
    video_info = get_video_info(probe_info)
    return probe_info, video_info


def build_hls_output_kwargs(input_video_info: dict, profile: str, dst_width: int = VOD_DEFAULT_WIDTH, dst_height: int = VOD_DEFAULT_HEIGHT):
    out_kwargs = copy.deepcopy(BASE_CONF)
    out_kwargs.update(
        {
            "format": "hls",
            "hls_time": VOD_HLS_TIME, # 4s per hls segment
            "hls_playlist_type": "vod",
            "hls_flags": "independent_segments",
            "preset": "veryfast",
            "start_number": 0,
        }
    )
    out_kwargs.pop("movflags", None)

    if product_info["product_key"].get("crf"):
        out_kwargs["crf"] = product_info["product_key"]["crf"]

    video_color_params(input_video_info, out_kwargs)
    video_corp(input_video_info, out_kwargs)
    video_rescale(input_video_info, out_kwargs, dst_width, dst_height)

    if profile == "hdr":
        if check_hdr_video(input_video_info):
            out_kwargs.update(
                {
                    "vcodec": "libx265",
                    "crf": product_info["product_key"].get("h265_crf", BASE_CONF["crf"]),
                }
            )
            add_hdr_x265_params(out_kwargs, input_video_info)
        return out_kwargs

    if profile == "sdr":
        convert_hdr2sdr(out_kwargs)
        add_x264_params(out_kwargs)
        if out_kwargs.get("vf"):
            if "format" not in out_kwargs["vf"]:
                out_kwargs["vf"] += ",format=yuv420p"
        else:
            out_kwargs["vf"] = "format=yuv420p"
        return out_kwargs

    raise ValueError("profile must be 'hdr' or 'sdr'")


def transcode_hls(input_file: str, output_dir: str, profile: str, dst_width: int = VOD_DEFAULT_WIDTH, dst_height: int = VOD_DEFAULT_HEIGHT):
    os.makedirs(output_dir, exist_ok=True)
    _, video_info = probe_video(input_file)
    out_kwargs = build_hls_output_kwargs(video_info, profile, dst_width, dst_height)
    out_kwargs["hls_segment_filename"] = str(Path(output_dir) / "segment_%05d.ts")

    playlist_path = str(Path(output_dir) / "index.m3u8")
    logger.info("start %s HLS transcode: %s", profile, playlist_path)
    (
        ffmpeg.input(input_file, noautorotate=None)
        .output(playlist_path, **out_kwargs)
        .global_args("-hide_banner", "-loglevel", "error")
        .run(overwrite_output=True)
    )
    logger.info("finish %s HLS transcode: %s", profile, playlist_path)
    return playlist_path


def extract_cover(input_file: str, output_path: str):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    (
        ffmpeg.input(input_file, ss=0)
        .output(output_path, vframes=1, format="image2", vcodec="mjpeg")
        .global_args("-hide_banner", "-loglevel", "error")
        .run(overwrite_output=True)
    )
    return output_path
