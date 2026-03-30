# -*- coding: utf-8 -*-
"""
EVE-LMA 日志监控器单元测试
"""
import os
import tempfile
import pytest

from log_monitor import _detect_encoding, LogFile


class TestDetectEncoding:
    """编码检测测试"""

    def test_detect_utf16_le(self, tmp_path):
        """测试 UTF-16 LE 编码检测"""
        filepath = tmp_path / "test_utf16le.txt"
        # 写入 UTF-16 LE BOM
        with open(filepath, 'wb') as f:
            f.write(b'\xff\xfe')
            f.write('test'.encode('utf-16-le'))
        
        result = _detect_encoding(str(filepath))
        assert result == 'utf-16-le'

    def test_detect_utf16_be(self, tmp_path):
        """测试 UTF-16 BE 编码检测"""
        filepath = tmp_path / "test_utf16be.txt"
        # 写入 UTF-16 BE BOM
        with open(filepath, 'wb') as f:
            f.write(b'\xfe\xff')
            f.write('test'.encode('utf-16-be'))
        
        result = _detect_encoding(str(filepath))
        assert result == 'utf-16-be'

    def test_detect_utf8_no_bom(self, tmp_path):
        """测试无 BOM 的 UTF-8 编码检测"""
        filepath = tmp_path / "test_utf8.txt"
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('test content')
        
        result = _detect_encoding(str(filepath))
        assert result == 'utf-8'

    def test_detect_nonexistent_file(self):
        """测试不存在的文件编码检测"""
        result = _detect_encoding('/nonexistent/file.txt')
        assert result == 'utf-8'  # 返回默认值


class TestLogFile:
    """LogFile 类测试"""

    def test_log_file_init(self):
        """测试 LogFile 初始化"""
        lf = LogFile("/path/to/file.txt")
        assert lf.filepath == "/path/to/file.txt"
        assert lf.file_handle is None
        assert lf.char_name == "Unknown"
        assert lf.initialized == False

    def test_log_file_close(self, tmp_path):
        """测试 LogFile 关闭"""
        filepath = tmp_path / "test.txt"
        filepath.write_text("test content", encoding='utf-8')
        
        lf = LogFile(str(filepath))
        lf.open()
        assert lf.file_handle is not None
        
        lf.close()
        assert lf.file_handle is None

    def test_log_file_context_cleanup(self, tmp_path):
        """测试 LogFile 析构时资源清理"""
        filepath = tmp_path / "test.txt"
        filepath.write_text("test content", encoding='utf-8')
        
        lf = LogFile(str(filepath))
        lf.open()
        file_handle = lf.file_handle
        
        # 删除对象，触发 __del__
        del lf
        
        # 文件句柄应该被关闭
        # 注意：__del__ 调用时机不确定，这里只是确保不会抛出异常


class TestLogFileReadNewLines:
    """LogFile.read_new_lines 测试"""

    def test_read_new_lines_empty_file(self, tmp_path):
        """测试读取空文件"""
        filepath = tmp_path / "empty.txt"
        filepath.write_text("", encoding='utf-8')
        
        lf = LogFile(str(filepath))
        lf.open()
        lines = lf.read_new_lines()
        
        assert lines == []
        lf.close()

    def test_read_new_lines_with_content(self, tmp_path):
        """测试读取有内容的文件"""
        filepath = tmp_path / "content.txt"
        filepath.write_text("line1\nline2\nline3\n", encoding='utf-8')
        
        lf = LogFile(str(filepath))
        lf.open()
        # 首次读取应该跳过已有内容（因为 open() 时 seek 到末尾）
        lines = lf.read_new_lines()
        
        assert lines == []  # 没有新内容
        lf.close()

    def test_read_new_lines_after_write(self, tmp_path):
        """测试写入后读取新内容"""
        filepath = tmp_path / "newcontent.txt"
        filepath.write_text("initial\n", encoding='utf-8')
        
        lf = LogFile(str(filepath))
        lf.open()
        
        # 写入新内容
        with open(filepath, 'a', encoding='utf-8') as f:
            f.write("new line 1\n")
            f.write("new line 2\n")
        
        # 读取新内容
        lines = lf.read_new_lines()
        
        assert len(lines) == 2
        assert "new line 1" in lines[0]
        assert "new line 2" in lines[1]
        lf.close()