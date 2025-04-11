import ctypes
import os
import logging
from ctypes import wintypes, Structure, c_void_p, POINTER, byref
from ctypes import c_ulong, c_ushort, c_ubyte
from .base import TouchpadController

logger = logging.getLogger(__name__)

# Constants
DIGCF_PRESENT = 0x00000002
SPDRP_DEVICEDESC = 0x00000000
DIF_PROPERTYCHANGE = 0x00000012
DICS_ENABLE = 1
DICS_DISABLE = 2
DICS_FLAG_GLOBAL = 0x00000001

class GUID(Structure):
    _fields_ = [
        ("Data1", c_ulong),
        ("Data2", c_ushort),
        ("Data3", c_ushort),
        ("Data4", c_ubyte * 8)
    ]

class SP_CLASSINSTALL_HEADER(Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("InstallFunction", wintypes.DWORD)
    ]

class SP_DEVINFO_DATA(Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("ClassGuid", GUID),
        ("DevInst", wintypes.DWORD),
        ("Reserved", c_void_p)
    ]

class SP_PROPCHANGE_PARAMS(Structure):
    _fields_ = [
        ("ClassInstallHeader", SP_CLASSINSTALL_HEADER),
        ("StateChange", wintypes.DWORD),
        ("Scope", wintypes.DWORD),
        ("HwProfile", wintypes.DWORD)
    ]

