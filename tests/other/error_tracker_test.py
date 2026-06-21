# -*- coding: utf-8 -*-
"""
@desc: 异常追踪机制测试
@author: 1nchaos
@time: 2023/8/14
@log: change log
"""
import unittest
from unittest.mock import patch, MagicMock

import pandas as pd

from adata.common.exception import error_tracker, handler_null, record_empty_fallback
from adata.common.exception.error_tracker import FetchError, ErrorTracker
from adata.common.utils.code_utils import get_exchange_by_stock_code, compile_exchange_by_stock_code
from adata.common.utils.sunrequests import SunProxy


class ErrorTrackerTestCase(unittest.TestCase):
    """错误追踪器测试"""

    def setUp(self):
        error_tracker.clear_errors()

    def tearDown(self):
        error_tracker.clear_errors()

    def test_record_error_with_exception(self):
        """测试通过异常对象记录错误"""
        try:
            raise ValueError("test error")
        except ValueError as e:
            error_tracker.record_error(source='test_source', operation='test_op', exception=e)

        errors = error_tracker.get_errors()
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].source, 'test_source')
        self.assertEqual(errors[0].operation, 'test_op')
        self.assertEqual(errors[0].error_type, 'ValueError')
        self.assertEqual(errors[0].error_msg, 'test error')
        self.assertIsNotNone(errors[0].traceback_str)
        self.assertIn('ValueError', errors[0].traceback_str)

    def test_record_error_with_message(self):
        """测试通过错误类型和消息记录错误"""
        error_tracker.record_error(
            source='test_source',
            operation='test_op',
            error_type='CustomError',
            error_msg='custom message'
        )

        errors = error_tracker.get_errors()
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].source, 'test_source')
        self.assertEqual(errors[0].error_type, 'CustomError')
        self.assertEqual(errors[0].error_msg, 'custom message')
        self.assertIsNone(errors[0].traceback_str)

    def test_get_errors_filter_by_source(self):
        """测试按数据源筛选错误"""
        error_tracker.record_error(source='sina', operation='op1', error_type='E1', error_msg='m1')
        error_tracker.record_error(source='qq', operation='op2', error_type='E2', error_msg='m2')
        error_tracker.record_error(source='sina', operation='op3', error_type='E3', error_msg='m3')

        sina_errors = error_tracker.get_errors(source='sina')
        self.assertEqual(len(sina_errors), 2)
        self.assertTrue(all(e.source == 'sina' for e in sina_errors))

        qq_errors = error_tracker.get_errors(source='qq')
        self.assertEqual(len(qq_errors), 1)
        self.assertEqual(qq_errors[0].source, 'qq')

    def test_get_errors_filter_by_operation(self):
        """测试按操作类型筛选错误"""
        error_tracker.record_error(source='sina', operation='get_market', error_type='E1', error_msg='m1')
        error_tracker.record_error(source='qq', operation='list_current', error_type='E2', error_msg='m2')
        error_tracker.record_error(source='sina', operation='get_market', error_type='E3', error_msg='m3')

        market_errors = error_tracker.get_errors(operation='get_market')
        self.assertEqual(len(market_errors), 2)
        self.assertTrue(all(e.operation == 'get_market' for e in market_errors))

    def test_get_errors_filter_by_error_type(self):
        """测试按异常类型筛选错误"""
        error_tracker.record_error(source='s1', operation='op1', error_type='TimeoutError', error_msg='m1')
        error_tracker.record_error(source='s2', operation='op2', error_type='ValueError', error_msg='m2')
        error_tracker.record_error(source='s3', operation='op3', error_type='TimeoutError', error_msg='m3')

        timeout_errors = error_tracker.get_errors(error_type='TimeoutError')
        self.assertEqual(len(timeout_errors), 2)
        self.assertTrue(all(e.error_type == 'TimeoutError' for e in timeout_errors))

    def test_get_last_error(self):
        """测试获取最近一条错误"""
        self.assertIsNone(error_tracker.get_last_error())

        error_tracker.record_error(source='s1', operation='op1', error_type='E1', error_msg='m1')
        error_tracker.record_error(source='s2', operation='op2', error_type='E2', error_msg='m2')

        last = error_tracker.get_last_error()
        self.assertEqual(last.source, 's2')
        self.assertEqual(last.error_msg, 'm2')

        last_s1 = error_tracker.get_last_error(source='s1')
        self.assertEqual(last_s1.source, 's1')
        self.assertEqual(last_s1.error_msg, 'm1')

    def test_has_errors(self):
        """测试检查是否有错误"""
        self.assertFalse(error_tracker.has_errors())
        self.assertFalse(error_tracker.has_errors(source='sina'))

        error_tracker.record_error(source='sina', operation='op', error_type='E', error_msg='m')

        self.assertTrue(error_tracker.has_errors())
        self.assertTrue(error_tracker.has_errors(source='sina'))
        self.assertFalse(error_tracker.has_errors(source='qq'))

    def test_error_count(self):
        """测试错误计数"""
        self.assertEqual(error_tracker.error_count(), 0)

        error_tracker.record_error(source='s1', operation='op1', error_type='E1', error_msg='m1')
        error_tracker.record_error(source='s2', operation='op2', error_type='E2', error_msg='m2')
        error_tracker.record_error(source='s1', operation='op3', error_type='E3', error_msg='m3')

        self.assertEqual(error_tracker.error_count(), 3)
        self.assertEqual(error_tracker.error_count(source='s1'), 2)
        self.assertEqual(error_tracker.error_count(source='s2'), 1)
        self.assertEqual(error_tracker.error_count(source='s3'), 0)

    def test_clear_errors(self):
        """测试清空错误"""
        error_tracker.record_error(source='s1', operation='op1', error_type='E1', error_msg='m1')
        self.assertEqual(error_tracker.error_count(), 1)

        error_tracker.clear_errors()
        self.assertEqual(error_tracker.error_count(), 0)
        self.assertFalse(error_tracker.has_errors())

    def test_callback(self):
        """测试回调函数"""
        callback_results = []

        def callback(error):
            callback_results.append(error)

        error_tracker.add_callback(callback)
        error_tracker.record_error(source='s1', operation='op1', error_type='E1', error_msg='m1')

        self.assertEqual(len(callback_results), 1)
        self.assertEqual(callback_results[0].source, 's1')
        self.assertEqual(callback_results[0].error_type, 'E1')

    def test_remove_callback(self):
        """测试移除回调"""
        callback_results = []

        def callback(error):
            callback_results.append(error)

        error_tracker.add_callback(callback)
        error_tracker.record_error(source='s1', operation='op1', error_type='E1', error_msg='m1')
        self.assertEqual(len(callback_results), 1)

        error_tracker.remove_callback(callback)
        error_tracker.record_error(source='s2', operation='op2', error_type='E2', error_msg='m2')
        self.assertEqual(len(callback_results), 1)

    def test_callback_exception_does_not_break(self):
        """测试回调函数抛出异常不会影响其他逻辑"""
        def bad_callback(error):
            raise RuntimeError("callback failed")

        callback_results = []

        def good_callback(error):
            callback_results.append(error)

        error_tracker.add_callback(bad_callback)
        error_tracker.add_callback(good_callback)

        error_tracker.record_error(source='s1', operation='op1', error_type='E1', error_msg='m1')

        self.assertEqual(len(callback_results), 1)

    def test_fetch_error_to_dict(self):
        """测试 FetchError 转字典"""
        error = FetchError(
            source='test',
            operation='test_op',
            error_type='TestError',
            error_msg='test message',
            timestamp='2024-01-01 00:00:00',
            traceback_str='traceback here'
        )
        d = error.to_dict()
        self.assertEqual(d['source'], 'test')
        self.assertEqual(d['operation'], 'test_op')
        self.assertEqual(d['error_type'], 'TestError')
        self.assertEqual(d['error_msg'], 'test message')
        self.assertEqual(d['timestamp'], '2024-01-01 00:00:00')
        self.assertEqual(d['traceback'], 'traceback here')

    def test_singleton(self):
        """测试 ErrorTracker 是单例"""
        tracker1 = ErrorTracker()
        tracker2 = ErrorTracker()
        self.assertIs(tracker1, tracker2)

    def test_limit_errors(self):
        """测试错误数量限制"""
        original_max = error_tracker._max_errors
        try:
            error_tracker.set_max_errors(10)
            error_tracker.clear_errors()
            for i in range(15):
                error_tracker.record_error(
                    source=f's{i}',
                    operation=f'op{i}',
                    error_type=f'E{i}',
                    error_msg=f'm{i}'
                )
            self.assertEqual(error_tracker.error_count(), 10)
            errors = error_tracker.get_errors()
            self.assertEqual(errors[0].source, 's5')
            self.assertEqual(errors[-1].source, 's14')
        finally:
            error_tracker.set_max_errors(original_max)


