
from __future__ import absolute_import, print_function
from os.path import basename
from sys import stdout, stderr
import os, re, sys, traceback

_start_dir = os.getcwd()

attempt = 0

def _result(msg, tb, ok):
    global attempt
    filename, line, func, text = tb
    filename = basename(filename)
    msg = re.sub(r'\s+', ' ', str(msg))
    attempt += 1
    if ok:
        print('ok %d %s:%d %s' % (attempt, filename, line, msg))
    else:
        print('not ok %d %s:%d %s' % (attempt, filename, line, msg))
    stdout.flush()

def _caller_stack(wv_call_depth):
    # Without the chdir, the source text lookup may fail
    orig = os.getcwd()
    os.chdir(_start_dir)
    try:
        return traceback.extract_stack()[-(wv_call_depth + 2)]
    finally:
        os.chdir(orig)

def _check(cond, msg = 'unknown', tb = None):
    if tb == None: tb = _caller_stack(2)
    _result(msg, tb, cond)
    return cond

def wvcheck(cond, msg, tb = None):
    if tb == None: tb = _caller_stack(2)
    _result(msg, tb, cond)
    return cond

_code_rx = re.compile(r'^\w+\((.*)\)(\s*#.*)?$')
def _code():
    text = _caller_stack(2)[3]
    return _code_rx.sub(r'\1', text)

def WVSTART(message):
    stdout.write('# %s: %s\n' % (basename(sys.argv[0]), message))
    stdout.flush()

def WVPASS(cond = True): return _check(cond, _code())
def WVFAIL(cond = True): return _check(not cond, 'NOT(%s)' % _code())
def WVPASSEQ(a, b): return _check(a == b, '%s == %s' % (repr(a), repr(b)))
def WVPASSNE(a, b): return _check(a != b, '%s != %s' % (repr(a), repr(b)))
def WVPASSLT(a, b): return _check(a < b, '%s < %s' % (repr(a), repr(b)))
def WVPASSLE(a, b): return _check(a <= b, '%s <= %s' % (repr(a), repr(b)))
def WVPASSGT(a, b): return _check(a > b, '%s > %s' % (repr(a), repr(b)))
def WVPASSGE(a, b): return _check(a >= b, '%s >= %s' % (repr(a), repr(b)))
def WVEXCEPT(etype, func, *args, **kwargs):
    ''' Counts a test failure unless func throws an 'etype' exception.
        You have to spell out the function name and arguments, rather than
        calling the function yourself, so that WVEXCEPT can run before
        your test code throws an exception.
    '''
    try:
        func(*args, **kwargs)
    except etype as e:
        return _check(True, 'EXCEPT(%s)' % _code())
    except:
        _check(False, 'EXCEPT(%s)' % _code())
        raise
    else:
        return _check(False, 'EXCEPT(%s)' % _code())

WVMSG = WVSTART
wvmsg = WVMSG
wvstart = WVSTART
wvpass = WVPASS
wvfail = WVFAIL
wvpasseq = WVPASSEQ
wvpassne = WVPASSNE
wvpaslt = WVPASSLT
wvpassle = WVPASSLE
wvpassgt = WVPASSGT
wvpassge = WVPASSGE
wvexcept = WVEXCEPT
