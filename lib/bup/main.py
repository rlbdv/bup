
from __future__ import absolute_import, print_function
from importlib import import_module
from pkgutil import iter_modules
from subprocess import PIPE
from threading import Thread
import errno, getopt, os, re, select, signal, subprocess, sys

from bup import compat, path, helpers
from bup.compat import (
    ModuleNotFoundError,
    add_ex_ctx,
    add_ex_tb,
    argv_bytes,
    environ,
    fsdecode,
    wrap_main
)
from bup.compat import add_ex_tb, add_ex_ctx, argv_bytes, wrap_main
from bup.helpers import (
    columnate,
    debug1,
    handle_ctrl_c,
    log,
    merge_dict,
    tty_width
)
from bup.git import close_catpipes
from bup.io import byte_stream, path_msg
from bup.options import _tty_width
import bup.cmd

def maybe_import_early(argv):
    """Scan argv and import any modules specified by --import-py-module."""
    while argv:
        if argv[0] != '--import-py-module':
            argv = argv[1:]
            continue
        if len(argv) < 2:
            log("bup: --import-py-module must have an argument\n")
            exit(2)
        mod = argv[1]
        import_module(mod)
        argv = argv[2:]

maybe_import_early(compat.argv)

handle_ctrl_c()

cmdpath = path.cmddir()

# We manipulate the subcmds here as strings, but they must be ASCII
# compatible, since we're going to be looking for exactly
# b'bup-SUBCMD' to exec.

def usage(msg=""):
    log('Usage: bup [-?|--help] [-d BUP_DIR] [--debug] [--profile] '
        '<command> [options...]\n\n')
    common = dict(
        ftp = 'Browse backup sets using an ftp-like client',
        fsck = 'Check backup sets for damage and add redundancy information',
        fuse = 'Mount your backup sets as a filesystem',
        help = 'Print detailed help for the given command',
        index = 'Create or display the index of files to back up',
        on = 'Backup a remote machine to the local one',
        restore = 'Extract files from a backup set',
        save = 'Save files into a backup set (note: run "bup index" first)',
        tag = 'Tag commits for easier access',
        web = 'Launch a web server to examine backup sets',
    )

    log('Common commands:\n')
    for cmd,synopsis in sorted(common.items()):
        log('    %-10s %s\n' % (cmd, synopsis))
    log('\n')
    
    log('Other available commands:\n')
    cmds = set()
    for c in sorted(os.listdir(cmdpath)):
        if c.startswith(b'bup-') and c.find(b'.') < 0:
            cname = fsdecode(c[4:])
            if cname not in common:
                cmds.add(c[4:].decode(errors='backslashreplace'))
    # built-in commands take precedence
    for _, name, _ in iter_modules(path=bup.cmd.__path__):
        name = name.replace('_','-')
        if name not in common:
            cmds.add(name)

    log(columnate(sorted(cmds), '    '))
    log('\n')
    
    log("See 'bup help COMMAND' for more information on " +
        "a specific command.\n")
    if msg:
        log("\n%s\n" % msg)
    sys.exit(99)

argv = compat.argv
if len(argv) < 2:
    usage()

# Handle global options.
try:
    optspec = ['help', 'version', 'debug', 'profile', 'bup-dir=',
               'import-py-module=']
    global_args, subcmd = getopt.getopt(argv[1:], '?VDd:', optspec)
except getopt.GetoptError as ex:
    usage('error: %s' % ex.msg)

subcmd = [argv_bytes(x) for x in subcmd]
help_requested = None
do_profile = False
bup_dir = None

for opt in global_args:
    if opt[0] in ['-?', '--help']:
        help_requested = True
    elif opt[0] in ['-V', '--version']:
        subcmd = [b'version']
    elif opt[0] in ['-D', '--debug']:
        helpers.buglvl += 1
        environ[b'BUP_DEBUG'] = b'%d' % helpers.buglvl
    elif opt[0] in ['--profile']:
        do_profile = True
    elif opt[0] in ['-d', '--bup-dir']:
        bup_dir = argv_bytes(opt[1])
    elif opt[0] == '--import-py-module':
        pass
    else:
        usage('error: unexpected option "%s"' % opt[0])

# Make BUP_DIR absolute, so we aren't affected by chdir (i.e. save -C, etc.).
if bup_dir:
    environ[b'BUP_DIR'] = os.path.abspath(bup_dir)

