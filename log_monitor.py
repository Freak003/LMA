# -*- coding: utf-8 -*-
import os
import re
import time
from datetime import datetime, timedelta

from PyQt5.QtCore import QObject, QTimer, pyqtSignal, QMutex, QMutexLocker
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

def _detect_encoding(filepath):
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
    def __init__(self, filepath):
        self.filepath = filepath
        self.file_handle = None
        self.char_name = "Unknown"
        self.session_start = None
        self.last_pos = 0
        self.last_activity = time.monotonic() # 优化：使用单调时间
        self.initialized = False
        self.encoding = 'utf-8'

    def open(self):
        try:
            self.encoding = _detect_encoding(self.filepath)
            self.file_handle = open(self.filepath, 'r',
                                     encoding=self.encoding,
                                     errors='replace')
            self._parse_header()
            self.file_handle.seek(0, 2)
            self.last_pos = self.file_handle.tell()
            self.initialized = True
            return True
        except Exception as e:
            print(f"[LogFile] 打开失败 {self.filepath}: {e}")
            return False

    def _parse_header(self):
        self.file_handle.seek(0)
        for _ in range(20):
            line = self.file_handle.readline()
            if not line:
                break
            line = line.strip().replace('\ufeff', '').replace('\x00', '')
            listener_match = re.search(r'(?:收听者|Listener)\s*[:：]\s*(.+)', line)
            if listener_match:
                self.char_name = listener_match.group(1).strip()
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
                self.last_activity = time.monotonic()
        except Exception as e:
            print(f"[LogFile] 读取失败 {self.filepath}: {e}")
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
        if self.file_handle:
            try:
                self.file_handle.close()
            except Exception:
                pass
            self.file_handle = None

    def __del__(self):
        self.close()

class _LogEventHandler(FileSystemEventHandler):
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
    new_line = pyqtSignal(str, str, str, str)
    files_changed = pyqtSignal(list)
    all_silent = pyqtSignal()

    _sig_file_created = pyqtSignal(str)
    _sig_file_modified = pyqtSignal(str)

    def __init__(self, log_path="", parent=None):
        super().__init__(parent)
        self.log_path = log_path
        self.log_files = {}
        self.silence_triggered = False
        self.silence_threshold = 30
        self.has_received_first_line = False
        self.checked_chars = set()

        self._observer = None
        self._event_handler = _LogEventHandler(self)
        self._read_lock = QMutex() # 优化：并发读取锁

        self._sig_file_created.connect(self._on_file_created)
        self._sig_file_modified.connect(self._on_file_modified)

        self._read_timer = QTimer(self)
        self._read_timer.timeout.connect(self._read_all)

        self._retry_timer = QTimer(self)
        self._retry_timer.timeout.connect(self._retry_scan)

        self.silence_timer = QTimer(self)
        self.silence_timer.timeout.connect(self._check_silence)

    def start(self):
        self.has_received_first_line = False
        self._scan_directory()
        if not self.log_files:
            print("[Monitor] 未找到活跃日志，将每 60 秒重试扫描")
            self._retry_timer.start(60_000)
        self._start_observer()
        self._read_timer.start(2000)
        self.silence_timer.start(5000)

    def stop(self):
        self._stop_observer()
        self._read_timer.stop()
        self._retry_timer.stop()
        self.silence_timer.stop()
        for lf in self.log_files.values():
            lf.close()
        self.log_files.clear()

    def set_path(self, path):
        self.stop()
        self.log_path = path
        self.silence_triggered = False
        self.has_received_first_line = False
        self.start()

    def set_checked_chars(self, char_names):
        self.checked_chars = set(char_names)

    def get_active_files(self):
        return [(fp, lf.char_name) for fp, lf in self.log_files.items()]

    def _start_observer(self):
        if not self.log_path or not os.path.isdir(self.log_path):
            return
        self._stop_observer()
        self._observer = Observer()
        self._observer.schedule(self._event_handler, self.log_path, recursive=False)
        self._observer.daemon = True
        self._observer.start()
        print(f"[Monitor] watchdog 监听启动: {self.log_path}")

    def _stop_observer(self):
        if self._observer:
            try:
                self._observer.stop()
                self._observer.join(timeout=2)
            except Exception:
                pass
            self._observer = None

    def _on_file_created(self, fpath):
        fpath = os.path.normpath(fpath)
        if fpath in self.log_files:
            return
        lf = LogFile(fpath)
        if lf.open():
            self.log_files[fpath] = lf
            print(f"[Monitor] 发现新日志: {lf.char_name} -> {fpath}")
            self.files_changed.emit(self.get_active_files())
            self._read_file(fpath)

    def _on_file_modified(self, fpath):
        fpath = os.path.normpath(fpath)
        if fpath in self.log_files:
            self._read_file(fpath)
        elif fpath.lower().endswith('.txt'):
            self._on_file_created(fpath)

    def _read_file(self, fpath):
        with QMutexLocker(self._read_lock):  # 优化：防止 watchdog 和回退定时器发生竞态读取
            lf = self.log_files.get(fpath)
            if not lf:
                return
            try:
                lines = lf.read_new_lines()
                for line in lines:
                    ts_beijing = self._extract_beijing_time(line)
                    self.new_line.emit(lf.char_name, ts_beijing, line, fpath)
                    if not self.has_received_first_line:
                        self.has_received_first_line = True
                if lines:
                    self.silence_triggered = False
            except Exception as e:
                print(f"[Monitor] 读取文件出错 {fpath}: {e}")

    def _scan_directory(self):
        if not self.log_path or not os.path.isdir(self.log_path):
            return

        cutoff = time.time() - 600
        changed = False
        try:
            for fname in os.listdir(self.log_path):
                if not fname.lower().endswith('.txt'):
                    continue
                fpath = os.path.normpath(os.path.join(self.log_path, fname))
                if fpath in self.log_files:
                    continue
                try:
                    mtime = os.path.getmtime(fpath)
                except OSError:
                    continue
                if mtime < cutoff:
                    continue
                lf = LogFile(fpath)
                if lf.open():
                    self.log_files[fpath] = lf
                    changed = True
                    print(f"[Monitor] 发现活跃日志: {lf.char_name} -> {fpath}")
        except OSError:
            return

        if changed:
            self.files_changed.emit(self.get_active_files())

    def _retry_scan(self):
        print("[Monitor] 重试扫描活跃日志...")
        self._scan_directory()
        if self.log_files:
            self._retry_timer.stop()
            print(f"[Monitor] 已找到 {len(self.log_files)} 个活跃日志，停止重试")

    def _read_all(self):
        for fpath in list(self.log_files.keys()):
            self._read_file(fpath)

    def _extract_beijing_time(self, line):
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
        if not self.log_files or not self.has_received_first_line:
            return
        
        now = time.monotonic() # 优化：使用单调时间
        all_silent = True
        silent_chars = []

        for lf in self.log_files.values():
            if not self.checked_chars or lf.char_name in self.checked_chars:
                time_since_activity = now - lf.last_activity
                if time_since_activity <= self.silence_threshold:
                    all_silent = False
                    break
                else:
                    silent_chars.append(lf.char_name)

        if all_silent and silent_chars and not self.silence_triggered:
            self.silence_triggered = True
            self.all_silent.emit()