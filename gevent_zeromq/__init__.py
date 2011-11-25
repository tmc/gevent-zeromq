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

import gevent_zeromq.core as zmq
zmq.Context = zmq._Context
zmq.Socket = zmq._Socket
zmq.Poller = zmq._Poller

def monkey_patch(test_suite=False):
    """
    Monkey patches `zmq.Context` and `zmq.Socket`
    
    If test_suite is True, the pyzmq test suite will be patched for
    compatibility as well.
    """
    ozmq = __import__('zmq')
    ozmq.Socket = zmq.Socket
    ozmq.Context = zmq.Context
    ozmq.Poller = zmq.Poller
	
    if test_suite:
        from gevent_zeromq.tests import monkey_patch_test_suite
        monkey_patch_test_suite()
