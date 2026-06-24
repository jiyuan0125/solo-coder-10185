# -*- coding: utf-8 -*-
"""
@desc: adata 异常可观测机制测试
@author: 1nchaos
@time: 2025/6/24
@log: change log
"""
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock

from adata.common.exception.exception_msg import AdataError, THS_IP_LIMIT_MSG, THS_IP_LIMIT_RES
from adata.common.exception.tracker import AdataTracker, EventType, tracker
from adata.common.exception.handler import handler_null
from adata.common.utils.code_utils import compile_exchange_by_stock_code, get_exchange_by_stock_code
from adata.common.utils.sunrequests import SunProxy


@pytest.fixture(autouse=True)
def _clear_tracker():
    tracker.clear()
    yield
    tracker.clear()


class TestAdataError:
    def test_basic_message(self):
        err = AdataError("test error")
        assert "test error" in str(err)
        assert err.source is None
        assert err.op_type is None

    def test_with_source_and_op_type(self):
        err = AdataError("ip limited", source="ths", op_type="get_market_index")
        assert "[source=ths|op_type=get_market_index] ip limited" == str(err)
        assert err.source == "ths"
        assert err.op_type == "get_market_index"

    def test_with_source_only(self):
        err = AdataError("fail", source="east")
        assert "[source=east] fail" == str(err)

    def test_with_op_type_only(self):
        err = AdataError("fail", op_type="fetch")
        assert "[op_type=fetch] fail" == str(err)


class TestTracker:
    def test_record_exception(self):
        tracker.record_exception(source="ths", op_type="get_index", message="ip limited")
        events = tracker.events
        assert len(events) == 1
        assert events[0].event_type == EventType.EXCEPTION
        assert events[0].source == "ths"
        assert events[0].op_type == "get_index"
        assert events[0].message == "ip limited"

    def test_record_fallback(self):
        tracker.record_fallback(from_source="sina", to_source="qq", op_type="list_market_current")
        events = tracker.events
        assert len(events) == 1
        assert events[0].event_type == EventType.FALLBACK
        assert events[0].source == "qq"
        assert "sina" in events[0].message
        assert "qq" in events[0].message

    def test_events_by_type(self):
        tracker.record_exception(source="ths", op_type="op1", message="e1")
        tracker.record_fallback(from_source="east", to_source="ths", op_type="op2")
        tracker.record_exception(source="baidu", op_type="op3", message="e2")
        exceptions = tracker.events_by_type(EventType.EXCEPTION)
        fallbacks = tracker.events_by_type(EventType.FALLBACK)
        assert len(exceptions) == 2
        assert len(fallbacks) == 1

    def test_events_by_type_string(self):
        tracker.record_exception(source="ths", op_type="op1", message="e1")
        result = tracker.events_by_type("exception")
        assert len(result) == 1

    def test_callback(self):
        received = []
        tracker.on_event(lambda e: received.append(e))
        tracker.record_exception(source="test", op_type="test", message="cb")
        assert len(received) == 1
        assert received[0].source == "test"

    def test_clear(self):
        tracker.record_exception(source="a", op_type="b", message="c")
        tracker.clear()
        assert len(tracker.events) == 0

    def test_disable(self):
        tracker.disable()
        tracker.record_exception(source="a", op_type="b", message="c")
        assert len(tracker.events) == 0
        tracker.enable()

    def test_last_event(self):
        assert tracker.last_event() is None
        tracker.record_exception(source="a", op_type="b", message="c")
        assert tracker.last_event().source == "a"

    def test_event_to_dict(self):
        tracker.record_exception(source="ths", op_type="op", message="msg")
        d = tracker.events[0].to_dict()
        assert d["event_type"] == "exception"
        assert d["source"] == "ths"
        assert d["op_type"] == "op"
        assert d["message"] == "msg"


