=============
gevent-zeromq
=============

Wrapper of pyzmq to make it compatible with gevent. ØMQ socket operations that
would normally block the current thread will only block the current greenlet.

Inspired by Ben Ford's work on ØMQ support in eventlet.

Requirements
------------

Requires pyzmq>=2.1.0

Before version 2.1.0 (of both ØMQ and pyzmq) the underlying file descriptors
that this library utilizes were not available.


Usage
-----

Instead of importing zmq directly, do so in the following manner:

..
    
    from gevent_zeromq import zmq


Any calls that would have blocked the current thread will now only block the
current green thread.


About
-----

This compatibility is accomplished by ensuring the nonblocking flag is set
before any blocking operation and the ØMQ file descriptor is polled internally
to trigger needed events.

Will build with cython if available. In my simple nonscientific test this
resulted in an almost 50% speedup in a local 1-1 PUB SUB sending of 100,000
1K messages in a single tight loop.

There are plans to further the integration with both gevent and pyzmq via
cython for speed.


License
-------
See LICENSE (New BSD)
