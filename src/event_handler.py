import platform
import time
import select
import threading
import keyboard
from pynput import mouse
from .controllers import create_controller
from .logger_config import configure_logger

logger = configure_logger()
Response_time = 0.1
Hot_key = 'space'
Left_click = 'c'
Right_click = 'v'

class EventHandler:
    def __init__(self):
        self.controller = create_controller()
        self.should_exit = False
        self.hotkey_pressed_time = 0
        self.long_press_timer = None
        self.long_press_triggered = False
        self.hotkey_is_pressed = False
        self.lock = threading.Lock()

        self.left_click = None
        self.right_click = None

    def handle_long_press(self):
        with self.lock:
            if time.time() - self.hotkey_pressed_time >= Response_time and self.hotkey_is_pressed:
                self.long_press_triggered = True
                self.controller.toggle(True)
                
                keyboard.release(Hot_key)
                
                try:
                    if self.right_click:
                        keyboard.remove_hotkey(self.right_click)
                    if self.left_click:
                        keyboard.remove_hotkey(self.left_click)
                except KeyError:
                    pass
                
                self.left_click = keyboard.add_hotkey(
                    Hot_key+'+'+Left_click,
                    self.controller.mouse.click,
                    args=(mouse.Button.left,),
                    suppress=True
                )
                self.right_click = keyboard.add_hotkey(
                    Hot_key+'+'+Right_click,
                    self.controller.mouse.click,
                    args=(mouse.Button.right,),
                    suppress=True
                )
                logger.info("触控板启用，"+Left_click+","+Right_click+"解绑")

    def on_key_event(self, event):
        logger.debug(f"Key event: {event.name} {event.event_type}")
        try:
            if event.name == Hot_key:
                if event.event_type == 'down':
                    with self.lock:
                        if self.hotkey_is_pressed:
                            return False  # 阻止重复事件
                        self.hotkey_is_pressed = True
                        self.hotkey_pressed_time = time.time()
                        if self.long_press_timer:
                            self.long_press_timer.cancel()
                        self.long_press_timer = threading.Timer(
                            Response_time,
                            self.handle_long_press
                        )
                        self.long_press_timer.start()
                    
                    # 长按触发后阻止所有空格按下事件
                    if self.long_press_triggered:
                        return False

                elif event.event_type == 'up':
                    with self.lock:
                        self.hotkey_is_pressed = False
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
                            logger.info("触控板禁用，"+Left_click+","+Right_click+"解绑")
                    
                    return False if self.long_press_triggered else None

            if event.name == Hot_key and event.event_type == 'down' and self.long_press_triggered:
                return False

        except Exception as e:
            logger.error(f"事件处理错误: {e}")
            self.should_exit = True
        return None

    def run(self):
        try:
            keyboard.hook(self.on_key_event)
            logger.info("betterTouchpad服务已启动")

            # Linux系统需要事件循环
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