class TestHandlerNull:
    def test_normal_return(self):
        class Foo:
            @handler_null
            def ok(self):
                return pd.DataFrame({"a": [1]})

        df = Foo().ok()
        assert not df.empty
        assert "_adata_event_type" not in df.attrs

    def test_exception_returns_empty_with_metadata(self):
        class Bar:
            @handler_null
            def fail(self):
                raise AdataError("boom", source="test_src", op_type="test_op")

        df = Bar().fail()
        assert df.empty
        assert df.attrs.get("_adata_event_type") == "exception"
        assert df.attrs.get("_adata_source") == "test_src"
        assert df.attrs.get("_adata_op_type") == "test_op"
        assert "boom" in df.attrs.get("_adata_message", "")

    def test_exception_tracked(self):
        class Baz:
            @handler_null
            def fail(self):
                raise RuntimeError("plain error")

        Baz().fail()
        events = tracker.events
        assert len(events) == 1
        assert events[0].event_type == EventType.EXCEPTION
        assert "plain error" in events[0].message

    def test_source_guess_from_class_name(self):
        class MockThsSource:
            @handler_null
            def fail(self):
                raise RuntimeError("err")

        MockThsSource().fail()
        events = tracker.events
        assert len(events) == 1
        assert events[0].source == "ths"


