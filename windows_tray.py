"""Windows tray icon extensions used by the TokenLens desktop shell."""

from __future__ import annotations

from collections.abc import Callable

import pystray


WM_MOUSEMOVE = 0x0200


def tray_event_code(lparam: int) -> int:
    """Return the mouse event from legacy and NOTIFYICON_VERSION_4 messages."""
    return int(lparam) & 0xFFFF


class HoverTrayIcon(pystray.Icon):
    """A pystray icon that also reports pointer movement over the icon.

    pystray handles clicks and menus on Windows but does not expose the
    ``WM_MOUSEMOVE`` notification. Keeping the small adapter here avoids
    coupling the desktop window controller to pystray's private Win32 class.
    """

    def __init__(self, *args, on_hover: Callable[[], None] | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._on_hover_callback = on_hover

    def _on_notify(self, wparam, lparam) -> None:
        event = tray_event_code(lparam)
        if event == WM_MOUSEMOVE and self._on_hover_callback is not None:
            self._on_hover_callback()
            return
        super()._on_notify(wparam, event)
