# -*- coding: utf-8 -*-
"""
@desc: readme
@author: 1nchaos
@time: 2023/12/4
@log: change log
"""
exchange_suffix = {
    '00': '.SZ',
    '20': '.SZ',
    '30': '.SZ',
    '43': '.BJ',
    '60': '.SH',
    '68': '.SH',
    '83': '.BJ',
    '87': '.BJ',
    '90': '.SH',
    '92': '.BJ',
}


def compile_exchange_by_stock_code(stock_code):
    """根据股票代码补全市场后缀"""

    prefix = stock_code[0:2]
    if prefix in exchange_suffix:
        return stock_code + exchange_suffix[prefix]
    return stock_code


def get_exchange_by_stock_code(stock_code):
    """根据股票代码获取交易所代码

    不认识的代码前缀返回原值，不会抛出异常。
    """
    prefix = stock_code[0:2]
    if prefix in exchange_suffix:
        return exchange_suffix[prefix][1:]
    return stock_code


if __name__ == '__main__':
    print(compile_exchange_by_stock_code('200039'))
    print(get_exchange_by_stock_code('200039'))
