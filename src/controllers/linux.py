import os
import time
import subprocess
import logging
from .base import TouchpadController

logger = logging.getLogger(__name__)

class LinuxTouchpadController(TouchpadController):
    """
    Linux系统触控板控制器
    使用xinput命令控制触控板设备
    """
    
    def __init__(self):
        """初始化Linux触控板控制器"""
        super().__init__()
        self.touchpad_id = None
        self._find_touchpad()
    
    def _find_touchpad(self):
        """查找系统中的触控板设备"""
        try:
            # 执行xinput list命令获取设备列表
            output = subprocess.check_output(["xinput", "list"], universal_newlines=True)
            
            # 查找包含TouchPad或Touchpad的行
            for line in output.splitlines():
                if "TouchPad" in line or "Touchpad" in line:
                    # 提取设备ID
                    parts = line.split("id=")
                    if len(parts) > 1:
                        self.touchpad_id = parts[1].split()[0].strip()
                        logger.info(f"找到触控板设备，ID: {self.touchpad_id}")
                        return
            
            if not self.touchpad_id:
                logger.warning("未找到触控板设备")
        except Exception as e:
            logger.error(f"查找触控板失败: {e}", exc_info=True)
    
    def toggle(self, enable):
        """
        切换触控板状态
        
        参数:
            enable: 布尔值，True启用触控板，False禁用触控板
            
        返回:
            bool - 操作是否成功
        """
        if not self.touchpad_id:
            logger.error("未找到触控板设备，无法切换状态")
            return False
        
        try:
            # 检查当前状态
            status_output = subprocess.check_output(
                ["xinput", "list-props", self.touchpad_id], 
                universal_newlines=True
            )
            
            # 查找Device Enabled行
            current_state = None
            for line in status_output.splitlines():
                if "Device Enabled" in line:
                    current_state = int(line.strip().split(":")[-1].strip())
                    break
            
            if current_state is None:
                logger.error("无法获取触控板当前状态")
                return False
            
            # 计算目标状态
            target_state = 1 if enable else 0
            
            # 如果状态已经是目标状态，则无需操作
            if current_state == target_state:
                logger.info(f"当前状态已为目标状态（{'启用' if enable else '禁用'}），跳过操作")
                return True
            
            # 设置触控板状态
            logger.info(f"状态变更需要（当前：{current_state}，目标：{target_state}），执行xinput...")
            
            subprocess.call([
                "xinput", "set-prop", 
                self.touchpad_id, 
                "Device Enabled", 
                str(target_state)
            ])
            
            logger.info(f"触控板状态已设置为: {'启用' if enable else '禁用'}")
            return True
            
        except Exception as e:
            logger.error(f"设置触控板状态失败: {e}", exc_info=True)
            return False
    
    def cleanup(self):
        """
        清理资源
        本实现无需特殊操作
        """
        pass