class TestIPRateLimitRaise:
    def test_market_index_ths_raises_adata_error(self):
        from adata.stock.market.index_market.market_index_ths import StockMarketIndexThs
        obj = StockMarketIndexThs()
        with patch.object(obj, '_get_text', return_value=THS_IP_LIMIT_RES):
            with pytest.raises(AdataError) as exc_info:
                obj.get_market_index(index_code='000001')
            assert exc_info.value.source == "ths"
            assert exc_info.value.op_type == "get_market_index"

    def test_market_index_min_raises_adata_error(self):
        from adata.stock.market.index_market.market_index_ths import StockMarketIndexThs
        obj = StockMarketIndexThs()
        with patch.object(obj, '_get_text', return_value=THS_IP_LIMIT_RES):
            with pytest.raises(AdataError) as exc_info:
                obj.get_market_index_min(index_code='000001')
            assert exc_info.value.source == "ths"
            assert exc_info.value.op_type == "get_market_index_min"

    def test_market_index_current_raises_adata_error(self):
        from adata.stock.market.index_market.market_index_ths import StockMarketIndexThs
        obj = StockMarketIndexThs()
        with patch.object(obj, '_get_text', return_value=THS_IP_LIMIT_RES):
            with pytest.raises(AdataError) as exc_info:
                obj.get_market_index_current(index_code='000001')
            assert exc_info.value.source == "ths"
            assert exc_info.value.op_type == "get_market_index_current"

    def test_concept_market_ths_raises_adata_error(self):
        from adata.stock.market.concepth_market.concept_market_ths import ConceptMarketThs
        obj = ConceptMarketThs()
        with patch.object(obj, '_get_text', return_value=THS_IP_LIMIT_RES):
            with pytest.raises(AdataError) as exc_info:
                obj.get_market_concept_ths(index_code='886013')
            assert exc_info.value.source == "ths"

    def test_concept_market_min_raises_adata_error(self):
        from adata.stock.market.concepth_market.concept_market_ths import ConceptMarketThs
        obj = ConceptMarketThs()
        with patch.object(obj, '_get_text', return_value=THS_IP_LIMIT_RES):
            with pytest.raises(AdataError) as exc_info:
                obj.get_market_concept_min_ths(index_code='886041')
            assert exc_info.value.source == "ths"

    def test_concept_market_current_raises_adata_error(self):
        from adata.stock.market.concepth_market.concept_market_ths import ConceptMarketThs
        obj = ConceptMarketThs()
        with patch.object(obj, '_get_text', return_value=THS_IP_LIMIT_RES):
            with pytest.raises(AdataError) as exc_info:
                obj.get_market_concept_current_ths(index_code='886013')
            assert exc_info.value.source == "ths"

    def test_etf_market_ths_raises_adata_error(self):
        from adata.fund.market.etf_market_ths import ETFMarketThs
        obj = ETFMarketThs()
        with patch.object(obj, '_get_text', return_value=THS_IP_LIMIT_RES):
            with pytest.raises(AdataError) as exc_info:
                obj.get_market_etf_ths(fund_code='512880')
            assert exc_info.value.source == "ths"

    def test_etf_market_min_raises_adata_error(self):
        from adata.fund.market.etf_market_ths import ETFMarketThs
        obj = ETFMarketThs()
        with patch.object(obj, '_get_text', return_value=THS_IP_LIMIT_RES):
            with pytest.raises(AdataError) as exc_info:
                obj.get_market_etf_min_ths(fund_code='512880')
            assert exc_info.value.source == "ths"

    def test_etf_market_current_raises_adata_error(self):
        from adata.fund.market.etf_market_ths import ETFMarketThs
        obj = ETFMarketThs()
        with patch.object(obj, '_get_text', return_value=THS_IP_LIMIT_RES):
            with pytest.raises(AdataError) as exc_info:
                obj.get_market_etf_current_ths(fund_code='512880')
            assert exc_info.value.source == "ths"

    def test_north_flow_min_ths_raises_adata_error(self):
        from adata.sentiment.north_flow import NorthFlow
        obj = NorthFlow()
        with patch('adata.sentiment.north_flow.requests') as mock_req:
            mock_res = MagicMock()
            mock_res.text = THS_IP_LIMIT_RES
            mock_req.request.return_value = mock_res
            with pytest.raises(AdataError) as exc_info:
                obj._NorthFlow__north_flow_min_ths()
            assert exc_info.value.source == "ths"

    def test_fund_info_ths_raises_adata_error(self):
        from adata.fund.info.fund_info import FundInfo
        obj = FundInfo()
        with patch('adata.fund.info.fund_info.requests') as mock_req, \
             patch.object(obj, 'wencai_hexin_v', return_value='fake_v'):
            mock_res = MagicMock()
            mock_res.status_code = 200
            mock_res.text = f'some text {THS_IP_LIMIT_RES} more text'
            mock_res.json.return_value = {"status_msg": "ok", "answer": {"components": [{"data": {"datas": []}}]}}
            mock_req.request.return_value = mock_res
            with pytest.raises(AdataError) as exc_info:
                obj._FundInfo__all_etf_exchange_traded_info_ths(wait_time=None)
            assert exc_info.value.source == "ths"

    def test_stock_concept_ths_by_concept_code_raises(self):
        from adata.stock.info.concept.stock_concept_ths import StockConceptThs
        obj = StockConceptThs()
        with patch('adata.stock.info.concept.stock_concept_ths.requests') as mock_req:
            mock_res = MagicMock()
            mock_res.status_code = 200
            mock_res.text = THS_IP_LIMIT_RES
            mock_req.request.return_value = mock_res
            with pytest.raises(AdataError) as exc_info:
                obj.concept_constituent_ths(concept_code='301539')
            assert exc_info.value.source == "ths"
            assert exc_info.value.op_type == "concept_constituent_by_concept_code"

    def test_stock_concept_ths_by_index_code_raises(self):
        from adata.stock.info.concept.stock_concept_ths import StockConceptThs
        obj = StockConceptThs()
        with patch('adata.stock.info.concept.stock_concept_ths.requests') as mock_req:
            mock_res = MagicMock()
            mock_res.status_code = 200
            mock_res.text = THS_IP_LIMIT_RES
            mock_req.request.return_value = mock_res
            with pytest.raises(AdataError) as exc_info:
                obj.concept_constituent_ths(index_code='885338')
            assert exc_info.value.source == "ths"
            assert exc_info.value.op_type == "concept_constituent_by_index_code"

    def test_stock_concept_ths_by_name_raises(self):
        from adata.stock.info.concept.stock_concept_ths import StockConceptThs
        obj = StockConceptThs()
        with patch('adata.stock.info.concept.stock_concept_ths.requests') as mock_req:
            mock_res = MagicMock()
            mock_res.status_code = 200
            mock_res.text = THS_IP_LIMIT_RES
            mock_res.json.return_value = {"answer": {"components": [{"data": {"datas": []}}]}}
            mock_req.request.return_value = mock_res
            with pytest.raises(AdataError) as exc_info:
                obj.concept_constituent_ths(name='test')
            assert exc_info.value.source == "ths"
            assert exc_info.value.op_type == "concept_constituent_by_name"


