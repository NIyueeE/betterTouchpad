import ctypes
import os
import logging
from ctypes import wintypes, Structure, c_void_p
from ctypes import c_ulong, c_ushort, c_ubyte
from .base import TouchpadController

logger = logging.getLogger(__name__)

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