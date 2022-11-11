
import sys

from bup import check_refs, git
from bup.io import byte_stream

def main(argv):
    git.check_repo_or_die()
    sys.stdout.flush()
    out = byte_stream(sys.stdout)
    rc = check_refs.via_cmdline(argv[1:], out=out)
    sys.exit(rc)
