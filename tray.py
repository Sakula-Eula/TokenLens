"""TokenLens Windows 系统托盘启动入口。

启动后：
- 后台线程运行 uvicorn，服务监听 http://127.0.0.1:7788
- 右下角显示托盘图标，单击显示紧凑浮窗
- 通过右键菜单打开独立 Dashboard 桌面窗口
- 右键菜单可打开 config.yaml、退出程序

用法:
    .venv/Scripts/python.exe tray.py
"""
import sys
import threading
import time
from multiprocessing import freeze_support
from pathlib import Path

import pystray
import uvicorn
from PIL import Image

from desktop_app import DesktopController
from windows_tray import HoverTrayIcon

ROOT = Path(__file__).resolve().parent
HOST = "127.0.0.1"
PORT = 7788
ICON_PATH = ROOT / "assets" / "icon.png"


def _load_icon(path: Path) -> Image.Image:
    """加载托盘图标；找不到图片时回退到程序化绘制的简易图标。"""
    if path.exists():
        img = Image.open(path).convert("RGBA")
        # 托盘图标缩到 64x64，Windows 会按 DPI 再缩放
        return img.resize((64, 64), Image.LANCZOS)

    from PIL import ImageDraw

    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((4, 4, 60, 60), fill=(37, 99, 235, 255))
    draw.text((22, 18), "TL", fill=(255, 255, 255, 255))
    return img


def _open_config() -> None:
    config_path = ROOT / "config.yaml"
    if not config_path.exists():
        config_path = ROOT / "config.yaml.example"
    if sys.platform == "win32":
        import os

        os.startfile(config_path)  # type: ignore[attr-defined]
    else:
        raise RuntimeError("TokenLens desktop mode currently supports Windows only")


def main() -> None:
    from backend.main import app

    desktop = DesktopController(f"http://{HOST}:{PORT}")
    config = uvicorn.Config(app=app, host=HOST, port=PORT, log_level="info")
    server = uvicorn.Server(config)

    # uvicorn 跑在后台线程，主线程留给托盘消息循环（pystray 在 Windows 需要主线程）
    server_thread = threading.Thread(target=server.run, name="uvicorn", daemon=True)
    server_thread.start()

    for _ in range(100):
        if server.started:
            break
        if not server_thread.is_alive():
            raise RuntimeError(f"TokenLens 无法启动：端口 {PORT} 可能已被占用")
        time.sleep(0.05)
    else:
        raise RuntimeError("TokenLens 后台服务启动超时")

    def on_widget(icon, item) -> None:
        desktop.on_tray_click()

    def on_open(icon, item) -> None:
        desktop.open_dashboard()

    def on_config(icon, item) -> None:
        _open_config()

    def on_exit(icon, item) -> None:
        server.should_exit = True
        desktop.stop()
        icon.stop()

    icon = HoverTrayIcon(
        "TokenLens",
        _load_icon(ICON_PATH),
        "TokenLens",
        on_hover=desktop.on_tray_hover,
        menu=pystray.Menu(
            pystray.MenuItem("显示悬浮窗", on_widget, default=True),
            pystray.MenuItem("打开 Dashboard", on_open),
            pystray.MenuItem("打开 config.yaml", on_config),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("退出", on_exit),
        ),
    )
    icon.run_detached()

    try:
        desktop.run()
    finally:
        # 无论窗口循环正常结束还是抛错，都回收托盘与后台服务。
        icon.stop()
        server.should_exit = True
        server_thread.join(timeout=5)


if __name__ == "__main__":
    freeze_support()
    main()
