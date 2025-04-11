import os
import ctypes
import logging
from .base import TouchpadController

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

    def _init_libinput(self):
        self.libinput = ctypes.CDLL("libinput.so.10")
        self.libinput.libinput_path_create_context.restype = ctypes.POINTER(ctypes.c_void_p)
        self.libinput.libinput_path_add_device.argtypes = [ctypes.POINTER(ctypes.c_void_p), c_char_p]
        self.libinput.libinput_device_has_capability.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self.libinput.libinput_device_has_capability.restype = ctypes.c_int
        self.libinput.libinput_get_fd.argtypes = [ctypes.POINTER(ctypes.c_void_p)]
        self.libinput.libinput_get_fd.restype = ctypes.c_int
        
        self.li = self.libinput.libinput_path_create_context(None)
        if not self.li:
            raise RuntimeError("无法创建libinput上下文")

    def _check_root(self):
        if os.geteuid() != 0:
            logger.error("需要root权限运行，请使用sudo执行")
            raise SystemExit

    def _find_touchpad(self):
        for device in os.listdir("/dev/input"):
            if device.startswith("event"):
                path = os.path.join("/dev/input", device)
                dev = self.libinput.libinput_path_add_device(self.li, path.encode())
                if self.libinput.libinput_device_has_capability(dev, 1):
                    self.device_path = path
                    self.fd = self.libinput.libinput_get_fd(self.li)
                    logger.info("找到触控板设备: %s", path)
                    return
        raise RuntimeError("未找到触控板设备")

    def toggle(self, enable):
        sys_path = f"/sys/class/input/{os.path.basename(self.device_path)}/device/authorized"
        try:
            with open(sys_path, "w") as f:
                f.write("1" if enable else "0")
            time.sleep(0.2)
        except IOError as e:
            logger.error("设备状态切换失败: %s", e)

    def cleanup(self):
        pass