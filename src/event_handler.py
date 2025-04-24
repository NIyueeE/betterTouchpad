import time
import threading
import json
import os
import queue
import keyboard
import pyautogui
from pynput import mouse
import pystray
from PIL import Image, ImageDraw
import tkinter as tk
from tkinter import ttk, messagebox
from .controllers import create_controller
from .logger_config import configure_logger

# 初始化日志
logger = configure_logger()

# ============================== 配置加载 ==============================
def load_config():
    """
    从配置文件加载设置，如果加载失败则使用默认值
    
    Returns:
        tuple: (响应时间, 热键, 左键点击按键, 右键点击按键, 模式)
    """
    try:
        # 获取当前文件所在目录路径
        current_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(current_dir, 'configure.json')
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            
        # 读取配置参数
        response_time = config.get("response_time", 0.2)  # 长按响应时间（秒）
        hot_key = config.get("hot_key", "f1")             # 触发键
        left_click = config.get("left_click", "f2")       # 左键点击对应按键
        right_click = config.get("right_click", "f3")     # 右键点击对应按键
        mode = config.get("mode", 0)                      # 0为长按模式, 1为切换模式
        
        logger.info(f"已从 {config_path} 加载配置")
        
    except Exception as e:
        logger.error(f"读取配置文件失败: {e}，使用默认配置")
        # 默认配置参数
        response_time = 0.2
        hot_key = 'f1'
        left_click = 'f2'
        right_click = 'f3'
        mode = 0
        
    return response_time, hot_key, left_click, right_click, mode

# 初始化全局配置变量
RESPONSE_TIME, HOT_KEY, LEFT_CLICK, RIGHT_CLICK, MODE = load_config()

