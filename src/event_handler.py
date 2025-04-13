import platform
import time
import select
import threading
import json
import os
import keyboard
import pyautogui
from pynput import mouse
from .controllers import create_controller
from .logger_config import configure_logger

logger = configure_logger()

# 从src/configure.json读取配置
try:
    # 获取当前文件所在目录路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(current_dir, 'configure.json')
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
        
    # 读取配置参数
    RESPONSE_TIME = config["response_time"]  # 长按响应时间（秒）
    HOT_KEY = config["hot_key"]              # 触发键
    LEFT_CLICK = config["left_click"]        # 左键点击对应按键
    RIGHT_CLICK = config["right_click"]      # 右键点击对应按键
    MODE = config["mode"]                    # 0为长按模式, 1为切换模式
    
    logger.info(f"已从 {config_path} 加载配置")
    
except Exception as e:
    logger.error(f"读取配置文件失败: {e}，使用默认配置")
    # 默认配置参数
    RESPONSE_TIME = 0.2  # 长按响应时间（秒）
    HOT_KEY = '`'        # 触发键
    LEFT_CLICK = 'c'     # 左键点击对应按键
    RIGHT_CLICK = 'v'    # 右键点击对应按键
    MODE = 0             # 0为长按模式, 1为切换模式

class EventHandler:
    """
    触控板事件处理器
    处理热键事件并在长按时启用触控板模式，短按时传递原始按键
    """
    def __init__(self):
        self.controller = create_controller()
        self.should_exit = False
        self.lock = threading.Lock()
        
        # 热键状态跟踪
        self.hotkey_pressed_time = 0
        self.hotkey_is_pressed = False
        self.long_press_triggered = False
        self.is_simulating = False
        self.touchpad_active = False  # 新增：跟踪触控板是否激活
        
        # 定时器
        self.long_press_timer = None
        
        # 热键绑定
        self.left_click = None
        self.right_click = None
        self.press_hotkey = None

    def _cleanup_hotkeys(self):
        """清理热键绑定"""
        try:
            if self.right_click:
                keyboard.remove_hotkey(self.right_click)
            if self.left_click:
                keyboard.remove_hotkey(self.left_click)
        except KeyError:
            pass

    def handle_long_press(self):
        """处理长按事件 - 激活触控板模式"""
        with self.lock:
            if time.time() - self.hotkey_pressed_time >= RESPONSE_TIME and self.hotkey_is_pressed:
                self.long_press_triggered = True
                
                # 切换模式下，根据当前状态决定是否启用触控板
                if MODE == 1:
                    self.touchpad_active = not self.touchpad_active
                    self.controller.toggle(self.touchpad_active)
                else:
                    self.touchpad_active = True
                    self.controller.toggle(True)  # 启用触控板
                
                keyboard.release(HOT_KEY)  # 释放热键，防止粘滞
                
                # 清理现有热键并重新设置
                self._cleanup_hotkeys()
                
                if self.touchpad_active:
                    # 设置鼠标点击热键
                    if MODE == 1:
                        self.left_click = keyboard.add_hotkey(
                            LEFT_CLICK,
                            self.controller.mouse.click,
                            args=(mouse.Button.left,),
                            suppress=True
                        )
                        self.right_click = keyboard.add_hotkey(
                            RIGHT_CLICK,
                            self.controller.mouse.click,
                            args=(mouse.Button.right,),
                            suppress=True
                        )
                    elif MODE == 0:
                        self.left_click = keyboard.add_hotkey(
                            f"{HOT_KEY}+{LEFT_CLICK}",
                            self.controller.mouse.click,
                            args=(mouse.Button.left,),
                            suppress=True
                        )
                        self.right_click = keyboard.add_hotkey(
                            f"{HOT_KEY}+{RIGHT_CLICK}",
                            self.controller.mouse.click,
                            args=(mouse.Button.right,),
                            suppress=True
                        )
                    logger.info(f"触控板启用，{LEFT_CLICK},{RIGHT_CLICK}解绑")
                else:
                    logger.info(f"触控板禁用，{LEFT_CLICK},{RIGHT_CLICK}解绑")
                
    def on_key_event(self, event):
        """
        处理键盘事件
        根据热键的按下和释放事件控制触控板模式
        """
        logger.debug(f"Key event: {event.name} {event.event_type}")
        
        try:            
            # 仅处理热键相关事件
            if event.name == HOT_KEY:
                # 处理模拟按键期间的热键事件
                if self.is_simulating:
                    if event.event_type == 'down':
                        return False
                    if event.event_type == 'up':
                        self.is_simulating = False
                        # 重新注册热键拦截
                        self.press_hotkey = keyboard.add_hotkey(HOT_KEY, lambda: None, suppress=True)
                        return False
                
                # 处理热键按下事件
                if event.event_type == 'down':
                    with self.lock:
                        # 防止重复触发
                        if self.hotkey_is_pressed:
                            return False
                            
                        self.hotkey_is_pressed = True
                        self.hotkey_pressed_time = time.time()
                        
                        # 设置长按检测定时器
                        if self.long_press_timer:
                            self.long_press_timer.cancel()
                        self.long_press_timer = threading.Timer(
                            RESPONSE_TIME,
                            self.handle_long_press
                        )
                        self.long_press_timer.start()
                    
                    # 阻止热键传递到系统
                    return False

                # 处理热键释放事件
                elif event.event_type == 'up':
                    logger.info("热键释放")               
                    with self.lock:
                        self.hotkey_is_pressed = False
                        
                        # 取消长按定时器
                        if self.long_press_timer:
                            self.long_press_timer.cancel()
                            self.long_press_timer = None

                        if self.long_press_triggered:
                            # 根据模式决定热键释放后的行为
                            if MODE == 0:  # 长按模式：释放热键后关闭触控板
                                self.controller.toggle(False)
                                self._cleanup_hotkeys()
                                self.touchpad_active = False
                                logger.info(f"触控板禁用，{LEFT_CLICK},{RIGHT_CLICK}解绑")
                            # 切换模式下不需要在热键释放时关闭触控板
                            self.long_press_triggered = False
                        else:
                            # 短按：传递原始热键到系统
                            self.is_simulating = True
                            try:
                                if self.press_hotkey:
                                    keyboard.remove_hotkey(self.press_hotkey)
                            except KeyError:
                                pass
                            pyautogui.press(HOT_KEY)

                    # 长按模式下阻止事件传递
                    return False if self.long_press_triggered else None
                
            # 在触控板模式下阻止所有热键按下事件
            if event.name == HOT_KEY and event.event_type == 'down' and self.touchpad_active:
                return False

        except Exception as e:
            logger.error(f"事件处理错误: {e}")
            self.should_exit = True
            
        return None

    def run(self):
        """启动事件处理服务"""
        try:
            # 注册键盘钩子
            keyboard.hook(self.on_key_event)
            # 确保热键被拦截，不会传递到系统
            self.press_hotkey = keyboard.add_hotkey(HOT_KEY, lambda: None, suppress=True)
            logger.info(f"betterTouchpad服务已启动 [热键:{HOT_KEY}, 左键:{LEFT_CLICK}, 右键:{RIGHT_CLICK}, 模式:{MODE}]")
            
            # 主循环
            if platform.system() == "Linux":
                # Linux系统需要事件循环
                poller = select.poll()
                poller.register(self.controller.fd, select.POLLIN)
                while not self.should_exit:
                    poller.poll(100)
            else:
                # Windows/Mac系统
                while not self.should_exit:
                    time.sleep(0.1)

        except KeyboardInterrupt:
            logger.info("用户中断，退出...")
        finally:
            # 清理资源
            self.controller.cleanup()
            keyboard.unhook_all()
            logger.info("服务已停止")