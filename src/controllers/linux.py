import subprocess
import logging
from .base import TouchpadController

# 配置日志记录器
logger = logging.getLogger(__name__)

# 常量定义
TOUCHPAD_IDENTIFIERS = ["Touchpad", "TouchPad"]
DEVICE_PREFIX = "Device:"

class LinuxTouchpadController(TouchpadController):
    """
    Linux系统触控板控制器
    使用libinput工具检测和管理触控板设备，通过evdev-ctl启用/禁用设备
    
    主要功能:
    1. 自动检测系统中的触控板设备
    2. 提供启用/禁用触控板的方法
    """
    
    def __init__(self):
        """
        初始化Linux触控板控制器
        检测系统中的触控板设备并存储其路径
        """
        super().__init__()
        self.touchpad_device = None
        self._find_touchpad()
    
    def _find_touchpad(self):
        """
        查找系统中的触控板设备
        
        使用libinput list-devices命令获取所有输入设备信息
        解析输出找到触控板设备并保存其路径
        """
        try:
            # 执行libinput命令获取所有设备信息
            output = subprocess.check_output(
                ["libinput", "list-devices"],
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )
            
            # 按设备块分割输出（每个设备间用空行分隔）
            device_blocks = output.split('\n\n')
            
            # 遍历每个设备块查找触控板
            for block in device_blocks:
                # 检查是否为触控板（包含"Touchpad"关键字）
                if any(identifier in block for identifier in TOUCHPAD_IDENTIFIERS):
                    # 解析设备路径
                    self._extract_device_path(block)
                    if self.touchpad_device:
                        return
            
            # 未找到触控板设备
            if not self.touchpad_device:
                logger.warning("未找到触控板设备，某些功能可能不可用")
        except FileNotFoundError:
            logger.error("未找到libinput命令，请确保已安装libinput-tools包")
        except subprocess.CalledProcessError as e:
            logger.error(f"执行libinput命令失败: {e.output}")
        except Exception as e:
            logger.error(f"查找触控板失败: {e}", exc_info=True)
    
    def _extract_device_path(self, device_block):
        """
        从设备块中提取设备路径
        
        参数:
            device_block: 设备信息块文本
            
        设置:
            self.touchpad_device: 触控板设备路径
        """
        for line in device_block.split('\n'):
            line = line.strip()
            if line.startswith(DEVICE_PREFIX):
                device_path = line.split(":", 1)[1].strip()
                self.touchpad_device = device_path
                logger.info(f"找到触控板设备: {device_path}")
                return
    
    def _check_device_state(self):
        """
        检查触控板设备当前状态
        
        返回:
            bool - True表示设备已启用，False表示设备已禁用
        """
        try:
            # 使用libinput debug-events命令检查设备状态
            # 如果设备已禁用，命令会失败
            subprocess.check_output(
                ["libinput", "debug-events", "--device", self.touchpad_device],
                stderr=subprocess.STDOUT,
                timeout=1
            )
            return True
        except subprocess.TimeoutExpired:
            # 命令超时通常意味着设备正在工作（已启用）
            return True
        except subprocess.CalledProcessError:
            # 命令失败通常意味着设备已禁用
            return False
    
    def toggle(self, enable):
        """
        切换触控板状态
        
        参数:
            enable: 布尔值，True启用触控板，False禁用触控板
            
        返回:
            bool - 操作是否成功
        """
        # 检查是否有可用的触控板设备
        if not self.touchpad_device:
            logger.error("未找到触控板设备，无法切换状态")
            return False
        
        try:
            # 检查当前状态
            current_state = self._check_device_state()
            
            # 如果状态已经是目标状态，则无需操作
            if current_state == enable:
                logger.info(f"当前状态已为目标状态（{'启用' if enable else '禁用'}），跳过操作")
                return True
            
            # 切换设备状态
            self._set_device_state(enable)
            
            # 记录操作结果
            logger.info(f"触控板状态已设置为: {'启用' if enable else '禁用'}")
            return True
            
        except Exception as e:
            logger.error(f"设置触控板状态失败: {e}", exc_info=True)
            return False
    
    def _set_device_state(self, enable):
        """
        设置触控板设备状态
        
        参数:
            enable: 布尔值，True启用设备，False禁用设备
            
        异常:
            subprocess.CalledProcessError: 如果命令执行失败
        """
        command = ["evdev-ctl", "enable" if enable else "disable", self.touchpad_device]
        subprocess.call(command)
    
    def cleanup(self):
        """
        清理资源
        本实现无需特殊操作
        """
        pass