import time
import threading
import queue
import keyboard
import pyautogui
from pynput import mouse
from controllers import create_controller
from configure_logger import configure_logger
from system_tray import SystemTrayController
from setting import SettingsManager
from cursor_indicator import CursorIndicator

# 初始化日志记录器
logger = configure_logger()

# ============================== 配置加载 ==============================
def load_config():
    """
    从配置文件加载设置，如果加载失败则使用默认值
    
    返回:
        tuple: (响应时间, 热键, 左键点击按键, 右键点击按键, 模式)
    """
    settings_manager = SettingsManager(queue.Queue())
    config = settings_manager.get_config()
    
    return (
        config["response_time"],
        config["hot_key"],
        config["left_click"],
        config["right_click"],
        config["mode"]
    )

# 初始化全局配置变量
RESPONSE_TIME, HOT_KEY, LEFT_CLICK, RIGHT_CLICK, MODE = load_config()

class TouchpadController:
    """
    触控板事件处理器
    
    负责检测热键事件并根据不同模式（长按/切换）处理触控板状态，
    管理鼠标点击模拟，并通过命令队列与其他组件通信。
    """
    def __init__(self):
        """初始化触控板事件处理器及其所有组件"""
        # 创建控制器和通信组件
        self.controller = create_controller()
        self.should_exit = False
        self.lock = threading.Lock()  # 线程锁，确保线程安全
        
        # ----- 状态跟踪变量 -----
        # 热键状态
        self.hotkey_pressed_time = 0    # 热键按下的时间戳
        self.hotkey_is_pressed = False  # 热键是否处于按下状态
        self.long_press_triggered = False  # 是否已触发长按事件
        self.is_simulating = False      # 是否正在模拟按键
        
        # 触控板和鼠标状态
        self.touchpad_active = False    # 触控板是否激活
        self.left_click_pressed = False  # 左键是否按下
        self.right_click_pressed = False  # 右键是否按下
        
        # 定时器和钩子
        self.long_press_timer = None  # 长按检测定时器
        self.press_hotkey = None  # 热键绑定句柄
        self.hotkey_down = None  # 热键按下钩子
        
        # 跨线程通信
        self.command_queue = queue.Queue()
        
        # 创建管理器组件
        self.tray_manager = SystemTrayController(self.controller, self.command_queue)
        self.config_manager = SettingsManager(self.command_queue)
        self.settings_window_open = False  # 设置窗口状态
        
        # 创建鼠标指示器
        self.cursor_indicator = CursorIndicator(self.command_queue)
    
    # ============================== 鼠标点击处理 ==============================
    def on_left_click(self, event):
        """
        处理左键点击事件
        
        参数:
            event: 键盘事件对象
        """
        if event.name == LEFT_CLICK:
            if event.event_type == 'down' and not self.left_click_pressed:
                self.controller.mouse.press(mouse.Button.left)
                self.left_click_pressed = True
            elif event.event_type == 'up':
                self.controller.mouse.release(mouse.Button.left)
                self.left_click_pressed = False

    def on_right_click(self, event):
        """
        处理右键点击事件
        
        参数:
            event: 键盘事件对象
        """
        if event.name == RIGHT_CLICK:
            if event.event_type == 'down' and not self.right_click_pressed:
                self.controller.mouse.press(mouse.Button.right)
                self.right_click_pressed = True
            elif event.event_type == 'up':
                self.controller.mouse.release(mouse.Button.right)
                self.right_click_pressed = False

    # ============================== 触控板模式控制 ==============================
    def handle_long_press(self):
        """处理热键长按事件 - 根据模式激活或切换触控板状态"""
        with self.lock:
            # 避免热键重复触发
            self.hotkey_down = keyboard.on_press_key(HOT_KEY, lambda e: None, suppress=True)
            
            # 判断是否满足长按条件
            if time.time() - self.hotkey_pressed_time >= RESPONSE_TIME and self.hotkey_is_pressed:
                self.long_press_triggered = True
                
                # 根据不同模式处理触控板状态
                if MODE == 1:  # 切换模式
                    self.touchpad_active = not self.touchpad_active
                    self.controller.toggle(self.touchpad_active)
                    
                    # 根据状态显示不同的鼠标指示器
                    if self.touchpad_active:
                        # 触控板激活后一直显示
                        self.cursor_indicator.start("on")
                    else:
                        # 触控板关闭时显示off图标，然后自动隐藏
                        self.cursor_indicator.start("off", 1.1)
                else:  # 长按模式
                    self.touchpad_active = True
                    self.controller.toggle(True)  # 启用触控板
                    
                    # 显示on图标
                    self.cursor_indicator.start("on")
                
                # 更新系统托盘图标
                self.tray_manager.update_touchpad_status(self.touchpad_active)
                
                keyboard.release(HOT_KEY)  # 释放热键，防止粘滞
                
                # 根据触控板状态设置按键绑定
                if self.touchpad_active:
                    # 绑定鼠标点击热键
                    keyboard.hook_key(LEFT_CLICK, self.on_left_click, suppress=True)
                    keyboard.hook_key(RIGHT_CLICK, self.on_right_click, suppress=True)
                    logger.info(f"触控板启用，{LEFT_CLICK},{RIGHT_CLICK}绑定")
                else:
                    logger.info(f"触控板禁用，{LEFT_CLICK},{RIGHT_CLICK}解绑")

    def on_key_event(self, event):
        """
        处理键盘事件，根据热键的按下和释放事件控制触控板模式
        
        参数:
            event: 键盘事件对象
            
        返回:
            False: 阻止事件传递到系统
            None: 允许事件传递到系统
        """
        logger.debug(f"按键事件: {event.name} {event.event_type}")
        
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
                            # 长按模式：释放热键后关闭触控板
                            if MODE == 0:
                                self.controller.toggle(False)
                                # 解绑键盘钩子
                                try:
                                    keyboard.unhook(self.on_left_click)
                                    keyboard.unhook(self.on_right_click)
                                except Exception as e:
                                    logger.error(f"解绑按键失败: {e}或者按键未绑定")
                                self.touchpad_active = False
                                
                                # 显示off图标，然后自动隐藏
                                self.cursor_indicator.start("off", 1.1)
                                
                                # 更新系统托盘图标
                                self.tray_manager.update_touchpad_status(self.touchpad_active)
                                logger.info(f"触控板禁用，{LEFT_CLICK},{RIGHT_CLICK}解绑")
                                
                            # 无论哪种模式，都需要清理状态
                            self.long_press_triggered = False
                            keyboard.unhook(self.hotkey_down)
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

    # ============================== 主程序运行 ==============================
    def run(self):
        """启动事件处理服务，包括键盘钩子和系统托盘"""
        try:
            # 注册键盘钩子
            keyboard.hook(self.on_key_event)
            # 确保热键被拦截，不会传递到系统
            self.press_hotkey = keyboard.add_hotkey(HOT_KEY, lambda: None, suppress=True)
            logger.info(f"betterTouchpad服务已启动 [热键:{HOT_KEY}, 左键:{LEFT_CLICK}, 右键:{RIGHT_CLICK}, 模式:{MODE}]")
            
            # 启动系统托盘图标
            self.tray_manager.start()
            logger.info("系统托盘图标已启动")
            
            # 显示首次启动提示图标并自动隐藏
            self.cursor_indicator.start("default", 0.7)
            
            # 主循环 - 处理队列中的命令
            while not self.should_exit:
                time.sleep(0.1)
                self._process_command_queue()

        except KeyboardInterrupt:
            logger.info("用户中断，退出...")
        except Exception as e:
            logger.error(f"运行时错误: {e}")
        finally:
            # 清理所有资源
            self._cleanup_resources()
            logger.info("服务已停止")
    
    def _cleanup_resources(self):
        """清理所有资源，包括控制器、键盘钩子和系统托盘"""
        # 清理控制器
        try:
            self.controller.cleanup()
        except Exception as e:
            logger.error(f"清理控制器失败: {e}")
            
        # 清理键盘钩子
        try:
            keyboard.unhook_all()
        except Exception as e:
            logger.error(f"卸载钩子失败: {e}")
        
        # 停止系统托盘图标
        self.tray_manager.stop()
        
        # 停止鼠标指示器
        try:
            self.cursor_indicator.stop()
        except Exception as e:
            logger.error(f"停止鼠标指示器失败: {e}")

    def _process_command_queue(self):
        """处理命令队列中的命令，响应用户操作和状态变更"""
        try:
            # 非阻塞方式获取命令
            command, args = self.command_queue.get_nowait()
            global RESPONSE_TIME, HOT_KEY, LEFT_CLICK, RIGHT_CLICK, MODE
            
            # 处理各种命令
            if command == 'open_settings':
                # 在主线程中打开设置窗口
                if not self.settings_window_open:
                    logger.info("准备创建设置窗口")
                    self.settings_window_open = True
                    if self.config_manager.create_settings_window():
                        logger.info("已创建设置窗口")
                    else:
                        self.settings_window_open = False
                        logger.warning("创建设置窗口失败")
                else:
                    logger.info("设置窗口已经打开，请关闭当前窗口后再试")
            
            elif command == 'settings_window_closed':
                # 设置窗口关闭，无论是否更新配置，确保标志被重置
                self.settings_window_open = False
                logger.info("设置窗口关闭事件已处理")
                
            elif command == 'settings_window_already_open':
                # ConfigManager 认为窗口已经打开，需要同步状态
                logger.warning("设置窗口已经在其他地方打开")
                self.settings_window_open = True
                
            elif command == 'settings_window_failed':
                # 窗口创建失败，确保状态重置
                self.settings_window_open = False
                logger.warning("设置窗口创建失败")
            
            elif command == 'toggle_mode':
                # 切换模式
                MODE = 1 if MODE == 0 else 0
                # 更新配置文件
                if self.config_manager.update_config("mode", MODE):
                    logger.info(f"模式已切换为: {'切换模式' if MODE == 1 else '长按模式'}")
                # 如果切换到长按模式且触控板处于激活状态，则关闭触控板
                if MODE == 0 and self.touchpad_active:
                    self.touchpad_active = False
                    self.controller.toggle(False)
                    # 显示触控板关闭提示
                    self.cursor_indicator.stop()
                    self.cursor_indicator.start("off", 2.0)
                    # 更新图标状态
                    self.tray_manager.update_touchpad_status(self.touchpad_active)
                
            elif command == 'reload_config':
                # 重新加载配置
                success, config = self.config_manager.reload_config()
                if success:
                    # 更新全局变量
                    RESPONSE_TIME = config["response_time"]
                    HOT_KEY = config["hot_key"]
                    LEFT_CLICK = config["left_click"]
                    RIGHT_CLICK = config["right_click"]
                    # MODE已在reload_config中更新
                    
                    # 处理热键绑定
                    self._update_key_bindings()
                    logger.info("配置已重新加载并应用")
                else:
                    logger.error("重新加载配置失败")
            
            elif command == 'config_updated':
                # 配置已更新，需要应用
                if args:
                    # 更新全局变量
                    RESPONSE_TIME = args["response_time"]
                    HOT_KEY = args["hot_key"]
                    LEFT_CLICK = args["left_click"]
                    RIGHT_CLICK = args["right_click"]
                    old_mode = MODE
                    MODE = args["mode"]
                    
                    # 更新热键绑定
                    self._update_key_bindings()
                    
                    # 处理模式变更
                    if old_mode != MODE and self.touchpad_active:
                        if MODE == 0:  # 切换到长按模式
                            self.controller.toggle(False)
                            self.touchpad_active = False
                            
                            # 显示触控板关闭提示
                            self.cursor_indicator.stop()
                            self.cursor_indicator.start("off", 2.0)
                            
                            self.tray_manager.update_touchpad_status(self.touchpad_active)
                            logger.info("模式切换为长按模式，触控板已禁用")
                    
                    logger.info("配置已更新并应用")
                    
                # 重置设置窗口状态
                self.settings_window_open = False
            
            elif command == 'exit':
                # 退出应用
                logger.info("收到退出命令")
                self.should_exit = True
            
            # 处理完成后标记任务完成
            self.command_queue.task_done()
            
        except queue.Empty:
            # 队列为空，不做任何处理
            pass
        except Exception as e:
            logger.error(f"处理命令队列出错: {e}")
    
    def _update_key_bindings(self):
        """更新热键绑定，适应配置变更"""
        try:
            # 解绑当前绑定的按键
            try:
                keyboard.unhook(self.on_left_click)
                keyboard.unhook(self.on_right_click)
            except Exception as e:
                logger.error(f"解绑按键失败: {e}或者按键未绑定")

            # 清理现有热键
            try:
                if self.press_hotkey:
                    keyboard.remove_hotkey(self.press_hotkey)
                    self.press_hotkey = None
            except Exception as e:
                logger.error(f"清理热键失败: {e}")
            
            # 如果触控板处于激活状态，重新设置热键绑定
            if self.touchpad_active:
                keyboard.hook_key(LEFT_CLICK, self.on_left_click, suppress=True)
                keyboard.hook_key(RIGHT_CLICK, self.on_right_click, suppress=True)
                logger.info(f"触控板热键已更新: {LEFT_CLICK}, {RIGHT_CLICK}")
            
            # 重新注册主热键
            self.press_hotkey = keyboard.add_hotkey(HOT_KEY, lambda: None, suppress=True)
            return True
        except Exception as e:
            logger.error(f"更新热键绑定失败: {e}")
            return False