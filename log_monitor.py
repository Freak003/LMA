# -*- coding: utf-8 -*-
"""
EVE-LMA 日志文件监控器
负责扫描、打开和实时读取 EVE 战斗日志文件

v3.2: watchdog 事件驱动 + 2s 回退轮询 + 启动阶段 10 分钟过滤
v3.7: 修复文件句柄泄漏、添加类型注解、改进异常处理、引入 logging
"""
import os
import re
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple

from PyQt5.QtCore import QObject, QTimer, pyqtSignal
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from constants import (
    SILENCE_THRESHOLD, INITIAL_SCAN_WINDOW, POLLING_INTERVAL,
    RETRY_SCAN_INTERVAL, SILENCE_CHECK_INTERVAL, LOG_FILE_EXTENSION,
    LOG_HEADER_MAX_LINES
)
from config_manager import ConfigManager
from logger_config import get_logger

# 获取日志记录器
logger = get_logger('EVE-LMA')


def _detect_encoding(filepath: str) -> str:
    """
    检测 EVE 日志文件编码。
    EVE 日志文件通常使用 UTF-16 LE (带 BOM: FF FE)。
    
    Args:
        filepath: 文件路径
    
    Returns:
        检测到的编码名称
    """
    try:
        with open(filepath, 'rb') as f:
            bom = f.read(2)
            if bom == b'\xff\xfe':
                return 'utf-16-le'
            elif bom == b'\xfe\xff':
                return 'utf-16-be'
        return 'utf-8'
    except (IOError, OSError) as e:
        logger.warning(f"[编码检测] 无法读取文件 {filepath}: {e}")
        return 'utf-8'


class LogFile:
    """
    单个日志文件的状态跟踪
    
    负责文件的打开、读取、关闭以及状态管理。
    """

    def __init__(self, filepath: str) -> None:
        """
        初始化日志文件对象
        
        Args:
            filepath: 日志文件的完整路径
        """
        self.filepath = filepath
        self.file_handle: Optional[object] = None
        self.char_name: str = "Unknown"
        self.session_start: Optional[datetime] = None
        self.last_pos: int = 0
        self.last_activity: float = time.time()
        self.initialized: bool = False
        self.encoding: str = 'utf-8'

    def open(self) -> bool:
        """
        打开日志文件并解析头部信息
        
        Returns:
            是否成功打开
        """
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
        except (IOError, OSError) as e:
            logger.error(f"[LogFile] 打开失败 {self.filepath}: {e}")
            self.initialized = False
            return False
        except PermissionError as e:
            logger.error(f"[LogFile] 权限不足 {self.filepath}: {e}")
            self.initialized = False
            return False

    def _parse_header(self) -> None:
        """
        解析日志文件头部，提取角色名和会话开始时间。
        自动处理 UTF-16 LE BOM 造成的不可见字符。
        """
        if not self.file_handle:
            return
            
        self.file_handle.seek(0)
        for _ in range(LOG_HEADER_MAX_LINES):
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
                except ValueError as e:
                    logger.debug(f"[LogFile] 时间解析失败: {e}")

    def read_new_lines(self) -> List[str]:
        """
        读取自上次以来的所有新行
        
        Returns:
            新行的列表，读取失败返回空列表
        """
        if not self.file_handle:
            return []

        lines: List[str] = []
        try:
            self.file_handle.seek(self.last_pos)
            for line in self.file_handle:
                line = line.rstrip('\n\r')
                if line.strip():
                    lines.append(line)
            self.last_pos = self.file_handle.tell()
            if lines:
                self.last_activity = time.time()
        except (IOError, OSError) as e:
            logger.error(f"[LogFile] 读取失败 {self.filepath}: {e}")
            # 确保关闭并标记为未初始化
            self.close()
            self.initialized = False
        except UnicodeDecodeError as e:
            logger.error(f"[LogFile] 编码错误 {self.filepath}: {e}")
            self.close()
            self.initialized = False

        return lines

    def close(self) -> None:
        """关闭文件句柄"""
        if self.file_handle:
            try:
                self.file_handle.close()
            except (IOError, OSError) as e:
                logger.debug(f"[LogFile] 关闭文件时出错: {e}")
            finally:
                self.file_handle = None

    def __del__(self) -> None:
        """析构时确保文件句柄关闭"""
        self.close()


