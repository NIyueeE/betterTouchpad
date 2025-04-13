import platform

from .base import TouchpadController
from .windows import WindowsTouchpadController
from .linux import LinuxTouchpadController

def create_controller():
    """
    创建触控板控制器
    根据当前操作系统创建并返回对应的控制器实例
    """
    system = platform.system()
    if system == "Windows":
        return WindowsTouchpadController()
    elif system == "Linux":
        return LinuxTouchpadController()
    else:
        raise NotImplementedError(f"不支持的平台: {system}")

__all__ = ['TouchpadController', 'create_controller']