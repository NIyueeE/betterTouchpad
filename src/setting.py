import json
import os
import tkinter as tk
from tkinter import ttk, messagebox
import threading
from .configure_logger import configure_logger
import platform

# 初始化日志记录器
logger = configure_logger()

class SettingsManager:
    """
    配置管理类
    
    负责处理设置窗口和配置文件的读写，提供用户界面进行配置修改，
    并通过命令队列与主程序通信。
    """
    def __init__(self, command_queue):
        """
        初始化配置管理器
        
        Args:
            command_queue: 用于跨线程通信的命令队列
        """
        self.command_queue = command_queue
        self.settings_window_open = False
        self.config_path = self._get_config_path()
        self._load_global_config()
    
    def _get_config_path(self):
        """
        获取配置文件路径
        
        Returns:
            str: 配置文件的完整路径
        """
        current_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(current_dir, 'configure.json')
    
    def _load_global_config(self):
        """从配置文件加载全局配置，若文件不存在则使用默认值"""
        try:
            global RESPONSE_TIME, HOT_KEY, LEFT_CLICK, RIGHT_CLICK, MODE
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                
            # 更新全局变量
            RESPONSE_TIME = config.get("response_time", 0.2)  
            HOT_KEY = config.get("hot_key", "f1")              
            LEFT_CLICK = config.get("left_click", "f2")        
            RIGHT_CLICK = config.get("right_click", "f3")      
            MODE = config.get("mode", 0)                    
            
            logger.info(f"已从 {self.config_path} 加载配置")
            
        except Exception as e:
            logger.error(f"读取配置文件失败: {e}，使用默认配置")
            # 设置默认值
            RESPONSE_TIME = 0.2
            HOT_KEY = 'f1'
            LEFT_CLICK = 'f2'
            RIGHT_CLICK = 'f3'
            MODE = 0
            
            # 尝试创建默认配置文件
            self._save_config(self.get_config())
    
    def get_config(self):
        """
        获取当前配置
        
        Returns:
            dict: 包含当前配置的字典
        """
        return {
            "response_time": RESPONSE_TIME,
            "hot_key": HOT_KEY,
            "left_click": LEFT_CLICK,
            "right_click": RIGHT_CLICK,
            "mode": MODE
        }
    
    def update_config(self, key, value):
        """
        更新配置文件中的单个配置项
        
        Args:
            key (str): 配置项键名
            value: 配置项值
        
        Returns:
            bool: 更新是否成功
        """
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            config[key] = value
            return self._save_config(config)
                
        except Exception as e:
            logger.error(f"更新配置失败: {e}")
            return False
    
    def _save_config(self, config):
        """
        保存配置到文件
        
        Args:
            config (dict): 配置字典
        
        Returns:
            bool: 保存是否成功
        """
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            logger.info(f"配置已保存到: {self.config_path}")
            return True
        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            return False
    
    def reload_config(self):
        """
        重新加载配置文件
        
        Returns:
            tuple: (重新加载是否成功, 配置字典)
        """
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # 更新全局变量
            global RESPONSE_TIME, HOT_KEY, LEFT_CLICK, RIGHT_CLICK, MODE
            RESPONSE_TIME = config.get("response_time", 0.2)  
            HOT_KEY = config.get("hot_key", "f1")              
            LEFT_CLICK = config.get("left_click", "f2")        
            RIGHT_CLICK = config.get("right_click", "f3")      
            MODE = config.get("mode", 0)
            
            logger.info(f"重新加载配置: 响应时间={RESPONSE_TIME}, 热键={HOT_KEY}, 左键={LEFT_CLICK}, 右键={RIGHT_CLICK}, 模式={MODE}")
            
            return True, self.get_config()
        except Exception as e:
            logger.error(f"重新加载配置文件失败: {e}")
            return False, None
    
    # -------------------------- 设置窗口 --------------------------
    
    def create_settings_window(self):
        """
        创建并显示设置窗口
        
        Returns:
            bool: 窗口创建是否成功
        """
        if self.settings_window_open:
            logger.info("设置窗口已经打开，忽略请求")
            # 通知主线程已经打开过窗口
            self.command_queue.put(('settings_window_already_open', None))
            return False
        
        try:
            # 在Windows中Tkinter在多线程环境中可能不稳定，
            # 使用独立线程来创建和管理窗口
            
            # 在独立线程中运行设置窗口
            def run_settings_window():
                try:
                    # 创建窗口对象 - 独立线程中创建新的Tk实例
                    settings_window = tk.Tk()
                    
                    # 设置窗口基本属性
                    settings_window.title("Better Touchpad 设置")
                    settings_window.geometry("450x500")
                    settings_window.resizable(False, False)
                    
                    # 确保窗口显示在最前面
                    settings_window.attributes('-topmost', True)
                    settings_window.update()
                    settings_window.attributes('-topmost', False)
                    
                    # 设置窗口图标
                    try:
                        current_dir = os.path.dirname(os.path.abspath(__file__))

                        # 根据不同系统使用不同的图标设置方法
                        if platform.system() == "Windows":
                            icon_name = 'setting_icon.ico'
                            icon_path = os.path.join(current_dir, 'source', icon_name)
                            if os.path.exists(icon_path):
                                settings_window.iconbitmap(icon_path)
                                logger.info(f"已设置窗口图标: {icon_path}")
                            else:
                                logger.error(f"窗口图标文件不存在: {icon_path}")

                        #elif platform.system() == "Linux":
                        #    icon_name = 'setting_icon.png'
                        #    # 好像不支持png格式, 到时候再修复吧, 不修复了。linux取消设置窗口!!!
                        #    icon_path = os.path.join(current_dir, 'source', icon_name)
                        #    if os.path.exists(icon_path):
                        #        icon_img = tk.PhotoImage(file=icon_path)
                        #        settings_window.iconphoto(True, icon_img)
                        #        # 保持引用以防止图像被垃圾回收
                        #        settings_window.icon_image = icon_img
                        #        logger.info(f"已设置窗口图标: {icon_path}")
                        #    else:
                        #        logger.error(f"窗口图标文件不存在: {icon_path}")
                        
                    except Exception as e:
                        logger.error(f"设置窗口图标失败: {e}")
                    
                    # 设置窗口关闭事件处理
                    def on_window_close():
                        self.settings_window_open = False
                        # 通知主线程设置窗口已关闭，确保标志被重置
                        self.command_queue.put(('settings_window_closed', None))
                        settings_window.destroy()
                        logger.info("设置窗口已关闭")
                    
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
                    self._create_settings_buttons(main_frame, settings_window, None, config_data)
                    
                    # 调整窗口大小和位置
                    self._adjust_settings_window(settings_window)
                    
                    # 强制更新窗口以确保显示正确
                    settings_window.update_idletasks()
                    settings_window.deiconify()
                    settings_window.focus_force()
                    
                    # 输出调试信息
                    logger.info(f"设置窗口创建完成，大小: {settings_window.winfo_width()}x{settings_window.winfo_height()}")
                    
                    # 启动窗口主循环
                    logger.info("启动设置窗口主循环")
                    settings_window.mainloop()
                    logger.info("设置窗口主循环结束")
                    
                except Exception as e:
                    logger.error(f"创建设置窗口线程内部错误: {e}")
                    self.settings_window_open = False
                    self.command_queue.put(('settings_window_failed', None))
            
            # 创建并启动线程
            self.settings_window_open = True
            window_thread = threading.Thread(target=run_settings_window)
            window_thread.daemon = True  # 设置为守护线程，主程序退出时自动终止
            window_thread.start()
            logger.info(f"设置窗口线程已启动: {window_thread.name}")
            
            return True
                
        except Exception as e:
            logger.error(f"创建设置窗口失败: {e}")
            self.settings_window_open = False
            # 通知主线程窗口创建失败
            self.command_queue.put(('settings_window_failed', None))
            return False
    
    def _load_settings_config(self):
        """
        加载设置窗口使用的配置数据
        
        Returns:
            dict: 包含当前配置的字典
        """
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                
            return {
                "response_time": config.get("response_time", 0.2),
                "hot_key": config.get("hot_key", "f1"),
                "left_click": config.get("left_click", "f2"),
                "right_click": config.get("right_click", "f3"),
                "mode": config.get("mode", 0),
                "config_path": self.config_path
            }
        except Exception as e:
            logger.error(f"读取配置失败: {e}")
            return {
                "response_time": RESPONSE_TIME,
                "hot_key": HOT_KEY,
                "left_click": LEFT_CLICK,
                "right_click": RIGHT_CLICK,
                "mode": MODE,
                "config_path": self.config_path
            }
    
    def _create_settings_controls(self, parent_frame, config_data):
        """
        创建设置界面的控件
        
        Args:
            parent_frame: 父框架
            config_data (dict): 配置数据字典
        """
        # 创建设置框架
        settings_frame = ttk.Frame(parent_frame)
        settings_frame.pack(fill=tk.BOTH, expand=True)
        
        # 设置行间距
        row_pady = 8
        
        # 功能键选项列表
        function_keys = ["f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10", "f11", "f12", 
                         "f13", "f14", "f15", "f16", "f17", "f18", "f19", "f20", "f21", "f22", "f23", "f24"]
        
        # 响应时间设置
        ttk.Label(settings_frame, text="长按响应时间 (秒):", font=("Arial", 10)).grid(row=0, column=0, sticky=tk.W, pady=row_pady)
        response_time_var = tk.StringVar(value=str(config_data["response_time"]))
        response_time_entry = ttk.Entry(settings_frame, textvariable=response_time_var, width=15)
        response_time_entry.grid(row=0, column=1, sticky=tk.W, pady=row_pady, padx=10)
        response_time_entry.insert(0, str(config_data["response_time"]))  # 显式设置初始值
        config_data["response_time_var"] = response_time_var
        
        # 热键设置
        ttk.Label(settings_frame, text="触发键:", font=("Arial", 10)).grid(row=1, column=0, sticky=tk.W, pady=row_pady)
        hot_key_var = tk.StringVar(value=config_data["hot_key"])
        hot_key_combo = ttk.Combobox(settings_frame, textvariable=hot_key_var, values=function_keys, width=12, state="readonly")
        hot_key_combo.grid(row=1, column=1, sticky=tk.W, pady=row_pady, padx=10)
        hot_key_combo.set(config_data["hot_key"] if config_data["hot_key"] in function_keys else "f1")  # 显式设置初始值
        config_data["hot_key_var"] = hot_key_var
        
        # 左键点击设置
        ttk.Label(settings_frame, text="左键点击:", font=("Arial", 10)).grid(row=2, column=0, sticky=tk.W, pady=row_pady)
        left_click_var = tk.StringVar(value=config_data["left_click"])
        left_click_combo = ttk.Combobox(settings_frame, textvariable=left_click_var, values=function_keys, width=12, state="readonly")
        left_click_combo.grid(row=2, column=1, sticky=tk.W, pady=row_pady, padx=10)
        left_click_combo.set(config_data["left_click"] if config_data["left_click"] in function_keys else "f2")  # 显式设置初始值
        config_data["left_click_var"] = left_click_var
        
        # 右键点击设置
        ttk.Label(settings_frame, text="右键点击:", font=("Arial", 10)).grid(row=3, column=0, sticky=tk.W, pady=row_pady)
        right_click_var = tk.StringVar(value=config_data["right_click"])
        right_click_combo = ttk.Combobox(settings_frame, textvariable=right_click_var, values=function_keys, width=12, state="readonly")
        right_click_combo.grid(row=3, column=1, sticky=tk.W, pady=row_pady, padx=10)
        right_click_combo.set(config_data["right_click"] if config_data["right_click"] in function_keys else "f3")  # 显式设置初始值
        config_data["right_click_var"] = right_click_var
        
        # 模式选择 - 使用单独的框架并添加标题
        mode_frame = ttk.LabelFrame(parent_frame, text="操作模式", padding=(15, 5))
        mode_frame.pack(fill=tk.X, expand=False, pady=15)
        
        mode_var = tk.IntVar(value=config_data["mode"])
        mode_0_radio = ttk.Radiobutton(mode_frame, text="长按模式", variable=mode_var, value=0)
        mode_0_radio.pack(anchor=tk.W, pady=3)
        mode_1_radio = ttk.Radiobutton(mode_frame, text="切换模式", variable=mode_var, value=1)
        mode_1_radio.pack(anchor=tk.W, pady=3)
        
        # 确保选中当前模式的单选按钮
        if config_data["mode"] == 0:
            mode_0_radio.invoke()
        else:
            mode_1_radio.invoke()
            
        config_data["mode_var"] = mode_var
    
    def _create_settings_buttons(self, parent_frame, settings_window, parent, config_data):
        """
        创建设置窗口的按钮
        
        Args:
            parent_frame: 父框架
            settings_window: 设置窗口
            parent: 父窗口
            config_data (dict): 配置数据字典
        """
        # 按钮区域
        button_frame = ttk.Frame(parent_frame)
        button_frame.pack(fill=tk.X, pady=(25, 0))
        
        # 保存按钮处理函数
        def save_settings():
            try:
                # 验证响应时间
                try:
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
                if not self._save_config(new_config):
                    messagebox.showerror("错误", "保存配置文件失败")
                    return
                
                # 发送配置已更新命令到主线程
                self.command_queue.put(('config_updated', new_config))
                
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
                # 通知主线程设置窗口已关闭，即使出错
                self.command_queue.put(('settings_window_closed', None))
        
        # 取消按钮处理函数
        def cancel_settings():
            self.settings_window_open = False
            # 通知主线程设置窗口已关闭
            self.command_queue.put(('settings_window_closed', None))
            settings_window.destroy()
            if parent:
                parent.destroy()
            logger.info("用户取消了设置")
        
        # 添加按钮
        save_button = ttk.Button(button_frame, text="保存", command=save_settings, width=10)
        save_button.pack(side=tk.RIGHT, padx=8)
        
        cancel_button = ttk.Button(button_frame, text="取消", command=cancel_settings, width=10)
        cancel_button.pack(side=tk.RIGHT, padx=8)
    
    def _adjust_settings_window(self, window):
        """
        调整设置窗口的大小和位置，使其根据屏幕分辨率自适应并居中显示
        
        Args:
            window: 要调整的窗口对象
        """
        # 更新窗口以获取实际尺寸
        window.update()
        window.update_idletasks()
        
        # 获取屏幕尺寸
        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()
        
        # 根据屏幕分辨率计算窗口尺寸
        # 在较小屏幕上使用较小的比例，较大屏幕上使用较大的比例
        if screen_width <= 1366:  # 小屏幕
            width = int(screen_width * 0.175)
            height = int(screen_height * 0.35)
        elif screen_width <= 1920:  # 中等屏幕
            width = int(screen_width * 0.15)
            height = int(screen_height * 0.2)
        else:  # 大屏幕
            width = int(screen_width * 0.125)
            height = int(screen_height * 0.25)
        
        # 确保窗口尺寸不小于最小值
        width = max(width, 400)
        height = max(height, 450)
        
        # 确保窗口不会超过屏幕的80%
        width = min(width, int(screen_width * 0.8))
        height = min(height, int(screen_height * 0.8))
        
        # 计算居中位置
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        
        # 设置窗口位置和大小
        window.geometry(f'{width}x{height}+{x}+{y}')
        
        # 设置为置顶窗口
        window.lift()

# 定义全局配置变量
RESPONSE_TIME = 0.2  # 长按响应时间（秒）
HOT_KEY = 'f1'       # 触发键
LEFT_CLICK = 'f2'    # 左键点击对应按键
RIGHT_CLICK = 'f3'   # 右键点击对应按键
MODE = 0             # 0为长按模式, 1为切换模式 