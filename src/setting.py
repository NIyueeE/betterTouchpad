import json
import os
import tkinter as tk
from tkinter import ttk, messagebox
import threading
from configure_logger import configure_logger
import platform
from path_resolver import get_config_path, get_resource_path

logger = configure_logger()

class SettingsManager:
    def __init__(self, command_queue):
        self.command_queue = command_queue
        self.settings_window_open = False
        self.config_path = self._get_config_path()
        self._load_global_config()
    
    def _get_config_path(self):
        config_path = get_config_path()
        if config_path is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(current_dir, 'configure.json')
        return config_path
    
    def _load_global_config(self):
        try:
            global RESPONSE_TIME, HOT_KEY, LEFT_CLICK, RIGHT_CLICK, MODE
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                
            RESPONSE_TIME = config.get("response_time", 0.2)
            HOT_KEY = config.get("hot_key", "f1")
            LEFT_CLICK = config.get("left_click", "f2")
            RIGHT_CLICK = config.get("right_click", "f3")
            MODE = config.get("mode", 0)
            
            logger.info(f"已从 {self.config_path} 加载配置")
            
        except Exception as e:
            logger.error(f"读取配置文件失败: {e}，使用默认配置")
            RESPONSE_TIME = 0.2
            HOT_KEY = 'f1'
            LEFT_CLICK = 'f2'
            RIGHT_CLICK = 'f3'
            MODE = 0
            self._save_config(self.get_config())
    
    def get_config(self):
        return {
            "response_time": RESPONSE_TIME,
            "hot_key": HOT_KEY,
            "left_click": LEFT_CLICK,
            "right_click": RIGHT_CLICK,
            "mode": MODE
        }
    
    def update_config(self, key, value):
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            config[key] = value
            return self._save_config(config)
        except Exception as e:
            logger.error(f"更新配置失败: {e}")
            return False
    
    def _save_config(self, config):
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            logger.info(f"配置已保存到: {self.config_path}")
            return True
        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            return False
    
    def reload_config(self):
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
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
    
    def create_settings_window(self):
        if self.settings_window_open:
            self.command_queue.put(('settings_window_already_open', None))
            return False
        
        def run_settings_window():
            try:
                settings_window = tk.Tk()
                settings_window.title("Better Touchpad 设置")
                settings_window.geometry("450x500")
                settings_window.resizable(False, False)
                settings_window.attributes('-topmost', True)
                settings_window.update()
                settings_window.attributes('-topmost', False)
                
                try:
                    if platform.system() == "Windows":
                        icon_path = get_resource_path('setting_icon.ico')
                        if icon_path and os.path.exists(icon_path):
                            settings_window.iconbitmap(icon_path)
                except Exception as e:
                    logger.error(f"设置窗口图标失败: {e}")
                
                def on_window_close():
                    self.settings_window_open = False
                    self.command_queue.put(('settings_window_closed', None))
                    settings_window.destroy()
                    logger.info("设置窗口已关闭")
                
                settings_window.protocol("WM_DELETE_WINDOW", on_window_close)
                
                config_data = self._load_settings_config()
                main_frame = ttk.Frame(settings_window, padding=25)
                main_frame.pack(fill=tk.BOTH, expand=True)
                
                ttk.Label(main_frame, text="Better Touchpad 设置", font=("Arial", 14, "bold")).pack(pady=(0, 25))
                self._create_settings_controls(main_frame, config_data)
                self._create_settings_buttons(main_frame, settings_window, None, config_data)
                self._adjust_settings_window(settings_window)
                settings_window.update_idletasks()
                settings_window.deiconify()
                settings_window.focus_force()
                settings_window.mainloop()
                
            except Exception as e:
                logger.error(f"创建设置窗口线程内部错误: {e}")
                self.settings_window_open = False
                self.command_queue.put(('settings_window_failed', None))
        
        self.settings_window_open = True
        window_thread = threading.Thread(target=run_settings_window)
        window_thread.daemon = True
        window_thread.start()
        logger.info(f"设置窗口线程已启动: {window_thread.name}")
        return True
    
    def _load_settings_config(self):
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
        settings_frame = ttk.Frame(parent_frame)
        settings_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        row_pady = 8

        # 输入验证函数
        def validate_float(text):
            if text == "" or text == ".":
                return True
            try:
                float(text)
                return True
            except ValueError:
                return False

        function_keys = [f"f{i}" for i in range(1, 25)]

        # 长按响应时间设置（改用 StringVar）
        ttk.Label(settings_frame, text="长按响应时间 (秒):", font=("Arial", 10)).grid(
            row=0, column=0, sticky=tk.E, pady=row_pady, padx=5)

        response_time_var = tk.StringVar()  # 改为 StringVar
        response_time_value = config_data.get("response_time", "0.5")  # 直接使用字符串
        response_time_var.set(response_time_value)
        validate_cmd = (settings_frame.register(validate_float), '%P')
        response_time_entry = ttk.Entry(
            settings_frame,
            textvariable=response_time_var,
            validate="key",
            validatecommand=validate_cmd,
            width=8
        )
        response_time_entry.grid(row=0, column=1, sticky=tk.W, pady=row_pady, padx=5)

        # 创建下拉框组件
        def create_key_selector(row, label, config_key):
            ttk.Label(settings_frame, text=f"{label}:", font=("Arial", 10)).grid(
                row=row, column=0, sticky=tk.E, pady=row_pady, padx=5)

            var = tk.StringVar()
            default_value = config_data.get(config_key, "f1")
            var.set(default_value)  # 显式设置
            combo = ttk.Combobox(
                settings_frame,
                textvariable=var,
                values=function_keys,
                width=6,
                state="readonly"
            )
            if default_value in function_keys:
                combo.current(function_keys.index(default_value))
            else:
                combo.current(0)
            combo.grid(row=row, column=1, sticky=tk.W, pady=row_pady, padx=5)
            return var

        hot_key_var = create_key_selector(1, "触发键", "hot_key")
        left_click_var = create_key_selector(2, "左键点击", "left_click")
        right_click_var = create_key_selector(3, "右键点击", "right_click")

        # 操作模式设置
        mode_frame = ttk.LabelFrame(parent_frame, text="操作模式", padding=(15, 5))
        mode_frame.pack(fill=tk.X, expand=False, pady=10, padx=10)

        mode_var = tk.IntVar()
        mode_value = int(config_data.get("mode", 0))
        mode_var.set(mode_value)  # 显式设置
        mode_0_radio = ttk.Radiobutton(
            mode_frame,
            text="长按模式",
            variable=mode_var,
            value=0
        )
        mode_0_radio.pack(anchor=tk.W, pady=3)

        mode_1_radio = ttk.Radiobutton(
            mode_frame,
            text="切换模式",
            variable=mode_var,
            value=1
        )
        mode_1_radio.pack(anchor=tk.W, pady=3)

        # 强制刷新界面
        settings_frame.update_idletasks()
        mode_frame.update_idletasks()

        # 保存变量引用
        config_data.update({
            "response_time_var": response_time_var,
            "hot_key_var": hot_key_var,
            "left_click_var": left_click_var,
            "right_click_var": right_click_var,
            "mode_var": mode_var
        })
    
    def _create_settings_buttons(self, parent_frame, settings_window, parent, config_data):
        button_frame = ttk.Frame(parent_frame)
        button_frame.pack(fill=tk.X, pady=(25, 0))
        
        def save_settings():
            try:
                response_time_val = float(config_data["response_time_entry"].get())
                if response_time_val <= 0 or response_time_val > 10:
                    messagebox.showerror("错误", "响应时间必须是大于0且不超过10的数值")
                    return
                
                hot_key = config_data["hot_key_combo"].get()
                left_click = config_data["left_click_combo"].get()
                right_click = config_data["right_click_combo"].get()
                
                if (left_click == right_click or
                    left_click == hot_key or
                    right_click == hot_key):
                    messagebox.showerror("错误", "触发键、左键点击和右键点击对应按键不能相同")
                    return
                
                new_config = {
                    "response_time": response_time_val,
                    "hot_key": hot_key,
                    "left_click": left_click,
                    "right_click": right_click,
                    "mode": config_data["mode_var"].get()
                }
                
                if not self._save_config(new_config):
                    messagebox.showerror("错误", "保存配置文件失败")
                    return
                
                self.command_queue.put(('config_updated', new_config))
                self.settings_window_open = False
                settings_window.destroy()
                logger.info("用户更新了配置并应用")
            except ValueError:
                messagebox.showerror("错误", "响应时间必须是数字")
            except Exception as e:
                messagebox.showerror("错误", f"保存配置失败: {str(e)}")
                logger.error(f"保存配置失败: {e}")
                self.settings_window_open = False
                self.command_queue.put(('settings_window_closed', None))
        
        def cancel_settings():
            self.settings_window_open = False
            self.command_queue.put(('settings_window_closed', None))
            settings_window.destroy()
            logger.info("用户取消了设置")
        
        save_button = ttk.Button(button_frame, text="保存", command=save_settings, width=10)
        save_button.pack(side=tk.RIGHT, padx=8)
        cancel_button = ttk.Button(button_frame, text="取消", command=cancel_settings, width=10)
        cancel_button.pack(side=tk.RIGHT, padx=8)
    
    def _adjust_settings_window(self, window):
        window.update()
        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()

        width = 450
        height = 500

        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        window.geometry(f'{width}x{height}+{x}+{y}')
        window.lift()

RESPONSE_TIME = 0.2
HOT_KEY = 'f1'
LEFT_CLICK = 'f2'
RIGHT_CLICK = 'f3'
MODE = 0