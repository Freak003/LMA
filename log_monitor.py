# -*- coding: utf-8 -*-
"""
EVE-LMA 日志文件监控器
负责扫描、打开和实时读取 EVE 战斗日志文件
v3.1: watchdog 文件系统事件驱动 + 静默冷启动保护
"""
import os
import re
import time
from datetime import datetime, timedelta

from PyQt5.QtCore import QObject, QTimer, pyqtSignal
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


def _detect_encoding(filepath):
    """
    检测 EVE 日志文件编码。
    EVE 日志文件通常使用 UTF-16 LE (带 BOM: FF FE)。
    """
    try:
        with open(filepath, 'rb') as f:
            bom = f.read(2)
            if bom == b'\xff\xfe':
                return 'utf-16-le'
            elif bom == b'\xfe\xff':
                return 'utf-16-be'
        return 'utf-8'
    except Exception:
        return 'utf-8'


class LogFile:
    """单个日志文件的状态跟踪"""

    def __init__(self, filepath):
        self.filepath = filepath
        self.file_handle = None
        self.char_name = "Unknown"
        self.session_start = None
        self.last_pos = 0
        self.last_activity = time.time()
        self.initialized = False
        self.encoding = 'utf-8'

    def open(self):
        """打开日志文件并解析头部信息"""
        try:
            self.encoding = _detect_encoding(self.filepath)
            self.file_handle = open(self.filepath, 'r',
                                     encoding=self.encoding,
                                     errors='replace')
            self._parse_header()
            # 移动到文件末尾，只监控新增内容
            self.file_handle.seek(0, 2)
            self.last_pos = self.file_handle.tell()
            self.initialized = True
            return True
        except Exception as e:
            print(f"[LogFile] 打开失败 {self.filepath}: {e}")
            return False

    def _parse_header(self):
        """
        解析日志文件头部，提取角色名和会话开始时间。
        自动处理 UTF-16 LE BOM 造成的不可见字符。
        """
        self.file_handle.seek(0)
        for _ in range(20):
            line = self.file_handle.readline()
            if not line:
                break

            # 清除 BOM 残余和不可见字符
            line = line.strip().replace('\ufeff', '').replace('\x00', '')

            # 匹配 "收听者:" 或 "Listener:"（兼容中英文冒号）
            listener_match = re.search(r'(?:收听者|Listener)\s*[:：]\s*(.+)', line)
            if listener_match:
                self.char_name = listener_match.group(1).strip()

            # 匹配会话开始时间
            time_match = re.search(
                r'(?:进拦开始|会话开始|Session [Ss]tarted)\s*[:：]\s*'
                r'(\d{4}\.\d{2}\.\d{2}\s+\d{2}:\d{2}:\d{2})',
                line
            )
            if time_match:
                try:
                    self.session_start = datetime.strptime(
                        time_match.group(1), '%Y.%m.%d %H:%M:%S'
                    )
                except ValueError:
                    pass

    def read_new_lines(self):
        """读取自上次以来的所有新行"""
        if not self.file_handle:
            return []

        lines = []
        try:
            self.file_handle.seek(self.last_pos)
            for line in self.file_handle:
                line = line.rstrip('\n\r')
                if line.strip():
                    lines.append(line)
            self.last_pos = self.file_handle.tell()
            if lines:
                self.last_activity = time.time()
        except Exception as e:
            print(f"[LogFile] 读取失败 {self.filepath}: {e}")
            # 尝试重新打开文件
            try:
                self.file_handle.close()
                self.encoding = _detect_encoding(self.filepath)
                self.file_handle = open(self.filepath, 'r',
                                         encoding=self.encoding,
                                         errors='replace')
                self.file_handle.seek(self.last_pos)
            except Exception:
                pass

        return lines

    def close(self):
        """关闭文件句柄"""
        if self.file_handle:
            try:
                self.file_handle.close()
            except Exception:
                pass
            self.file_handle = None

    def __del__(self):
        self.close()


# ── watchdog 事件处理器 ──

class _LogEventHandler(FileSystemEventHandler):
    """
    文件系统事件处理器（运行在 watchdog 后台线程）。
    通过 LogMonitor 的 Qt 信号安全转发到主线程。
    """

    def __init__(self, monitor):
        super().__init__()
        self._monitor = monitor

    def on_created(self, event):
        if event.is_directory:
            return
        if event.src_path.lower().endswith('.txt'):
            self._monitor._sig_file_created.emit(event.src_path)

    def on_modified(self, event):
        if event.is_directory:
            return
        if event.src_path.lower().endswith('.txt'):
            self._monitor._sig_file_modified.emit(event.src_path)


