import os
import sys

from distutils.core import Command, setup
from distutils.command.build_ext import build_ext
from traceback import print_exc

cython_available = False
try:
    from Cython.Distutils import build_ext
    from Cython.Distutils.extension import Extension
    cython_available = True
except ImportError, e:
    pass

try:
    import nose
except ImportError:
    nose = None

def get_ext_modules():
    if not cython_available:
        print 'WARNING: cython not available, proceeding with pure python implementation.'
        return []
    try:
        import gevent
    except ImportError, e:
        print 'WARNING: gevent must be installed to build cython version of gevent-zeromq (%s).' % e
        return []
    try:
        import zmq
    except ImportError, e:
        print 'WARNING: pyzmq(>=2.1.0) must be installed to build cython version of gevent-zeromq (%s).' % e
        return []

    return [Extension('gevent_zeromq.core', ['gevent_zeromq/core.pyx'], include_dirs=zmq.get_includes())]

class TestCommand(Command):
    """Custom distutils command to run the test suite."""

    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        # crude check for inplace build:
        try:
            import gevent_zeromq
        except ImportError:
            print_exc()
            print ("Could not import gevent_zeromq!")
            print ("You must build gevent_zeromq with 'python setup.py build_ext --inplace' for 'python setup.py test' to work.")
            print ("If you did build gevent_zeromq in-place, then this is a real error.")
            sys.exit(1)

        gevent_zeromq.monkey_patch(test_suite=True) # monkey patch
        import zmq
        self._zmq_dir = os.path.dirname(zmq.__file__)

        if nose is None:
            print ("nose unavailable, skipping tests.")
        else:
            return nose.core.TestProgram(argv=["", '-vvs', os.path.join(self._zmq_dir, 'tests')])

__version__ = (0, 2, 2)

setup(
    name = 'gevent_zeromq',
    version = '.'.join([str(x) for x in __version__]),
    packages = ['gevent_zeromq'],
    cmdclass = {'build_ext': build_ext, 'test': TestCommand},
    ext_modules = get_ext_modules(),
    author = 'Travis Cline',
    author_email = 'travis.cline@gmail.com',
    url = 'http://github.com/traviscline/gevent-zeromq',
    description = 'gevent compatibility layer for pyzmq',
    long_description=open('README.rst').read(),
    install_requires = ['pyzmq>=2.1.0', 'gevent'],
    license = 'New BSD',
)
