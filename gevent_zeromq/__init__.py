"""gevent_zmq - gevent compatibility with zeromq.

"""

import gevent_zeromq.core as zmq
zmq.Context = zmq._Context
zmq.Socket = zmq._Socket

def monkey_patch(test_suite=False, zmq_devices=False):
    """
    Monkey patches `zmq.Context` and `zmq.Socket`

    If test_suite is True, the pyzmq test suite will be patched for
    compatibility as well.
    """
    ozmq = __import__('zmq')
    ozmq_core = __import__('zmq.core')
    ozmq.Socket = ozmq_core.Socket = zmq.Socket
    ozmq.Context = ozmq_core.Context = zmq.Context


    if test_suite:
        from gevent_zeromq.tests import monkey_patch_test_suite
        monkey_patch_test_suite()
