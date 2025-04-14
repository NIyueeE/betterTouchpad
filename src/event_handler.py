import platform
import time
import select
import threading
import json
import os
import sys
import subprocess
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
        
        # 系统托盘图标
        self.tray_icon = None
        self.tray_thread = None
        
        # 用于跨线程通信的队列
        self.command_queue = queue.Queue()
        
        # 正在显示设置窗口的标志
        self.settings_window_open = False

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
            
            # 启动系统托盘图标（在新线程中）
            self.tray_thread = threading.Thread(target=self._start_tray_icon, daemon=True)
            self.tray_thread.start()
            logger.info("系统托盘图标已启动")
            
            # 主循环
            if platform.system() == "Linux":
                # Linux系统需要事件循环
                poller = select.poll()
                poller.register(self.controller.fd, select.POLLIN)
                while not self.should_exit:
                    poller.poll(100)
                    self._process_command_queue()
            else:
                # Windows/Mac系统
                while not self.should_exit:
                    time.sleep(0.1)
                    self._process_command_queue()

        except KeyboardInterrupt:
            logger.info("用户中断，退出...")
        finally:
            # 清理资源
            self.controller.cleanup()
            keyboard.unhook_all()
            
            # 停止系统托盘图标
            if self.tray_icon:
                self.tray_icon.stop()
                
            logger.info("服务已停止")

    def _create_tray_icon(self):
        """创建系统托盘图标"""
        # 创建一个简单的图标
        current_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(current_dir, 'icon.png')
        
        # 检查图标是否存在，不存在则创建一个默认图标
        if not os.path.exists(icon_path):
            # 创建一个蓝色圆形图标，表示触控板
            image = Image.new('RGBA', (64, 64), color=(0, 0, 0, 0))
            
            # 画一个圆
            draw = ImageDraw.Draw(image)
            draw.ellipse([(4, 4), (60, 60)], fill=(0, 120, 212), outline=(255, 255, 255, 128), width=2)
            
            # 在中间画一个小的触控点
            draw.ellipse([(28, 28), (36, 36)], fill=(255, 255, 255))
            
            # 保存图像
            image.save(icon_path)
            logger.info(f"创建默认图标: {icon_path}")
        
        # 创建图标菜单
        menu = (
            pystray.MenuItem('切换模式', self._toggle_mode),
            pystray.MenuItem('设置', self._open_settings),
            pystray.MenuItem('刷新配置', self._reload_config),
            pystray.MenuItem('退出', self._exit_app),
        )
        
        # 创建系统托盘图标
        icon = pystray.Icon(
            'betterTouchpad',
            Image.open(icon_path),
            'Better Touchpad',
            menu
        )
        
        return icon
    
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
            
        # 将打开设置窗口的命令放入队列，由主线程处理
        self.command_queue.put(('open_settings', None))
        self.settings_window_open = True
    
    def _create_settings_window(self, parent=None):
        """创建设置窗口"""
        try:
            # 如果没有提供父窗口，则创建一个新窗口
            if parent is None:
                settings_window = tk.Tk()
            else:
                settings_window = tk.Toplevel(parent)
                
            # 设置窗口关闭事件处理
            def on_window_close():
                self.settings_window_open = False
                settings_window.destroy()
                if parent:
                    parent.destroy()
            
            settings_window.protocol("WM_DELETE_WINDOW", on_window_close)
                
            settings_window.title("Better Touchpad 设置")
            settings_window.geometry("450x420")  # 进一步增加窗口尺寸
            settings_window.resizable(False, False)
            
            # 读取当前配置
            current_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(current_dir, 'configure.json')
            
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    
                response_time = config.get("response_time", 0.2)
                hot_key = config.get("hot_key", "`")
                left_click = config.get("left_click", "c")
                right_click = config.get("right_click", "v")
                mode = config.get("mode", 0)
            except Exception as e:
                logger.error(f"读取配置失败: {e}")
                response_time = 0.2
                hot_key = "`"
                left_click = "c"
                right_click = "v"
                mode = 0
            
            # 创建设置界面 - 增加内边距
            main_frame = ttk.Frame(settings_window, padding=25)
            main_frame.pack(fill=tk.BOTH, expand=True)
            
            # 标题
            ttk.Label(main_frame, text="Better Touchpad 设置", font=("Arial", 14, "bold")).pack(pady=(0, 25))
            
            # 创建设置项
            settings_frame = ttk.Frame(main_frame)
            settings_frame.pack(fill=tk.BOTH, expand=True)
            
            # 调整各行的间距
            row_pady = 8  # 行间距
            
            # 响应时间
            ttk.Label(settings_frame, text="长按响应时间 (秒):", font=("Arial", 10)).grid(row=0, column=0, sticky=tk.W, pady=row_pady)
            response_time_var = tk.StringVar(value=str(response_time))
            ttk.Entry(settings_frame, textvariable=response_time_var, width=15).grid(row=0, column=1, sticky=tk.W, pady=row_pady, padx=10)
            
            # 热键
            ttk.Label(settings_frame, text="触发键:", font=("Arial", 10)).grid(row=1, column=0, sticky=tk.W, pady=row_pady)
            hot_key_var = tk.StringVar(value=hot_key)
            ttk.Entry(settings_frame, textvariable=hot_key_var, width=15).grid(row=1, column=1, sticky=tk.W, pady=row_pady, padx=10)
            
            # 左键点击
            ttk.Label(settings_frame, text="左键点击对应按键:", font=("Arial", 10)).grid(row=2, column=0, sticky=tk.W, pady=row_pady)
            left_click_var = tk.StringVar(value=left_click)
            ttk.Entry(settings_frame, textvariable=left_click_var, width=15).grid(row=2, column=1, sticky=tk.W, pady=row_pady, padx=10)
            
            # 右键点击
            ttk.Label(settings_frame, text="右键点击对应按键:", font=("Arial", 10)).grid(row=3, column=0, sticky=tk.W, pady=row_pady)
            right_click_var = tk.StringVar(value=right_click)
            ttk.Entry(settings_frame, textvariable=right_click_var, width=15).grid(row=3, column=1, sticky=tk.W, pady=row_pady, padx=10)
            
            # 模式选择 - 使用单独的框架并添加标题
            mode_frame = ttk.LabelFrame(main_frame, text="操作模式", padding=(15, 5))
            mode_frame.pack(fill=tk.X, expand=False, pady=15)
            
            mode_var = tk.IntVar(value=mode)
            ttk.Radiobutton(mode_frame, text="长按模式", variable=mode_var, value=0).pack(anchor=tk.W, pady=3)
            ttk.Radiobutton(mode_frame, text="切换模式", variable=mode_var, value=1).pack(anchor=tk.W, pady=3)
            
            # 按钮区域 - 增加按钮的大小和醒目程度
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill=tk.X, pady=(25, 0))
            
            # 保存按钮
            def save_settings():
                try:
                    # 验证响应时间是数字
                    try:
                        float(response_time_var.get())
                    except ValueError:
                        messagebox.showerror("错误", "响应时间必须是数字")
                        return
                    
                    # 更新配置
                    new_config = {
                        "response_time": float(response_time_var.get()),
                        "hot_key": hot_key_var.get(),
                        "left_click": left_click_var.get(),
                        "right_click": right_click_var.get(),
                        "mode": mode_var.get()
                    }
                    
                    # 保存到文件
                    with open(config_path, 'w', encoding='utf-8') as f:
                        json.dump(new_config, f, indent=4, ensure_ascii=False)
                    
                    # 重新加载配置并立即应用
                    if self.reload_config():
                        # messagebox.showinfo("成功", "设置已保存并立即生效")
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
            
            # 取消按钮
            def cancel_settings():
                self.settings_window_open = False
                settings_window.destroy()
                if parent:
                    parent.destroy()
            
            # 使用更大的按钮
            save_button = ttk.Button(button_frame, text="保存", command=save_settings, width=10)
            save_button.pack(side=tk.RIGHT, padx=8)
            
            cancel_button = ttk.Button(button_frame, text="取消", command=cancel_settings, width=10)
            cancel_button.pack(side=tk.RIGHT, padx=8)
            
            # 先显示窗口，然后计算尺寸并居中
            settings_window.update()
            
            # 确保按钮可见
            settings_window.update_idletasks()
            
            # 获取窗口实际尺寸
            width = settings_window.winfo_width()
            height = settings_window.winfo_height()
            
            # 确保窗口尺寸足够大
            if width < 450:
                width = 450
            if height < 500:
                height = 500
            
            # 居中窗口
            x = (settings_window.winfo_screenwidth() // 2) - (width // 2)
            y = (settings_window.winfo_screenheight() // 2) - (height // 2)
            settings_window.geometry(f'{width}x{height}+{x}+{y}')
            
            # 设置为模态窗口，但不使用grab_set以避免线程问题
            settings_window.transient(parent if parent else None)
            
            if parent is None:
                settings_window.mainloop()
        except Exception as e:
            logger.error(f"创建设置窗口失败: {e}")
            self.settings_window_open = False
    
    def _exit_app(self, icon, item):
        """退出应用"""
        logger.info("用户从系统托盘退出应用")
        icon.stop()
        self.should_exit = True
    
    def _update_config(self, key, value):
        """更新配置"""
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
    
    def _start_tray_icon(self):
        """在独立线程中启动系统托盘图标"""
        self.tray_icon = self._create_tray_icon()
        self.tray_icon.run()

    def reload_config(self):
        """重新加载配置文件并应用更改"""
        global RESPONSE_TIME, HOT_KEY, LEFT_CLICK, RIGHT_CLICK, MODE
        
        try:
            # 获取当前文件所在目录路径
            current_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(current_dir, 'configure.json')
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                
            # 读取新的配置参数
            old_hot_key = HOT_KEY
            old_left_click = LEFT_CLICK
            old_right_click = RIGHT_CLICK
            old_mode = MODE
            
            # 更新全局配置
            RESPONSE_TIME = config["response_time"]  
            HOT_KEY = config["hot_key"]              
            LEFT_CLICK = config["left_click"]        
            RIGHT_CLICK = config["right_click"]      
            MODE = config["mode"]                    
            
            logger.info(f"重新加载配置: 响应时间={RESPONSE_TIME}, 热键={HOT_KEY}, 左键={LEFT_CLICK}, 右键={RIGHT_CLICK}, 模式={MODE}")
            
            # 清理现有热键绑定
            self._cleanup_hotkeys()
            try:
                if self.press_hotkey:
                    keyboard.remove_hotkey(self.press_hotkey)
            except KeyError:
                pass
            
            # 如果触控板处于激活状态且热键相关配置有变化
            if self.touchpad_active:
                # 根据当前模式设置热键绑定
                if MODE == 1:  # 切换模式
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
                else:  # 长按模式
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
                logger.info(f"触控板热键已更新: {LEFT_CLICK}, {RIGHT_CLICK}")
            
            # 重新注册主热键
            self.press_hotkey = keyboard.add_hotkey(HOT_KEY, lambda: None, suppress=True)
            
            # 如果模式从长按切换到切换模式或反之，可能需要调整触控板状态
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