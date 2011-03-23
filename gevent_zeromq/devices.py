# -*- coding: utf-8 -*-
"""
    gevent_zeromq.devices
    ~~~~~~~


    :copyright: © 2011 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: BSD, see LICENSE for more details.
"""

import gevent
from zmq.devices import basedevice
from gevent_zeromq import zmq
from gevent_zeromq.core import _Socket
from gevent.greenlet import Greenlet

__all__ = basedevice.__all__ + ['GeventGreenletDevice']

def device(device_type, isocket, osocket):
    if device_type not in (zmq.FORWARDER, zmq.QUEUE, zmq.STREAMER):
        # Invalid device type
        raise zmq.ZMQError(zmq.EINVAL)

    if not isinstance(isocket, _Socket):
        # Non gevent cooperative socket
        raise NonCooperativeSocket(
            "isocket is not a green socket. Have you monkey_patch()?"
        )
    elif not isinstance(osocket, _Socket):
        # Non gevent cooperative socket
        raise NonCooperativeSocket(
            "osocket is not a green socket. Have you monkey_patch()?"
        )

    def process_isocket():
        while True:
            try:
                osocket.send(isocket.recv())
            except Exception:
                # XXX: Should we raise the exceptions? or keep mimicing pyzmq?
                return -1
        return 0

    def process_osocket():
        while True:
            try:
                isocket.send(osocket.recv())
            except Exception:
                # XXX: Should we raise the exceptions? or keep mimicing pyzmq?
                return -1
        return 0

    iprocess = gevent.spawn(process_isocket)
    oprocess = gevent.spawn(process_osocket)
    return gevent.joinall([iprocess, oprocess])


class NonCooperativeSocket(Exception):
    def __init__(self, message=None):
        self.message = message

    def __str__(self):
        return repr(self.message)

class __ContextChoose(object):
    def __init__(self, device_type, in_type, out_type):
        self.device_type = device_type
        self.in_type = in_type
        self.out_type = out_type
        self._in_binds = list()
        self._in_connects = list()
        self._in_sockopts = list()
        self._out_binds = list()
        self._out_connects = list()
        self._out_sockopts = list()
        self.daemon = True
        self.done = False

    def _setup_sockets(self):
        if self.__class__.__name__ == 'GeventGreenletDevice':
            ctx = zmq.Context()
        else:
            from zmq.core.context import Context as _original_Context
            ctx = _original_Context()
        self._context = ctx

        # create the sockets
        ins = ctx.socket(self.in_type)
        if self.out_type < 0:
            outs = ins
        else:
            outs = ctx.socket(self.out_type)

        # set sockopts (must be done first, in case of zmq.IDENTITY)
        for opt,value in self._in_sockopts:
            ins.setsockopt(opt, value)
        for opt,value in self._out_sockopts:
            outs.setsockopt(opt, value)

        for iface in self._in_binds:
            ins.bind(iface)
        for iface in self._out_binds:
            outs.bind(iface)

        for iface in self._in_connects:
            ins.connect(iface)
        for iface in self._out_connects:
            outs.connect(iface)

        return ins,outs

class Device(__ContextChoose, basedevice.Device):
    pass

class BackgroundDevice(__ContextChoose, basedevice.BackgroundDevice):
    pass

class ThreadDevice( __ContextChoose, basedevice.ThreadDevice):
    pass


if 'ProcessDevice' in basedevice.__all__:
    class ProcessDevice(__ContextChoose, basedevice.ProcessDevice):
        pass

class GeventGreenletDevice(BackgroundDevice):
    """
    A Device that will be run in a Greenlet.
    See Device for details.
    """
    _launch_class=Greenlet

    def start(self):
        self.launcher = self._launch_class(self.run)
        return self.launcher.start()

    def run(self):
        ins, outs = self._setup_sockets()
        rc = device(self.device_type, ins, outs)
        self.done = True
        return rc
