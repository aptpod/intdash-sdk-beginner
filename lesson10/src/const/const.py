"""
定数定義

- iSCP設定
- 受信データ名
- 送信データ名
- 送受信データ設定
- 画像要約設定
- グリッド画像設定
- GStreame パイプライン
"""

# iSCP設定

import cv2

PORT = 443
READ_TIMEOUT = 5 * 60.0  # 秒
PING_INTERVAL = 10 * 60.0  # 秒
PING_TIMEOUT = 10.0  # 秒

# 受信データ名
DOWN_DATA_NAME_H264 = "1/h264"

# 送信データ名
UP_DATA_NAME_PREVIEW = "11/preview"
UP_DATA_NAME_SUMMARY = "12/summary"
UP_DATA_NAME_ANSWER = "12/answer"

# 送受信データ設定
H264_SIZE = 640, 480
JPEG_SIZE = 1280, 960
FPS = 15
QUALITY = 50

# 画像要約設定
MODEL = "gpt-4o-mini"
PROMPT_PATH = "./lesson10/config/prompt.txt"

# グリッド画像設定
GRID = (4, 4)
DIFF_THRESHOLD = 0.20
FLUSH_TIMEOUT = 10.0  # sec
TEXT_FONT = cv2.FONT_HERSHEY_PLAIN
TEXT_OFFSET = (8, 18)
TEXT_SCALE = 0.9
TEXT_COLOR = (133, 62, 215)  # D73E85 -> BGR
TEXT_THICK = 1

# GStreame パイプライン
# - H.264デコード
# - JPEGエンコード
DECODE_PIPELINE = """
    appsrc name=src is-live=true format=time caps=video/x-h264,stream-format=byte-stream ! 
    h264parse config-interval=-1 ! avdec_h264 ! videoconvert ! video/x-raw,format=BGR !
    appsink name=sink sync=false emit-signals=true
"""
ENCODE_PIPELINE = """
    appsrc name=src is-live=true format=time caps=video/x-raw,format=BGR,width={width},height={height},framerate={fps}/1 !
    videoconvert !
    jpegenc quality={quality} !
    appsink name=sink sync=false emit-signals=true caps=image/jpeg
""".format(
    width=JPEG_SIZE[0],
    height=JPEG_SIZE[1],
    fps=FPS,
    quality=QUALITY,
)
