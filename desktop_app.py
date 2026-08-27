"""Native desktop window controller for TokenLens on Windows."""

from __future__ import annotations

import ctypes
import logging
import multiprocessing
import threading
import time
from urllib.parse import urlencode
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any


LOGGER = logging.getLogger(__name__)

WIDGET_WIDTH = 480
WIDGET_HEIGHT = 600
WIDGET_MARGIN = 12
HOVER_GRACE_SECONDS = 0.35
APP_ICON_PATH = Path(__file__).resolve().parent / "assets" / "icon.ico"


@dataclass(frozen=True)
class WorkArea:
    left: int
    top: int
    right: int
    bottom: int


def calculate_widget_bounds(work_area: WorkArea) -> tuple[int, int, int, int]:
    """Fit and anchor the widget to the bottom-right of a monitor work area."""
    available_width = max(320, work_area.right - work_area.left - WIDGET_MARGIN * 2)
    available_height = max(320, work_area.bottom - work_area.top - WIDGET_MARGIN * 2)
    width = min(WIDGET_WIDTH, available_width)
    height = min(WIDGET_HEIGHT, available_height)
    x = max(work_area.left + WIDGET_MARGIN, work_area.right - width - WIDGET_MARGIN)
    y = max(work_area.top + WIDGET_MARGIN, work_area.bottom - height - WIDGET_MARGIN)
    return x, y, width, height


def _cursor_position() -> tuple[int, int]:
    point = wintypes.POINT()
    if not ctypes.windll.user32.GetCursorPos(ctypes.byref(point)):
        return 0, 0
    return point.x, point.y


def _cursor_work_area() -> WorkArea:
    class MonitorInfo(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("rcMonitor", wintypes.RECT),
            ("rcWork", wintypes.RECT),
            ("dwFlags", wintypes.DWORD),
        ]

    x, y = _cursor_position()
    point = wintypes.POINT(x, y)
    monitor = ctypes.windll.user32.MonitorFromPoint(point, 2)
    info = MonitorInfo(cbSize=ctypes.sizeof(MonitorInfo))
    if monitor and ctypes.windll.user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
        rect = info.rcWork
        scale = 1.0
        try:
            dpi_x = wintypes.UINT()
            dpi_y = wintypes.UINT()
            if ctypes.windll.shcore.GetDpiForMonitor(
                monitor, 0, ctypes.byref(dpi_x), ctypes.byref(dpi_y)
            ) == 0:
                scale = max(1.0, dpi_x.value / 96.0)
        except (AttributeError, OSError):
            LOGGER.debug("Per-monitor DPI is unavailable", exc_info=True)
        return WorkArea(
            round(rect.left / scale),
            round(rect.top / scale),
            round(rect.right / scale),
            round(rect.bottom / scale),
        )

    rect = wintypes.RECT()
    ctypes.windll.user32.SystemParametersInfoW(48, 0, ctypes.byref(rect), 0)
    return WorkArea(rect.left, rect.top, rect.right, rect.bottom)


def _set_app_user_model_id() -> None:
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "TokenLens.Desktop"
        )
    except (AttributeError, OSError):
        LOGGER.debug("Windows AppUserModelID is unavailable", exc_info=True)


class WidgetApi:
    """Methods exposed to the Vue widget through ``window.pywebview.api``."""

    def __init__(self, controller: "DesktopController") -> None:
        self._controller = controller

    def open_dashboard(self, path: str = "/dashboard") -> None:
        self._controller.open_dashboard(path)

    def set_widget_pinned(self, pinned: bool) -> None:
        self._controller.set_widget_pinned(bool(pinned))

    def close_widget(self) -> None:
        self._controller.hide_widget()

    def widget_pointer_enter(self) -> None:
        self._controller.set_widget_pointer_inside(True)

    def widget_pointer_leave(self) -> None:
        self._controller.set_widget_pointer_inside(False)


