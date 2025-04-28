# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

# 分析阶段
a = Analysis(
    ['src/main.py'],
    pathex=[],
    binaries=[],
    datas=[], 
    hiddenimports=['pynput.keyboard._win32', 'pynput.mouse._win32', 'PIL._tkinter_finder'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# 创建EXE文件，但不包含资源文件
exe = EXE(
    pyz,
    a.scripts,
    [],  # 不包含二进制文件
    exclude_binaries=True,  # 重要：设置为True以分离文件
    name='betterTouchpad',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='src/resources/setting_icon.ico',
)

# 创建集合文件夹，包含exe和所有其他必要文件
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    # 添加资源和配置文件为独立文件
    # 它们会被复制到dist目录，但不会打包到exe内部
    strip=False,
    upx=True,
    upx_exclude=[],
    name='betterTouchpad',
)

# 将资源文件和配置文件单独复制到输出目录
# 这一步会在COLLECT之后执行，确保文件在最终的发布包中
import shutil
import os

def copy_external_files():
    # 确保dist目录存在
    os.makedirs('dist/betterTouchpad/resources', exist_ok=True)
    
    # 复制resources目录
    src_resources = 'src/resources'
    dst_resources = 'dist/betterTouchpad/resources'
    
    # 复制resources中的所有文件
    for file in os.listdir(src_resources):
        src_file = os.path.join(src_resources, file)
        dst_file = os.path.join(dst_resources, file)
        if os.path.isfile(src_file):
            shutil.copy2(src_file, dst_file)
            print(f"Copied: {src_file} -> {dst_file}")
    
    # 复制configure.json
    shutil.copy2('src/configure.json', 'dist/betterTouchpad/configure.json')
    print("Copied: src/configure.json -> dist/betterTouchpad/configure.json")

# 注册PyInstaller钩子来执行复制
copy_external_files()