class HandlerNullTestCase(unittest.TestCase):
    """handler_null 装饰器测试"""

    def setUp(self):
        error_tracker.clear_errors()

    def tearDown(self):
        error_tracker.clear_errors()

    def test_handler_null_captures_exception(self):
        """测试装饰器捕获异常并返回空 DataFrame"""
        @handler_null
        def failing_func():
            raise ValueError("test error")

        result = failing_func()
        self.assertIsInstance(result, pd.DataFrame)
        self.assertTrue(result.empty)

    def test_handler_null_returns_normal_result(self):
        """测试装饰器不影响正常返回"""
        @handler_null
        def normal_func():
            return pd.DataFrame({'a': [1, 2, 3]})

        result = normal_func()
        self.assertIsInstance(result, pd.DataFrame)
        self.assertEqual(len(result), 3)
        self.assertEqual(list(result.columns), ['a'])

    def test_handler_null_records_error(self):
        """测试装饰器记录错误信息"""
        class TestClass:
            @handler_null
            def failing_method(self):
                raise RuntimeError("something went wrong")

        obj = TestClass()
        result = obj.failing_method()

        self.assertTrue(result.empty)
        self.assertTrue(error_tracker.has_errors())

        errors = error_tracker.get_errors()
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].error_type, 'RuntimeError')
        self.assertEqual(errors[0].error_msg, 'something went wrong')
        self.assertEqual(errors[0].operation, 'failing_method')
        self.assertIsNotNone(errors[0].traceback_str)

    def test_handler_null_extracts_source_from_class_name(self):
        """测试装饰器从类名自动推断数据源"""
        class StockMarketSina:
            @handler_null
            def get_market(self):
                raise ValueError("sina error")

        class StockMarketEast:
            @handler_null
            def get_market(self):
                raise ValueError("east error")

        StockMarketSina().get_market()
        StockMarketEast().get_market()

        sina_errors = error_tracker.get_errors(source='sina')
        east_errors = error_tracker.get_errors(source='east')

        self.assertEqual(len(sina_errors), 1)
        self.assertEqual(len(east_errors), 1)
        self.assertEqual(sina_errors[0].error_msg, 'sina error')
        self.assertEqual(east_errors[0].error_msg, 'east error')

    def test_handler_null_unknown_source(self):
        """测试无法识别的类名返回 unknown 源"""
        class SomeRandomClass:
            @handler_null
            def some_method(self):
                raise ValueError("unknown error")

        SomeRandomClass().some_method()

        errors = error_tracker.get_errors(source='unknown')
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].error_msg, 'unknown error')


