import os
import time
import ctypes
import logging

from .base import TouchpadController

logger = logging.getLogger(__name__)

class LinuxTouchpadController(TouchpadController):
    """
    Linux系统触控板控制器
    使用libinput库控制触控板设备
    """
    def __init__(self):
        """初始化Linux触控板控制器"""
        super().__init__()
        self._check_root()
        self.li = None
        self.fd = -1
        self.device_path = None
        self._init_libinput()
        self._find_touchpad()
        self.dummy_window = None

    def _init_libinput(self):
        """初始化libinput库"""
        self.libinput = ctypes.CDLL("libinput.so.10")
        self.libinput.libinput_path_create_context.restype = ctypes.POINTER(ctypes.c_void_p)
        self.libinput.libinput_path_add_device.argtypes = [ctypes.POINTER(ctypes.c_void_p), ctypes.c_char_p]
        self.libinput.libinput_device_has_capability.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self.libinput.libinput_device_has_capability.restype = ctypes.c_int
        self.libinput.libinput_get_fd.argtypes = [ctypes.POINTER(ctypes.c_void_p)]
        self.libinput.libinput_get_fd.restype = ctypes.c_int
        
        self.li = self.libinput.libinput_path_create_context(None)
        if not self.li:
            raise RuntimeError("无法创建libinput上下文")

    def _check_root(self):
        """检查是否具有root权限"""
        if os.geteuid() != 0:
            logger.error("需要root权限运行，请使用sudo执行")
            raise SystemExit

    def _find_touchpad(self):
        """查找系统中的触控板设备"""
        for device in os.listdir("/dev/input"):
            if device.startswith("event"):
                path = os.path.join("/dev/input", device)
                dev = self.libinput.libinput_path_add_device(self.li, path.encode())
                if self.libinput.libinput_device_has_capability(dev, 1):
                    self.device_path = path
                    self.fd = self.libinput.libinput_get_fd(self.li)
                    logger.info(f"找到触控板设备: {path}")
                    return
        raise RuntimeError("未找到触控板设备")

    def toggle(self, enable):
        """
        切换触控板状态
        
        参数:
            enable: 布尔值，True启用触控板，False禁用触控板
        """
        sys_path = f"/sys/class/input/{os.path.basename(self.device_path)}/device/authorized"
        try:
            with open(sys_path, "w") as f:
                f.write("1" if enable else "0")
            time.sleep(0.2)
        except IOError as e:
            logger.error(f"设备状态切换失败: {e}")

    def cleanup(self):
        """释放资源"""
        pass