"""This module wraps the :class:`Socket` and :class:`Context` found in :mod:`pyzmq <zmq>` to be non blocking
"""
import zmq
from zmq import *
from zmq.core import context, socket
from gevent.hub import _threadlocal
from gevent.socket import wait_read, wait_write


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



