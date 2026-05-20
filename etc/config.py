product_info = {
    "product_key": {
        "secret": "secret_for_signature",
        "callback_url": "example.com/url",
        "token_url": "example.com/token",
        "fp_upload_url": "example.com",
        "compress_rate_threshold": 0.2,
        "crf_step_size": 3,
        "max_crf_adj_num": 3,
        "big_file_size": 500 * 1024 * 1024,
        "crf": 25,
    }
}

minio_config = {
    "endpoint": "127.0.0.1:7000",   # minio endpoint
    "public_base_url": "http://127.0.0.1:7000",
    "access_key": "minioadmin",     # minio access_key
    "secret_key": "minioadmin123",  # minio secret_key
    "secure": False,
}
