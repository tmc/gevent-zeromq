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

import sys

if __name__ == '__main__':
    run_on_gevent = sys.argv[1] == 'gevent'
    if run_on_gevent:
#        from gevent import monkey
##        monkey.patch_all()
#        monkey.patch_socket()
        import gevent
        from gevent_zeromq import zmq
        print 'Starting gevent heart'
    else:
        print 'Starting regular heart'
        import zmq

import os
import time
import numpy
from zmq import devices

def start_device():
    dev = devices.ThreadDevice(zmq.FORWARDER, zmq.SUB, zmq.XREQ)
    dev.setsockopt_in(zmq.SUBSCRIBE, "")
    dev.setsockopt_out(zmq.IDENTITY, str(os.getpid()))
    dev.connect_in('tcp://127.0.0.1:5555')
    dev.connect_out('tcp://127.0.0.1:5556')
    dev.start()

def start_blocking_call(A):
    tic = time.time()
    numpy.dot(A,A.transpose())
    print "blocked for %.3f s"%(time.time()-tic)


if __name__ == '__main__':
    start_device()
    #wait for connections
    if run_on_gevent:
        gevent.sleep(1)
    else:
        time.sleep(1)


    A = numpy.random.random((2**11,2**11))
    try:
        print "starting blocking loop"
        while True:
            if run_on_gevent:
                gevent.spawn(start_blocking_call, A).join()
            else:
                start_blocking_call()
    except KeyboardInterrupt:
        print 'Exiting'
        sys.exit()