if len(subcmd) == 0:
    if help_requested:
        subcmd = [b'help']
    else:
        usage()

if help_requested and subcmd[0] != b'help':
    subcmd = [b'help'] + subcmd

if len(subcmd) > 1 and subcmd[1] == b'--help' and subcmd[0] != b'help':
    subcmd = [b'help', subcmd[0]] + subcmd[2:]

subcmd_name = subcmd[0]
if not subcmd_name:
    usage()

def subpath(subcmd):
    return os.path.join(cmdpath, b'bup-' + subcmd)

try:
    cmd_module = import_module('bup.cmd.'
                               + subcmd_name.decode('ascii').replace('-', '_'))
except ModuleNotFoundError as ex:
    cmd_module = None

if not cmd_module:
    subcmd[0] = subpath(subcmd_name)
    if not os.path.exists(subcmd[0]):
        usage('error: unknown command "%s"' % path_msg(subcmd_name))

already_fixed = int(environ.get(b'BUP_FORCE_TTY', 0))
if subcmd_name in [b'mux', b'ftp', b'help']:
    already_fixed = True
fix_stdout = not already_fixed and os.isatty(1)
fix_stderr = not already_fixed and os.isatty(2)

if fix_stdout or fix_stderr:
    tty_env = merge_dict(environ,
                         {b'BUP_FORCE_TTY': (b'%d'
                                             % ((fix_stdout and 1 or 0)
                                                + (fix_stderr and 2 or 0))),
                          b'BUP_TTY_WIDTH': b'%d' % _tty_width(), })
else:
    tty_env = environ


sep_rx = re.compile(br'([\r\n])')

def print_clean_line(dest, content, width, sep=None):
    """Write some or all of content, followed by sep, to the dest fd after
    padding the content with enough spaces to fill the current
    terminal width or truncating it to the terminal width if sep is a
    carriage return."""
    global sep_rx
    assert sep in (b'\r', b'\n', None)
    if not content:
        if sep:
            os.write(dest, sep)
        return
    for x in content:
        assert not sep_rx.match(x)
    content = b''.join(content)
    if sep == b'\r' and len(content) > width:
        content = content[width:]
    os.write(dest, content)
    if len(content) < width:
        os.write(dest, b' ' * (width - len(content)))
    if sep:
        os.write(dest, sep)

def filter_output(srcs, dests):
    """Transfer data from file descriptors in srcs to the corresponding
    file descriptors in dests print_clean_line until all of the srcs
    have closed.

    """
    global sep_rx
    assert all(type(x) in int_types for x in srcs)
    assert all(type(x) in int_types for x in srcs)
    assert len(srcs) == len(dests)
    srcs = tuple(srcs)
    dest_for = dict(zip(srcs, dests))
    pending = {}
    pending_ex = None
    try:
        while srcs:
            ready_fds, _, _ = select.select(srcs, [], [])
            width = tty_width()
            for fd in ready_fds:
                buf = os.read(fd, 4096)
                dest = dest_for[fd]
                if not buf:
                    srcs = tuple([x for x in srcs if x is not fd])
                    print_clean_line(dest, pending.pop(fd, []), width)
                else:
                    split = sep_rx.split(buf)
                    while len(split) > 1:
                        content, sep = split[:2]
                        split = split[2:]
                        print_clean_line(dest,
                                         pending.pop(fd, []) + [content],
                                         width,
                                         sep)
                    assert len(split) == 1
                    if split[0]:
                        pending.setdefault(fd, []).extend(split)
    except BaseException as ex:
        pending_ex = add_ex_ctx(add_ex_tb(ex), pending_ex)
    try:
        # Try to finish each of the streams
        for fd, pending_items in compat.items(pending):
            dest = dest_for[fd]
            width = tty_width()
            try:
                print_clean_line(dest, pending_items, width)
            except (EnvironmentError, EOFError) as ex:
                pending_ex = add_ex_ctx(add_ex_tb(ex), pending_ex)
    except BaseException as ex:
        pending_ex = add_ex_ctx(add_ex_tb(ex), pending_ex)
    if pending_ex:
        raise pending_ex


def import_and_run_main(module, args):
    if do_profile:
        import cProfile
        f = compile('module.main(args)', __file__, 'exec')
        cProfile.runctx(f, globals(), locals())
    else:
        module.main(args)


