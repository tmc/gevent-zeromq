=============
gevent-zeromq
=============

Wrapper of pyzmq to make it compatible with gevent. 0MQ socket operations that
would normally block the current thread will only block the current greenlet.

Inspired by Ben Ford's work on 0MQ support in eventlet.

Requirements
------------

Requires pyzmq>=2.1.0

Before version 2.1.0 (of both 0MQ and pyzmq) the underlying file descriptors
that this library utilizes were not available.


Usage
-----

Instead of importing zmq directly do a:

..
    
    from gevent_zeromq import zmq


And use as normal.


About
-----

This compatibility is accomplished by ensuring the nonblocking flag is set
before any blocking operation and the 0MQ file descriptor is polled internally
to trigger needed events.

Will build with cython if available. In my simple nonscientific test this
resulted in an almost 50% speedup in a local 1-1 PUB SUB sending of 100,000
1K messages in a single tight loop.

There are plans to further the integration with both gevent and pyzmq via
cython for speed.

License
-------
See LICENSE (New BSD)
