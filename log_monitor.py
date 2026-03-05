# -*- coding: utf-8 -*-
"""
EVE-LMA 日志文件监控器
负责扫描、打开和实时读取 EVE 战斗日志文件
v3.0: UTF-16 LE 解码修复 + 静默冷启动保护
"""
import os
import re
import time
from datetime import datetime, timedelta

from PyQt5.QtCore import QObject, QTimer, pyqtSignal


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


class LogMonitor(QObject):
    """
    日志监控器：周期性扫描目录、读取新行、检测静默

    v3.0:
    - 静默冷启动保护：启动后不自动倒计时，仅在检测到已勾选角色的
      首行新日志后，才开启 30 秒静默检测。
    """

    new_line = pyqtSignal(str, str, str, str)   # char_name, ts_beijing, raw_line, filepath
    files_changed = pyqtSignal(list)              # [(filepath, char_name)]
    all_silent = pyqtSignal()                     # 全局静默

    def __init__(self, log_path="", parent=None):
        super().__init__(parent)
        self.log_path = log_path
        self.log_files = {}           # filepath -> LogFile
        self.silence_triggered = False
        self.silence_threshold = 30   # 静默阈值（秒）
        self.file_time_window = 60    # 文件发现时间窗口（秒）
        self.has_received_first_line = False  # 冷启动保护

        # 已勾选角色（由 GUI 设置）
        self.checked_chars = set()

        # 定时器
        self.scan_timer = QTimer(self)
        self.scan_timer.timeout.connect(self._scan_directory)

        self.read_timer = QTimer(self)
        self.read_timer.timeout.connect(self._read_all)

        self.silence_timer = QTimer(self)
        self.silence_timer.timeout.connect(self._check_silence)

    def start(self):
        """启动监控"""
        self.has_received_first_line = False
        self._scan_directory()
        self.scan_timer.start(5000)
        self.read_timer.start(500)
        self.silence_timer.start(5000)

    def stop(self):
        """停止监控并释放资源"""
        self.scan_timer.stop()
        self.read_timer.stop()
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

    def _scan_directory(self):
        """扫描日志目录，发现新的活跃日志文件"""
        if not self.log_path or not os.path.isdir(self.log_path):
            return

        now = time.time()
        newly_discovered = set()

        try:
            for fname in os.listdir(self.log_path):
                if not fname.lower().endswith('.txt'):
                    continue
                fpath = os.path.join(self.log_path, fname)
                try:
                    mtime = os.path.getmtime(fpath)
                    if abs(now - mtime) <= self.file_time_window:
                        newly_discovered.add(fpath)
                except OSError:
                    continue
        except OSError:
            return

        changed = False

        # 添加新发现的文件
        for fpath in newly_discovered:
            if fpath not in self.log_files:
                lf = LogFile(fpath)
                if lf.open():
                    self.log_files[fpath] = lf
                    changed = True
                    print(f"[Monitor] 发现新日志: {lf.char_name} -> {fpath}")
                else:
                    # 如果无法打开文件，则跳过
                    continue

        # 清理已删除的文件
        to_remove = []
        for fpath in self.log_files:
            if not os.path.exists(fpath):
                to_remove.append(fpath)
        for fpath in to_remove:
            self.log_files[fpath].close()
            del self.log_files[fpath]
            changed = True

        if changed:
            self.files_changed.emit(self.get_active_files())

    def _read_all(self):
        """读取所有监控文件的新行"""
        for fpath, lf in list(self.log_files.items()):
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