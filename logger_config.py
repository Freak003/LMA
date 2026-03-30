# -*- coding: utf-8 -*-
"""
EVE-LMA 日志配置模块
提供统一的日志记录器配置
"""
import logging
import os
import sys
from datetime import datetime
from typing import Optional


def get_base_path() -> str:
    """返回程序运行基础路径（兼容 PyInstaller 打包）"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def setup_logger(
    name: str = 'EVE-LMA',
    log_file: Optional[str] = None,
    console_level: int = logging.INFO,
    file_level: int = logging.DEBUG
) -> logging.Logger:
    """
    配置并返回日志记录器
    
    Args:
        name: 日志记录器名称
        log_file: 日志文件路径（可选，不提供则仅输出到控制台）
        console_level: 控制台日志级别
        file_level: 文件日志级别
    
    Returns:
        配置好的日志记录器
    """
    logger = logging.getLogger(name)
    
    # 避免重复添加处理器
    if logger.handlers:
        return logger
    
    logger.setLevel(logging.DEBUG)
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    console_format = logging.Formatter('[%(levelname)s] %(message)s')
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)
    
    # 文件处理器（可选）
    if log_file:
        try:
            # 确保日志目录存在
            log_dir = os.path.dirname(log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir)
            
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(file_level)
            file_format = logging.Formatter(
                '%(asctime)s [%(levelname)s] [%(filename)s:%(lineno)d] %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(file_format)
            logger.addHandler(file_handler)
        except (IOError, PermissionError) as e:
            logger.warning(f"无法创建日志文件: {e}")
    
    return logger


def get_logger(module_name: str = 'EVE-LMA') -> logging.Logger:
    """
    获取已配置的日志记录器
    
    Args:
        module_name: 模块名称
    
    Returns:
        日志记录器实例
    """
    return logging.getLogger(module_name)


# 模块级日志记录器（延迟初始化）
_logger: Optional[logging.Logger] = None


def init_logging(log_to_file: bool = False) -> logging.Logger:
    """
    初始化全局日志系统
    
    Args:
        log_to_file: 是否输出到文件
    
    Returns:
        日志记录器实例
    """
    global _logger
    
    log_file = None
    if log_to_file:
        base_path = get_base_path()
        log_dir = os.path.join(base_path, 'logs')
        log_file = os.path.join(log_dir, f'eve-lma-{datetime.now().strftime("%Y%m%d")}.log')
    
    _logger = setup_logger('EVE-LMA', log_file=log_file)
    return _logger


def log_debug(message: str) -> None:
    """记录调试日志"""
    global _logger
    if _logger:
        _logger.debug(message)


def log_info(message: str) -> None:
    """记录信息日志"""
    global _logger
    if _logger:
        _logger.info(message)


def log_warning(message: str) -> None:
    """记录警告日志"""
    global _logger
    if _logger:
        _logger.warning(message)


def log_error(message: str) -> None:
    """记录错误日志"""
    global _logger
    if _logger:
        _logger.error(message)