class TestFallbackTracking:
    def test_stock_market_get_market_min_fallback(self):
        from adata.stock.market.stock_market.stock_market import StockMarket
        sm = StockMarket()
        empty_df = pd.DataFrame(data=[], columns=[])
        full_df = pd.DataFrame({"a": [1]})
        with patch.object(sm.east_market, 'get_market_min', return_value=empty_df), \
             patch.object(sm.baidu_market, 'get_market_min', return_value=full_df):
            result = sm.get_market_min(stock_code='000001')
            assert not result.empty
            fallback_events = tracker.events_by_type(EventType.FALLBACK)
            assert len(fallback_events) == 1
            assert fallback_events[0].source == "baidu"
            assert result.attrs.get("_adata_event_type") == "fallback"
            assert result.attrs.get("_adata_from_source") == "east"

    def test_stock_market_list_market_current_fallback(self):
        from adata.stock.market.stock_market.stock_market import StockMarket
        sm = StockMarket()
        empty_df = pd.DataFrame(data=[], columns=[])
        full_df = pd.DataFrame({"a": [1]})
        with patch.object(sm.sina_market, 'list_market_current', return_value=empty_df), \
             patch.object(sm.qq_market, 'list_market_current', return_value=full_df):
            result = sm.list_market_current(code_list=['000001'])
            fallback_events = tracker.events_by_type(EventType.FALLBACK)
            assert len(fallback_events) == 1
            assert result.attrs.get("_adata_event_type") == "fallback"
            assert result.attrs.get("_adata_from_source") == "sina"

    def test_stock_market_get_market_five_fallback(self):
        from adata.stock.market.stock_market.stock_market import StockMarket
        sm = StockMarket()
        empty_df = pd.DataFrame(data=[], columns=[])
        full_df = pd.DataFrame({"a": [1]})
        with patch.object(sm.qq_market, 'get_market_five', return_value=empty_df), \
             patch.object(sm.baidu_market, 'get_market_five', return_value=full_df):
            result = sm.get_market_five(stock_code='000001')
            fallback_events = tracker.events_by_type(EventType.FALLBACK)
            assert len(fallback_events) == 1
            assert result.attrs.get("_adata_event_type") == "fallback"

    def test_stock_market_get_market_bar_fallback(self):
        from adata.stock.market.stock_market.stock_market import StockMarket
        sm = StockMarket()
        empty_df = pd.DataFrame(data=[], columns=[])
        full_df = pd.DataFrame({"a": [1]})
        with patch.object(sm.baidu_market, 'get_market_bar', return_value=empty_df), \
             patch.object(sm.qq_market, 'get_market_bar', return_value=full_df):
            result = sm.get_market_bar(stock_code='000001')
            fallback_events = tracker.events_by_type(EventType.FALLBACK)
            assert len(fallback_events) == 1
            assert result.attrs.get("_adata_event_type") == "fallback"

    def test_market_index_fallback(self):
        from adata.stock.market.index_market.market_index import StockMarketIndex
        mi = StockMarketIndex()
        empty_df = pd.DataFrame(data=[], columns=[])
        full_df = pd.DataFrame({"a": [1]})
        with patch.object(mi.east_index, 'get_market_index', return_value=empty_df), \
             patch.object(mi.ths_index, 'get_market_index', return_value=full_df):
            result = mi.get_market_index(index_code='000001')
            fallback_events = tracker.events_by_type(EventType.FALLBACK)
            assert len(fallback_events) == 1
            assert fallback_events[0].source == "ths"

    def test_north_flow_min_fallback(self):
        from adata.sentiment.north_flow import NorthFlow
        nf = NorthFlow()
        empty_df = pd.DataFrame(data=[], columns=nf._NorthFlow__NORTH_FLOW_MIN_COLUMNS)
        full_df = pd.DataFrame(data=[[1, 2, 3, 4]], columns=nf._NorthFlow__NORTH_FLOW_MIN_COLUMNS)
        with patch.object(nf, '_NorthFlow__north_flow_min_east', return_value=empty_df), \
             patch.object(nf, '_NorthFlow__north_flow_min_ths', return_value=full_df):
            result = nf.north_flow_min()
            fallback_events = tracker.events_by_type(EventType.FALLBACK)
            assert len(fallback_events) == 1
            assert fallback_events[0].source == "ths"


