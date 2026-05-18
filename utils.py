from fractions import Fraction
from typing import Any, Dict, Optional
import logging
from constant import *

logger = logging.getLogger()

def video_color_params(video_info, out_kwargs):
    colorspace = video_info.get("color_space")
    if colorspace not in COLOR_SPACE.values():
        colorspace = COLOR_SPACE.get(colorspace, "unspecified")
    out_kwargs["colorspace"] = colorspace

    color_trc = video_info.get("color_transfer")
    if color_trc not in COLOR_TRC.values():
        color_trc = COLOR_TRC.get(color_trc, "unspecified")
    out_kwargs["color_trc"] = color_trc

    color_primaries = video_info.get("color_primaries")
    if color_primaries not in COLOR_PRIM.values():
        color_primaries = COLOR_PRIM.get(color_primaries, "unspecified")
    out_kwargs["color_primaries"] = color_primaries


def get_video_info(probe_info):
    video_stream = next(
        (stream for stream in probe_info["streams"] if stream["codec_type"] == "video"),
        None,
    )
    assert video_stream is not None
    return video_stream

def video_corp(video_info, out_kwargs):
    if video_info["width"] % 2 != 0 or video_info["height"] % 2 != 0:
        if out_kwargs.get("vf"):
            out_kwargs["vf"] += ",crop=trunc(iw/2)*2:trunc(ih/2)*2"
        else:
            out_kwargs["vf"] = "crop=trunc(iw/2)*2:trunc(ih/2)*2"

def video_rescale(video_info, out_kwargs, dst_width, dst_height):
    if video_info["width"] < video_info["height"]:
        dst_width, dst_height = dst_height, dst_width

    if video_info["width"] / video_info["height"] >= dst_width / dst_height:
        if video_info["width"] > dst_width:
            if out_kwargs.get("vf"):
                out_kwargs["vf"] += "," + "scale=w={w}:h=-2".format(w=dst_width)
            else:
                out_kwargs["vf"] = "scale=w={w}:h=-2".format(w=dst_width)
    else:
        if video_info["height"] > dst_height:
            if out_kwargs.get("vf"):
                out_kwargs["vf"] += "," + "scale=w=-2:h={h}".format(h=dst_height)
            else:
                out_kwargs["vf"] = "scale=w=-2:h={h}".format(h=dst_height)

def check_hdr_video(video_info):
    if (
        video_info.get("color_space") == "bt2020nc"
        and video_info.get("color_transfer") in ("arib-std-b67", "smpte2084")
        and video_info.get("color_primaries") == "bt2020"
    ):
        return True
    else:
        return False

def hdr_to_sdr(out_kwargs):
    vf = (
        "zscale=t=linear:npl=100,tonemap=tonemap=hable:desat=0,"
        "zscale=t=bt709:p=bt709:m=bt709:r=tv,format=yuv420p"
    )
    if out_kwargs.get("vf"):
        out_kwargs["vf"] += "," + vf
    else:
        out_kwargs["vf"] = vf
    for key in ("colorspace", "color_trc", "color_primaries"):
        out_kwargs[key] = "bt709"

"""
def add_hdr_x265_params(out_kwargs):
    hdr_params = (
        "aq-mode=3:"
        "aq-strength=0.6:"
        "rc-lookahead=60:"
        "bframes=4:"
        "b-adapt=2:"
        "ref=4:"
        "me=star:"
        "merange=32:"
        "subme=4:"
        "deblock=0,0:"
        "psy-rd=2.0:"
        "psy-rdoq=1.0:"
        "hdr-opt=1:"
        "repeat-headers=1:"
        "no-open-gop=1"
    )
    existing = out_kwargs.get("x265-params")
    out_kwargs["x265-params"] = f"{existing}:{hdr_params}" if existing else hdr_params
"""

