import platform
import ctypes
import time
import os
import select
import logging
import threading
from ctypes import wintypes, Structure, c_void_p, c_char_p
from ctypes import c_ulong, c_ushort, c_ubyte
from pynput import mouse
import keyboard

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========================== 平台抽象层 ==========================
class TouchpadController:
    def __init__(self):
        self.mouse = mouse.Controller()
    
    def toggle(self, enable):
        raise NotImplementedError
    
    def cleanup(self):
        pass

    def create_dummy_window(self):
        raise NotImplementedError

# ========================== Windows 实现 ==========================
class GUID(Structure):
    _fields_ = [
        ("Data1", c_ulong),
        ("Data2", c_ushort),
        ("Data3", c_ushort),
        ("Data4", c_ubyte * 8)
    ]

class SP_DEVINFO_DATA(Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("ClassGuid", GUID),
        ("DevInst", wintypes.DWORD),
        ("Reserved", c_void_p)
    ]

class WindowsTouchpadController(TouchpadController):
    def __init__(self):
        super().__init__()
        self._check_admin()
        self.device_handles = []
        self._init_api()
        self._find_touchpad_devices()
        self.dummy_hwnd = None
    
    def _init_api(self):
        self.setupapi = ctypes.WinDLL('SetupAPI')
        
        # API函数定义
        self.SetupDiGetClassDevs = self.setupapi.SetupDiGetClassDevsW
        self.SetupDiGetClassDevs.argtypes = [ctypes.POINTER(GUID), wintypes.LPCWSTR, wintypes.HWND, wintypes.DWORD]
        self.SetupDiGetClassDevs.restype = wintypes.HANDLE

        self.SetupDiEnumDeviceInfo = self.setupapi.SetupDiEnumDeviceInfo
        self.SetupDiEnumDeviceInfo.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(SP_DEVINFO_DATA)]
        self.SetupDiEnumDeviceInfo.restype = wintypes.BOOL

        self.SetupDiCallClassInstaller = self.setupapi.SetupDiCallClassInstaller
        self.SetupDiCallClassInstaller.argtypes = [wintypes.DWORD, wintypes.HANDLE, ctypes.POINTER(SP_DEVINFO_DATA)]
        self.SetupDiCallClassInstaller.restype = wintypes.BOOL

        self.SetupDiGetDeviceRegistryPropertyW = self.setupapi.SetupDiGetDeviceRegistryPropertyW
        self.SetupDiGetDeviceRegistryPropertyW.argtypes = [
            wintypes.HANDLE, 
            ctypes.POINTER(SP_DEVINFO_DATA),
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD)
        ]
        self.SetupDiGetDeviceRegistryPropertyW.restype = wintypes.BOOL

    def _check_admin(self):
        if ctypes.windll.shell32.IsUserAnAdmin() == 0:
            logger.error("需要管理员权限运行")
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", os.sys.executable, __file__, None, 1
            )
            raise SystemExit

    def _find_touchpad_devices(self):
        self.device_handles = []
        GUID_HIDCLASS = GUID()
        GUID_HIDCLASS.Data1 = 0x745A17A0
        GUID_HIDCLASS.Data2 = 0x74D3
        GUID_HIDCLASS.Data3 = 0x11D0
        GUID_HIDCLASS.Data4 = (0xB6, 0xFE, 0x00, 0xA0, 0xC9, 0x0F, 0x57, 0xDA)
        
        hdev = self.SetupDiGetClassDevs(ctypes.byref(GUID_HIDCLASS), None, None, 0x00000002)
        if hdev == -1:
            logger.error("获取设备类失败")
            return

        try:
            dev_info = SP_DEVINFO_DATA()
            dev_info.cbSize = ctypes.sizeof(SP_DEVINFO_DATA)
            index = 0
            
            while True:
                if not self.SetupDiEnumDeviceInfo(hdev, index, ctypes.byref(dev_info)):
                    if ctypes.get_last_error() == 259:
                        break
                    index += 1
                    continue
                
                buf = (wintypes.WCHAR * 256)()
                buf_size = wintypes.DWORD(256)
                if self.SetupDiGetDeviceRegistryPropertyW(
                    hdev,
                    ctypes.byref(dev_info),
                    0x00000000,
                    None,
                    ctypes.byref(buf),
                    buf_size,
                    None
                ):
                    hwid = buf.value
                    if "触摸板" in hwid:
                        dev_info_copy = SP_DEVINFO_DATA()
                        ctypes.memmove(ctypes.byref(dev_info_copy), ctypes.byref(dev_info), ctypes.sizeof(SP_DEVINFO_DATA))
                        self.device_handles.append((hdev, dev_info_copy))
                        logger.info(f"找到触控板设备: {hwid}")
                        break
                index += 1
                
        except Exception as e:
            logger.error(f"查找触控板设备时出错: {e}")
        finally:
            if not self.device_handles:
                logger.warning("未找到任何触控板设备")
    
    def toggle(self, enable):
        if not self.device_handles:
            return
        for hdev, dev_info in self.device_handles:
            self.SetupDiCallClassInstaller(0x12, hdev, ctypes.byref(dev_info))
    
    def cleanup(self):
        pass