class _LogEventHandler(FileSystemEventHandler):
    """
    文件系统事件处理器（运行在 watchdog 后台线程）。
    通过 LogMonitor 的 Qt 信号安全转发到主线程。
    """

    def __init__(self, monitor: 'LogMonitor') -> None:
        """
        初始化事件处理器
        
        Args:
            monitor: LogMonitor 实例
        """
        super().__init__()
        self._monitor = monitor

    def on_created(self, event) -> None:
        """文件创建事件"""
        if event.is_directory:
            return
        if event.src_path.lower().endswith(LOG_FILE_EXTENSION):
            self._monitor._sig_file_created.emit(event.src_path)

    def on_modified(self, event) -> None:
        """文件修改事件"""
        if event.is_directory:
            return
        if event.src_path.lower().endswith(LOG_FILE_EXTENSION):
            self._monitor._sig_file_modified.emit(event.src_path)


class LogMonitor(QObject):
    """
    日志监控器：watchdog 事件驱动 + 2s 回退轮询 + 静默定时检测

    v3.2:
    - watchdog 监听文件创建/修改（低延迟）
    - 2 秒回退轮询兜底读取（防止 watchdog 事件丢失）
    - 启动时仅打开最近 10 分钟活跃的日志文件
    - 未找到活跃文件时每 1 分钟重试扫描
    - 静默检测 5 秒定时器 + 冷启动保护
    
    v3.7:
    - 修复文件句柄泄漏
    - 添加类型注解
    - 改进异常处理
    - 引入 logging
    """

    # 日志信号：角色名, 北京时间, 原始行, 文件路径
    new_line = pyqtSignal(str, str, str, str)
    # 文件列表变化信号
    files_changed = pyqtSignal(list)  # List[Tuple[str, str]]
    # 全局静默信号
    all_silent = pyqtSignal()

    # 内部信号：从 watchdog 后台线程转发到 Qt 主线程
    _sig_file_created = pyqtSignal(str)
    _sig_file_modified = pyqtSignal(str)

    def __init__(self, log_path: str = "", config: ConfigManager = None, parent=None) -> None:
        """
        初始化日志监控器
        
        Args:
            log_path: 日志目录路径
            config: 配置管理器实例
            parent: 父对象
        """
        super().__init__(parent)
        self.log_path = log_path
        self.config = config
        self.log_files: Dict[str, LogFile] = {}  # filepath -> LogFile
        self.silence_triggered: bool = False
        self.silence_threshold: int = SILENCE_THRESHOLD
        self.has_received_first_line: bool = False  # 冷启动保护

        # 已勾选角色（由 GUI 设置）
        self.checked_chars: Set[str] = set()

        # watchdog
        self._observer: Optional[Observer] = None
        self._event_handler = _LogEventHandler(self)

        # 内部信号连接（确保在主线程执行）
        self._sig_file_created.connect(self._on_file_created)
        self._sig_file_modified.connect(self._on_file_modified)

        # 回退轮询定时器
        self._read_timer = QTimer(self)
        self._read_timer.timeout.connect(self._read_all)

        # 重试扫描定时器
        self._retry_timer = QTimer(self)
        self._retry_timer.timeout.connect(self._retry_scan)

        # 静默检测定时器
        self.silence_timer = QTimer(self)
        self.silence_timer.timeout.connect(self._check_silence)

    def start(self) -> None:
        """启动监控"""
        self.has_received_first_line = False

        # 初始扫描（仅最近活跃文件）
        self._scan_directory()

        # 如果没找到活跃文件，启动重试定时器
        if not self.log_files:
            logger.info("[Monitor] 未找到活跃日志，将定期重试扫描")
            self._retry_timer.start(RETRY_SCAN_INTERVAL)

        # 启动 watchdog 文件监听
        self._start_observer()

        # 回退轮询
        self._read_timer.start(POLLING_INTERVAL)

        # 静默定时器
        self.silence_timer.start(SILENCE_CHECK_INTERVAL)

    def stop(self) -> None:
        """停止监控并释放资源"""
        self._stop_observer()
        self._read_timer.stop()
        self._retry_timer.stop()
        self.silence_timer.stop()

        # 关闭所有日志文件
        for lf in self.log_files.values():
            lf.close()
        self.log_files.clear()

    def set_path(self, path: str) -> None:
        """
        更换日志路径并重新开始监控
        
        Args:
            path: 新的日志目录路径
        """
        self.stop()
        self.log_path = path
        self.silence_triggered = False
        self.has_received_first_line = False
        self.start()

    def set_checked_chars(self, char_names: List[str]) -> None:
        """
        设置当前已勾选的角色集合
        
        Args:
            char_names: 角色名列表
        """
        self.checked_chars = set(char_names)

    def get_active_files(self) -> List[Tuple[str, str]]:
        """
        返回当前监控的文件列表
        
        Returns:
            文件路径和角色名的元组列表
        """
        return [(fp, lf.char_name) for fp, lf in self.log_files.items()]

    def _start_observer(self) -> None:
        """启动 watchdog 目录监听"""
        if not self.log_path or not os.path.isdir(self.log_path):
            return
        self._stop_observer()
        
        self._observer = Observer()
        self._observer.schedule(self._event_handler, self.log_path, recursive=False)
        self._observer.daemon = True
        self._observer.start()
        logger.debug(f"[Monitor] watchdog 监听启动: {self.log_path}")

    def _stop_observer(self) -> None:
        """停止 watchdog"""
        if self._observer:
            try:
                self._observer.stop()
                self._observer.join(timeout=2)
            except Exception as e:
                logger.debug(f"[Monitor] 停止 watchdog 时出错: {e}")
            finally:
                self._observer = None

    def _on_file_created(self, fpath: str) -> None:
        """
        新文件创建事件处理
        
        Args:
            fpath: 新创建的文件路径
        """
        fpath = os.path.normpath(fpath)
        if fpath in self.log_files:
            return
            
        lf = LogFile(fpath)
        if lf.open():
            self.log_files[fpath] = lf
            logger.info(f"[Monitor] 发现新日志: {lf.char_name} -> {fpath}")
            self.files_changed.emit(self.get_active_files())
            # 新文件可能已有内容，立即读取一次
            self._read_file(fpath)

    def _on_file_modified(self, fpath: str) -> None:
        """
        文件修改事件处理
        
        Args:
            fpath: 被修改的文件路径
        """
        fpath = os.path.normpath(fpath)
        if fpath in self.log_files:
            self._read_file(fpath)
        elif fpath.lower().endswith(LOG_FILE_EXTENSION):
            # 可能是之前未跟踪的文件被修改，尝试打开
            self._on_file_created(fpath)

    def _read_file(self, fpath: str) -> None:
        """
        读取指定文件的新行
        
        Args:
            fpath: 文件路径
        """
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
                    self.has_received_first_line = True

            if lines:
                self.silence_triggered = False
        except Exception as e:
            logger.error(f"[Monitor] 读取文件出错 {fpath}: {e}")

    def _scan_directory(self) -> None:
        """扫描目录，仅打开最近活跃的日志文件"""
        if not self.log_path or not os.path.isdir(self.log_path):
            return

        cutoff = time.time() - INITIAL_SCAN_WINDOW
        changed = False
        
        try:
            for fname in os.listdir(self.log_path):
                if not fname.lower().endswith(LOG_FILE_EXTENSION):
                    continue
                    
                fpath = os.path.normpath(os.path.join(self.log_path, fname))
                if fpath in self.log_files:
                    continue
                    
                # 只打开最近活跃的文件
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
                    logger.info(f"[Monitor] 发现活跃日志: {lf.char_name} -> {fpath}")
        except OSError as e:
            logger.error(f"[Monitor] 扫描目录失败: {e}")
            return

        if changed:
            self.files_changed.emit(self.get_active_files())

    def _retry_scan(self) -> None:
        """启动阶段重试扫描，找到活跃文件后自动停止"""
        logger.debug("[Monitor] 重试扫描活跃日志...")
        self._scan_directory()
        if self.log_files:
            self._retry_timer.stop()
            logger.info(f"[Monitor] 已找到 {len(self.log_files)} 个活跃日志，停止重试")

    def _read_all(self) -> None:
        """回退轮询：读取所有已跟踪文件的新行"""
        for fpath in list(self.log_files.keys()):
            self._read_file(fpath)

    def _extract_beijing_time(self, line: str) -> str:
        """
        从日志行中提取 UTC 时间并转为北京时间 (UTC+8)
        
        Args:
            line: 日志行内容
        
        Returns:
            北京时间字符串 (HH:MM:SS) 或空字符串
        """
        ts_match = re.match(r'\[\s*(\d{4}\.\d{2}\.\d{2}\s+\d{2}:\d{2}:\d{2})\s*\]', line)
        if ts_match:
            try:
                utc_time = datetime.strptime(ts_match.group(1), '%Y.%m.%d %H:%M:%S')
                beijing_time = utc_time + timedelta(hours=8)
                return beijing_time.strftime('%H:%M:%S')
            except ValueError:
                pass
        return ""

    def _check_silence(self) -> None:
        """全局静默检测 + 冷启动保护 + 分组检测"""
        if not self.log_files:
            return

        if not self.has_received_first_line:
            return

        now = time.time()
        
        # 检查是否启用分组检测
        if self.config and self.config.is_silence_by_group():
            # 分组检测模式：按组检查静默
            self._check_silence_by_group(now)
        else:
            # 传统模式：检查所有勾选的角色
            self._check_silence_traditional(now)

    def _check_silence_traditional(self, now: float) -> None:
        """传统静默检测：检查所有勾选的角色"""
        all_silent = True
        silent_chars: List[str] = []

        # 检查所有勾选的角色是否都静默了
        for lf in self.log_files.values():
            if not self.checked_chars or lf.char_name in self.checked_chars:
                time_since_activity = now - lf.last_activity
                if time_since_activity <= self.silence_threshold:
                    # 至少有一个勾选的角色还在活动
                    all_silent = False
                    break
                else:
                    silent_chars.append(lf.char_name)

        # 如果所有勾选的角色都超过了静默阈值，且还没有触发过静默
        if all_silent and silent_chars and not self.silence_triggered:
            self.silence_triggered = True
            self.all_silent.emit()

    def _check_silence_by_group(self, now: float) -> None:
        """分组静默检测：按组检查，任意组全部静默即触发"""
        if not self.config:
            return
            
        # 获取所有角色分组
        char_groups = self.config.get_char_groups()
        if not char_groups:
            # 没有分组配置，回退到传统模式
            self._check_silence_traditional(now)
            return
        
        # 按组统计静默情况
        group_status: Dict[str, Dict[str, any]] = {}
        
        for lf in self.log_files.values():
            # 只检查勾选的角色
            if self.checked_chars and lf.char_name not in self.checked_chars:
                continue
                
            # 获取角色所在组
            group_name = char_groups.get(lf.char_name)
            if not group_name:
                # 没有分组的角色，归入"未分组"
                group_name = "未分组"
            
            if group_name not in group_status:
                group_status[group_name] = {
                    'chars': [],
                    'active_count': 0,
                    'silent_chars': []
                }
            
            group_status[group_name]['chars'].append(lf.char_name)
            time_since_activity = now - lf.last_activity
            
            if time_since_activity <= self.silence_threshold:
                group_status[group_name]['active_count'] += 1
            else:
                group_status[group_name]['silent_chars'].append(lf.char_name)
        
        # 检查是否有任意组全部静默
        for group_name, status in group_status.items():
            if status['chars'] and status['active_count'] == 0:
                # 该组所有角色都静默了
                if status['silent_chars'] and not self.silence_triggered:
                    logger.info(f"[Silence] 组 '{group_name}' 全部静默，触发警报")
                    self.silence_triggered = True
                    self.all_silent.emit()
                    return
        
        # 也检查未勾选角色但不在分组里的情况（回退）
        if not group_status and not self.silence_triggered:
            self._check_silence_traditional(now)