"""gevent_zmq - gevent compatibility with zeromq.

"""

import gevent_zeromq.core as zmq
zmq.Context = zmq._Context
zmq.Socket = zmq._Socket

def monkey_patch(test_suite=False):
    """
    Monkey patches `zmq.Context` and `zmq.Socket`
    
    If test_suite is True, the pyzmq test suite will be patched for
    compatibility as well.
    """
    ozmq = __import__('zmq')
    ozmq.Socket = zmq.Socket
    ozmq.Context = zmq.Context

    if test_suite:
        from gevent_zeromq.tests import monkey_patch_test_suite
        monkey_patch_test_suite()
