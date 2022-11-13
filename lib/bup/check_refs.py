
from binascii import hexlify, unhexlify
from time import localtime, strftime

from bup import options, git
from bup.compat import argv_bytes
from bup.helpers import exo, log, qprogress
from bup.io import path_msg

# Just does what rev-parse does

optspec = """
bup check-refs [OPTION...] [REF_PATTERN...]
--
unrelated  specify when the refs are likely unrelated to save RAM
commit-hash ...
connectivity-only ...
v,verbose   increase verbosity (can be used more than once)
"""

def report_item(commit_prefix, item, verbosity):
    if not item:
        assert commit_prefix
        log(commit_prefix + '\n')
        return

    chunk_path = item.chunk_path
    if chunk_path:
        if verbosity < 4:
            return
        path = []
        if commit_prefix:
            path.append(commit_prefix)
        path.append(path_msg(b''.join(item.path)))
        path.append(path_msg(b''.join(chunk_path)))
        if item.type == b'tree' and item.path:
            path.append('')  # adds trailing slash
        log('/'.join(path) + '\n')
        return

    # Top commit, for example has none.
    demangled = git.demangle_name(item.path[-1], item.mode)[0] if item.path \
                else None

    # Don't print mangled paths unless the verbosity is over 3.
    if demangled:
        ps = b'/'.join(item.path[:-1] + [demangled])
        if verbosity == 1:
            path = []
            if commit_prefix:
                path.append(commit_prefix)
            path.append(path_msg(ps))
            if item.type == b'tree' and item.path:
                path.append('')  # adds trailing slash
            qprogress('/'.join(path) + '\r')
        elif (verbosity > 1 and item.type == b'tree') \
             or (verbosity > 2 and item.type == b'blob'):
            # log(commit_prefix + ('/' if commit_prefix else '')
            #     + path_msg(ps) + ('/' if item.type == b'tree' and item.path else '')
            #     + '\n')
            if commit_prefix:
                path = commit_prefix + path_msg(ps)
            else:
                path = path_msg(ps)
            if item.type == b'tree' and item.path:
                log(path + '/\n')
            else:
                log(path + '\n')
    elif verbosity > 3:
        ps = b'/'.join(item.path)
        path = []
        if commit_prefix:
            path.append(commit_prefix)
        path.append(path_msg(ps))
        if item.type == b'tree' and item.path:
            path.append('')  # adds trailing slash
        log('/'.join(path) + '\n')

def report_missing_oidx(oidx, path, chunk, out):
    # FIXME: encoding for paths (quash newlines, etc.)?
    out.write(b'missing %s %s\n' % (oidx, b'/'.join((*path, *chunk))))

# FIXME: does gc walk all tags?

# For now the output uses spaces to delimit REF, COMMIT_INFO_IF_COMMIT, and PATH

# YYYY-MM-DD/opt-hash/path -- commit
# HASH/path/ -- tree
# HASH/path -- blob

def fsck_ref(ref, oid, visited, *, commit_hash=False, connectivity_only=False,
             verbose=0, out):
    git.check_repo_or_die()
    cat_pipe = git.cp()
    stop_at = lambda x: unhexlify(x) in visited

    ref_prefix = path_msg(ref) + ' '
    commit_prefix = ref_prefix + ' '
    for item in git.walk_object(cat_pipe.get, hexlify(oid), stop_at=stop_at,
                                include_data=(not connectivity_only),
                                for_missing=lambda oidx, path, chunk: report_missing_oidx(oidx, path, chunk, out)):
        if verbose:
            if item.type == b'commit':
                commit = git.parse_commit(item.data)
                commit_utc = commit.author_sec + commit.author_offset
                commit_prefix = ref_prefix + strftime('%Y-%m-%d-%H%M%S', localtime(commit_utc))
                if commit_hash:
                    commit_prefix += commit.tree.decode('ascii')
                commit_prefix += ' '
                report_item(commit_prefix, None, verbose)
            else:
                report_item(commit_prefix, item, verbose)
        if item.type in (b'tree', b'commit'):
            visited.add(item.oid)

def via_cmdline(args, *, out):
    o = options.Options(optspec)
    opt, flags, extra = o.parse_bytes(args)
    opt.verbose = opt.verbose or 0

    refs = [argv_bytes(x) for x in extra]
    if refs:
        # --revs-only ?
        ref_oidxs = exo((b'git', b'rev-parse', b'--revs-only',
                         b'--end-of-options', *refs))[0].splitlines()
        ref_info = list(zip(refs, (unhexlify(x) for x in ref_oidxs)))
    else:
        ref_info = git.list_refs()

    visited = set()
    for ref, oid in ref_info:
        if opt.unrelated:
            visited = set()
        fsck_ref(ref, oid, visited,
                 commit_hash=opt.commit_hash,
                 connectivity_only=opt.connectivity_only,
                 verbose=opt.verbose,
                 out=out)
    return 0