def run_module_cmd(module, args):
    if not (fix_stdout or fix_stderr):
        import_and_run_main(module, args)
        return
    # Interpose filter_output between all attempts to write to the
    # stdout/stderr and the real stdout/stderr (e.g. the fds that
    # connect directly to the terminal) via a thread that runs
    # filter_output in a pipeline.
    srcs = []
    dests = []
    real_out_fd = real_err_fd = stdout_pipe = stderr_pipe = None
    filter_thread = filter_thread_started = None
    pending_ex = None
    try:
        if fix_stdout:
            sys.stdout.flush()
            stdout_pipe = os.pipe()  # monitored_by_filter, stdout_everyone_uses
            real_out_fd = os.dup(sys.stdout.fileno())
            os.dup2(stdout_pipe[1], sys.stdout.fileno())
            srcs.append(stdout_pipe[0])
            dests.append(real_out_fd)
        if fix_stderr:
            sys.stderr.flush()
            stderr_pipe = os.pipe()  # monitored_by_filter, stderr_everyone_uses
            real_err_fd = os.dup(sys.stderr.fileno())
            os.dup2(stderr_pipe[1], sys.stderr.fileno())
            srcs.append(stderr_pipe[0])
            dests.append(real_err_fd)

        filter_thread = Thread(name='output filter',
                               target=lambda : filter_output(srcs, dests))
        filter_thread.start()
        filter_thread_started = True
        import_and_run_main(module, args)
    except Exception as ex:
        add_ex_tb(ex)
        pending_ex = ex
        raise
    finally:
        # Try to make sure that whatever else happens, we restore
        # stdout and stderr here, if that's possible, so that we don't
        # risk just losing some output.
        try:
            real_out_fd is not None and os.dup2(real_out_fd, sys.stdout.fileno())
        except Exception as ex:
            add_ex_tb(ex)
            add_ex_ctx(ex, pending_ex)
        try:
            real_err_fd is not None and os.dup2(real_err_fd, sys.stderr.fileno())
        except Exception as ex:
            add_ex_tb(ex)
            add_ex_ctx(ex, pending_ex)
        # Kick filter loose
        try:
            stdout_pipe is not None and os.close(stdout_pipe[1])
        except Exception as ex:
            add_ex_tb(ex)
            add_ex_ctx(ex, pending_ex)
        try:
            stderr_pipe is not None and os.close(stderr_pipe[1])
        except Exception as ex:
            add_ex_tb(ex)
            add_ex_ctx(ex, pending_ex)
        try:
            close_catpipes()
        except Exception as ex:
            add_ex_tb(ex)
            add_ex_ctx(ex, pending_ex)
    if pending_ex:
        raise pending_ex
    # There's no point in trying to join unless we finished the finally block.
    if filter_thread_started:
        filter_thread.join()


def run_subproc_cmd(args):

    c = (do_profile and [sys.executable, b'-m', b'cProfile'] or []) + args
    if not (fix_stdout or fix_stderr):
        os.execvp(c[0], c)

    sys.stdout.flush()
    sys.stderr.flush()
    out = byte_stream(sys.stdout)
    err = byte_stream(sys.stderr)
    p = None
    try:
        p = subprocess.Popen(c,
                             stdout=PIPE if fix_stdout else out,
                             stderr=PIPE if fix_stderr else err,
                             env=tty_env, bufsize=4096, close_fds=True)
        # Assume p will receive these signals and quit, which will
        # then cause us to quit.
        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGQUIT):
            signal.signal(sig, signal.SIG_IGN)

        srcs = []
        dests = []
        if fix_stdout:
            srcs.append(p.stdout.fileno())
            dests.append(out.fileno())
        if fix_stderr:
            srcs.append(p.stderr.fileno())
            dests.append(err.fileno())
        filter_output(srcs, dests)
        return p.wait()
    except BaseException as ex:
        add_ex_tb(ex)
        try:
            if p and p.poll() == None:
                os.kill(p.pid, signal.SIGTERM)
                p.wait()
        except BaseException as kill_ex:
            raise add_ex_ctx(add_ex_tb(kill_ex), ex)
        raise ex


def run_subcmd(module, args):
    if module:
        run_module_cmd(module, args)
    else:
        run_subproc_cmd(args)

def main():
    wrap_main(lambda : run_subcmd(cmd_module, subcmd))
