### Usage
```bash
python app.py <input_file> <hdr_output_file> <sdr_output_file>
```

### ffprobe
use `ffprobe` to print out input video's info:
```bash
ffprobe -v quiet -print_format json -show_streams <input_file>
```

### PSNR

use the following `ffmpeg` command to calculate PSNR:

```bash
ffmpeg -i <trancoded_video> -i <original_video> -lavfi "psnr" -f null -
```

### SSIM
use the following `ffmpeg` command to calculate SSIM:
```bash
ffmpeg -i <trancoded_video> -i <original_video> -lavfi "ssim" -f null -
```

### TODO
- [ ] add `celery` for video transcoding
- [ ] support hdr10+ video