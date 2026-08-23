from desktop_app import DesktopController, WorkArea, calculate_widget_bounds
from windows_tray import WM_MOUSEMOVE, tray_event_code


def test_widget_anchors_to_bottom_right():
    bounds = calculate_widget_bounds(WorkArea(0, 0, 1920, 1040))

    assert bounds == (1428, 428, 480, 600)


def test_widget_fits_small_work_area():
    x, y, width, height = calculate_widget_bounds(WorkArea(100, 50, 700, 550))

    assert (x, y) == (208, 62)
    assert (width, height) == (480, 476)


def test_tray_event_code_accepts_version_four_lparam():
    assert tray_event_code((42 << 16) | WM_MOUSEMOVE) == WM_MOUSEMOVE


class FakeWindow:
    def __init__(self):
        self.urls = []
        self.shown = 0
        self.hidden = 0
        self.restored = 0

    def load_url(self, url):
        self.urls.append(url)

    def show(self):
        self.shown += 1

    def hide(self):
        self.hidden += 1

    def restore(self):
        self.restored += 1


class FakeQueue:
    def __init__(self):
        self.items = []

    def put(self, value):
        self.items.append(value)


class FakeProcess:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.alive = False

    def start(self):
        self.alive = True

    def is_alive(self):
        return self.alive


class FakeProcessContext:
    def __init__(self):
        self.queue = FakeQueue()
        self.process = None

    def Queue(self):
        return self.queue

    def Process(self, **kwargs):
        self.process = FakeProcess(**kwargs)
        return self.process


def ready_controller(context=None):
    controller = DesktopController(
        "http://127.0.0.1:7788", process_context=context or FakeProcessContext()
    )
    controller.widget = FakeWindow()
    controller._ready = True
    controller._webview = object()
    return controller


def test_tray_hover_does_not_show_widget():
    controller = ready_controller()
    shown = []
    controller._show_widget = lambda: shown.append(True)

    controller.on_tray_hover()

    assert shown == []
    assert controller._last_tray_hover > 0


def test_tray_click_shows_ready_widget():
    controller = ready_controller()
    shown = []
    controller._show_widget = lambda: shown.append(True)

    controller.on_tray_click()

    assert shown == [True]


def test_widget_close_hides_without_exiting():
    controller = ready_controller()
    controller._widget_visible = True

    controller.hide_widget()

    assert controller.widget.hidden == 1
    assert controller._widget_visible is False
    assert controller._exiting is False


def test_tray_click_is_remembered_until_widget_loads():
    controller = DesktopController(
        "http://127.0.0.1:7788", process_context=FakeProcessContext()
    )
    controller.widget = FakeWindow()
    shown = []
    controller._make_widget_non_activating = lambda: None
    controller._show_widget = lambda: shown.append(True)

    controller.on_tray_click()

    assert controller._widget_show_requested is True

    controller._on_widget_loaded()

    assert controller._widget_show_requested is False
    assert controller.widget.hidden == 1
    assert shown == [True]


def test_open_dashboard_starts_then_reuses_native_process():
    context = FakeProcessContext()
    controller = ready_controller(context)
    controller._widget_visible = True

    controller.open_dashboard("/dashboard")

    assert context.process.alive is True
    assert context.process.kwargs["args"][1] == "/dashboard"
    assert controller.widget.hidden == 1
    assert controller._widget_visible is False

    controller.open_dashboard("/models")

    assert context.queue.items == ["/models"]


def test_open_dashboard_rejects_non_local_path():
    context = FakeProcessContext()
    controller = ready_controller(context)

    controller.open_dashboard("https://example.com")

    assert context.process.kwargs["args"][1] == "/dashboard"


def test_dashboard_click_is_queued_until_widget_loads():
    controller = DesktopController(
        "http://127.0.0.1:7788", process_context=FakeProcessContext()
    )
    controller.widget = FakeWindow()

    controller.open_dashboard("/settings")

    assert controller._dashboard_process is None
    assert controller._pending_dashboard_path == "/settings"
