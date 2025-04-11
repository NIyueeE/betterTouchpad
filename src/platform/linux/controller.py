# touchpad-control/platform/linux/controller.py
import logging
from Xlib import display
from core.base_controller import TouchpadController

logger = logging.getLogger(__name__)

class LinuxTouchpadController(TouchpadController):
    def __init__(self):
        super().__init__()
        self._check_root()
        self.li = None
        self.fd = -1
        self.device_path = None
        self._init_libinput()
        self._find_touchpad()
        self.dummy_window = None
        self._init_xlib()

    def _init_xlib(self):
        self.dpy = display.Display()
        screen = self.dpy.screen()
        self.dummy_window = screen.root.create_window(
            0, 0, 1, 1, 0, X.CopyFromParent
        )

    # ...保持原有Linux实现的其他方法...