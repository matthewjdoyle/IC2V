import sys
import ctypes
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget
from PySide6.QtGui import QColor

app = QApplication(sys.argv)
window = QMainWindow()
window.resize(400, 300)
window.setStyleSheet("QMainWindow { background: #090B0E; }")

DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_CAPTION_COLOR = 35

hwnd = window.winId()

# Enable dark mode first to get the text white
set_window_attribute = ctypes.windll.dwmapi.DwmSetWindowAttribute
set_window_attribute.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32]
set_window_attribute.restype = ctypes.c_int32

dark_mode = ctypes.c_int(1)
set_window_attribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(dark_mode), ctypes.sizeof(dark_mode))

# Set caption color
# 0x00bbggrr -> 0x000E0B09 for #090B0E
caption_color = ctypes.c_int(0x000E0B09)
set_window_attribute(hwnd, DWMWA_CAPTION_COLOR, ctypes.byref(caption_color), ctypes.sizeof(caption_color))

window.show()
print("Success")