class WindowsTouchpadController(TouchpadController):
    def __init__(self):
        super().__init__()
        self._check_admin()
        self._init_api()
        self.hdev = None
        self.dev_info = None
        self._find_touchpad_devices()
    
    def _init_api(self):
        self.setupapi = ctypes.WinDLL('SetupAPI')
        
        # API function definitions
        self.SetupDiGetClassDevs = self.setupapi.SetupDiGetClassDevsW
        self.SetupDiGetClassDevs.argtypes = [POINTER(GUID), wintypes.LPCWSTR, wintypes.HWND, wintypes.DWORD]
        self.SetupDiGetClassDevs.restype = wintypes.HANDLE

        self.SetupDiEnumDeviceInfo = self.setupapi.SetupDiEnumDeviceInfo
        self.SetupDiEnumDeviceInfo.argtypes = [wintypes.HANDLE, wintypes.DWORD, POINTER(SP_DEVINFO_DATA)]
        self.SetupDiEnumDeviceInfo.restype = wintypes.BOOL

        self.SetupDiCallClassInstaller = self.setupapi.SetupDiCallClassInstaller
        self.SetupDiCallClassInstaller.argtypes = [wintypes.DWORD, wintypes.HANDLE, POINTER(SP_DEVINFO_DATA)]
        self.SetupDiCallClassInstaller.restype = wintypes.BOOL

        self.SetupDiGetDeviceRegistryPropertyW = self.setupapi.SetupDiGetDeviceRegistryPropertyW
        self.SetupDiGetDeviceRegistryPropertyW.argtypes = [
            wintypes.HANDLE, 
            POINTER(SP_DEVINFO_DATA),
            wintypes.DWORD,
            POINTER(wintypes.DWORD),
            c_void_p,
            wintypes.DWORD,
            POINTER(wintypes.DWORD)
        ]
        self.SetupDiGetDeviceRegistryPropertyW.restype = wintypes.BOOL
        
        self.SetupDiSetClassInstallParams = self.setupapi.SetupDiSetClassInstallParamsW
        self.SetupDiSetClassInstallParams.argtypes = [
            wintypes.HANDLE,
            POINTER(SP_DEVINFO_DATA),
            c_void_p,
            wintypes.DWORD
        ]
        self.SetupDiSetClassInstallParams.restype = wintypes.BOOL
        
        # Add SetupDiDestroyDeviceInfoList for proper cleanup
        self.SetupDiDestroyDeviceInfoList = self.setupapi.SetupDiDestroyDeviceInfoList
        self.SetupDiDestroyDeviceInfoList.argtypes = [wintypes.HANDLE]
        self.SetupDiDestroyDeviceInfoList.restype = wintypes.BOOL

    def _check_admin(self):
        if ctypes.windll.shell32.IsUserAnAdmin() == 0:
            logger.error("需要管理员权限运行")
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", os.sys.executable, __file__, None, 1
            )
            raise SystemExit

    def _find_touchpad_devices(self):
        # Clean up any existing device handle
        if self.hdev and self.hdev != -1:
            self.SetupDiDestroyDeviceInfoList(self.hdev)
            self.hdev = None
            
        GUID_HIDCLASS = GUID()
        GUID_HIDCLASS.Data1 = 0x745A17A0
        GUID_HIDCLASS.Data2 = 0x74D3
        GUID_HIDCLASS.Data3 = 0x11D0
        GUID_HIDCLASS.Data4 = (0xB6, 0xFE, 0x00, 0xA0, 0xC9, 0x0F, 0x57, 0xDA)
        
        self.hdev = self.SetupDiGetClassDevs(byref(GUID_HIDCLASS), None, None, DIGCF_PRESENT)
        if self.hdev == -1:
            logger.error("获取设备类失败")
            return

        try:
            dev_info = SP_DEVINFO_DATA()
            dev_info.cbSize = ctypes.sizeof(SP_DEVINFO_DATA)
            index = 0
            
            self.dev_info = None
            while True:
                if not self.SetupDiEnumDeviceInfo(self.hdev, index, byref(dev_info)):
                    if ctypes.get_last_error() == 259:  # ERROR_NO_MORE_ITEMS
                        break
                    index += 1
                    continue
                
                buf = (wintypes.WCHAR * 256)()
                buf_size = wintypes.DWORD(256)
                if self.SetupDiGetDeviceRegistryPropertyW(
                    self.hdev,
                    byref(dev_info),
                    SPDRP_DEVICEDESC,
                    None,
                    byref(buf),
                    buf_size,
                    None
                ):
                    hwdesc = buf.value
                    if "触摸板" in hwdesc:
                        # Found touchpad, save a copy of the device info
                        self.dev_info = SP_DEVINFO_DATA()
                        ctypes.memmove(byref(self.dev_info), byref(dev_info), ctypes.sizeof(SP_DEVINFO_DATA))
                        logger.info(f"找到触控板设备: {hwdesc}")
                        break
                index += 1
                
        except Exception as e:
            logger.error(f"查找触控板设备时出错: {e}")
            if self.hdev and self.hdev != -1:
                self.SetupDiDestroyDeviceInfoList(self.hdev)
                self.hdev = None
            
        if not self.dev_info:
            logger.warning("未找到任何触控板设备")
            if self.hdev and self.hdev != -1:
                self.SetupDiDestroyDeviceInfoList(self.hdev)
                self.hdev = None
    
    def toggle(self, enable):
        if not self.hdev or not self.dev_info or self.hdev == -1:
            logger.error("没有有效的触控板设备")
            return False
        
        try:
            # Create the property change parameters
            prop_change_params = SP_PROPCHANGE_PARAMS()
            prop_change_params.ClassInstallHeader.cbSize = ctypes.sizeof(SP_CLASSINSTALL_HEADER)
            prop_change_params.ClassInstallHeader.InstallFunction = DIF_PROPERTYCHANGE
            
            prop_change_params.StateChange = DICS_ENABLE if enable else DICS_DISABLE
            prop_change_params.Scope = DICS_FLAG_GLOBAL
            prop_change_params.HwProfile = 0
            
            # Set the property change parameters
            if not self.SetupDiSetClassInstallParams(
                self.hdev, 
                byref(self.dev_info), 
                byref(prop_change_params), 
                ctypes.sizeof(prop_change_params)
            ):
                error = ctypes.GetLastError()
                logger.error(f"设置触控板属性参数失败，错误码: {error}")
                return False
            
            # Call the class installer
            if not self.SetupDiCallClassInstaller(DIF_PROPERTYCHANGE, self.hdev, byref(self.dev_info)):
                error = ctypes.GetLastError()
                logger.error(f"调用触控板类安装程序失败，错误码: {error}")
                return False
                
            logger.info(f"触控板已{'启用' if enable else '禁用'}")
            return True
            
        except Exception as e:
            logger.error(f"控制触控板时出错: {e}")
            return False
    
    def cleanup(self):
        if self.hdev and self.hdev != -1:
            self.SetupDiDestroyDeviceInfoList(self.hdev)
            self.hdev = None
            self.dev_info = None                  