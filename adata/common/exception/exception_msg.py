# -*- coding: utf-8 -*-
"""
@desc: 异常信息
@author: 1nchaos
@time: 2023/7/8
@log: change log
"""

THS_IP_LIMIT_RES = '<h1>Nginx forbidden.</h1>'
"""同花顺Ip限制的返回结果"""
THS_IP_LIMIT_MSG = "ths流量防控：当前ip被限制，请降低请求频率或更换ip或使用代理设置，勿使用国外ip！！！"
"""同花顺IP：403限制提醒"""


class AdataError(Exception):
    """adata 统一异常基类，携带数据源和操作类型信息"""

    def __init__(self, message, source=None, op_type=None):
        self.source = source
        self.op_type = op_type
        full = message
        parts = []
        if source:
            parts.append(f"source={source}")
        if op_type:
            parts.append(f"op_type={op_type}")
        if parts:
            full = f"[{'|'.join(parts)}] {message}"
        super().__init__(full)