def add_hdr_x265_params(out_kwargs, video_info, *, enable_quality_params = True):
    """ add corresponding x265 parameters for input video

    Args:
        out_kwargs (Dict[str, Any]): output video parameters
        video_info (Dict[Str, Any]): video information gained from ffprobe
        enable_quality_params (bool, optional): Whether to turn on quality parameters or not. Defaults to True.
    """
    hdr_format = detect_hdr_format(video_info) # detect hdr format
    logger.info("Detected video format: %s", hdr_format)
    if hdr_format == "sdr":
        # no need to add hdr params
        return

    params = {}
    if enable_quality_params:
        params.update({
            "aq-mode":"3",
            "aq-strength":"0.6",
            "rc-lookahead":"60",
            "bframes":"4",
            "b-adapt":"2",
            "ref":"4",
            "me":"star",
            "merange":"32",
            "subme":"4",
            "deblock":"0,0",
            "psy-rd":"2.0",
            "psy-rdoq":"1.0",
        })
        
    # TODO: detect hdr10+ format
    if hdr_format in ("hdr10", "dolby_vision"):
        params.update({
            "hdr10": "1",
            "hdr-opt": "1",
            "repeat-headers": "1",
            "no-open-gop": "1",
            "colorprim": "bt2020",
            "transfer": "smpte2084",
            "colormatrix": "bt2020nc",
        })
        
        # TODO: get mastering display metadata from video info
        master_display = None
        if master_display:
            params["master-display"] = master_display
            
        # TODO: get max cll and max fall from video info
        max_cll = None
        if max_cll:
            params["max-cll"] = max_cll
        
        if hdr_format in ("dolby_vision"):
            logger.warning("%s dynamic metadata not supported yet", hdr_format)
    elif hdr_format in ("hlg"):
        # different from hdr10
        params.update(
            {
                "repeat-headers": "1",
                "no-open-gop": "1",
                "colorprim": "bt2020",
                "transfer": "arib-std-b67",
                "colormatrix": "bt2020nc",
            }
        )
        
    _merge_x265_params(out_kwargs, params)


def _get_side_data_types(video_info):
    """ get "side_data_types" field from input video_info

    Args:
        video_info (Dict[str, Any]): input video information gained from ffprobe
    Returns:
        list[str]: list of side data types
    """
    side_data_list = video_info.get("side_data_list") or []
    return [
        str(item.get("side_data_type", "")).lower() # lower case
        for item in side_data_list
        if isinstance(item, dict)
    ]

def detect_hdr_format(video_info):
    """ detect hdr format

    Args:
        video_info (Dict[str, Any]): input video information gained from ffprobe

    Returns:
        str: hdr format, "sdr", "hlg", "hdr10" and "dolby_vision", note: "hdr10+" not supported yet
    """
    color_space = video_info.get("color_space")
    color_transfer = video_info.get("color_transfer")
    color_primaries = video_info.get("color_primaries")
    
    side_data_types = _get_side_data_types(video_info)
    
    if color_primaries != "bt2020":
        return "sdr"
    
    if color_transfer == "arib-std-b67":
        return "hlg"

    if color_transfer == "smpte2084" and color_space == "bt2020nc":
        # already lower case when get side_data_types from _get_side_data_types
        if any("dovi" in item or "dolby vision" in item for item in side_data_types):
            return "dolby_vision"
        # TODO: detect hdr10+ format
        return "hdr10"

    return "sdr"

def _merge_x265_params(out_kwargs, params):
    """ merge current x265 parameters into out_kwargs

    Args:
        out_kwargs (Dict[str, str]): output video parameters
        params (Dict[str, str]): current x265 parameters
    """
    current_params = ""
    for key, value in params.items():
        if(len(current_params) == 0):
            current_params = f"{key}={value}"
        else:
            current_params = f"{current_params}:{key}={value}"
        
    existing = out_kwargs.get("x265-params")
    if existing:
        out_kwargs["x265-params"] = f"{existing}:{current_params}"
    else:
        out_kwargs["x265-params"] = current_params

