# -*- coding: utf-8 -*-
"""
@desc: 数据采集异常追踪器
@author: 1nchaos
@time: 2023/8/14
@log: change log
"""

import threading
import traceback
from collections import deque
from datetime import datetime
from typing import Callable, List, Optional


class FetchError:
    """数据拉取错误记录"""

    def __init__(self, source: str, operation: str, error_type: str, error_msg: str,
                 timestamp: Optional[str] = None, traceback_str: Optional[str] = None):
        self.source = source
        self.operation = operation
        self.error_type = error_type
        self.error_msg = error_msg
        self.timestamp = timestamp or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.traceback_str = traceback_str

    def to_dict(self):
        return {
            'source': self.source,
            'operation': self.operation,
            'error_type': self.error_type,
            'error_msg': self.error_msg,
            'timestamp': self.timestamp,
            'traceback': self.traceback_str
        }

    def __repr__(self):
        return (f"FetchError(source='{self.source}', operation='{self.operation}', "
                f"error_type='{self.error_type}', error_msg='{self.error_msg}', "
                f"timestamp='{self.timestamp}')")


class ErrorTracker:
    """数据采集异常追踪器

    用于记录所有数据拉取过程中的异常，提供查询接口和回调通知机制。
    """

    _instance = None
    _instance_lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = object.__new__(cls)
        return cls._instance

    def __init__(self, max_errors: int = 1000):
        if hasattr(self, '_initialized') and self._initialized:
            return
        self._initialized = True
        self._max_errors = max_errors
        self._errors = deque(maxlen=max_errors)
        self._callbacks = []
        self._lock = threading.Lock()

    def set_max_errors(self, max_errors: int):
        """设置最大错误记录数

        :param max_errors: 最大错误记录数
        """
        with self._lock:
            self._max_errors = max_errors
            self._errors = deque(self._errors, maxlen=max_errors)

    def record_error(self, source: str, operation: str, exception: Exception = None,
                     error_type: str = None, error_msg: str = None):
        """记录一个错误

        :param source: 数据源名称，如 'sina', 'qq', 'baidu', 'east', 'ths'
        :param operation: 操作类型，如 'get_market', 'list_market_current'
        :param exception: 异常对象
        :param error_type: 异常类型字符串（如果不提供 exception 则必填）
        :param error_msg: 异常消息（如果不提供 exception 则必填）
        """
        if exception is not None:
            error_type = type(exception).__name__
            error_msg = str(exception)
            traceback_str = traceback.format_exc()
        else:
            traceback_str = None

        if error_type is None or error_msg is None:
            raise ValueError("error_type and error_msg must be provided if exception is not given")

        error = FetchError(
            source=source,
            operation=operation,
            error_type=error_type,
            error_msg=error_msg,
            traceback_str=traceback_str
        )

        with self._lock:
            self._errors.append(error)

        self._notify_callbacks(error)

    def _notify_callbacks(self, error: FetchError):
        """通知所有注册的回调"""
        for callback in self._callbacks:
            try:
                callback(error)
            except Exception:
                pass

    def add_callback(self, callback: Callable[[FetchError], None]):
        """注册错误回调

        :param callback: 回调函数，接收一个 FetchError 参数
        """
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    def remove_callback(self, callback: Callable[[FetchError], None]):
        """移除错误回调

        :param callback: 要移除的回调函数
        """
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def get_errors(self, source: str = None, operation: str = None,
                   error_type: str = None, limit: int = None) -> List[FetchError]:
        """查询错误记录

        :param source: 按数据源筛选
        :param operation: 按操作类型筛选
        :param error_type: 按异常类型筛选
        :param limit: 返回的最大数量
        :return: 错误记录列表
        """
        with self._lock:
            errors = list(self._errors)

        if source:
            errors = [e for e in errors if e.source == source]
        if operation:
            errors = [e for e in errors if e.operation == operation]
        if error_type:
            errors = [e for e in errors if e.error_type == error_type]

        if limit:
            errors = errors[-limit:]

        return errors

    def get_last_error(self, source: str = None, operation: str = None) -> Optional[FetchError]:
        """获取最近的一条错误

        :param source: 按数据源筛选
        :param operation: 按操作类型筛选
        :return: 最近的错误记录，如果没有则返回 None
        """
        errors = self.get_errors(source=source, operation=operation)
        return errors[-1] if errors else None

    def has_errors(self, source: str = None, operation: str = None) -> bool:
        """检查是否有错误记录

        :param source: 按数据源筛选
        :param operation: 按操作类型筛选
        :return: 是否有错误
        """
        return len(self.get_errors(source=source, operation=operation)) > 0

    def clear_errors(self):
        """清空所有错误记录"""
        with self._lock:
            self._errors.clear()

    def error_count(self, source: str = None, operation: str = None) -> int:
        """获取错误数量

        :param source: 按数据源筛选
        :param operation: 按操作类型筛选
        :return: 错误数量
        """
        return len(self.get_errors(source=source, operation=operation))


error_tracker = ErrorTracker()
