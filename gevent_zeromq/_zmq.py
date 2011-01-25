"""This module wraps the :class:`Socket` and :class:`Context` found in :mod:`pyzmq <zmq>` to be non blocking
"""
import zmq
from zmq import *
from zmq.core import context, socket

from gevent.event import Event
from gevent.hub import get_hub, _threadlocal


class Context(context.Context):
    """Replacement for :class:`zmq.core.context.Context`

    Ensures only one Context instance per thread. Returns our greened Socket on
    calls to `socket`.
    """
    def __new__(cls, io_threads=1):
        try:
            c = _threadlocal.zmq_context
            if c.closed:
                raise AttributeError
        except AttributeError:
            _threadlocal.zmq_context = context.Context.__new__(cls, io_threads)
            c = _threadlocal.zmq_context
        return c

    def socket(self, socket_type):
        """Overridden method to ensure that the green version of socket is used

        Behaves the same as :meth:`zmq.core.context.Context.socket`, but ensures
        that a :class:`Socket` with all of its send and recv methods set to be
        non-blocking is returned
        """
        return Socket(self, socket_type)


class Socket(socket.Socket):
    """Green version of :class:`zmq.core.socket.Socket`

    The following four methods are overridden:

        * _send_message
        * _send_copy
        * _recv_message
        * _recv_copy

    To ensure that the ``zmq.NOBLOCK`` flag is set and that sending or recieving
    is deferred to the hub if a ``zmq.EAGAIN`` (retry) error is raised.
    
    The `__setup_events` method is triggered when the zmq.FD for the socket is
    marked as readable and triggers the necessary read and write events (which
    are waited for in the recv and send methods).
    """

    def __init__(self, context, socket_type):
        super(Socket, self).__init__(context, socket_type)
        self.__setup_events()

    def __setup_events(self):
        self._read_ready = Event()
        self._write_ready = Event()
        try:
            read_event = get_hub().reactor.read_event
            self._state_event = read_event(self.getsockopt(zmq.FD), persist=True)
            self._state_event.add(None, self.__state_changed)
        except AttributeError:
            # for gevent<=0.14 compatibility
            from gevent.core import read_event
            self._state_event = read_event(self.getsockopt(zmq.FD), self.__state_changed, persist=True)

    def __state_changed(self, event, _evtype):
        events = self.getsockopt(zmq.EVENTS)
        if events & zmq.POLLOUT:
            self._write_ready.set()
        if events & zmq.POLLIN:
            self._read_ready.set()

    def _send_message(self, msg, flags=0):
        flags |= zmq.NOBLOCK
        while True:
            try:
                super(Socket, self)._send_message(msg, flags)
                return
            except zmq.ZMQError, e:
                if e.errno != zmq.EAGAIN:
                    raise
                self._write_ready.clear()
            self._write_ready.wait()

    def _send_copy(self, msg, flags=0):
        flags |= zmq.NOBLOCK
        while True:
            try:
                super(Socket, self)._send_copy(msg, flags)
                return
            except zmq.ZMQError, e:
                if e.errno != zmq.EAGAIN:
                    raise
                self._write_ready.clear()
            self._write_ready.wait()

    def _recv_message(self, flags=0, track=False):
        flags |= zmq.NOBLOCK
        while True:
            try:
                m = super(Socket, self)._recv_message(flags, track)
                if m is not None:
                    return m
            except zmq.ZMQError, e:
                if e.errno != zmq.EAGAIN:
                    raise
                self._read_ready.clear()
            self._read_ready.wait()

    def _recv_copy(self, flags=0):
        flags |= zmq.NOBLOCK
        while True:
            try:
                m = super(Socket, self)._recv_copy(flags)
                if m is not None:
                    return m
            except zmq.ZMQError, e:
                if e.errno != zmq.EAGAIN:
                    raise
                self._read_ready.clear()
            self._read_ready.wait()