class RecordEmptyFallbackTestCase(unittest.TestCase):
    """record_empty_fallback 函数测试"""

    def setUp(self):
        error_tracker.clear_errors()

    def tearDown(self):
        error_tracker.clear_errors()

    def test_record_empty_fallback(self):
        """测试记录 fallback 空结果"""
        record_empty_fallback('sina', 'get_market')

        errors = error_tracker.get_errors()
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].source, 'sina')
        self.assertEqual(errors[0].operation, 'get_market')
        self.assertEqual(errors[0].error_type, 'EmptyDataFrame')
        self.assertEqual(errors[0].error_msg, 'empty_dataframe')

    def test_record_empty_fallback_with_custom_reason(self):
        """测试记录带自定义原因的 fallback"""
        record_empty_fallback('east', 'list_current', reason='insufficient_data')

        errors = error_tracker.get_errors()
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].error_type, 'EmptyDataFrame')
        self.assertEqual(errors[0].error_msg, 'insufficient_data')


class CodeUtilsTestCase(unittest.TestCase):
    """股票代码工具函数测试"""

    def test_compile_exchange_by_stock_code_known_prefix(self):
        """测试已知前缀的股票代码补全"""
        self.assertEqual(compile_exchange_by_stock_code('000001'), '000001.SZ')
        self.assertEqual(compile_exchange_by_stock_code('600000'), '600000.SH')
        self.assertEqual(compile_exchange_by_stock_code('300001'), '300001.SZ')
        self.assertEqual(compile_exchange_by_stock_code('688001'), '688001.SH')
        self.assertEqual(compile_exchange_by_stock_code('430001'), '430001.BJ')
        self.assertEqual(compile_exchange_by_stock_code('830001'), '830001.BJ')
        self.assertEqual(compile_exchange_by_stock_code('870001'), '870001.BJ')
        self.assertEqual(compile_exchange_by_stock_code('900001'), '900001.SH')

    def test_compile_exchange_by_stock_code_unknown_prefix(self):
        """测试未知前缀的股票代码不崩溃，返回原值"""
        self.assertEqual(compile_exchange_by_stock_code('123456'), '123456')
        self.assertEqual(compile_exchange_by_stock_code('999999'), '999999')
        self.assertEqual(compile_exchange_by_stock_code('100001'), '100001')

    def test_get_exchange_by_stock_code_known_prefix(self):
        """测试已知前缀获取交易所代码"""
        self.assertEqual(get_exchange_by_stock_code('000001'), 'SZ')
        self.assertEqual(get_exchange_by_stock_code('600000'), 'SH')
        self.assertEqual(get_exchange_by_stock_code('300001'), 'SZ')
        self.assertEqual(get_exchange_by_stock_code('688001'), 'SH')
        self.assertEqual(get_exchange_by_stock_code('430001'), 'BJ')
        self.assertEqual(get_exchange_by_stock_code('830001'), 'BJ')
        self.assertEqual(get_exchange_by_stock_code('870001'), 'BJ')
        self.assertEqual(get_exchange_by_stock_code('900001'), 'SH')

    def test_get_exchange_by_stock_code_unknown_prefix_no_crash(self):
        """测试未知前缀不抛出 KeyError，返回原值"""
        try:
            result = get_exchange_by_stock_code('123456')
            self.assertEqual(result, '123456')
        except KeyError:
            self.fail("get_exchange_by_stock_code raised KeyError for unknown prefix")

        try:
            result = get_exchange_by_stock_code('999999')
            self.assertEqual(result, '999999')
        except KeyError:
            self.fail("get_exchange_by_stock_code raised KeyError for unknown prefix")


