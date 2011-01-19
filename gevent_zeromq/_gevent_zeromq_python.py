"""This module wraps the :class:`Socket` and :class:`Context` found in :mod:`pyzmq <zmq>` to be non blocking
"""
import zmq
from zmq import *
from gevent.hub import _threadlocal
from gevent.socket import wait_read, wait_write


def Context(io_threads=1):
    """Factory function replacement for :class:`zmq.core.context.Context`
    
    It's a factory function due to the fact that there can only be one :class:`_Context`
    instance per thread. This is due to the way :class:`zmq.core.poll.Poller`
    works
    """
    try:
        return _threadlocal.zmq_context
    except AttributeError:
        _threadlocal.zmq_context = _Context(io_threads)
        return _threadlocal.zmq_context

class _Context(zmq.Context):
    """Internal subclass of :class:`zmq.core.context.Context`

    .. warning:: Do not call this directly
    """

    def socket(self, socket_type):
        """Overridden method to ensure that the green version of socket is used

        Behaves the same as :meth:`zmq.core.context.Context.socket`, but ensures
        that a :class:`Socket` with all of its send and recv methods set to be
        non-blocking is returned
        """
        return Socket(self, socket_type)

class Socket(zmq.Socket):
    """Green version of :class:`zmq.core.socket.Socket

    The following four methods are overridden:

        * _send_message
        * _send_copy
        * _recv_message
        * _recv_copy

    To ensure that the ``zmq.NOBLOCK`` flag is set and that sending or recieving
    is deferred to the hub if a ``zmq.EAGAIN`` (retry) error is raised
    """

    def _send_message(self, msg, flags=0):
        flags |= zmq.NOBLOCK
        while True:
            try:
                super(Socket, self)._send_message(msg, flags)
                return
            except zmq.ZMQError, e:
                if e.errno != zmq.EAGAIN:
                    raise
            wait_write(self.getsockopt(zmq.FD))

    def _send_copy(self, msg, flags=0):
        flags |= zmq.NOBLOCK
        while True:
            try:
                super(Socket, self)._send_copy(msg, flags)
                return
            except zmq.ZMQError, e:
                if e.errno != zmq.EAGAIN:
                    raise
            wait_write(self.getsockopt(zmq.FD))

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
            wait_read(self.getsockopt(zmq.FD))

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
            wait_read(self.getsockopt(zmq.FD))



