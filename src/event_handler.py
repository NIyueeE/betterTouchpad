import time
import select
import threading
import keyboard
from pynput import mouse
from .controllers import create_controller
from .logger_config import configure_logger

logger = configure_logger()

class EventHandler:
    def __init__(self):
        self.controller = create_controller()
        self.should_exit = False
        self.space_pressed_time = 0
        self.long_press_timer = None
        self.long_press_triggered = False
        self.space_is_pressed = False
        self.lock = threading.Lock()

        self.left_click = None
        self.right_click = None

    def handle_long_press(self):
        with self.lock:
            if time.time() - self.space_pressed_time >= 0.5 and self.space_is_pressed:
                self.long_press_triggered = True
                self.controller.toggle(True)

                try:
                    if self.right_click:
                        keyboard.remove_hotkey(self.right_click)
                    if self.left_click:
                        keyboard.remove_hotkey(self.left_click)
                except KeyError:
                    pass

                self.left_click = keyboard.add_hotkey('space+c', self.controller.mouse.click, args=(mouse.Button.left,), suppress=True)
                self.right_click = keyboard.add_hotkey('space+v', self.controller.mouse.click, args=(mouse.Button.right,), suppress=True)
                logger.info("触控板启用，C/V绑定为鼠标左右键")

    def on_key_event(self, event):
        logger.debug(event.name)
        logger.debug(event.event_type)
        try:
            if event.name == 'space':
                if event.event_type == 'down':
                    with self.lock:
                        if self.space_is_pressed:
                            return
                        self.space_is_pressed = True
                        self.space_pressed_time = time.time()
                        if self.long_press_timer:
                            self.long_press_timer.cancel()
                        self.long_press_timer = threading.Timer(0.5, self.handle_long_press)
                        self.long_press_timer.start()

                elif event.event_type == 'up':
                    with self.lock:
                        if self.long_press_timer:
                            self.long_press_timer.cancel()
                            self.long_press_timer = None
                        if self.long_press_triggered:
                            self.controller.toggle(False)

                            try:
                                if self.right_click:
                                    keyboard.remove_hotkey(self.right_click)
                                if self.left_click:
                                    keyboard.remove_hotkey(self.left_click)
                            except KeyError:
                                pass

                            self.long_press_triggered = False
                            logger.info("触控板禁用，C/V解绑")
                    
                        self.space_pressed_time = 0 

        except Exception as e:
            logger.error("事件处理错误: %s", e)
            self.should_exit = True

    def run(self):
        try:
            keyboard.hook(self.on_key_event)
            logger.info("服务已启动，长按空格0.5秒启用触控板，C/V作为鼠标左右键。释放空格后禁用。")

            if platform.system() == "Linux":
                poller = select.poll()
                poller.register(self.controller.fd, select.POLLIN)
                while not self.should_exit:
                    poller.poll(100)
            else:
                while not self.should_exit:
                    time.sleep(0.1)

        except KeyboardInterrupt:
            logger.info("用户中断，退出...")
        finally:
            self.controller.cleanup()
            keyboard.unhook_all()
            logger.info("服务已停止")