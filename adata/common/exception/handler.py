# -*- coding: utf-8 -*-
"""
@desc: 异常-空值处理
@author: 1nchaos
@time: 2023/8/14
@log: change log
"""

import functools

import pandas as pd

from adata.common.exception.tracker import tracker, EventType


def handler_null(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            source = getattr(exc, "source", None) or _guess_source(args)
            op_type = getattr(exc, "op_type", None) or func.__name__
            message = str(exc)
            tracker.record_exception(source=source, op_type=op_type, message=message)
            df = pd.DataFrame(data=[], columns=[])
            df.attrs["_adata_event_type"] = EventType.EXCEPTION.value
            df.attrs["_adata_source"] = source
            df.attrs["_adata_op_type"] = op_type
            df.attrs["_adata_message"] = message
            return df

    return wrapper


def _guess_source(args):
    if args:
        cls_name = type(args[0]).__name__
        low = cls_name.lower()
        for tag in ("ths", "east", "baidu", "sina", "qq", "tdx"):
            if tag in low:
                return tag
    return None
