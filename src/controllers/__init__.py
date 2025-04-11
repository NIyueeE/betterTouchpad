import platform
from .base import TouchpadController
from .windows import WindowsTouchpadController
from .linux import LinuxTouchpadController

def create_controller():
    system = platform.system()
    if system == "Windows":
        return WindowsTouchpadController()
    elif system == "Linux":
        return LinuxTouchpadController()
    else:
        raise NotImplementedError(f"Unsupported platform: {system}")

__all__ = ['TouchpadController', 'create_controller']