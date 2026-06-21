# -*- coding: utf-8 -*-
"""
@desc: 异常-空值处理
@author: 1nchaos
@time: 2023/8/14
@log: change log
"""

import pandas as pd

from adata.common.exception.error_tracker import error_tracker


def handler_null(func):
    """异常处理装饰器，捕获所有异常并返回空 DataFrame，同时记录错误信息

    自动从类名推断数据源名称，从函数名获取操作类型。
    """
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            source = 'unknown'
            if args:
                cls = args[0]
                if hasattr(cls, '__class__'):
                    class_name = cls.__class__.__name__
                    source = _extract_source_from_class(class_name)
            operation = func.__name__
            error_tracker.record_error(source=source, operation=operation, exception=e)
            return pd.DataFrame(data=[], columns=[])

    return wrapper


def handler_null_with_error(source: str = None, operation: str = None):
    """带错误记录的异常处理装饰器（显式指定参数版本）

    :param source: 数据源名称，如 'sina', 'qq', 'baidu', 'east', 'ths'
    :param operation: 操作类型，默认使用函数名
    :return: 装饰器函数
    """

    def decorator(func):
        op_name = operation or func.__name__

        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                src_name = source
                if src_name is None and args:
                    cls = args[0]
                    if hasattr(cls, '__class__'):
                        class_name = cls.__class__.__name__
                        src_name = _extract_source_from_class(class_name)
                if src_name is None:
                    src_name = 'unknown'

                error_tracker.record_error(source=src_name, operation=op_name, exception=e)
                return pd.DataFrame(data=[], columns=[])

        return wrapper

    return decorator


def _extract_source_from_class(class_name: str) -> str:
    """从类名中提取数据源名称

    :param class_name: 类名，如 'StockMarketSina', 'StockMarketEast'
    :return: 数据源名称，如 'sina', 'east'
    """
    class_lower = class_name.lower()
    source_mapping = [
        ('sina', 'sina'),
        ('baidu', 'baidu'),
        ('east', 'east'),
        ('qq', 'qq'),
        ('ths', 'ths'),
        ('10jqka', 'ths'),
    ]
    for key, value in source_mapping:
        if key in class_lower:
            return value
    return 'unknown'


def record_empty_fallback(source: str, operation: str, reason: str = 'empty_dataframe'):
    """记录 fallback 切换时的空结果

    当一个数据源返回空 DataFrame 导致 fallback 切换到下一个源时调用此函数记录。

    :param source: 数据源名称
    :param operation: 操作类型
    :param reason: 原因，默认 'empty_dataframe'
    """
    error_tracker.record_error(
        source=source,
        operation=operation,
        error_type='EmptyDataFrame',
        error_msg=reason
    )
