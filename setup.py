import os
import sys
from glob import glob
from traceback import print_exc

cython_available = False
try:
    from setuptools import setup
    from setuptools import Command
    from Cython.Distutils import build_ext
    from Cython.Distutils.extension import Extension
    cython_available = True

except ImportError, e:
    print 'WARNING: cython not available, proceeding with pure python implementation. (%s)' % e
    from setuptools.core import Command, Extension, setup
    from setuptools.command.build_ext import build_ext


try:
    import nose
except ImportError:
    nose = None

def get_ext_modules():

    try:
        import gevent
    except ImportError, e:
        print 'WARNING: gevent must be installed to build cython version of gevent-zeromq (%s).', e
        return []
    try:
        import zmq
    except ImportError, e:
        print 'WARNING: pyzmq(>=2.1.0) must be installed to build cython version of gevent-zeromq (%s).', e
        return []

    extension = Extension(
        'gevent_zeromq.core',
        ['gevent_zeromq/core.pyx'],
        include_dirs = zmq.get_includes() + [
            os.path.dirname(os.path.dirname(zmq.__file__))
        ]
    )

    if extension.sources == ['gevent_zeromq/core.c']:
        extension.sources = ['gevent_zeromq/core.pyx']
    return [extension]


class TestCommand(Command):
    """Custom distutils command to run the test suite."""

    user_options = [ ]

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run_nose(self):
        """Run the test suite with nose."""
        return nose.core.TestProgram(argv=["", '-vvs', os.path.join(self._zmq_dir, 'tests')])

    def run_unittest(self):
        """Finds all the tests modules in zmq/tests/ and runs them."""
        testfiles = [ ]
        for t in glob(os.path.join(self._zmq_dir, 'tests', '*.py')):
            name = os.path.splitext(os.path.basename(t))[0]
            if name.startswith('test_'):
                testfiles.append('.'.join(
                    ['zmq.tests', name])
                )
        tests = TestLoader().loadTestsFromNames(testfiles)
        t = TextTestRunner(verbosity = 2)
        t.run(tests)

    def run(self):
        # crude check for inplace build:
        try:
            import gevent_zeromq
        except ImportError:
            print_exc()
            print ("Could not import gevent_zeromq!")
            print ("You must build pyzmq with 'python setup.py build_ext --inplace' for 'python setup.py test' to work.")
            print ("If you did build gevent_zeromq in-place, then this is a real error.")
            sys.exit(1)

        gevent_zeromq.monkey_patch(test_suite=True) # monkey patch
        import zmq
        self._zmq_dir = os.path.dirname(zmq.__file__)

        if nose is None:
            print ("nose unavailable, falling back on unittest. Skipped tests will appear as ERRORs.")
            return self.run_unittest()
        else:
            return self.run_nose()

if cython_available:
    ext_modules = get_ext_modules()
else:
    ext_modules = []

__version__ = (0, 0, 2)

setup(
    name = 'gevent_zeromq',
    version = '.'.join([str(x) for x in __version__]),
    packages = ['gevent_zeromq'],
    cmdclass = {'build_ext': build_ext, 'test': TestCommand},
    ext_modules = ext_modules,
    author = 'Travis Cline',
    author_email = 'travis.cline@gmail.com',
    description = 'gevent compatibility layer for pyzmq',
)
