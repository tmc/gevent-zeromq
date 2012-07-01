"""This module wraps the :class:`Socket` and :class:`Context` found in :mod:`pyzmq <zmq>` to be non blocking
"""
import zmq
from zmq import *
from zmq import devices
__all__ = zmq.__all__

import gevent
from gevent import select
from gevent.event import AsyncResult
from gevent.hub import get_hub

from zmq.core.context cimport Context as _Context
from zmq.core.socket cimport Socket as _Socket


cdef class GreenSocket(_Socket):
    """Green version of :class:`zmq.core.socket.Socket`

    The following methods are overridden:

        * send
        * send_multipart
        * recv
        * recv_multipart

    To ensure that the ``zmq.NOBLOCK`` flag is set and that sending or recieving
    is deferred to the hub if a ``zmq.EAGAIN`` (retry) error is raised.
    
    The `__state_changed` method is triggered when the zmq.FD for the socket is
    marked as readable and triggers the necessary read and write events (which
    are waited for in the recv and send methods).

    Some double underscore prefixes are used to minimize pollution of
    :class:`zmq.core.socket.Socket`'s namespace.
    """
    cdef object __readable
    cdef object __writable
    cdef object __in_send_mulitpart
    cdef object __in_recv_mulitpart
    cdef public object _state_event

    def __init__(self, context, int socket_type):
        self.__in_send_multipart = False
        self.__in_recv_multipart = False
        self.__setup_events()

    def __del__(self):
        self.close()

    def close(self, linger=None):
        super(GreenSocket, self).close(linger)
        self.__cleanup_events()

    def __cleanup_events(self):
        # close the _state_event event, keeps the number of active file descriptors down
        if getattr(self, '_state_event', None):
            try:
                self._state_event.stop()
            except AttributeError, e:
                # gevent<1.0 compat
                self._state_event.cancel()

        # if the socket has entered a close state resume any waiting greenlets
        if hasattr(self, '__writable'):
            self.__writable.set()
            self.__readable.set()

    def __setup_events(self):
        self.__readable = AsyncResult()
        self.__writable = AsyncResult()
        try:
            self._state_event = get_hub().loop.io(self.getsockopt(FD), 1) # read state watcher
            self._state_event.start(self.__state_changed)
        except AttributeError:
            # for gevent<1.0 compatibility
            from gevent.core import read_event
            self._state_event = read_event(self.getsockopt(FD), self.__state_changed, persist=True)

    def __state_changed(self, event=None, _evtype=None):
        cdef int events
        if self.closed:
            self.__cleanup_events()
            return
        try:
            events = super(GreenSocket, self).getsockopt(EVENTS)
        except ZMQError, exc:
            self.__writable.set_exception(exc)
            self.__readable.set_exception(exc)
        else:
            if events & POLLOUT:
                self.__writable.set()
            if events & POLLIN:
                self.__readable.set()

    cdef _wait_write(self) with gil:
        self.__writable = AsyncResult()
        try:
            self.__writable.get(timeout=1)
        except gevent.Timeout:
            self.__writable.set()

    cdef _wait_read(self) with gil:
        self.__readable = AsyncResult()
        try:
            self.__readable.get(timeout=1)
        except gevent.Timeout:
            self.__readable.set()

    cpdef object send(self, object data, int flags=0, copy=True, track=False):
        # if we're given the NOBLOCK flag act as normal and let the EAGAIN get raised
        if flags & NOBLOCK:
            return _Socket.send(self, data, flags, copy, track)
        # ensure the zmq.NOBLOCK flag is part of flags
        flags = flags | NOBLOCK
        while True: # Attempt to complete this operation indefinitely, blocking the current greenlet
            try:
                # attempt the actual call
                return _Socket.send(self, data, flags, copy, track)
            except ZMQError, e:
                # if the raised ZMQError is not EAGAIN, reraise
                if e.errno != EAGAIN:
                    raise
            # defer to the event loop until we're notified the socket is writable
            self._wait_write()

    cpdef object recv(self, int flags=0, copy=True, track=False):
        if flags & NOBLOCK:
            return _Socket.recv(self, flags, copy, track)
        flags = flags | NOBLOCK
        while True:
            try:
                return _Socket.recv(self, flags, copy, track)
            except ZMQError, e:
                if e.errno != EAGAIN:
                    raise
            self._wait_read()

    def send_multipart(self, *args, **kwargs):
        """wrap send_multipart to prevent state_changed on each partial send"""
        self.__in_send_multipart = True
        try:
            msg = super(GreenSocket, self).send_multipart(*args, **kwargs)
        finally:
            self.__in_send_multipart = False
            self.__state_changed()
        return msg

    def recv_multipart(self, *args, **kwargs):
        """wrap recv_multipart to prevent state_changed on each partial recv"""
        self.__in_recv_multipart = True
        try:
            msg = super(GreenSocket, self).recv_multipart(*args, **kwargs)
        finally:
            self.__in_recv_multipart = False
            self.__state_changed()
        return msg


class GreenContext(_Context):
    """Replacement for :class:`zmq.core.context.Context`

    Ensures that the greened Socket below is used in calls to `socket`.
    """
    _socket_class = GreenSocket


class GreenPoller(Poller):
    """Replacement for :class:`zmq.core.Poller`

    Ensures that the greened Poller below is used in calls to
    :meth:`zmq.core.Poller.poll`.
    """

    def _get_descriptors(self):
        """Returns three elements tuple with socket descriptors ready
        for gevent.select.select
        """
        rlist = []
        wlist = []
        xlist = []

        for socket, flags in self.sockets.items():
            if isinstance(socket, zmq.Socket):
                rlist.append(socket.getsockopt(zmq.FD))
                continue
            elif isinstance(socket, int):
                fd = socket
            elif hasattr(socket, 'fileno'):
                try:
                    fd = int(socket.fileno())
                except:
                    raise ValueError('fileno() must return an valid integer fd')
            else:
                raise TypeError('Socket must be a 0MQ socket, an integer fd '
                                'or have a fileno() method: %r' % socket)

            if flags & zmq.POLLIN:
                rlist.append(fd)
            if flags & zmq.POLLOUT:
                wlist.append(fd)
            if flags & zmq.POLLERR:
                xlist.append(fd)

        return (rlist, wlist, xlist)

    def poll(self, timeout=-1):
        """Overridden method to ensure that the green version of
        Poller is used.

        Behaves the same as :meth:`zmq.core.Poller.poll`
        """

        if timeout is None:
            timeout = -1

        if timeout < 0:
            timeout = -1

        rlist = None
        wlist = None
        xlist = None

        if timeout > 0:
            tout = gevent.Timeout.start_new(timeout/1000.0)

        try:
            # Loop until timeout or events available
            rlist, wlist, xlist = self._get_descriptors()
            while True:
                events = super(GreenPoller, self).poll(0)
                if events or timeout == 0:
                    return events

                # wait for activity on sockets in a green way
                select.select(rlist, wlist, xlist)

        except gevent.Timeout, t:
            if t is not tout:
                raise
            return []
        finally:
           if timeout > 0:
               tout.cancel()
