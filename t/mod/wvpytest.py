
from __future__ import absolute_import
from sys import stdout
import os, pytest, traceback

_start_dir = os.getcwd()

def _caller_stack(wv_call_depth):
    # Without the chdir, the source text lookup may fail
    orig = os.getcwd()
    os.chdir(_start_dir)
    try:
        return traceback.extract_stack()[-(wv_call_depth + 2)]
    finally:
        os.chdir(orig)

def WVSTART(message):
    filename = _caller_stack(1)[0]
    stdout.write('# %s: %s\n' % (filename, message))
    stdout.flush()

def WVPASS(cond = True): assert cond
def WVFAIL(cond = True): assert not cond
def WVPASSEQ(a, b): assert a == b
def WVPASSNE(a, b): assert a != b
def WVPASSLT(a, b): assert a < b
def WVPASSLE(a, b): assert a <= b
def WVPASSGT(a, b): assert a > b
def WVPASSGE(a, b): assert a >= b
def WVEXCEPT(etype, func, *args, **kwargs):
    with pytest.raises(etype):
        func(*args, **kwargs)

WVMSG = WVSTART
wvstart = WVSTART
wvmsg = WVMSG
wvpass = WVPASS
wvfail = WVFAIL
wvpasseq = WVPASSEQ
wvpassne = WVPASSNE
wvpaslt = WVPASSLT
wvpassle = WVPASSLE
wvpassgt = WVPASSGT
wvpassge = WVPASSGE
wvexcept = WVEXCEPT
