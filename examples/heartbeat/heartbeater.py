#!/usr/bin/env python
"""

For use with heart.py

A basic heartbeater using PUB and XREP sockets. pings are sent out on the PUB,
and hearts are tracked based on their XREQ identities.

You can start many hearts with heart.py, and the heartbeater will monitor all
of them, and notice when they stop responding.

Authors
-------
* MinRK
* Pedro Algarvio
"""

from gevent import monkey
monkey.patch_all()

import sys
import time
import gevent
from gevent_zeromq import zmq

class HeartBeater(object):
    """A basic HeartBeater class"""

    def __init__(self, period=1, check_xrep=False):
        self.period = period
        self.check_xrep = check_xrep

        self.hearts = set()
        self.responses = set()
        self.lifetime = 0
        self.tic = time.time()
        self.beating = False

        context = zmq.Context()
        self.pub = context.socket(zmq.PUB)
        self.pub.bind('tcp://127.0.0.1:5555')
        self.xrep = context.socket(zmq.XREP)
        self.xrep.bind('tcp://127.0.0.1:5556')

    def run(self):
        self.beating = True
        gevent.spawn(self.log_beating_hearts)
        if self.check_xrep:
            gevent.spawn_later(1, self.check_xrep_state)
        else:
            gevent.spawn_raw(self.recv_hearts_no_xrep_state_check)
        gevent.spawn_later(2, self.beat)

        while self.beating:
            gevent.sleep(5)

    def check_xrep_state(self):
        while True:
            events = self.xrep.getsockopt(zmq.EVENTS)
            if (events & zmq.POLLIN):
                gevent.spawn(self.recv_hearts)
            elif (events & zmq.POLLERR):
                print 'zmq.POLLERR'
                e = sys.exc_info()[1]
                if e.errno == zmq.EAGAIN:
                    # state changed since poll event
                    pass
                else:
                    print zmq.strerror(e.errno)
            gevent.sleep(0.001)

    def recv_hearts(self):
        buffer = []
        while True:
            message = self.xrep.recv(zmq.NOBLOCK)
            if message:
                buffer.append(message)
            if not self.xrep.rcvmore():
                # Message is now complete
                # break to process it!
                break
        gevent.spawn_later(0.001, self.handle_pong, buffer)

    def recv_hearts_no_xrep_state_check(self):
        buffer = []
        while True:
            message = self.xrep.recv()
            if message:
                buffer.append(message)
            if not self.xrep.rcvmore():
                # Message is now complete
                # break to process it!
                gevent.spawn_raw(self.handle_pong, buffer[:])
                buffer = []

    def beat(self):
        toc = time.time()
        self.lifetime += toc-self.tic
        self.tic = toc
        # self.message = str(self.lifetime)
        goodhearts = self.hearts.intersection(self.responses)
        heartfailures = self.hearts.difference(goodhearts)
        newhearts = self.responses.difference(goodhearts)
        # print newhearts, goodhearts, heartfailures
        map(self.handle_new_heart, newhearts)
        map(self.handle_heart_failure, heartfailures)
        self.responses = set()
        gevent.spawn_later(self.period, self.beat)
        gevent.spawn_raw(self.pub.send, str(self.lifetime))

    def log_beating_hearts(self):
        print "%i beating hearts: %s" % (len(self.hearts), self.hearts)
        gevent.spawn_later(5, self.log_beating_hearts)

    def handle_new_heart(self, heart):
        print "yay, got new heart %s!"%heart
        self.hearts.add(heart)

    def handle_heart_failure(self, heart):
        print "Heart %s failed :("%heart
        self.hearts.remove(heart)

    def handle_pong(self, msg):
        "if heart is beating"
        if msg[1] == str(self.lifetime):
            self.responses.add(msg[0])
        else:
            print "got bad heartbeat (possibly old?): %s"%msg[1]

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1]=='check_xrep':
        hb = HeartBeater(check_xrep=True)
    else:
        hb = HeartBeater(check_xrep=False)
    try:
        hb.run()
    except (KeyboardInterrupt, SystemExit):
        print "Exiting..."