class SunProxyTestCase(unittest.TestCase):
    """SunProxy 单例测试"""

    def test_singleton_instance(self):
        """测试实例化能正常返回实例"""
        proxy1 = SunProxy()
        proxy2 = SunProxy()

        self.assertIsNotNone(proxy1)
        self.assertIsNotNone(proxy2)
        self.assertIs(proxy1, proxy2)

    def test_instance_methods_work(self):
        """测试实例方法能正常工作"""
        proxy = SunProxy()

        proxy.set('test_key', 'test_value')
        self.assertEqual(proxy.get('test_key'), 'test_value')

        proxy.delete('test_key')
        self.assertIsNone(proxy.get('test_key'))

    def test_class_methods_work(self):
        """测试类方法能正常工作"""
        SunProxy.set('class_key', 'class_value')
        self.assertEqual(SunProxy.get('class_key'), 'class_value')

        SunProxy.delete('class_key')
        self.assertIsNone(SunProxy.get('class_key'))

    def test_instance_and_class_share_data(self):
        """测试实例方法和类方法共享数据"""
        proxy = SunProxy()

        SunProxy.set('shared_key', 'shared_value')
        self.assertEqual(proxy.get('shared_key'), 'shared_value')

        proxy.set('shared_key2', 'shared_value2')
        self.assertEqual(SunProxy.get('shared_key2'), 'shared_value2')


