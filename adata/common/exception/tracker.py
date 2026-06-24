# -*- coding: utf-8 -*-
"""
@desc: adata 事件追踪器 — 记录数据源异常和 fallback 切换事件
@author: 1nchaos
@time: 2025/6/24
@log: change log
"""

import enum
import threading
import traceback


class EventType(enum.Enum):
    EXCEPTION = "exception"
    FALLBACK = "fallback"


class _Event:
    __slots__ = ("event_type", "source", "op_type", "message", "detail", "from_source")

    def __init__(self, event_type, source, op_type, message, detail=None, from_source=None):
        self.event_type = event_type
        self.source = source
        self.op_type = op_type
        self.message = message
        self.detail = detail
        self.from_source = from_source

    def to_dict(self):
        d = {
            "event_type": self.event_type.value,
            "source": self.source,
            "op_type": self.op_type,
            "message": self.message,
        }
        if self.from_source:
            d["from_source"] = self.from_source
        if self.detail:
            d["detail"] = self.detail
        return d


class AdataTracker:
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._events = []
            self._callbacks = []
            self._enabled = True
            self._initialized = True

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def reset(cls):
        with cls._lock:
            if cls._instance is not None:
                cls._instance._events.clear()
                cls._instance._callbacks.clear()
                cls._instance._enabled = True

    def record_exception(self, source, op_type, message, detail=None):
        if not self._enabled:
            return
        event = _Event(EventType.EXCEPTION, source, op_type, message, detail)
        self._events.append(event)
        self._dispatch(event)

    def record_fallback(self, from_source, to_source, op_type, message="", detail=None):
        if not self._enabled:
            return
        msg = message or f"data source fallback: {from_source} -> {to_source}"
        event = _Event(EventType.FALLBACK, to_source, op_type, msg, detail, from_source=from_source)
        self._events.append(event)
        self._dispatch(event)

    def on_event(self, callback):
        self._callbacks.append(callback)

    def clear(self):
        self._events.clear()

    @property
    def events(self):
        return list(self._events)

    def last_event(self):
        return self._events[-1] if self._events else None

    def events_by_type(self, event_type):
        if isinstance(event_type, str):
            event_type = EventType(event_type)
        return [e for e in self._events if e.event_type == event_type]

    def _dispatch(self, event):
        for cb in self._callbacks:
            try:
                cb(event)
            except Exception:
                pass

    def enable(self):
        self._enabled = True

    def disable(self):
        self._enabled = False


tracker = AdataTracker()
