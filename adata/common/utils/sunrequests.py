# -*- coding: utf-8 -*-
"""
代理:https://jahttp.zhimaruanjian.com/getapi/

@desc: adata 请求工具类
@author: 1nchaos
@time:2023/3/30
@log: 封装请求次数
"""

import threading
import time

import requests


class SunProxy(object):
    _data = {}
    _instance_lock = threading.Lock()

    def __init__(self):
        pass

    def __new__(cls, *args, **kwargs):
        if not hasattr(SunProxy, "_instance"):
            with SunProxy._instance_lock:
                if not hasattr(SunProxy, "_instance"):
                    SunProxy._instance = object.__new__(cls)
        return SunProxy._instance

    @classmethod
    def set(cls, key, value):
        cls._data[key] = value

    @classmethod
    def get(cls, key):
        return cls._data.get(key)

    @classmethod
    def delete(cls, key):
        if key in cls._data:
            del cls._data[key]


class SunRequests(object):
    def __init__(self, sun_proxy: SunProxy = None) -> None:
        super().__init__()
        self.sun_proxy = sun_proxy

    def get(self, url, **kwargs):
        """GET 请求便捷方法，同 requests.get

        :param url: 请求 URL
        :param kwargs: 其它参数，同 request 方法
        :return: Response 对象
        """
        return self.request(method='get', url=url, **kwargs)

    def post(self, url, **kwargs):
        """POST 请求便捷方法，同 requests.post

        :param url: 请求 URL
        :param kwargs: 其它参数，同 request 方法
        :return: Response 对象
        """
        return self.request(method='post', url=url, **kwargs)

    def put(self, url, **kwargs):
        """PUT 请求便捷方法，同 requests.put

        :param url: 请求 URL
        :param kwargs: 其它参数，同 request 方法
        :return: Response 对象
        """
        return self.request(method='put', url=url, **kwargs)

    def delete(self, url, **kwargs):
        """DELETE 请求便捷方法，同 requests.delete

        :param url: 请求 URL
        :param kwargs: 其它参数，同 request 方法
        :return: Response 对象
        """
        return self.request(method='delete', url=url, **kwargs)

    def head(self, url, **kwargs):
        """HEAD 请求便捷方法，同 requests.head

        :param url: 请求 URL
        :param kwargs: 其它参数，同 request 方法
        :return: Response 对象
        """
        return self.request(method='head', url=url, **kwargs)

    def patch(self, url, **kwargs):
        """PATCH 请求便捷方法，同 requests.patch

        :param url: 请求 URL
        :param kwargs: 其它参数，同 request 方法
        :return: Response 对象
        """
        return self.request(method='patch', url=url, **kwargs)

    def options(self, url, **kwargs):
        """OPTIONS 请求便捷方法，同 requests.options

        :param url: 请求 URL
        :param kwargs: 其它参数，同 request 方法
        :return: Response 对象
        """
        return self.request(method='options', url=url, **kwargs)

    def __getattr__(self, name):
        """对未知属性给出明确错误提示

        避免用户把 adata 的 requests 包装器当成标准库 requests 使用时，
        得到模糊的 AttributeError 而不知道原因。
        """
        if name.startswith('_'):
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

        raise AttributeError(
            f"'SunRequests' object has no attribute '{name}'.\n"
            f"提示：adata.common.utils.requests 是 adata 内部的 HTTP 请求包装器，"
            f"不是 Python 标准库的 requests 模块。\n"
            f"如果你想发起 HTTP 请求，可以使用：\n"
            f"  - requests.request(method='get', url=...)\n"
            f"  - requests.get(url, ...)  # 便捷方法\n"
            f"  - requests.post(url, ...)  # 便捷方法\n"
            f"如果你需要标准库 requests，请显式导入：\n"
            f"  import requests as real_requests"
        )

    def request(self, method='get', url=None, times=3, retry_wait_time=1588, proxies=None, wait_time=None, **kwargs):
        """
        简单封装的请求，参考requests，增加循环次数和次数之间的等待时间
        :param proxies: 代理配置
        :param method: 请求方法： get；post
        :param url: url
        :param times: 次数，int
        :param retry_wait_time: 重试等待时间，毫秒
        :param wait_time: 等待时间：毫秒；表示每个请求的间隔时间，在请求之前等待sleep，主要用于防止请求太频繁的限制。
        :param kwargs: 其它 requests 参数，用法相同
        :return: res
        """
        # 1. 获取设置代理
        proxies = self.__get_proxies(proxies)
        # 2. 请求数据结果
        res = None
        for i in range(times):
            if wait_time:
                time.sleep(wait_time / 1000)
            res = requests.request(method=method, url=url, proxies=proxies, **kwargs)
            if res.status_code in (200, 404):
                return res
            time.sleep(retry_wait_time / 1000)
            if i == times - 1:
                return res
        return res

    def __get_proxies(self, proxies):
        """
        获取代理配置
        """
        if proxies is None:
            proxies = {}
        is_proxy = SunProxy.get('is_proxy')
        ip = SunProxy.get('ip')
        proxy_url = SunProxy.get('proxy_url')
        if not ip and is_proxy and proxy_url:
            ip = requests.get(url=proxy_url).text.replace('\r\n', '') \
                .replace('\r', '').replace('\n', '').replace('\t', '')
        if is_proxy and ip:
            if ip.startswith('http'):
                proxies = {'https': f"{ip}", 'http': f"{ip}"}
            else:
                proxies = {'https': f"http://{ip}", 'http': f"http://{ip}"}
        return proxies


sun_requests = SunRequests()