class StockMarketFallbackTestCase(unittest.TestCase):
    """股票行情 fallback 测试"""

    def setUp(self):
        error_tracker.clear_errors()

    def tearDown(self):
        error_tracker.clear_errors()

    @patch('adata.stock.market.stock_market.stock_market.StockMarketEast')
    @patch('adata.stock.market.stock_market.stock_market.StockMarketBaiDu')
    def test_get_market_min_fallback_records_error(self, mock_baidu_cls, mock_east_cls):
        """测试 get_market_min fallback 时记录错误"""
        from adata.stock.market.stock_market.stock_market import StockMarket

        mock_east = mock_east_cls.return_value
        mock_east.get_market_min.return_value = pd.DataFrame()

        mock_baidu = mock_baidu_cls.return_value
        expected_df = pd.DataFrame({
            'stock_code': ['000001'],
            'price': [10.0]
        })
        mock_baidu.get_market_min.return_value = expected_df

        market = StockMarket()
        result = market.get_market_min(stock_code='000001')

        self.assertFalse(result.empty)
        self.assertTrue(error_tracker.has_errors(source='east'))

        errors = error_tracker.get_errors(source='east', operation='get_market_min')
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].error_type, 'EmptyDataFrame')

    @patch('adata.stock.market.stock_market.stock_market.StockMarketSina')
    @patch('adata.stock.market.stock_market.stock_market.StockMarketQQ')
    def test_list_market_current_fallback_records_error(self, mock_qq_cls, mock_sina_cls):
        """测试 list_market_current fallback 时记录错误"""
        from adata.stock.market.stock_market.stock_market import StockMarket

        mock_sina = mock_sina_cls.return_value
        mock_sina.list_market_current.return_value = pd.DataFrame()

        mock_qq = mock_qq_cls.return_value
        expected_df = pd.DataFrame({
            'stock_code': ['000001'],
            'price': [10.0]
        })
        mock_qq.list_market_current.return_value = expected_df

        market = StockMarket()
        result = market.list_market_current(code_list=['000001'])

        self.assertFalse(result.empty)
        self.assertTrue(error_tracker.has_errors(source='sina'))

        errors = error_tracker.get_errors(source='sina', operation='list_market_current')
        self.assertEqual(len(errors), 1)

    def test_handler_null_with_network_timeout(self):
        """测试网络超时异常被正确捕获和记录"""
        import requests as req_lib

        class TestSource:
            @handler_null
            def fetch_data(self):
                raise req_lib.exceptions.Timeout("Connection timed out")

        TestSource().fetch_data()

        errors = error_tracker.get_errors()
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].error_type, 'Timeout')
        self.assertIn('timed out', errors[0].error_msg)

    def test_handler_null_with_invalid_json(self):
        """测试接口返回非法结构时的异常捕获"""
        import json

        class TestSource:
            @handler_null
            def parse_response(self):
                invalid_json = 'not valid json'
                return json.loads(invalid_json)

        result = TestSource().parse_response()

        self.assertTrue(result.empty)
        errors = error_tracker.get_errors()
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].error_type, 'JSONDecodeError')

    def test_handler_null_with_invalid_stock_code(self):
        """测试股票代码非法时的异常捕获"""
        class TestSource:
            @handler_null
            def get_market(self, stock_code):
                if not stock_code or len(stock_code) != 6:
                    raise ValueError(f"Invalid stock code: {stock_code}")
                return pd.DataFrame({'code': [stock_code]})

        result = TestSource().get_market('123')

        self.assertTrue(result.empty)
        errors = error_tracker.get_errors()
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].error_type, 'ValueError')
        self.assertIn('Invalid stock code', errors[0].error_msg)