# ========================== Linux 实现 ==========================
class LinuxTouchpadController(TouchpadController):
    def __init__(self):
        super().__init__()
        self._check_root()
        self.li = None
        self.fd = -1
        self.device_path = None
        self._init_libinput()
        self._find_touchpad()
        self.dummy_window = None

    def _init_libinput(self):
        self.libinput = ctypes.CDLL("libinput.so.10")
        self.libinput.libinput_path_create_context.restype = ctypes.POINTER(ctypes.c_void_p)
        self.libinput.libinput_path_add_device.argtypes = [ctypes.POINTER(ctypes.c_void_p), c_char_p]
        self.libinput.libinput_device_has_capability.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self.libinput.libinput_device_has_capability.restype = ctypes.c_int
        self.libinput.libinput_get_fd.argtypes = [ctypes.POINTER(ctypes.c_void_p)]
        self.libinput.libinput_get_fd.restype = ctypes.c_int
        
        self.li = self.libinput.libinput_path_create_context(None)
        if not self.li:
            raise RuntimeError("无法创建libinput上下文")

    def _check_root(self):
        if os.geteuid() != 0:
            logger.error("需要root权限运行，请使用sudo执行")
            raise SystemExit

    def _find_touchpad(self):
        for device in os.listdir("/dev/input"):
            if device.startswith("event"):
                path = os.path.join("/dev/input", device)
                dev = self.libinput.libinput_path_add_device(self.li, path.encode())
                if self.libinput.libinput_device_has_capability(dev, 1):
                    self.device_path = path
                    self.fd = self.libinput.libinput_get_fd(self.li)
                    logger.info("找到触控板设备: %s", path)
                    return
        raise RuntimeError("未找到触控板设备")

    def toggle(self, enable):
        sys_path = f"/sys/class/input/{os.path.basename(self.device_path)}/device/authorized"
        try:
            with open(sys_path, "w") as f:
                f.write("1" if enable else "0")
            time.sleep(0.2)
        except IOError as e:
            logger.error("设备状态切换失败: %s", e)

    def cleanup(self):
        pass

# ========================== 工厂方法 ==========================
def create_controller():
    system = platform.system()
    if system == "Windows":
        return WindowsTouchpadController()
    elif system == "Linux":
        return LinuxTouchpadController()
    else:
        raise NotImplementedError(f"Unsupported platform: {system}")

# ========================== 事件处理器 ==========================
class EventHandler:
    def __init__(self):
        self.controller = create_controller()
        self.should_exit = False
        self.space_pressed_time = 0
        self.long_press_timer = None
        self.long_press_triggered = False
        self.space_is_pressed = False
        self.lock = threading.Lock()

        self.left_click = None
        self.right_click = None

    def handle_long_press(self):
        with self.lock:
            if time.time() - self.space_pressed_time >= 0.5 and self.space_is_pressed:
                self.long_press_triggered = True
                self.controller.toggle(True)

                try:
                    if self.right_click:
                        keyboard.remove_hotkey(self.right_click)
                    if self.left_click:
                        keyboard.remove_hotkey(self.left_click)
                except KeyError:
                    pass

                self.left_click = keyboard.add_hotkey('space+c', self.controller.mouse.click, args=(mouse.Button.left,), suppress=True)
                self.right_click = keyboard.add_hotkey('space+v', self.controller.mouse.click, args=(mouse.Button.right,), suppress=True)
                logger.info("触控板启用，C/V绑定为鼠标左右键")

    def on_key_event(self, event):
        logger.info(event.name)
        logger.info(event.event_type)
        try:
            
            if event.name == 'space':
                
                if event.event_type == 'down':
                    with self.lock:
                        if self.space_is_pressed:
                            return
                        self.space_is_pressed = True
                        self.space_pressed_time = time.time()
                        if self.long_press_timer:
                            self.long_press_timer.cancel()
                        self.long_press_timer = threading.Timer(0.5, self.handle_long_press)
                        self.long_press_timer.start()

                elif event.event_type == 'up':
                    with self.lock:
                        if self.long_press_timer:
                            self.long_press_timer.cancel()
                            self.long_press_timer = None
                        if self.long_press_triggered:
                            self.controller.toggle(False)

                            try:
                                if self.right_click:
                                    keyboard.remove_hotkey(self.right_click)
                                if self.left_click:
                                    keyboard.remove_hotkey(self.left_click)
                            except KeyError:
                                pass

                            self.long_press_triggered = False
                            logger.info("触控板禁用，C/V解绑")
                    
                        self.space_pressed_time = 0 

        except Exception as e:
            logger.error("事件处理错误: %s", e)
            self.should_exit = True

    def run(self):
        try:
            keyboard.hook(self.on_key_event)
            logger.info("服务已启动，长按空格0.5秒启用触控板，C/V作为鼠标左右键。释放空格后禁用。")

            if platform.system() == "Linux":
                poller = select.poll()
                poller.register(self.controller.fd, select.POLLIN)
                while not self.should_exit:
                    poller.poll(100)
            else:
                while not self.should_exit:
                    time.sleep(0.1)

        except KeyboardInterrupt:
            logger.info("用户中断，退出...")
        finally:
            self.controller.cleanup()
            keyboard.unhook_all()
            logger.info("服务已停止")

if __name__ == "__main__":
    handler = EventHandler()
    handler.run()