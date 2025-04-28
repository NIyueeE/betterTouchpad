import subprocess
import logging
import re
from controllers.base import BaseTouchpadController

# 配置日志记录器
logger = logging.getLogger(__name__)

# 常量定义
TOUCHPAD_IDENTIFIERS = ["Touchpad", "TouchPad"]
DEVICE_PREFIX = "Device:"

class LinuxTouchpadController(BaseTouchpadController):
    """
    Linux系统触控板控制器
    使用libinput工具检测和xinput管理触控板设备
    
    主要功能:
    1. 自动检测系统中的触控板设备
    2. 提供启用/禁用触控板的方法
    """
    
    def __init__(self):
        """
        初始化Linux触控板控制器
        检测系统中的触控板设备并存储其路径和ID
        """
        super().__init__()
        self.touchpad_device = None  # 设备路径
        self.touchpad_id = None      # 设备ID (用于xinput)
        self.touchpad_name = None    # 设备名称
        self._find_touchpad()
    
    def _find_touchpad(self):
        """
        查找系统中的触控板设备
        
        使用libinput list-devices命令获取所有输入设备信息
        解析输出找到触控板设备并保存其路径
        然后使用xinput获取设备ID
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
                    # 解析设备路径和名称
                    self._extract_device_info(block)
                    if self.touchpad_device and self.touchpad_name:
                        # 获取设备ID (用于xinput)
                        self._get_device_id()
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
    
    def _extract_device_info(self, device_block):
        """
        从设备块中提取设备路径和名称
        
        参数:
            device_block: 设备信息块文本
            
        设置:
            self.touchpad_device: 触控板设备路径
            self.touchpad_name: 触控板设备名称
        """
        device_name = None
        device_path = None
        
        lines = device_block.split('\n')
        for i, line in enumerate(lines):
            line = line.strip()
            # 第一行通常是设备名称
            if i == 0:
                device_name = line
            # 寻找设备路径
            elif line.startswith(DEVICE_PREFIX):
                device_path = line.split(":", 1)[1].strip()
        
        if device_name and device_path:
            self.touchpad_device = device_path
            self.touchpad_name = device_name
            logger.info(f"找到触控板设备: {device_name} ({device_path})")
    
    def _get_device_id(self):
        """
        使用xinput获取触控板设备ID
        """
        try:
            # 获取所有输入设备列表
            output = subprocess.check_output(
                ["xinput", "list"],
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )
            
            # 查找触控板设备的ID
            for line in output.split('\n'):
                if self.touchpad_name in line or "touchpad" in line.lower() or "Touchpad" in line:
                    # 使用正则表达式提取ID
                    match = re.search(r'id=(\d+)', line, re.IGNORECASE)
                    if match:
                        self.touchpad_id = match.group(1)
                        logger.info(f"触控板设备ID: {self.touchpad_id}")
                        return
            
            logger.warning(f"无法找到触控板设备ID，将尝试使用设备名称: {self.touchpad_name}")
        except FileNotFoundError:
            logger.error("未找到xinput命令，请确保已安装xorg-xinput包")
        except subprocess.CalledProcessError as e:
            logger.error(f"执行xinput命令失败: {e.output}")
        except Exception as e:
            logger.error(f"获取触控板ID失败: {e}", exc_info=True)
    
    def _check_device_state(self):
        """
        检查触控板设备当前状态
        
        返回:
            bool - True表示设备已启用，False表示设备已禁用
        """
        try:
            if not self.touchpad_id:
                logger.warning("未找到触控板ID，无法检查状态")
                return True
                
            # 使用xinput命令检查设备状态
            output = subprocess.check_output(
                ["xinput", "list-props", self.touchpad_id],
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )
            
            # 查找"Device Enabled"属性
            for line in output.split('\n'):
                if "Device Enabled" in line:
                    state = line.strip().split(':')[-1].strip()
                    return state == "1"
            
            # 如果找不到状态属性，假设设备已启用
            return True
        except subprocess.CalledProcessError:
            # 命令失败通常意味着设备不可用或已禁用
            return False
        except Exception as e:
            logger.error(f"检查触控板状态失败: {e}", exc_info=True)
            return True  # 出错时假设设备已启用
    
    def toggle(self, enable):
        """
        切换触控板状态
        
        参数:
            enable: 布尔值，True启用触控板，False禁用触控板
            
        返回:
            bool - 操作是否成功
        """
        # 检查是否有可用的触控板设备
        if not (self.touchpad_id or self.touchpad_name):
            logger.error("未找到触控板设备ID或名称，无法切换状态")
            return False
        
        try:
            # 检查当前状态
            current_state = self._check_device_state()
            
            # 如果状态已经是目标状态，则无需操作
            if current_state == enable:
                logger.info(f"触控板当前已{'启用' if enable else '禁用'}，无需更改")
                return True
            
            # 切换设备状态
            self._set_device_state(enable)
            
            # 验证状态是否已更改
            new_state = self._check_device_state()
            success = new_state == enable
            
            # 记录操作结果
            if success:
                logger.info(f"触控板状态已成功设置为: {'启用' if enable else '禁用'}")
            else:
                logger.error(f"触控板状态设置失败，当前状态: {'启用' if new_state else '禁用'}")
                
            return success
            
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
        action = "enable" if enable else "disable"
        
        # 首先尝试使用设备ID
        if self.touchpad_id:
            try:
                command = ["xinput", action, self.touchpad_id]
                logger.info(f"执行命令: {' '.join(command)}")
                subprocess.run(command, check=True)
                return
            except Exception as e:
                logger.error(f"使用设备ID切换触控板状态失败: {e}")
        
        # 如果使用ID失败，尝试使用设备名称
        if self.touchpad_name:
            try:
                command = ["xinput", action, self.touchpad_name]
                logger.info(f"执行命令: {' '.join(command)}")
                subprocess.run(command, check=True)
                return
            except Exception as e:
                logger.error(f"使用设备名称切换触控板状态失败: {e}")
                
        # 如果所有方法都失败，尝试搜索触控板名称
        try:
            # 获取所有输入设备列表
            output = subprocess.check_output(
                ["xinput", "list"],
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )
            
            # 查找任何看起来像触控板的设备
            for line in output.split('\n'):
                if "touchpad" in line.lower() or "Touchpad" in line or "DELL" in line and "Touchpad" in line:
                    # 尝试提取ID
                    match = re.search(r'id=(\d+)', line, re.IGNORECASE)
                    if match:
                        device_id = match.group(1)
                        try:
                            command = ["xinput", action, device_id]
                            logger.info(f"尝试使用搜索到的设备ID: {device_id}, 命令: {' '.join(command)}")
                            subprocess.run(command, check=True)
                            # 更新设备ID以便后续使用
                            self.touchpad_id = device_id
                            return
                        except Exception:
                            pass
        except Exception as e:
            logger.error(f"搜索触控板设备并切换状态失败: {e}")
            
        raise RuntimeError("无法找到有效的触控板设备控制方法")
    
    def cleanup(self):
        """
        清理资源
        本实现无需特殊操作
        """
        pass