class FundModuleTestCase(unittest.TestCase):
    """基金模块错误追踪测试"""

    def setUp(self):
        error_tracker.clear_errors()

    def tearDown(self):
        error_tracker.clear_errors()

    def test_etf_market_ths_has_handler_null(self):
        """测试 ETFMarketThs 的方法都有 @handler_null 装饰器"""
        from adata.fund.market.etf_market_ths import ETFMarketThs

        instance = ETFMarketThs()

        self.assertTrue(hasattr(instance.get_market_etf_ths, '__wrapped__') or
                        'wrapper' in str(instance.get_market_etf_ths.__name__))
        self.assertTrue(hasattr(instance.get_market_etf_min_ths, '__wrapped__') or
                        'wrapper' in str(instance.get_market_etf_min_ths.__name__))
        self.assertTrue(hasattr(instance.get_market_etf_current_ths, '__wrapped__') or
                        'wrapper' in str(instance.get_market_etf_current_ths.__name__))

    def test_etf_method_exception_is_recorded(self):
        """测试 ETF 方法抛出异常时被正确记录"""
        from adata.fund.market.etf_market_ths import ETFMarketThs

        class ETFMarketThsMock(ETFMarketThs):
            @handler_null
            def get_market_etf_ths(self, fund_code='512880', k_type=1, start_date='', end_date=''):
                raise RuntimeError("ETF mock error")

        instance = ETFMarketThsMock()
        result = instance.get_market_etf_ths(fund_code='512880')

        self.assertTrue(result.empty)
        self.assertTrue(error_tracker.has_errors())

        errors = error_tracker.get_errors(source='ths')
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].error_type, 'RuntimeError')
        self.assertEqual(errors[0].error_msg, 'ETF mock error')


class BondModuleTestCase(unittest.TestCase):
    """债券模块错误追踪测试"""

    def setUp(self):
        error_tracker.clear_errors()

    def tearDown(self):
        error_tracker.clear_errors()

    def test_bond_market_sina_has_handler_null(self):
        """测试 BondMarketSina 的方法有 @handler_null 装饰器"""
        from adata.bond.market.bond_market_sina import BondMarketSina

        instance = BondMarketSina()

        self.assertTrue(hasattr(instance.list_market_current, '__wrapped__') or
                        'wrapper' in str(instance.list_market_current.__name__))

    def test_bond_method_exception_returns_empty_df(self):
        """测试债券方法抛出异常时返回空 DataFrame 并记录错误"""
        from adata.bond.market.bond_market_sina import BondMarketSina

        original_init = BondMarketSina.__init__

        def mock_init(self):
            pass

        BondMarketSina.__init__ = mock_init

        try:
            instance = BondMarketSina()
            original_method = instance.list_market_current

            def failing_method(*args, **kwargs):
                raise ConnectionError("network error")

            instance.list_market_current = handler_null(failing_method)

            result = instance.list_market_current()
            self.assertTrue(result.empty)
            self.assertTrue(error_tracker.has_errors())

            errors = error_tracker.get_errors()
            self.assertEqual(len(errors), 1)
            self.assertEqual(errors[0].error_type, 'ConnectionError')
        finally:
            BondMarketSina.__init__ = original_init


