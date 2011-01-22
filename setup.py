from distutils.core import setup
from distutils.extension import Extension
from distutils.command.build_ext import build_ext

cython_available = False
try:
    from Cython.Distutils import build_ext
    from Cython.Distutils.extension import Extension
    cython_available = True
except ImportError:
    print 'cython not available, proceeding with pure python implementation.'
    pass

def get_ext_modules():
    import zmq
    return [
        Extension(
            'gevent_zeromq._zmq',
            ['gevent_zeromq/_zmq.py'],
            include_dirs = zmq.get_includes(),
        ),
    ]

if cython_available:
    ext_modules = get_ext_modules()
else:
    ext_modules = []

__version__ = (0, 0, 1)

setup(
    name = 'gevent_zeromq',
    version = '.'.join([str(x) for x in __version__]),
    packages = ['gevent_zeromq'],
    cmdclass = {'build_ext': build_ext},
    ext_modules = ext_modules,
    author = 'Travis Cline',
    author_email = 'travis.cline@gmail.com',
    description = 'gevent compatibility layer for pyzmq',
    install_requires = ['pyzmq>=2.1.0', 'gevent'],
)
