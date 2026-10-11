"""
tools/capture_screenshots.py
批量使用 Headless Edge 截取 OmniAgent Platform 的 8 组高精暗黑主题真机截图并覆写 assets/screenshots/
"""

import os
import subprocess
import time

EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
TARGET_DIR = os.path.abspath("assets/screenshots")
TEMP_USER_DIR = r"C:\Users\21942\AppData\Local\Temp\edge_screenshot_session"

SHOTS = [
    {
        "name": "01-overview.png",
        "url": "http://127.0.0.1:8899/index.html",
        "size": "1920,1080",
        "wait": 4000,
    },
    {
        "name": "02-history.png",
        "url": "http://127.0.0.1:8899/index.html?tab=history",
        "size": "1920,1080",
        "wait": 4000,
    },
    {
        "name": "03-guide.png",
        "url": "http://127.0.0.1:8899/index.html?tab=guide&action=demo",
        "size": "1920,1080",
        "wait": 4000,
    },
    {
        "name": "04-gateway.png",
        "url": "http://127.0.0.1:8899/index.html?tab=gateway&action=demo",
        "size": "1920,1080",
        "wait": 3500,
    },
    {
        "name": "05-marketing.png",
        "url": "http://127.0.0.1:8899/index.html?tab=marketing&action=demo",
        "size": "1920,1080",
        "wait": 3500,
    },
    {
        "name": "06-analytics.png",
        "url": "http://127.0.0.1:8899/index.html?tab=analytics&action=demo",
        "size": "1920,1080",
        "wait": 3500,
    },
    {
        "name": "07-rag.png",
        "url": "http://127.0.0.1:8899/index.html?tab=rag&action=demo",
        "size": "1920,1080",
        "wait": 3500,
    },
    {
        "name": "08-mobile.png",
        "url": "http://127.0.0.1:8899/index.html",
        "size": "430,932",
        "wait": 3500,
    },
]


def capture_all():
    os.makedirs(TARGET_DIR, exist_ok=True)
    for s in SHOTS:
        out_path = os.path.join(TARGET_DIR, s["name"])
        print(f"[*] Capturing {s['name']} from {s['url']}...")
        cmd = [
            EDGE_PATH,
            "--headless=new",
            "--no-sandbox",
            "--disable-gpu",
            f"--user-data-dir={TEMP_USER_DIR}",
            f"--window-size={s['size']}",
            f"--virtual-time-budget={s['wait']}",
            f"--screenshot={out_path}",
            s["url"],
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if os.path.exists(out_path):
            size_kb = os.path.getsize(out_path) // 1024
            print(f"    [OK] {s['name']} ({size_kb} KB)")
        else:
            print(f"    [FAIL] {s['name']}: {res.stderr}")
        time.sleep(0.5)


if __name__ == "__main__":
    capture_all()
