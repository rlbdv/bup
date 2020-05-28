#
# WvTest:
#   Copyright (C)2007-2012 Versabanq Innovations Inc. and contributors.
#       Licensed under the GNU Library General Public License, version 2.
#       See the included file named LICENSE for license information.
#       You can get wvtest from: http://github.com/apenwarr/wvtest
#

from __future__ import absolute_import, print_function
import os
import re
import traceback

_start_dir = os.getcwd()

attempt = 0
failures = 0

def wvfailure_count():
    return failures

def wvtest(func):
    """ Use this decorator (@wvtest) in front of any function you want to
        run as part of the unit test suite.  Then run:
            python wvtest.py path/to/yourtest.py [other test.py files...]
        to run all the @wvtest functions in the given file(s).
    """
    _registered.append(func)
    return func

def _result(msg, tb, ok):
    global attempt, failures
    filename, line, func, text = tb
    filename = os.path.basename(filename)
    msg = re.sub(r'\s+', ' ', str(msg))
    attempt += 1
    if ok:
        print('ok %d %s:%d %s' % (attempt, filename, line, msg))
    else:
        failures += 1
        print('not ok %d %s:%d %s' % (attempt, filename, line, msg))

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
    filename = _caller_stack(1)[0]
    print('# %s: %s' % (filename, message))

def WVMSG(message):
    return _result(message, _caller_stack(1), True)

def WVPASS(cond = True):
    ''' Counts a test failure unless cond is true. '''
    return _check(cond, _code())

def WVFAIL(cond = True):
    ''' Counts a test failure  unless cond is false. '''
    return _check(not cond, 'NOT(%s)' % _code())

def WVPASSEQ(a, b):
    ''' Counts a test failure unless a == b. '''
    return _check(a == b, '%s == %s' % (repr(a), repr(b)))

def WVPASSNE(a, b):
    ''' Counts a test failure unless a != b. '''
    return _check(a != b, '%s != %s' % (repr(a), repr(b)))

def WVPASSLT(a, b):
    ''' Counts a test failure unless a < b. '''
    return _check(a < b, '%s < %s' % (repr(a), repr(b)))

def WVPASSLE(a, b):
    ''' Counts a test failure unless a <= b. '''
    return _check(a <= b, '%s <= %s' % (repr(a), repr(b)))

def WVPASSGT(a, b):
    ''' Counts a test failure unless a > b. '''
    return _check(a > b, '%s > %s' % (repr(a), repr(b)))

def WVPASSGE(a, b):
    ''' Counts a test failure unless a >= b. '''
    return _check(a >= b, '%s >= %s' % (repr(a), repr(b)))

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
