"""gevent_zmq - gevent compatibility with zeromq.

"""

import gevent_zeromq.core as zmq
zmq.Context = zmq._Context
zmq.Socket = zmq._Socket

def monkey_patch():
    ozmq = __import__('zmq')
    ozmq.Socket = zmq.Socket
    ozmq.Context = zmq.Context
