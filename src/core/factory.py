# touchpad-control/core/factory.py
import platform
import logging
from platform.windows.controller import WindowsTouchpadController
from platform.linux.controller import LinuxTouchpadController

logger = logging.getLogger(__name__)

def create_controller():
    system = platform.system()
    if system == "Windows":
        return WindowsTouchpadController()
    elif system == "Linux":
        return LinuxTouchpadController()
    else:
        logger.error(f"Unsupported platform: {system}")
        raise NotImplementedError(f"Unsupported platform: {system}")