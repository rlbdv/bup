
from __future__ import absolute_import
import os.path, sys

from bup import git, options
from bup.gc import bup_gc
from bup.helpers import die_if_errors, handle_ctrl_c, log


optspec = """
bup gc [options...]
--
v,verbose   increase log output (can be used more than once)
threshold=  only rewrite a packfile if it's over this percent garbage [10]
#,compress= set compression level to # (0-9, 9 is highest) [1]
unsafe      use the command even though it may be DANGEROUS
"""

# FIXME: server mode?
# FIXME: make sure client handles server-side changes reasonably

def main(argv):
    o = options.Options(optspec)
    opt, flags, extra = o.parse_bytes(argv[1:])

    if not opt.unsafe:
        o.fatal('refusing to run dangerous, experimental command without --unsafe')

    if extra:
        o.fatal('no positional parameters expected')

    if opt.threshold:
        try:
            opt.threshold = int(opt.threshold)
        except ValueError:
            o.fatal('threshold must be an integer percentage value')
        if opt.threshold < 0 or opt.threshold > 100:
            o.fatal('threshold must be an integer percentage value')

    git.check_repo_or_die()

    bup_gc(threshold=opt.threshold,
           compression=opt.compress,
           verbosity=opt.verbose)

    die_if_errors()
