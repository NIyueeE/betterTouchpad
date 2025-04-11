# touchpad-control/core/event_handler.py
import time
import threading
import logging
import keyboard
from pynput import mouse

logger = logging.getLogger(__name__)

class EventHandler:
    def __init__(self, controller):
        self.controller = controller
        self.should_exit = False
        self.space_pressed_time = 0
        self.long_press_timer = None
        self.long_press_triggered = False
        self.space_is_pressed = False
        self.lock = threading.Lock()
        self.left_click = None
        self.right_click = None

    def handle_long_press(self):
        # ...保持原有事件处理逻辑...
    
    def on_key_event(self, event):
        # ...保持原有键盘事件处理逻辑...
    
    def run(self):
        try:
            keyboard.hook(self.on_key_event)
            logger.info("服务已启动，长按空格0.5秒启用触控板...")

            if platform.system() == "Linux":
                # ...保持原有Linux事件循环...
            else:
                while not self.should_exit:
                    time.sleep(0.1)
        finally:
            self.controller.cleanup()
            keyboard.unhook_all()