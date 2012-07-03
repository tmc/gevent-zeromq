=============
gevent-zeromq
=============

This library wraps pyzmq to make it compatible with gevent. ØMQ socket
operations that would normally block the current thread will only block the
current greenlet instead.

Requirements
------------

* pyzmq==2.2.0
* gevent (compatible with 1.0 pre-releases as well)


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

Will build with cython if available, decreasing overhead.

License
-------
See LICENSE (New BSD)
