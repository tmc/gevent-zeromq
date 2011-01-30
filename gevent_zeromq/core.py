"""This module wraps the :class:`Socket` and :class:`Context` found in :mod:`pyzmq <zmq>` to be non blocking
"""
import zmq
from zmq import *

# imported with different names as to not have the star import try to to clobber (when building with cython)
from zmq.core.context import Context as _original_Context
from zmq.core.socket import Socket as _original_Socket

from gevent.event import Event
from gevent.hub import get_hub

# the number of EAGAINS to encounter before defering to file descriptor polling
NUM_EAGAINS_BEFORE_DEFER = 5


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

    Some doubleunderscore prefixes are used to minimize pollution of
    :class:`zmq.core.socket.Socket`'s namespace.
    """

    def __init__(self, context, socket_type):
        super(Socket, self).__init__(context, socket_type)
        self.__setup_events()

    def close(self):
        # close the _state_event event and delete it, keeps the number of
        # of active file descriptors down
        super(Socket, self).close()
        if hasattr(self, '_state_event'):
            self._state_event.cancel()
            del(self._state_event)

    def __setup_events(self):
        self.__readable = Event()
        self.__writable = Event()
        try:
            read_event = get_hub().reactor.read_event
            self._state_event = read_event(self.getsockopt(zmq.FD), persist=True)
            self._state_event.add(None, self.__state_changed)
        except AttributeError:
            # for gevent<=0.14 compatibility
            from gevent.core import read_event
            self._state_event = read_event(self.getsockopt(zmq.FD), self.__state_changed, persist=True)

    def __state_changed(self, event, _evtype):
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
        # Marker as to if we've encountered EAGAIN yet. Required have zmq work well with deallocating many sockets
        num_eagains = 0
        # ensure the zmq.NOBLOCK flag is part of flags
        flags |= zmq.NOBLOCK
        while True: # Attempt to complete this operation indefinitely, blocking the current greenlet
            try:
                # attempt the actual call
                return super(Socket, self).send(data, flags, copy, track)
            except zmq.ZMQError, e:
                # if the raised ZMQError is not EAGAIN, reraise
                if e.errno != zmq.EAGAIN:
                    raise
                # if this is our first time seeing EAGAIN, avoid calling _wait_write just yet
                if num_eagains < NUM_EAGAINS_BEFORE_DEFER:
                    num_eagains += 1
                    continue
            # at this point we've seen enough EAGAINs, defer to the event loop until we're notified the socket is writable
            self._wait_write()

    def recv(self, flags=0, copy=True, track=False):
        num_eagains = 0
        flags |= zmq.NOBLOCK
        while True:
            try:
                return super(Socket, self).recv(flags, copy, track)
            except zmq.ZMQError, e:
                if e.errno != zmq.EAGAIN:
                    raise
                if num_eagains < NUM_EAGAINS_BEFORE_DEFER:
                    num_eagains += 1
                    continue
            self._wait_read()
