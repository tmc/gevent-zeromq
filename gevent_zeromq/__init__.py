"""gevent_zmq - gevent compatibility with zeromq.

The star imports below are unfortunate, if you have a cleaner way to fall back
to a pure-python implementation please let me know.
"""
try:
    # attempt to import the straight c version
    import gevent_zeromq._gevent_zeromq as zmq
except ImportError:
    # falling back to pure python if we hit an ImportError
    import gevent_zeromq._gevent_zeromq_python as zmq
