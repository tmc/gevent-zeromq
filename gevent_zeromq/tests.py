from gevent_zeromq import zmq

def monkey_patch_test_suite():
    """
    Monkey patches parts of pyzmq's test suite to run them with gevent-zeromq.
    """
    zmqtests = __import__('zmq.tests', fromlist=['*', 'test_device', 'test_monqueue'])
    #import ipdb; ipdb.set_trace()
    
    import sys
    try:
        from nose import SkipTest
    except ImportError:
        class SkipTest(Exception):
            pass

    class GreenBaseZMQTestCase(zmqtests.BaseZMQTestCase):
        def assertRaisesErrno(self, errno, func, *args, **kwargs):
            if errno == zmq.EAGAIN:
                raise SkipTest("Skipping because we're green.")
            try:
                func(*args, **kwargs)
            except zmq.ZMQError:
                e = sys.exc_info()[1]
                self.assertEqual(e.errno, errno, "wrong error raised, expected '%s' \
    got '%s'" % (zmq.ZMQError(errno), zmq.ZMQError(e.errno)))
            else:
                self.fail("Function did not raise any error")

    zmqtests.BaseZMQTestCase = GreenBaseZMQTestCase
    
    class BlankTest(GreenBaseZMQTestCase):
        pass

    zmqtests.test_device.TestDevice = BlankTest
    zmqtests.test_monqueue.TestMonitoredQueue = BlankTest
    