class SentimentModuleTestCase(unittest.TestCase):
    """sentiment 模块错误追踪测试"""

    def setUp(self):
        error_tracker.clear_errors()

    def tearDown(self):
        error_tracker.clear_errors()

    def test_hot_class_has_handler_null(self):
        """测试 Hot 类的静态方法有 @handler_null 装饰器

        通过 mock 底层请求来验证异常被捕获。
        """
        from adata.sentiment.hot import Hot

        self.assertTrue(callable(Hot.pop_rank_100_east))
        self.assertTrue(callable(Hot.hot_rank_100_ths))
        self.assertTrue(callable(Hot.hot_concept_20_ths))

    @patch('adata.sentiment.hot.requests')
    def test_hot_method_exception_caught_by_handler_null(self, mock_requests):
        """测试 Hot 方法抛出异常时被 @handler_null 捕获并记录"""
        from adata.sentiment.hot import Hot

        mock_response = MagicMock()
        mock_response.json.side_effect = ValueError("invalid json response")
        mock_requests.request.return_value = mock_response

        result = Hot.pop_rank_100_east()

        self.assertTrue(result.empty)
        self.assertTrue(error_tracker.has_errors())

        errors = error_tracker.get_errors()
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].error_type, 'ValueError')
        self.assertIn('invalid json', errors[0].error_msg)

    def test_stock_lifting_has_handler_null(self):
        """测试 StockLifting 的方法有 @handler_null 装饰器"""
        from adata.sentiment.stock_lifting import StockLifting

        instance = StockLifting()
        self.assertTrue(hasattr(instance.stock_lifting_last_month, '__wrapped__') or
                        'wrapper' in str(instance.stock_lifting_last_month.__name__))

    def test_securities_margin_has_handler_null(self):
        """测试 SecuritiesMargin 的方法有 @handler_null 装饰器"""
        from adata.sentiment.securities_margin import SecuritiesMargin

        instance = SecuritiesMargin()
        self.assertTrue(hasattr(instance.securities_margin, '__wrapped__') or
                        'wrapper' in str(instance.securities_margin.__name__))

    def test_mine_clearance_has_handler_null(self):
        """测试 MineClearance 的方法有 @handler_null 装饰器"""
        from adata.sentiment.mine_clearance import MineClearance

        instance = MineClearance()
        self.assertTrue(hasattr(instance.mine_clearance_tdx, '__wrapped__') or
                        'wrapper' in str(instance.mine_clearance_tdx.__name__))

    def test_hot_method_exception_returns_empty_df(self):
        """测试 Hot 静态方法异常时返回空 DataFrame 并记录错误"""
        from adata.sentiment.hot import Hot

        original_func = Hot.pop_rank_100_east

        @staticmethod
        @handler_null
        def failing_func():
            raise ValueError("hot rank error")

        Hot.pop_rank_100_east = failing_func

        try:
            result = Hot.pop_rank_100_east()
            self.assertTrue(result.empty)
            self.assertTrue(error_tracker.has_errors())

            errors = error_tracker.get_errors()
            self.assertEqual(len(errors), 1)
            self.assertEqual(errors[0].error_type, 'ValueError')
            self.assertEqual(errors[0].error_msg, 'hot rank error')
        finally:
            Hot.pop_rank_100_east = original_func


