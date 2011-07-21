"""This module wraps the :class:`Socket` and :class:`Context` found in :mod:`pyzmq <zmq>` to be non blocking
"""
import zmq
from zmq import *

# imported with different names as to not have the star import try to to clobber (when building with cython)
from zmq.core.context cimport Context as _original_Context
from zmq.core.socket cimport Socket as _original_Socket

from gevent.coros import Semaphore
from gevent.event import Event
from gevent.hub import get_hub

from gevent_zeromq.helpers import allow_unbound_disappear


cdef class _Socket(_original_Socket)

cdef class _Context(_original_Context):
    """Replacement for :class:`zmq.core.context.Context`

    Ensures that the greened Socket below is used in calls to `socket`.
    """

    def socket(self, int socket_type):
        """Overridden method to ensure that the green version of socket is used

        Behaves the same as :meth:`zmq.core.context.Context.socket`, but ensures
        that a :class:`Socket` with all of its send and recv methods set to be
        non-blocking is returned
        """
        if self.closed:
            raise ZMQError(ENOTSUP)
        return _Socket(self, socket_type)

cdef class _Socket(_original_Socket):
    """Green version of :class:`zmq.core.socket.Socket`

    The following methods are overridden:

        * send
        * recv

    To ensure that the ``zmq.NOBLOCK`` flag is set and that sending or recieving
    is deferred to the hub if a ``zmq.EAGAIN`` (retry) error is raised.
    
    The `__state_changed` method is triggered when the zmq.FD for the socket is
    marked as readable and triggers the necessary read and write events (which
    are waited for in the recv and send methods).

    Some doubleunderscore prefixes are used to minimize pollution of
    :class:`zmq.core.socket.Socket`'s namespace.
    """
    cdef object __send_multipart_semaphore
    cdef object __readable
    cdef object __writable
    cdef object __weakref__
    cdef public object _state_event

    def __init__(self, _Context context, int socket_type):
        super(_Socket, self).__init__(context, socket_type)
        self.__setup_events()
        self.__send_multipart_semaphore = Semaphore()

    def close(self):
        # close the _state_event event, keeps the number of active file descriptors down
        if not self.closed and getattr3(self, '_state_event', None):
            try:
                self._state_event.stop()
            except AttributeError, e:
                # gevent<1.0 compat
                self._state_event.cancel()
        super(_Socket, self).close()

    cdef __setup_events(self) with gil:
        self.__readable = Event()
        self.__writable = Event()
        callback = allow_unbound_disappear(
                _Socket.__state_changed, self, _Socket)
        try:
            self._state_event = get_hub().loop.io(self.__getsockopt(FD), 1) # read state watcher
            self._state_event.start(callback)
        except AttributeError, e:
            # for gevent<1.0 compatibility
            from gevent.core import read_event
            self._state_event = read_event(self.__getsockopt(FD), callback, persist=True)

    def __state_changed(self, event=None, _evtype=None):
        if self.closed:
            # if the socket has entered a close state resume any waiting greenlets
            self.__writable.set()
            self.__readable.set()
            return

        cdef int events = self.__getsockopt(EVENTS)
        if events & POLLOUT:
            self.__writable.set()
        if events & POLLIN:
            self.__readable.set()

    cdef __notify_waiters(self):
        """Notifies all waiters about a possible change in the socket state.
        The waiters can try to read or write.
        """
        self.__writable.set()
        self.__readable.set()

    cdef _wait_write(self) with gil:
        self.__writable.clear()
        self.__writable.wait()

    cdef _wait_read(self) with gil:
        self.__readable.clear()
        self.__readable.wait()

    cpdef object send(self, object data, int flags=0, copy=True, track=False):
        try:
            return self.__send(data, flags, copy, track)
        finally:
            self.__notify_waiters()

    cpdef object __send(self, object data, int flags=0, copy=True, track=False):
        # if we're given the NOBLOCK flag act as normal and let the EAGAIN get raised
        if flags & NOBLOCK:
            return _original_Socket.send(self, data, flags, copy, track)
        # ensure the zmq.NOBLOCK flag is part of flags
        flags = flags | NOBLOCK
        while True: # Attempt to complete this operation indefinitely, blocking the current greenlet
            try:
                # attempt the actual call
                return _original_Socket.send(self, data, flags, copy, track)
            except ZMQError, e:
                # if the raised ZMQError is not EAGAIN, reraise
                if e.errno != EAGAIN:
                    raise
            # defer to the event loop until we're notified the socket is writable
            self.__notify_waiters()
            self._wait_write()

    def send_multipart(self, msg_parts, flags=0, copy=True, track=False):
        # send_multipart is not greenlet-safe, i.e. message parts might get
        # split up if multiple greenlets call send_multipart on the same socket.
        # so we use a semaphore to ensure that there's only ony greenlet
        # calling send_multipart at any time
        with self.__send_multipart_semaphore:
            return _original_Socket.send_multipart(self, msg_parts, flags, copy, track)

    cpdef object recv(self, int flags=0, copy=True, track=False):
        try:
            return self.__recv(flags, copy, track)
        finally:
            self.__notify_waiters()

    cpdef object __recv(self, int flags=0, copy=True, track=False):
        if flags & NOBLOCK:
            return _original_Socket.recv(self, flags, copy, track)
        flags = flags | NOBLOCK
        while True:
            try:
                return _original_Socket.recv(self, flags, copy, track)
            except ZMQError, e:
                if e.errno != EAGAIN:
                    raise
            self.__notify_waiters()
            self._wait_read()

    def getsockopt(self, *args, **kw):
        try:
            return self.__getsockopt(*args, **kw)
        finally:
            self.__notify_waiters()

    def __getsockopt(self, *args, **kw):
        return _original_Socket.getsockopt(self, *args, **kw)
