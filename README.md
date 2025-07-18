# ~~betterTouchpad~~
已停止开发, 目前仅能在Windows系统下使用, 且仅支持功能键绑定。
考虑使用[rust重构](https://github.com/NIyueeE/Enable-Touchpad)

<br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br>

============================================================================================================================================================================================================================
基于热键的触控板控制工具，主要支持Windows系统。

## 功能特性

- 通过热键快速切换触控板启用/禁用状态
- 支持长按模式和切换模式两种工作方式
- 可自定义热键和鼠标点击按键
- 鼠标指示器提供视觉反馈
- Windows系统完整支持（Linux支持开发中，尚未完成测试）

## 配置说明

配置文件位于`src/configure.json`，可设置以下参数：

```json
{
    "response_time": 0.2,     // 长按响应时间（秒）
    "hot_key": "f1",          // 触发键
    "left_click": "f2",       // 左键点击对应按键
    "right_click": "f3",      // 右键点击对应按键
    "mode": 0                 // 模式：0为长按模式, 1为切换模式
}
```

## 使用方法

1. 运行程序：`python ./src/main.py`, linux需要`sudo`且不支持设置窗口
2. 长按模式下，长按触发键进入触控板模式，释放触发键退出
3. 切换模式下，按下触发键切换触控板模式状态
4. 在触控板模式下，使用配置的按键模拟鼠标点击

## 运行环境要求
- 可能还有其他的。。。
- Python 3.6+
- 依赖库：
  - tkinter
  - pynput
  - pyautogui
  - PIL (Pillow)

## 开发状态

- [x] Windows11平台支持
- [x] 视觉反馈指示器
- [x] Ubuntu平台xrog桌面环境支持, 但是光标指示器显示有问题
- [ ] 多语言支持
