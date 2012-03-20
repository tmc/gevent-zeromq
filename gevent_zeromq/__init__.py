# -*- coding: utf-8 -*-
"""gevent_zmq - gevent compatibility with zeromq.

Usage
-----

Instead of importing zmq directly, do so in the following manner:

..

    from gevent_zeromq import zmq


Any calls that would have blocked the current thread will now only block the
current green thread.

This compatibility is accomplished by ensuring the nonblocking flag is set
before any blocking operation and the ØMQ file descriptor is polled internally
to trigger needed events.
"""

from zmq import *
from zmq import devices
import gevent_zeromq.core as zmq
from gevent_zeromq.poll import GreenPoller

zmq.Socket = zmq.GreenSocket
zmq.Context = zmq.GreenContext
zmq.Poller = GreenPoller
Socket = zmq.GreenSocket
Context = zmq.GreenContext
Poller = GreenPoller

def monkey_patch():
    """
    Monkey patches `zmq.Context` and `zmq.Socket`

    If test_suite is True, the pyzmq test suite will be patched for
    compatibility as well.
    """
    ozmq = __import__('zmq')
    ozmq.Socket = zmq.Socket
    ozmq.Context = zmq.Context
    ozmq.Poller = zmq.Poller
    ioloop = __import__('zmq.eventloop.ioloop')
    ioloop.Poller = zmq.Poller

__all__ = zmq.__all__ + ['monkey_patch']
