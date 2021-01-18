
from __future__ import absolute_import, print_function
from array import array
from binascii import hexlify
from traceback import print_exception
import os, sys

import bup_main

# Please see CODINGSTYLE for important exception handling guidelines
# and the rationale behind add_ex_tb(), add_ex_ctx(), etc.

py_maj = sys.version_info[0]
py3 = py_maj >= 3

if py3:

    from os import environb as environ
    from os import fsdecode, fsencode
    from shlex import quote
    ModuleNotFoundError = ModuleNotFoundError
    input = input
    range = range
    str_type = str
    int_types = (int,)

    def hexstr(b):
        """Return hex string (not bytes as with hexlify) representation of b."""
        return b.hex()

    def reraise(ex):
        raise ex.with_traceback(sys.exc_info()[2])

    def add_ex_tb(ex):
        """Do nothing (already handled by Python 3 infrastructure)."""
        return ex

    def add_ex_ctx(ex, context_ex):
        """Do nothing (already handled by Python 3 infrastructure)."""
        return ex

    class pending_raise:
        """Rethrow either the provided ex, or any exception raised by the with
        statement body.  (Supports Python 2 compatibility.)

        """
        def __init__(self, ex):
            self.ex = ex
        def __enter__(self):
            return None
        def __exit__(self, exc_type, exc_value, traceback):
            if not exc_type:
                raise self.ex
            return None

    def items(x):
        return x.items()

    def argv_bytes(x):
        """Return the original bytes passed to main() for an argv argument."""
        return fsencode(x)

    def bytes_from_uint(i):
        return bytes((i,))

    def bytes_from_byte(b):  # python > 2: b[3] returns ord('x'), not b'x'
        return bytes((b,))

    byte_int = lambda x: x

    def buffer(object, offset=None, size=None):
        if size:
            assert offset is not None
            return memoryview(object)[offset:offset + size]
        if offset:
            return memoryview(object)[offset:]
        return memoryview(object)

    def getcwd():
        return fsencode(os.getcwd())

else:  # Python 2

    ModuleNotFoundError = ImportError

    def fsdecode(x):
        return x

    def fsencode(x):
        return x

    from pipes import quote
    from os import environ, getcwd

    from bup.py2raise import reraise

    input = raw_input
    range = xrange
    str_type = basestring
    int_types = (int, long)

    hexstr = hexlify

    def add_ex_tb(ex):
        """Add a traceback to ex if it doesn't already have one.  Return ex.

        """
        if not getattr(ex, '__traceback__', None):
            ex.__traceback__ = sys.exc_info()[2]
        return ex

    def add_ex_ctx(ex, context_ex):
        """Make context_ex the __context__ of ex (unless it already has one).
        Return ex.

        """
        if context_ex:
            if not getattr(ex, '__context__', None):
                ex.__context__ = context_ex
        return ex

    class pending_raise:
        """Rethrow either the provided ex, or any exception raised by the with
        statement body, after making ex the __context__ of the newer
        exception (assuming there's no existing __context__).  Ensure
        the exceptions have __tracebacks__.  (Supports Python 2
        compatibility.)

        """
        def __init__(self, ex):
            self.ex = ex
        def __enter__(self):
            add_ex_tb(self.ex)
            return None
        def __exit__(self, exc_type, exc_value, traceback):
            if not exc_type:
                raise self.ex
            add_ex_tb(exc_value)
            add_ex_ctx(exc_value, self.ex)
            return None

    def dump_traceback(ex):
        stack = [ex]
        next_ex = getattr(ex, '__context__', None)
        while next_ex:
            stack.append(next_ex)
            next_ex = getattr(next_ex, '__context__', None)
        stack = reversed(stack)
        ex = next(stack)
        tb = getattr(ex, '__traceback__', None)
        print_exception(type(ex), ex, tb)
        for ex in stack:
            print('\nDuring handling of the above exception, another exception occurred:\n',
                  file=sys.stderr)
            tb = getattr(ex, '__traceback__', None)
            print_exception(type(ex), ex, tb)

    def items(x):
        return x.iteritems()

    def argv_bytes(x):
        """Return the original bytes passed to main() for an argv argument."""
        return x

    bytes_from_uint = chr

    def bytes_from_byte(b):
        return b

    byte_int = ord

    buffer = buffer


argvb = bup_main.argv()
if py3:
    argv = [x.decode(errors='surrogateescape') for x in argvb]
else:
    argv = argvb


def wrap_main(main):
    """Run main() and raise a SystemExit with the return value if it
    returns, pass along any SystemExit it raises, convert
    KeyboardInterrupts into exit(130), and print a Python 3 style
    contextual backtrace for other exceptions in both Python 2 and
    3)."""
    try:
        sys.exit(main())
    except KeyboardInterrupt as ex:
        sys.exit(130)
    except SystemExit as ex:
        raise
    except BaseException as ex:
        if py3:
            raise
        add_ex_tb(ex)
        dump_traceback(ex)
        sys.exit(1)


# Excepting wrap_main() in the traceback, these should produce similar output:
#   python2 lib/bup/compat.py
#   python3 lib/bup/compat.py
# i.e.:
#   diff -u <(python2 lib/bup/compat.py 2>&1) <(python3 lib/bup/compat.py 2>&1)
#
# Though the python3 output for 'second' will include a stacktrace
# starting from wrap_main, rather than from outer().

if __name__ == '__main__':

    def inner():
        raise Exception('first')

    def outer():
        try:
            inner()
        except Exception as ex:
            add_ex_tb(ex)
            try:
                raise Exception('second')
            except Exception as ex2:
                raise add_ex_ctx(add_ex_tb(ex2), ex)

    wrap_main(outer)