class TestCodeUtils:
    def test_compile_exchange_known_prefix(self):
        assert compile_exchange_by_stock_code('000001') == '000001.SZ'
        assert compile_exchange_by_stock_code('600001') == '600001.SH'
        assert compile_exchange_by_stock_code('830001') == '830001.BJ'

    def test_compile_exchange_unknown_prefix(self):
        assert compile_exchange_by_stock_code('XX0001') == 'XX0001'

    def test_compile_exchange_empty(self):
        assert compile_exchange_by_stock_code('') == ''
        assert compile_exchange_by_stock_code(None) is None

    def test_compile_exchange_short(self):
        assert compile_exchange_by_stock_code('A') == 'A'

    def test_get_exchange_known_prefix(self):
        assert get_exchange_by_stock_code('000001') == 'SZ'
        assert get_exchange_by_stock_code('600001') == 'SH'
        assert get_exchange_by_stock_code('830001') == 'BJ'

    def test_get_exchange_unknown_prefix(self):
        assert get_exchange_by_stock_code('XX0001') == ''

    def test_get_exchange_empty(self):
        assert get_exchange_by_stock_code('') == ''
        assert get_exchange_by_stock_code(None) == ''

    def test_get_exchange_short(self):
        assert get_exchange_by_stock_code('A') == ''

    def test_safety_in_apply(self):
        df = pd.DataFrame({"code": ["000001", "XX9999", "", "600001"]})
        df["exchange"] = df["code"].apply(get_exchange_by_stock_code)
        assert list(df["exchange"]) == ["SZ", "", "", "SH"]


class TestSunProxy:
    def test_instantiation_not_none(self):
        SunProxy._instance = None
        proxy = SunProxy()
        assert proxy is not None
        assert isinstance(proxy, SunProxy)

    def test_singleton(self):
        SunProxy._instance = None
        p1 = SunProxy()
        p2 = SunProxy()
        assert p1 is p2

    def test_set_get_delete(self):
        SunProxy._instance = None
        SunProxy._data = {}
        proxy = SunProxy()
        proxy.set("key1", "val1")
        assert proxy.get("key1") == "val1"
        proxy.delete("key1")
        assert proxy.get("key1") is None


class TestEmptyDataFrameMetadata:
    def test_exception_df_metadata_distinguishes_from_fallback(self):
        class FailSrc:
            @handler_null
            def fail(self):
                raise AdataError("src error", source="src_a", op_type="fetch_data")

        df_exc = FailSrc().fail()
        assert df_exc.attrs.get("_adata_event_type") == "exception"

        from adata.stock.market.stock_market.stock_market import _attach_fallback_meta
        df_fb = _attach_fallback_meta(pd.DataFrame(), "sina", "qq", "list_market_current")
        assert df_fb.attrs.get("_adata_event_type") == "fallback"

        assert df_exc.attrs["_adata_event_type"] != df_fb.attrs["_adata_event_type"]

    def test_fallback_df_has_from_source(self):
        from adata.stock.market.stock_market.stock_market import _attach_fallback_meta
        df = _attach_fallback_meta(pd.DataFrame(), "sina", "qq", "list_market_current")
        assert df.attrs.get("_adata_from_source") == "sina"
        assert df.attrs.get("_adata_source") == "qq"

    def test_exception_df_no_from_source(self):
        class FailSrc:
            @handler_null
            def fail(self):
                raise AdataError("err", source="x", op_type="y")

        df = FailSrc().fail()
        assert "_adata_from_source" not in df.attrs


class TestBareExceptFixed:
    def test_qq_market_bar_tracks_exception(self):
        from adata.stock.market.stock_market.stock_market_qq import StockMarketQQ
        qq = StockMarketQQ()
        with patch('adata.stock.market.stock_market.stock_market_qq.requests') as mock_req:
            mock_res = MagicMock()
            mock_res.text = 'bad data'
            mock_req.request.return_value = mock_res
            result = qq.get_market_bar(stock_code='000001')
            assert isinstance(result, pd.DataFrame)
            exceptions = tracker.events_by_type(EventType.EXCEPTION)
            assert any(e.op_type == "get_market_bar_page" for e in exceptions)

    def test_mine_clearance_tracks_exception(self):
        from adata.sentiment.mine_clearance import MineClearance
        mc = MineClearance()
        with patch('adata.common.utils.sunrequests.sun_requests.request', side_effect=ConnectionError("refused")):
            result = mc.mine_clearance_tdx(stock_code='600811')
            assert isinstance(result, pd.DataFrame)
            exceptions = tracker.events_by_type(EventType.EXCEPTION)
            assert any(e.source == "tdx" for e in exceptions)