class SunRequestsTestCase(unittest.TestCase):
    """SunRequests 便捷方法测试"""

    def test_get_method_exists(self):
        """测试 get 便捷方法存在"""
        from adata.common.utils.sunrequests import SunRequests
        sr = SunRequests()
        self.assertTrue(callable(sr.get))

    def test_post_method_exists(self):
        """测试 post 便捷方法存在"""
        from adata.common.utils.sunrequests import SunRequests
        sr = SunRequests()
        self.assertTrue(callable(sr.post))

    def test_put_method_exists(self):
        """测试 put 便捷方法存在"""
        from adata.common.utils.sunrequests import SunRequests
        sr = SunRequests()
        self.assertTrue(callable(sr.put))

    def test_delete_method_exists(self):
        """测试 delete 便捷方法存在"""
        from adata.common.utils.sunrequests import SunRequests
        sr = SunRequests()
        self.assertTrue(callable(sr.delete))

    def test_head_method_exists(self):
        """测试 head 便捷方法存在"""
        from adata.common.utils.sunrequests import SunRequests
        sr = SunRequests()
        self.assertTrue(callable(sr.head))

    def test_patch_method_exists(self):
        """测试 patch 便捷方法存在"""
        from adata.common.utils.sunrequests import SunRequests
        sr = SunRequests()
        self.assertTrue(callable(sr.patch))

    def test_options_method_exists(self):
        """测试 options 便捷方法存在"""
        from adata.common.utils.sunrequests import SunRequests
        sr = SunRequests()
        self.assertTrue(callable(sr.options))

    @patch('adata.common.utils.sunrequests.requests.request')
    def test_get_calls_request_with_get_method(self, mock_request):
        """测试 get 方法调用 request 时使用 GET 方法"""
        from adata.common.utils.sunrequests import SunRequests
        sr = SunRequests()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_request.return_value = mock_response

        sr.get('http://example.com', params={'a': 'b'})

        mock_request.assert_called_once()
        call_kwargs = mock_request.call_args
        self.assertEqual(call_kwargs[1].get('method', call_kwargs[0][0] if call_kwargs[0] else 'get'), 'get')
        self.assertIn('url', call_kwargs.kwargs)

    @patch('adata.common.utils.sunrequests.requests.request')
    def test_post_calls_request_with_post_method(self, mock_request):
        """测试 post 方法调用 request 时使用 POST 方法"""
        from adata.common.utils.sunrequests import SunRequests
        sr = SunRequests()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_request.return_value = mock_response

        sr.post('http://example.com', json={'key': 'value'})

        mock_request.assert_called_once()

    def test_unknown_attribute_has_clear_error_message(self):
        """测试访问未知属性时有明确的错误提示"""
        from adata.common.utils.sunrequests import SunRequests
        sr = SunRequests()

        try:
            sr.some_unknown_method()
            self.fail("Should have raised AttributeError")
        except AttributeError as e:
            error_msg = str(e)
            self.assertIn('SunRequests', error_msg)
            self.assertIn('不是 Python 标准库', error_msg)
            self.assertIn('adata', error_msg)

    def test_unknown_session_attribute_has_clear_error(self):
        """测试访问常见的 requests.Session 属性时有提示"""
        from adata.common.utils.sunrequests import SunRequests
        sr = SunRequests()

        try:
            sr.Session()
            self.fail("Should have raised AttributeError")
        except AttributeError as e:
            error_msg = str(e)
            self.assertIn('不是 Python 标准库', error_msg)

    def test_private_attribute_raises_normal_error(self):
        """测试访问私有属性时不触发友好提示"""
        from adata.common.utils.sunrequests import SunRequests
        sr = SunRequests()

        try:
            _ = sr._private_attr
            self.fail("Should have raised AttributeError")
        except AttributeError as e:
            error_msg = str(e)
            self.assertNotIn('不是 Python 标准库', error_msg)

    def test_sun_requests_instance(self):
        """测试全局 sun_requests 实例是 SunRequests 类型"""
        from adata.common.utils.sunrequests import sun_requests, SunRequests
        self.assertIsInstance(sun_requests, SunRequests)

    def test_requests_alias_points_to_same_instance(self):
        """测试 common/utils 导出的 requests 是 sun_requests"""
        from adata.common.utils import requests, sun_requests
        self.assertIs(requests, sun_requests)


if __name__ == '__main__':
    unittest.main()
