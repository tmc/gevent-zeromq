import gevent
from gevent_zeromq import zmq

try:
    from gevent_utils import BlockingDetector
    gevent.spawn(BlockingDetector(25))
except ImportError:
    print 'If you encounter hangs consider installing gevent_utils'

