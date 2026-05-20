import logging
from fractions import Fraction

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger()

def get_video_info(probe_info):
    video_stream = next(
        (stream for stream in probe_info["streams"] if stream["codec_type"] == "video"),
        None,
    )
    assert video_stream is not None
    return video_stream

def check_hdr_video(video_info):
    return detect_hdr_format(video_info) != "sdr"


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

def _find_side_data(video_info, keyword:str):
    """ find the side_data according to the input keyword

    Args:
        video_info (Dict[str, Any]): input video information gained from ffprobe
        keyword (str): side_data_type keyword
    """
    side_data_list = video_info.get("side_data_list") or []

    for side_data in side_data_list:
        if not isinstance(side_data, dict):
            continue

        # get side data type
        side_data_type = str(side_data.get("side_data_type", "")).lower()
        if keyword.lower() in side_data_type:
            return side_data    # already found the side_data

        return None

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

def build_master_display(video_info):
    metadata_keyword = "Mastering display metadata"
    side_data = _find_side_data(video_info, metadata_keyword)
    if not side_data:
        return None

    red_x = _parse_chromaticity(side_data.get("red_x"))
    red_y = _parse_chromaticity(side_data.get("red_y"))
    green_x = _parse_chromaticity(side_data.get("green_x"))
    green_y = _parse_chromaticity(side_data.get("green_y"))
    blue_x = _parse_chromaticity(side_data.get("blue_x"))
    blue_y = _parse_chromaticity(side_data.get("blue_y"))
    white_x = _parse_chromaticity(side_data.get("white_point_x"))
    white_y = _parse_chromaticity(side_data.get("white_point_y"))
    min_luminance = _parse_luminance(side_data.get("min_luminance"))
    max_luminance = _parse_luminance(side_data.get("max_luminance"))

    values = (
        red_x,
        red_y,
        green_x,
        green_y,
        blue_x,
        blue_y,
        white_x,
        white_y,
        min_luminance,
        max_luminance,
    )
    if any(value is None for value in values):
        return None
    return (
        f"G({green_x},{green_y})"
        f"B({blue_x},{blue_y})"
        f"R({red_x},{red_y})"
        f"WP({white_x},{white_y})"
        f"L({max_luminance},{min_luminance})"
    )

def build_max_cll(video_info):
    metadata_keyword = "Content light level metadata"
    side_data = _find_side_data(video_info, metadata_keyword)
    if not side_data:
        # not found
        return None
    max_content = _parse_int(side_data.get("max_content"))
    max_average = _parse_int(side_data.get("max_average"))

    if max_content is None or max_average is None:
        return None
    return f"{max_content},{max_average}"

def _parse_chromaticity(raw_value):
    value = _parse_fraction(raw_value)
    if value is None:
        return None
    return round(value * 50000)

def _parse_luminance(raw_value):
    value = _parse_fraction(raw_value)
    if value is None:
        return None
    return round(value * 10000)

def _parse_fraction(raw_value):
    if raw_value is None:
        return None

    try:
        return float(Fraction(raw_value))
    except (ValueError, ZeroDivisionError):
        logger.error("Invalid HDR metadata value: %s", raw_value)
        return None

def _parse_int(raw_value):
    if raw_value is None:
        return None

    try:
        return int(raw_value)
    except (TypeError, ValueError):
        logger.error("Invalid integer HDR metadata value: %s", raw_value)
        return None
