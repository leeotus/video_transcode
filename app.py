import sys
import copy
import os
import logging

import ffmpeg
from utils import *
from converter import *
from etc.config import product_info

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger()

BASE_CONF = {
    "format": "mp4",
    "movflags": "use_metadata_tags+faststart",
    "map_metadata": "0:g",
    "vcodec": "libx264",
    "vsync": 2,  # variable frame rate
    "crf": 24,
    "preset": "veryfast",
    "acodec": "aac",
    "audio_bitrate": "96k",
    "max_muxing_queue_size": 1024,
}

def transcode_video_impl(input_file, dst_params, hdr_filepath, sdr_filepath):
    '''
    @brief Transcode function test
    @param input_file [in] input file path
    @param dst_params [in] output file parameters
    @param hdr_filepath [in] output hdr video path
    @param sdr_filepath [in] output sdr video path
    '''

    ori_info = ffprobe_impl(input_file) # get input file information
    input_file_size = int(ori_info["format"]["size"])
    min_output_file_size = (
        input_file_size * product_info["product_key"]["compress_rate_threshold"]
    )

    # get video stream and the corresponding information
    input_video_info = get_video_info(ori_info)

    # get the name of video stream codec
    input_file_video_codec = input_video_info["codec_name"]

    out_kwargs = copy.deepcopy(BASE_CONF)  # video transcode parameters

    if product_info["product_key"].get("crf"):
        out_kwargs["crf"] = product_info["product_key"]["crf"]

    video_color_params(input_video_info, out_kwargs)  # color parameters
    video_corp(input_video_info, out_kwargs)  # video crop

    video_rescale(
        input_video_info,
        out_kwargs,
        dst_params["dst_width"],
        dst_params["dst_height"],
    ) # video re-scale

    hdr_video = check_hdr_video(input_video_info)  # check if hdr video
    if hdr_video:
        logger.info("hdr video detected")
        hdr_kwargs = copy.deepcopy(out_kwargs)
        if input_video_info.get("codec_tag_string") == "hvc1":
            hdr_kwargs["tag:v"] = "hvc1"

        # use libx265 if hdr video
        if input_file_video_codec == "hevc":  # use libx265 if hdr video
            logger.info("input video codec is hevc")
            hdr_kwargs.update(
                {
                    "vcodec": "libx265",
                    "crf": product_info["product_key"].get("h265_crf", BASE_CONF["crf"]),
                }
            )
            add_hdr_x265_params(hdr_kwargs, input_video_info)

        # QUESTION need test: add x264-params, in case of some videos are encoded by x264 ?

        # hdr video transcode
        logger.info("transcode into hdr video")
        _ = _ffmpeg_impl(input_file, hdr_kwargs, min_output_file_size, hdr_filepath)

    convert_hdr2sdr(out_kwargs)
    # TODO need test: improve x264 parameters
    add_x264_params(out_kwargs)

    if out_kwargs.get("vf"):
        if "format" not in out_kwargs["vf"]:
            out_kwargs["vf"] += ",format=yuv420p"
    else:
        out_kwargs["vf"] = "format=yuv420p"

    logger.info("transcode into sdr video")
    out_info = _ffmpeg_impl(input_file, out_kwargs, min_output_file_size, sdr_filepath)
    output_video_info = get_video_info(out_info)

    video_rotate = output_video_info.get("tags", {}).get("rotate", 0)
    if abs(int(video_rotate)) in (90, 270):
        new_file_height, new_file_width = (
            output_video_info["width"],
            output_video_info["height"],
        )
    else:
        new_file_width, new_file_height = (
            output_video_info["width"],
            output_video_info["height"],
        )

    logger.info("transcode succeed.")
    return

# @brief ffprobe
def ffprobe_impl(input_file, headers = None):
    if headers is not None:
        info = ffmpeg.probe(input_file, headers=headers)
    else:
        info = ffmpeg.probe(input_file)

    return info


def _ffmpeg_impl(input_file, out_kwargs, min_output_file_size, output_file_path):
    info = ffprobe_impl(input_file)
    if int(info["format"]["size"]) > product_info["product_key"]["big_file_size"]:
        max_crf_adj_num = 1
    else:
        max_crf_adj_num = product_info["product_key"]["max_crf_adj_num"]

    os.makedirs(os.path.dirname(output_file_path), exist_ok=True)   # make sure the output file path exists

    for _ in range(max_crf_adj_num):
        (
            ffmpeg.input(input_file, noautorotate=None)
            .output(output_file_path, **out_kwargs)
            .run(quiet=True, overwrite_output=True)
        )

        new_info = ffprobe_impl(output_file_path)
        if(
            (not min_output_file_size) or
            int(new_info["format"]["size"]) > min_output_file_size or
            out_kwargs["crf"] <= 0
        ) :
            break
        else:
            out_kwargs["crf"] -= product_info["product_key"]["crf_step_size"]

    # no need to upload
    return new_info

# @brief main function
def main(source_file, hdr_file, sdr_file):
    output_file_params = {
        "dst_width": 1920,
        "dst_height": 1080,
    }
    transcode_video_impl(source_file, output_file_params, hdr_file, sdr_file)
    return

if __name__ == '__main__':
    source = sys.argv[1]
    hdr = sys.argv[2]
    sdr = sys.argv[3]

    # calculate duration
    import time
    start = time.time()
    main(source, hdr, sdr)
    end = time.time()
    logger.info("duration: %ss", end - start)