class EventHandler:
    """
    触控板事件处理器
    负责检测热键事件并根据不同模式（长按/切换）处理触控板状态，
    同时提供系统托盘和设置界面支持
    """
    def __init__(self):
        """初始化触控板事件处理器"""
        # 创建控制器
        self.controller = create_controller()
        self.should_exit = False
        self.lock = threading.Lock()  # 线程锁，确保线程安全
        
        # --------- 状态跟踪 ---------
        # 热键状态追踪
        self.hotkey_pressed_time = 0    # 热键按下的时间戳
        self.hotkey_is_pressed = False  # 热键是否处于按下状态
        self.long_press_triggered = False  # 是否已触发长按事件
        self.is_simulating = False      # 是否正在模拟按键
        self.touchpad_active = False    # 触控板是否激活
        
        # 鼠标点击状态跟踪
        self.left_click_pressed = False
        self.right_click_pressed = False
        
        # 定时器
        self.long_press_timer = None
        
        # 热键绑定句柄
        self.press_hotkey = None
        self.hotkey_down = None
        
        # 系统托盘相关
        self.tray_icon = None
        self.tray_thread = None
        
        # 跨线程通信队列
        self.command_queue = queue.Queue()
        
        # UI状态
        self.settings_window_open = False
    
    # ============================== 鼠标点击处理 ==============================
    def on_left_click(self, event):
        """
        处理左键点击事件
        
        Args:
            event: 键盘事件对象
        """
        if event.name == LEFT_CLICK:
            if event.event_type == 'down' and not self.left_click_pressed:
                # 按下左键并更新状态
                self.controller.mouse.press(mouse.Button.left)
                self.left_click_pressed = True
            elif event.event_type == 'up':
                # 释放左键并重置状态
                self.controller.mouse.release(mouse.Button.left)
                self.left_click_pressed = False

    def on_right_click(self, event):
        """
        处理右键点击事件
        
        Args:
            event: 键盘事件对象
        """
        if event.name == RIGHT_CLICK:
            if event.event_type == 'down' and not self.right_click_pressed:
                # 按下右键并更新状态
                self.controller.mouse.press(mouse.Button.right)
                self.right_click_pressed = True
            elif event.event_type == 'up':
                # 释放右键并重置状态
                self.controller.mouse.release(mouse.Button.right)
                self.right_click_pressed = False

    # ============================== 触控板模式控制 ==============================
    def handle_long_press(self):
        """处理长按事件 - 激活触控板模式"""
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
                else:  # 长按模式
                    self.touchpad_active = True
                    self.controller.toggle(True)  # 启用触控板
                
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
        
        Args:
            event: 键盘事件对象
            
        Returns:
            False: 阻止事件传递到系统
            None: 允许事件传递到系统
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
            
            # 启动系统托盘图标（在新线程中）
            self.tray_thread = threading.Thread(target=self._start_tray_icon, daemon=True)
            self.tray_thread.start()
            logger.info("系统托盘图标已启动")
            
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
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception as e:
                logger.error(f"停止系统托盘图标失败: {e}")

    def _start_tray_icon(self):
        """在独立线程中启动系统托盘图标"""
        self.tray_icon = self._create_tray_icon()
        self.tray_icon.run()

    def _create_tray_icon(self):
        """
        创建系统托盘图标
        
        Returns:
            pystray.Icon: 创建的系统托盘图标对象
        """
        # 创建图标路径
        current_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(current_dir, './source/icon.png')
        
        # 确保图标目录存在
        icon_dir = os.path.dirname(icon_path)
        if not os.path.exists(icon_dir):
            try:
                os.makedirs(icon_dir, exist_ok=True)
                logger.info(f"创建图标目录: {icon_dir}")
            except Exception as e:
                logger.error(f"创建图标目录失败: {e}")
                # 如果无法创建目录，回退到当前目录
                icon_path = os.path.join(current_dir, 'icon.png')
        
        # 检查图标是否存在，不存在则创建一个默认图标
        image = None
        if not os.path.exists(icon_path):
            # 创建一个蓝色圆形图标，表示触控板
            image = self._create_default_icon()
            try:
                image.save(icon_path)
                logger.info(f"创建默认图标: {icon_path}")
            except Exception as e:
                logger.error(f"保存图标失败: {e}")
        
        # 创建图标菜单
        menu = (
            pystray.MenuItem('切换模式', self._toggle_mode),
            pystray.MenuItem('设置', self._open_settings),
            pystray.MenuItem('刷新配置', self._reload_config),
            pystray.MenuItem('退出', self._exit_app),
        )
        
        # 创建系统托盘图标，处理图标文件不存在的情况
        try:
            icon_image = Image.open(icon_path) if os.path.exists(icon_path) else image or self._create_default_icon()
            icon = pystray.Icon(
                'betterTouchpad',
                icon_image,
                'Better Touchpad',
                menu
            )
            return icon
        except Exception as e:
            logger.error(f"创建系统托盘图标失败: {e}")
            # 创建一个备用图标（纯色图标）
            backup_image = Image.new('RGB', (64, 64), color=(0, 120, 212))
            icon = pystray.Icon(
                'betterTouchpad',
                backup_image,
                'Better Touchpad',
                menu
            )
            return icon
    
    def _create_default_icon(self):
        """创建默认图标"""
        # 创建一个蓝色圆形图标，表示触控板
        image = Image.new('RGBA', (64, 64), color=(0, 0, 0, 0))
        
        # 画一个圆
        draw = ImageDraw.Draw(image)
        draw.ellipse([(4, 4), (60, 60)], fill=(0, 120, 212), outline=(255, 255, 255, 128), width=2)
        
        # 在中间画一个小的触控点
        draw.ellipse([(28, 28), (36, 36)], fill=(255, 255, 255))
        
        return image
    
    def _toggle_mode(self, icon, item):
        """切换模式"""
        global MODE
        MODE = 1 if MODE == 0 else 0
        # 更新配置文件
        self._update_config("mode", MODE)
        logger.info(f"模式已切换为: {'切换模式' if MODE == 1 else '长按模式'}")
    
    def _open_settings(self, icon, item):
        """打开设置窗口"""
        logger.info("打开设置窗口请求")
        # 防止重复打开设置窗口
        if self.settings_window_open:
            logger.info("设置窗口已经打开，忽略请求")
            return
            
        # 确保标志正确设置，即使在出现异常的情况下
        try:
            # 将打开设置窗口的命令放入队列，由主线程处理
            self.command_queue.put(('open_settings', None))
            self.settings_window_open = True
        except Exception as e:
            logger.error(f"打开设置窗口失败: {e}")
            self.settings_window_open = False  # 重置标志确保用户可以再次尝试
    
    def _create_settings_window(self, parent=None):
        """
        创建设置窗口
        
        Args:
            parent: 父窗口对象，如果为None则创建独立窗口
        """
        try:
            # 创建窗口对象
            settings_window = tk.Tk() if parent is None else tk.Toplevel(parent)
            
            # 设置窗口基本属性
            settings_window.title("Better Touchpad")
            settings_window.geometry("450x420")
            settings_window.resizable(False, False)
            
            # 设置窗口关闭事件处理
            def on_window_close():
                self.settings_window_open = False
                settings_window.destroy()
                if parent:
                    parent.destroy()
            
            settings_window.protocol("WM_DELETE_WINDOW", on_window_close)
            
            # 加载当前配置
            config_data = self._load_settings_config()
            
            # 创建主框架
            main_frame = ttk.Frame(settings_window, padding=25)
            main_frame.pack(fill=tk.BOTH, expand=True)
            
            # 添加标题
            ttk.Label(main_frame, text="Better Touchpad 设置", font=("Arial", 14, "bold")).pack(pady=(0, 25))
            
            # 创建设置选项
            self._create_settings_controls(main_frame, config_data)
            
            # 创建保存和取消按钮
            self._create_settings_buttons(main_frame, settings_window, parent, config_data)
            
            # 调整窗口大小和位置
            self._adjust_settings_window(settings_window)
            
            # 启动窗口主循环
            if parent is None:
                settings_window.mainloop()
                
        except Exception as e:
            logger.error(f"创建设置窗口失败: {e}")
            self.settings_window_open = False
    
    def _load_settings_config(self):
        """
        加载设置窗口使用的配置数据
        
        Returns:
            dict: 包含当前配置的字典
        """
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(current_dir, 'configure.json')
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                
            response_time = config.get("response_time", 0.2)
            hot_key = config.get("hot_key", "f1")
            left_click = config.get("left_click", "f2")
            right_click = config.get("right_click", "f3")
            mode = config.get("mode", 0)
            
            return {
                "response_time": response_time,
                "hot_key": hot_key,
                "left_click": left_click,
                "right_click": right_click,
                "mode": mode,
                "config_path": config_path
            }
        except Exception as e:
            logger.error(f"读取配置失败: {e}")
            return {
                "response_time": 0.2,
                "hot_key": "f1",
                "left_click": "f2",
                "right_click": "f3",
                "mode": 0,
                "config_path": os.path.join(os.path.dirname(os.path.abspath(__file__)), 'configure.json')
            }
    
    def _create_settings_controls(self, parent_frame, config_data):
        """
        创建设置界面的控件
        
        Args:
            parent_frame: 父框架
            config_data: 配置数据字典
        """
        # 创建设置框架
        settings_frame = ttk.Frame(parent_frame)
        settings_frame.pack(fill=tk.BOTH, expand=True)
        
        # 设置行间距
        row_pady = 8
        
        # 功能键选项
        function_keys = ["f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10", "f11", "f12", 
                         "f13", "f14", "f15", "f16", "f17", "f18", "f19", "f20", "f21", "f22", "f23", "f24"]
        
        # 响应时间设置
        ttk.Label(settings_frame, text="长按响应时间 (秒):", font=("Arial", 10)).grid(row=0, column=0, sticky=tk.W, pady=row_pady)
        response_time_var = tk.StringVar(value=str(config_data["response_time"]))
        ttk.Entry(settings_frame, textvariable=response_time_var, width=15).grid(row=0, column=1, sticky=tk.W, pady=row_pady, padx=10)
        config_data["response_time_var"] = response_time_var
        
        # 热键设置
        ttk.Label(settings_frame, text="触发键:", font=("Arial", 10)).grid(row=1, column=0, sticky=tk.W, pady=row_pady)
        hot_key_var = tk.StringVar(value=config_data["hot_key"] if config_data["hot_key"] in function_keys else "f1")
        hot_key_combo = ttk.Combobox(settings_frame, textvariable=hot_key_var, values=function_keys, width=12, state="readonly")
        hot_key_combo.grid(row=1, column=1, sticky=tk.W, pady=row_pady, padx=10)
        config_data["hot_key_var"] = hot_key_var
        
        # 左键点击设置
        ttk.Label(settings_frame, text="左键点击:", font=("Arial", 10)).grid(row=2, column=0, sticky=tk.W, pady=row_pady)
        left_click_var = tk.StringVar(value=config_data["left_click"] if config_data["left_click"] in function_keys else "f2")
        left_click_combo = ttk.Combobox(settings_frame, textvariable=left_click_var, values=function_keys, width=12, state="readonly")
        left_click_combo.grid(row=2, column=1, sticky=tk.W, pady=row_pady, padx=10)
        config_data["left_click_var"] = left_click_var
        
        # 右键点击设置
        ttk.Label(settings_frame, text="右键点击:", font=("Arial", 10)).grid(row=3, column=0, sticky=tk.W, pady=row_pady)
        right_click_var = tk.StringVar(value=config_data["right_click"] if config_data["right_click"] in function_keys else "f3")
        right_click_combo = ttk.Combobox(settings_frame, textvariable=right_click_var, values=function_keys, width=12, state="readonly")
        right_click_combo.grid(row=3, column=1, sticky=tk.W, pady=row_pady, padx=10)
        config_data["right_click_var"] = right_click_var
        
        # 模式选择 - 使用单独的框架并添加标题
        mode_frame = ttk.LabelFrame(parent_frame, text="操作模式", padding=(15, 5))
        mode_frame.pack(fill=tk.X, expand=False, pady=15)
        
        mode_var = tk.IntVar(value=config_data["mode"])
        ttk.Radiobutton(mode_frame, text="长按模式", variable=mode_var, value=0).pack(anchor=tk.W, pady=3)
        ttk.Radiobutton(mode_frame, text="切换模式", variable=mode_var, value=1).pack(anchor=tk.W, pady=3)
        config_data["mode_var"] = mode_var
    
    def _create_settings_buttons(self, parent_frame, settings_window, parent, config_data):
        """
        创建设置窗口的按钮
        
        Args:
            parent_frame: 父框架
            settings_window: 设置窗口
            parent: 父窗口
            config_data: 配置数据字典
        """
        # 按钮区域
        button_frame = ttk.Frame(parent_frame)
        button_frame.pack(fill=tk.X, pady=(25, 0))
        
        # 保存按钮
        def save_settings():
            try:
                # 验证配置值
                try:
                    # 验证响应时间
                    response_time_val = float(config_data["response_time_var"].get())
                    if response_time_val <= 0 or response_time_val > 10:
                        messagebox.showerror("错误", "响应时间必须是大于0且不超过10的数值")
                        return
                        
                    # 验证按键选择 - 不能相同
                    if (config_data["left_click_var"].get() == config_data["right_click_var"].get() or 
                        config_data["left_click_var"].get() == config_data["hot_key_var"].get() or 
                        config_data["right_click_var"].get() == config_data["hot_key_var"].get()):
                        messagebox.showerror("错误", "触发键、左键点击和右键点击对应按键不能相同")
                        return
                except ValueError:
                    messagebox.showerror("错误", "响应时间必须是数字")
                    return
                
                # 更新配置
                new_config = {
                    "response_time": float(config_data["response_time_var"].get()),
                    "hot_key": config_data["hot_key_var"].get(),
                    "left_click": config_data["left_click_var"].get(),
                    "right_click": config_data["right_click_var"].get(),
                    "mode": config_data["mode_var"].get()
                }
                
                # 保存到文件
                try:
                    with open(config_data["config_path"], 'w', encoding='utf-8') as f:
                        json.dump(new_config, f, indent=4, ensure_ascii=False)
                except Exception as e:
                    messagebox.showerror("错误", f"保存配置文件失败: {str(e)}")
                    logger.error(f"保存配置文件失败: {e}")
                    return
                
                # 重新加载配置并立即应用
                if self.reload_config():
                    logger.info("设置已保存并立即生效")
                else:
                    messagebox.showwarning("警告", "设置已保存，但应用更改失败，可能需要重启应用")
                
                # 关闭窗口
                self.settings_window_open = False
                settings_window.destroy()
                if parent:
                    parent.destroy()
                    
                logger.info("用户更新了配置并应用")
            except Exception as e:
                messagebox.showerror("错误", f"保存配置失败: {str(e)}")
                logger.error(f"保存配置失败: {e}")
                # 确保发生错误时也能正确重置窗口状态
                self.settings_window_open = False
        
        # 取消按钮
        def cancel_settings():
            self.settings_window_open = False
            settings_window.destroy()
            if parent:
                parent.destroy()
        
        # 添加按钮
        save_button = ttk.Button(button_frame, text="保存", command=save_settings, width=10)
        save_button.pack(side=tk.RIGHT, padx=8)
        
        cancel_button = ttk.Button(button_frame, text="取消", command=cancel_settings, width=10)
        cancel_button.pack(side=tk.RIGHT, padx=8)
    
    def _adjust_settings_window(self, window):
        """
        调整设置窗口的大小和位置
        
        Args:
            window: 要调整的窗口对象
        """
        # 更新窗口
        window.update()
        window.update_idletasks()
        
        # 获取窗口实际尺寸
        width = window.winfo_width()
        height = window.winfo_height()
        
        # 确保窗口尺寸足够大
        if width < 450:
            width = 450
        if height < 500:
            height = 500
        
        # 居中窗口
        x = (window.winfo_screenwidth() // 2) - (width // 2)
        y = (window.winfo_screenheight() // 2) - (height // 2)
        window.geometry(f'{width}x{height}+{x}+{y}')
        
        # 设置为模态窗口，但不使用grab_set以避免线程问题
        window.lift()

    def _exit_app(self, icon, item):
        """退出应用"""
        logger.info("用户从系统托盘退出应用")
        # 停止图标
        try:
            icon.stop()
        except Exception as e:
            logger.error(f"停止系统托盘图标失败: {e}")
            
        # 置退出标志
        self.should_exit = True
        
        # 清理资源
        try:
            keyboard.unhook(self.on_left_click)
            keyboard.unhook(self.on_right_click)

            if self.press_hotkey:
                keyboard.remove_hotkey(self.press_hotkey)
        except Exception as e:
            logger.error(f"清理热键失败: {e}")
            
        # 完全清理其他资源
        self._cleanup_resources()

    # ============================== 配置管理 ==============================
    def _update_config(self, key, value):
        """
        更新配置文件中的单个配置项
        
        Args:
            key: 配置项键名
            value: 配置项值
        """
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(current_dir, 'configure.json')
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            config[key] = value
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
                
            logger.info(f"配置已更新: {key}={value}")
        except Exception as e:
            logger.error(f"更新配置失败: {e}")
    
    def reload_config(self):
        """
        重新加载配置文件并应用更改
        
        Returns:
            bool: 重新加载是否成功
        """
        global RESPONSE_TIME, HOT_KEY, LEFT_CLICK, RIGHT_CLICK, MODE
        
        try:
            # 获取当前文件所在目录路径
            current_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(current_dir, 'configure.json')
            
            # 使用锁确保线程安全
            with self.lock:
                # 备份当前模式配置
                old_mode = MODE
                
                # 读取配置文件
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                # 更新全局配置
                RESPONSE_TIME = config.get("response_time", 0.2)  
                HOT_KEY = config.get("hot_key", "f1")              
                LEFT_CLICK = config.get("left_click", "f2")        
                RIGHT_CLICK = config.get("right_click", "f3")      
                MODE = config.get("mode", 0)                    
                
                logger.info(f"重新加载配置: 响应时间={RESPONSE_TIME}, 热键={HOT_KEY}, 左键={LEFT_CLICK}, 右键={RIGHT_CLICK}, 模式={MODE}")
                
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
                
                # 处理模式改变的情况
                if old_mode != MODE and self.touchpad_active:
                    if MODE == 0:  # 切换到长按模式
                        # 长按模式下需保持按住热键才能使用触控板，所以这里关闭触控板
                        self.controller.toggle(False)
                        self.touchpad_active = False
                        logger.info("模式切换为长按模式，触控板已禁用")
                
                return True
            
        except Exception as e:
            logger.error(f"重新加载配置文件失败: {e}")
            return False

    def _reload_config(self, icon, item):
        """重新加载配置"""
        if self.reload_config():
            # 如果使用 pystray 的通知功能
            if hasattr(icon, 'notify'):
                icon.notify("配置已更新", "Better Touchpad")
            logger.info("配置已重新加载并应用")
        else:
            # 如果使用 pystray 的通知功能
            if hasattr(icon, 'notify'):
                icon.notify("重新加载配置失败", "Better Touchpad")
            logger.info("重新加载配置失败")

    def _process_command_queue(self):
        """处理命令队列中的命令"""
        try:
            # 非阻塞方式获取命令
            command, args = self.command_queue.get_nowait()
            
            # 处理各种命令
            if command == 'open_settings':
                # 在主线程中打开设置窗口
                self._create_settings_window()
                
            # 处理完成后标记任务完成
            self.command_queue.task_done()
        except queue.Empty:
            # 队列为空，不做任何处理
            pass
        except Exception as e:
            logger.error(f"处理命令队列出错: {e}")