class LogMonitor(QObject):
    """
    日志监控器：watchdog 事件驱动 + 静默定时检测

    v3.1:
    - 文件创建/修改由 watchdog 事件驱动（替代轮询）
    - 启动时做一次初始全目录扫描
    - 静默检测保留 5 秒定时器（超时逻辑）
    - 冷启动保护不变
    """

    new_line = pyqtSignal(str, str, str, str)   # char_name, ts_beijing, raw_line, filepath
    files_changed = pyqtSignal(list)              # [(filepath, char_name)]
    all_silent = pyqtSignal()                     # 全局静默

    # 内部信号：从 watchdog 后台线程转发到 Qt 主线程
    _sig_file_created = pyqtSignal(str)
    _sig_file_modified = pyqtSignal(str)

    def __init__(self, log_path="", parent=None):
        super().__init__(parent)
        self.log_path = log_path
        self.log_files = {}           # filepath -> LogFile
        self.silence_triggered = False
        self.silence_threshold = 30   # 静默阈值（秒）
        self.has_received_first_line = False  # 冷启动保护

        # 已勾选角色（由 GUI 设置）
        self.checked_chars = set()

        # watchdog
        self._observer = None
        self._event_handler = _LogEventHandler(self)

        # 内部信号连接（确保在主线程执行）
        self._sig_file_created.connect(self._on_file_created)
        self._sig_file_modified.connect(self._on_file_modified)

        # 静默检测定时器（保留：超时逻辑需要周期性检查）
        self.silence_timer = QTimer(self)
        self.silence_timer.timeout.connect(self._check_silence)

    def start(self):
        """启动监控"""
        self.has_received_first_line = False

        # 初始全目录扫描
        self._scan_directory()

        # 启动 watchdog 文件监听
        self._start_observer()

        # 静默定时器
        self.silence_timer.start(5000)

    def stop(self):
        """停止监控并释放资源"""
        self._stop_observer()
        self.silence_timer.stop()

        # 关闭所有日志文件
        for lf in self.log_files.values():
            lf.close()
        self.log_files.clear()

    def set_path(self, path):
        """更换日志路径并重新开始监控"""
        self.stop()
        self.log_path = path
        self.silence_triggered = False
        self.has_received_first_line = False
        self.start()

    def set_checked_chars(self, char_names):
        """设置当前已勾选的角色集合"""
        self.checked_chars = set(char_names)

    def get_active_files(self):
        """返回当前监控的文件列表"""
        return [(fp, lf.char_name) for fp, lf in self.log_files.items()]

    # ── watchdog 控制 ──

    def _start_observer(self):
        """启动 watchdog 目录监听"""
        if not self.log_path or not os.path.isdir(self.log_path):
            return
        self._stop_observer()
        self._observer = Observer()
        self._observer.schedule(self._event_handler, self.log_path, recursive=False)
        self._observer.daemon = True
        self._observer.start()
        print(f"[Monitor] watchdog 监听启动: {self.log_path}")

    def _stop_observer(self):
        """停止 watchdog"""
        if self._observer:
            try:
                self._observer.stop()
                self._observer.join(timeout=2)
            except Exception:
                pass
            self._observer = None

    # ── 事件回调（主线程） ──

    def _on_file_created(self, fpath):
        """新文件创建 → 打开并跟踪"""
        fpath = os.path.normpath(fpath)
        if fpath in self.log_files:
            return
        lf = LogFile(fpath)
        if lf.open():
            self.log_files[fpath] = lf
            print(f"[Monitor] 发现新日志: {lf.char_name} -> {fpath}")
            self.files_changed.emit(self.get_active_files())
            # 新文件可能已有内容，立即读取一次
            self._read_file(fpath)

    def _on_file_modified(self, fpath):
        """文件修改 → 读取新行"""
        fpath = os.path.normpath(fpath)
        if fpath in self.log_files:
            self._read_file(fpath)
        elif fpath.lower().endswith('.txt'):
            # 可能是之前未跟踪的文件被修改，尝试打开
            self._on_file_created(fpath)

    # ── 读取逻辑 ──

    def _read_file(self, fpath):
        """读取指定文件的新行"""
        lf = self.log_files.get(fpath)
        if not lf:
            return
        try:
            lines = lf.read_new_lines()
            for line in lines:
                ts_beijing = self._extract_beijing_time(line)
                self.new_line.emit(lf.char_name, ts_beijing, line, fpath)

                # 冷启动保护：首行日志到达后开启静默计时
                if not self.has_received_first_line:
                    if not self.checked_chars or lf.char_name in self.checked_chars:
                        self.has_received_first_line = True

            if lines:
                self.silence_triggered = False
        except Exception as e:
            print(f"[Monitor] 读取文件出错 {fpath}: {e}")

    def _scan_directory(self):
        """初始全目录扫描，发现已有的活跃日志文件"""
        if not self.log_path or not os.path.isdir(self.log_path):
            return

        changed = False
        try:
            for fname in os.listdir(self.log_path):
                if not fname.lower().endswith('.txt'):
                    continue
                fpath = os.path.normpath(os.path.join(self.log_path, fname))
                if fpath not in self.log_files:
                    lf = LogFile(fpath)
                    if lf.open():
                        self.log_files[fpath] = lf
                        changed = True
                        print(f"[Monitor] 发现新日志: {lf.char_name} -> {fpath}")
        except OSError:
            return

        if changed:
            self.files_changed.emit(self.get_active_files())

    def _extract_beijing_time(self, line):
        """从日志行中提取 UTC 时间并转为北京时间 (UTC+8)"""
        ts_match = re.match(r'\[\s*(\d{4}\.\d{2}\.\d{2}\s+\d{2}:\d{2}:\d{2})\s*\]', line)
        if ts_match:
            try:
                utc_time = datetime.strptime(ts_match.group(1), '%Y.%m.%d %H:%M:%S')
                beijing_time = utc_time + timedelta(hours=8)
                return beijing_time.strftime('%H:%M:%S')
            except ValueError:
                pass
        return ""

    def _check_silence(self):
        """
        全局静默检测 + 冷启动保护
        必须已收到过首行新日志才启动检测
        """
        if not self.log_files:
            return

        if not self.has_received_first_line:
            return

        now = time.time()

        # 检查所有勾选的角色是否都静默了
        active_checked_chars = []
        for lf in self.log_files.values():
            if not self.checked_chars or lf.char_name in self.checked_chars:
                time_since_activity = now - lf.last_activity
                if time_since_activity <= self.silence_threshold:
                    # 至少有一个勾选的角色还在活动
                    return
                else:
                    active_checked_chars.append(lf.char_name)

        # 如果所有勾选的角色都超过了静默阈值，且还没有触发过静默
        if active_checked_chars and not self.silence_triggered:
            self.silence_triggered = True
            self.all_silent.emit()