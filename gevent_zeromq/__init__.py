"""gevent_zmq - gevent compatibility with zeromq.

"""

import gevent_zeromq._zmq as zmq

def monkey_patch():
    ozmq = __import__('zmq')
    ozmq.Socket = zmq.Socket
    ozmq.Context = zmq.Context
