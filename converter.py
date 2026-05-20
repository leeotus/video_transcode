import logging
from constant import *
from utils import build_master_display
from utils import build_max_cll
from utils import detect_hdr_format

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
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

def convert_hdr2sdr(out_kwargs):
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

def add_hdr_x265_params(out_kwargs, video_info, *, enable_quality_params = True):
    """ add corresponding x265 parameters for input video

    Args:
        out_kwargs (Dict[str, Any]): output video parameters
        video_info (Dict[Str, Any]): video information gained from ffprobe
        enable_quality_params (bool, optional): Whether to turn on quality parameters or not. Defaults to True.
    """
    hdr_format = detect_hdr_format(video_info) # detect hdr format
    logger.info("detected video format: %s", hdr_format)
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

        master_display = build_master_display(video_info)
        if master_display:
            params["master-display"] = master_display

        max_cll = build_max_cll(video_info)
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

def add_x264_params(out_kwargs):
    if out_kwargs.get("vcodec", "") != "libx264":
        logger.info("vcodec is not libx264, skip adding x264 params")
        return

    out_kwargs.update(
        {
            "pix_fmt": "yuv420p",
            "profile:v": "high",
            "level:v": "4.1",
            "tag:v": "avc1",
            "preset": "veryfast",

            "x264-params": (
                "keyint=60:"
                "min-keyint=30:"
                "scenecut=40:"
                "ref=3:"
                "bframes=3:"
                "aq-mode=1:"
                "aq-strength=1.0"
            ),
        }
    )
