"""This module wraps the :class:`Socket` and :class:`Context` found in :mod:`pyzmq <zmq>` to be non blocking
"""
import zmq
from zmq import *

# imported with different names as to not have the star import try to to clobber (when building with cython)
from zmq.core.context import Context as _original_Context
from zmq.core.socket import Socket as _original_Socket
from zmq.core.poll import Poller as _original_Poller

import gevent
import gevent.core
from gevent.event import Event
from gevent.hub import get_hub


class _Context(_original_Context):
    """Replacement for :class:`zmq.core.context.Context`

    Ensures that the greened Socket below is used in calls to `socket`.
    """

    def socket(self, socket_type):
        """Overridden method to ensure that the green version of socket is used

        Behaves the same as :meth:`zmq.core.context.Context.socket`, but ensures
        that a :class:`Socket` with all of its send and recv methods set to be
        non-blocking is returned
        """
        if self.closed:
            raise ZMQError(ENOTSUP)
        return _Socket(self, socket_type)

class _Socket(_original_Socket):
    """Green version of :class:`zmq.core.socket.Socket`

    The following methods are overridden:

        * send
        * recv

    To ensure that the ``zmq.NOBLOCK`` flag is set and that sending or recieving
    is deferred to the hub if a ``zmq.EAGAIN`` (retry) error is raised.
    
    The `__state_changed` method is triggered when the zmq.FD for the socket is
    marked as readable and triggers the necessary read and write events (which
    are waited for in the recv and send methods).

    Some double underscore prefixes are used to minimize pollution of
    :class:`zmq.core.socket.Socket`'s namespace.
    """

    def __init__(self, context, socket_type):
        self.__setup_events()

    def close(self):
        # close the _state_event event, keeps the number of active file descriptors down
        if not self.closed and getattr(self, '_state_event', None):
            try:
                self._state_event.stop()
            except AttributeError, e:
                # gevent<1.0 compat
                self._state_event.cancel()
        super(_Socket, self).close()

    def __setup_events(self):
        self.__readable = Event()
        self.__writable = Event()
        try:
            self._state_event = get_hub().loop.io(self.getsockopt(FD), 1) # read state watcher
            self._state_event.start(self.__state_changed)
        except AttributeError:
            # for gevent<1.0 compatibility
            from gevent.core import read_event
            self._state_event = read_event(self.getsockopt(FD), self.__state_changed, persist=True)

    def __state_changed(self, event=None, _evtype=None):
        if self.closed:
            # if the socket has entered a close state resume any waiting greenlets
            self.__writable.set()
            self.__readable.set()
            return

        events = self.getsockopt(zmq.EVENTS)
        if events & zmq.POLLOUT:
            self.__writable.set()
        if events & zmq.POLLIN:
            self.__readable.set()

    def _wait_write(self):
        self.__writable.clear()
        self.__writable.wait()

    def _wait_read(self):
        self.__readable.clear()
        self.__readable.wait()

    def send(self, data, flags=0, copy=True, track=False):
        # if we're given the NOBLOCK flag act as normal and let the EAGAIN get raised
        if flags & zmq.NOBLOCK:
            return super(_Socket, self).send(data, flags, copy, track)
        # ensure the zmq.NOBLOCK flag is part of flags
        flags |= zmq.NOBLOCK
        while True: # Attempt to complete this operation indefinitely, blocking the current greenlet
            try:
                # attempt the actual call
                return super(_Socket, self).send(data, flags, copy, track)
            except zmq.ZMQError, e:
                # if the raised ZMQError is not EAGAIN, reraise
                if e.errno != zmq.EAGAIN:
                    raise
            # defer to the event loop until we're notified the socket is writable
            self._wait_write()

    def recv(self, flags=0, copy=True, track=False):
        if flags & zmq.NOBLOCK:
            return super(_Socket, self).recv(flags, copy, track)
        flags |= zmq.NOBLOCK
        while True:
            try:
                return super(_Socket, self).recv(flags, copy, track)
            except zmq.ZMQError, e:
                if e.errno != zmq.EAGAIN:
                    raise
            self._wait_read()


class _Poller(object):

    def __init__(self):
        self.sockets = {}
        self.result = []
        self.event = Event()
		
    def register(self, socket, flags=POLLIN|POLLOUT):

        if socket in self.sockets:
            self.unregister(socket)

        if flags:

            gevent_flags = 0
            if flags & zmq.POLLIN: gevent_flags |= gevent.core.EV_READ
            if flags & zmq.POLLOUT: gevent_flags |= gevent.core.EV_WRITE

            try:
                watcher = get_hub().loop.io(self._get_handle(socket), gevent_flags)
                watcher.priority = get_hub().loop.MAXPRI
                watcher.start(self._sockready, socket)
            except AttributeError, e:
                from gevent.core import readwrite_event, read_event, write_event
                if flags & zmq.POLLIN and flags & zmq.POLLOUT :
                    watcher = readwrite_event(self._get_handle(socket), self._sockready, persist=True, arg=socket)
                elif flags & zmq.POLLIN:
                    watcher = read_event(self._get_handle(socket), self._sockready, persist=True, arg=socket)
                elif flags & zmq.POLLOUT:
                    watcher = write_event(self._get_handle(socket), self._sockready, persist=True, arg=socket)

            self.sockets[socket] = { 'watcher': watcher, 'flags': flags }

        else:
            pass

    def modify(self, socket, flags):
        self.register(socket, flags)

    def unregister(self, socket):

        if not socket in self.sockets:
            return
        try:
            self.sockets[socket]['watcher'].stop()
        except AttributeError, e:
            self.sockets[socket]['watcher'].cancel()


    def _sockready(self, event, flags):

        zmq_flags = 0	
        if flags & gevent.core.EV_READ: zmq_flags |= zmq.POLLIN
        if flags & gevent.core.EV_WRITE: zmq_flags |= zmq.POLLOUT

        self.result.append((event.arg, zmq_flags))
        print 'event set'
        self.event.set()

    def _get_handle(self, socket):

        if isinstance(socket, Socket):
            return socket.getsockopt(FD)
        if isinstance(socket, int):
            return socket
        elif hasattr(socket, 'fileno'):
            try:
                return int(socket.fileno())
            except:
                raise ValueError('fileno() must return an valid integer fd')
        else:
            raise TypeError(
                "Socket must be a 0MQ socket, an integer fd or have "
                "a fileno() method: %r" % socket
            )


    def poll(self, timeout=-1):

        if timeout is None:
            timeout = -1
        
        timeout = int(timeout)
        if timeout < 0:
            timeout = -1

        self.event.wait(timeout=timeout)
        res = self.result
        self.event.clear()
        self.result = []
        return res 


			
