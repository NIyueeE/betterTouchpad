# touchpad-control/core/base_controller.py
import logging
from pynput import mouse

logger = logging.getLogger(__name__)

class TouchpadController:
    def __init__(self):
        self.mouse = mouse.Controller()
    
    def toggle(self, enable):
        raise NotImplementedError
    
    def cleanup(self):
        pass

    def create_dummy_window(self):
        raise NotImplementedError