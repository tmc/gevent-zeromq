#!/usr/bin/env python
"""This launches an echoing rep socket device,
and runs a blocking numpy action. The rep socket should
remain responsive to pings during this time. Use heartbeater.py to
ping this heart, and see the responsiveness.

Authors
-------
* MinRK
* Pedro Algarvio
"""

import os
import time
import numpy
import gevent
import threading
import gevent_zeromq
from gevent_zeromq import zmq
from gevent_zeromq.devices import GeventGreenletDevice

gevent_zeromq.monkey_patch()

def im_alive(t=None):
    print "I'm alive!"
    if t:
        gevent.spawn_later(t, im_alive, t)

def run_blocking_call():
    A = numpy.random.random((2**11, 2**11))
    while True:
        print "starting blocking loop"
        tic = time.time()
        numpy.dot(A,A.transpose())
        print "blocked for %.3f s"%(time.time()-tic)


if __name__ == '__main__':

    dev = GeventGreenletDevice(zmq.FORWARDER, zmq.SUB, zmq.XREQ)
    dev.setsockopt_in(zmq.SUBSCRIBE, "")
    dev.setsockopt_out(zmq.IDENTITY, str(os.getpid()))
    dev.connect_in('tcp://127.0.0.1:5555')
    dev.connect_out('tcp://127.0.0.1:5556')
    dev.start()
    gevent.spawn_later(0, im_alive, 5)
    t = threading.Thread(target=run_blocking_call)
    t.daemon = True
    gevent.spawn_later(1, t.start)

    try:
        while True:
            print 'Sleeping'
            gevent.sleep(1)
    except KeyboardInterrupt:
        print 'Exiting'
        t.join(0)
