import ctypes
import time
import logging
import winreg
from .base import TouchpadController

logger = logging.getLogger(__name__)

# 虚拟键码定义
VK_CONTROL = 0x11
VK_LWIN = 0x5B      # 左Win键
VK_F24 = 0x87       # F24键

# 键盘事件标志
KEYEVENTF_KEYDOWN = 0x0000
KEYEVENTF_KEYUP = 0x0002

# 注册表键值
reg_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\PrecisionTouchPad\Status"
value_name = "Enabled"

class WindowsTouchpadController(TouchpadController):
    """
    Windows 精确触摸板控制器（通过模拟按下 Ctrl + Win + F24 组合键实现）
    来自https://learn.microsoft.com/zh-cn/windows-hardware/design/component-guidelines/touchpad-enable-or-disable-toggle-button
    """
    
    def __init__(self):
        super().__init__()

    def toggle(self, enable):
        """
        仅在注册表状态与目标状态不同时模拟组合键
        返回: bool - 操作是否成功
        """
        try:
            # 读取当前注册表值
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path) as key:
                current_value, _ = winreg.QueryValueEx(key, value_name)
        except FileNotFoundError:
            logger.error("注册表路径不存在: %s", reg_path)
            return False
        except Exception as e:
            logger.error("读取注册表失败: %s", e, exc_info=True)
            return False

        # 转换目标值为整数
        target_value = 1 if enable else 0
        
        # 状态一致则无需操作
        if current_value == target_value:
            logger.info("当前状态已为目标状态（%s），跳过操作", "启用" if enable else "禁用")
            return True

        logger.info("状态变更需要（当前：%d，目标：%d），发送组合键...", current_value, target_value)
        
        try:
            # 按下 Ctrl
            ctypes.windll.user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYDOWN, 0)
            # 按下 Win
            ctypes.windll.user32.keybd_event(VK_LWIN, 0, KEYEVENTF_KEYDOWN, 0)
            # 按下 F24
            ctypes.windll.user32.keybd_event(VK_F24, 0, KEYEVENTF_KEYDOWN, 0)
            time.sleep(0.05)

            # 释放所有按键（顺序与按下相反）
            ctypes.windll.user32.keybd_event(VK_F24, 0, KEYEVENTF_KEYUP, 0)
            ctypes.windll.user32.keybd_event(VK_LWIN, 0, KEYEVENTF_KEYUP, 0)
            ctypes.windll.user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)

            logger.info("组合键发送成功")
            return True

        except Exception as e:
            logger.error("模拟按键失败: %s", e, exc_info=True)
            return False

    def cleanup(self):
        """清理资源（本实现无需特殊操作）"""
        pass