def _app_url(base_url: str, path: str, admin_token: str) -> str:
    return f"{base_url}{path}?{urlencode({'admin_token': admin_token})}"


def _dashboard_command_monitor(window, commands, base_url: str, admin_token: str) -> None:
    while True:
        path = commands.get()
        if path is None:
            window.destroy()
            return
        window.load_url(_app_url(base_url, path, admin_token))
        window.show()
        window.restore()


def run_dashboard_process(base_url: str, initial_path: str, commands, admin_token: str) -> None:
    """Run the Dashboard in its own native GUI process."""
    import webview

    _set_app_user_model_id()
    window = webview.create_window(
        "TokenLens",
        _app_url(base_url, initial_path, admin_token),
        width=1280,
        height=820,
        min_size=(960, 640),
        background_color="#f4f7fb",
    )

    def start_command_monitor() -> None:
        threading.Thread(
            target=_dashboard_command_monitor,
            args=(window, commands, base_url, admin_token),
            name="dashboard-command-monitor",
            daemon=True,
        ).start()

    webview.start(
        start_command_monitor,
        gui="edgechromium",
        debug=False,
        icon=str(APP_ICON_PATH),
    )


class DesktopController:
    """Own the pywebview windows and coordinate them with the tray thread."""

    def __init__(
        self,
        base_url: str,
        admin_token: str = "",
        *,
        hover_grace: float = HOVER_GRACE_SECONDS,
        process_context=None,
    ):
        self.base_url = base_url.rstrip("/")
        self.admin_token = admin_token
        self.hover_grace = hover_grace
        self.widget: Any | None = None
        self._webview: Any | None = None
        self._lock = threading.RLock()
        self._last_tray_hover = 0.0
        self._widget_show_requested = False
        self._widget_visible = False
        self._widget_pointer_inside = False
        self._widget_pinned = False
        self._ready = False
        self._pending_dashboard_path: str | None = None
        self._process_context = process_context or multiprocessing.get_context("spawn")
        self._dashboard_process: Any | None = None
        self._dashboard_commands: Any | None = None
        self._exiting = False
        self._monitor_thread: threading.Thread | None = None

    def create_windows(self) -> None:
        import webview

        _set_app_user_model_id()
        self._webview = webview
        api = WidgetApi(self)
        self.widget = webview.create_window(
            "TokenLens 概览",
            _app_url(self.base_url, "/widget", self.admin_token),
            js_api=api,
            width=WIDGET_WIDTH,
            height=WIDGET_HEIGHT,
            x=-10000,
            y=-10000,
            frameless=True,
            easy_drag=False,
            shadow=True,
            resizable=False,
            on_top=True,
            background_color="#f4f7fb",
        )
        self.widget.events.closing += self._on_widget_closing
        self.widget.events.loaded += self._on_widget_loaded

    def run(self) -> None:
        if self._webview is None:
            self.create_windows()
        self._webview.start(
            self._start_hover_monitor,
            gui="edgechromium",
            debug=False,
            icon=str(APP_ICON_PATH),
        )

    def _start_hover_monitor(self) -> None:
        self._monitor_thread = threading.Thread(
            target=self._monitor_hover,
            name="widget-hover-monitor",
            daemon=True,
        )
        self._monitor_thread.start()

    def _on_widget_loaded(self) -> None:
        with self._lock:
            first_load = not self._ready
            self._ready = True
            pending_path = self._pending_dashboard_path
            self._pending_dashboard_path = None
            should_show = not self._exiting and self._widget_show_requested
            self._widget_show_requested = False
            widget = self.widget
        self._make_widget_non_activating()
        if first_load and widget is not None:
            widget.hide()
        if pending_path is not None:
            self.open_dashboard(pending_path)
        if should_show:
            self._show_widget()

    def _widget_handle(self) -> int | None:
        try:
            handle = self.widget.native.Handle
            return int(handle.ToInt64() if hasattr(handle, "ToInt64") else handle)
        except (AttributeError, RuntimeError, TypeError):
            return None

    def _make_widget_non_activating(self) -> None:
        """Apply popup window styles only after WebView2 has initialized."""
        handle = self._widget_handle()
        if handle is None:
            return
        try:
            style = ctypes.windll.user32.GetWindowLongW(handle, -20)
            style = (style | 0x08000000 | 0x00000080) & ~0x00040000
            ctypes.windll.user32.SetWindowLongW(handle, -20, style)
        except (AttributeError, OSError):
            LOGGER.debug("Could not apply widget popup styles", exc_info=True)

    def on_tray_hover(self) -> None:
        with self._lock:
            self._last_tray_hover = time.monotonic()

    def on_tray_click(self) -> None:
        with self._lock:
            if self._exiting:
                return
            self._last_tray_hover = time.monotonic()
            if not self._ready:
                self._widget_show_requested = True
                return
            should_show = not self._widget_visible
        if should_show:
            self._show_widget()

    def open_dashboard(self, path: str = "/dashboard") -> None:
        if not path.startswith("/"):
            path = "/dashboard"
        with self._lock:
            if self._exiting:
                return
            if not self._ready or self._webview is None:
                self._pending_dashboard_path = path
                return
            widget = self.widget
            self._widget_visible = False
        if widget is not None:
            widget.hide()
        with self._lock:
            process = self._dashboard_process
            commands = self._dashboard_commands
            if process is not None and process.is_alive() and commands is not None:
                commands.put(path)
                return
            commands = self._process_context.Queue()
            process = self._process_context.Process(
                target=run_dashboard_process,
                args=(self.base_url, path, commands, self.admin_token),
                name="TokenLens-Dashboard",
                daemon=True,
            )
            process.start()
            self._dashboard_commands = commands
            self._dashboard_process = process

    def set_widget_pinned(self, pinned: bool) -> None:
        with self._lock:
            self._widget_pinned = pinned

    def hide_widget(self) -> None:
        """Hide the popup without terminating the tray application."""
        self._hide_widget()

    def set_widget_pointer_inside(self, inside: bool) -> None:
        with self._lock:
            self._widget_pointer_inside = inside

    def stop(self) -> None:
        with self._lock:
            if self._exiting:
                return
            self._exiting = True
            widget = self.widget
            process = self._dashboard_process
            commands = self._dashboard_commands
        if commands is not None and process is not None and process.is_alive():
            commands.put(None)
            process.join(timeout=5)
            if process.is_alive():
                process.terminate()
                process.join(timeout=2)
        if widget is not None:
            try:
                widget.destroy()
            except Exception:
                LOGGER.debug("Failed to destroy widget window", exc_info=True)

    def _show_widget(self) -> None:
        with self._lock:
            if self._widget_visible or self.widget is None or self._exiting:
                return
            widget = self.widget
            self._widget_visible = True
        x, y, width, height = calculate_widget_bounds(_cursor_work_area())
        try:
            widget.resize(width, height)
            widget.move(x, y)
            handle = self._widget_handle()
            if handle is None:
                widget.show()
            else:
                ctypes.windll.user32.ShowWindow(handle, 4)
        except Exception:
            with self._lock:
                self._widget_visible = False
            LOGGER.exception("Failed to show TokenLens widget")

    def _hide_widget(self) -> None:
        with self._lock:
            if not self._widget_visible or self.widget is None:
                return
            self._widget_visible = False
            widget = self.widget
        widget.hide()

    def _monitor_hover(self) -> None:
        while True:
            time.sleep(0.1)
            with self._lock:
                if self._exiting:
                    return
                should_hide = (
                    self._widget_visible
                    and not self._widget_pinned
                    and not self._widget_pointer_inside
                    and time.monotonic() - self._last_tray_hover > self.hover_grace
                )
            if should_hide:
                self._hide_widget()

    def _on_widget_closing(self) -> bool:
        with self._lock:
            if self._exiting:
                return True
        self._hide_widget()
        return False
