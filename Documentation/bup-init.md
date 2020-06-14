% bup-init(1) Bup %BUP_VERSION%
% Avery Pennarun <apenwarr@gmail.com>
% %BUP_DATE%

# NAME

bup-init - initialize a bup repository

# SYNOPSIS

[BUP_DIR=*localpath*] bup init [-r *host*:*path*] [*path*]

# DESCRIPTION

`bup init` initializes your local bup repository.  If neither a remote
or local *path* is specified, initializes the BUP_DIR which defaults
to `~/.bup`.

# OPTIONS

-r, \--remote=*host*:*path*
:   Initialize the remote repository given by the *host* and *path*.
    This is not necessary if you intend to back up to the default
    location on the server (ie. a blank *path*).  The connection to
    the remote server is made with SSH.  If you'd like to specify
    which port, user or private key to use for the SSH connection, we
    recommend you use the `~/.ssh/config` file.

# EXAMPLES
    bup init
    
# SEE ALSO

`bup-fsck`(1), `ssh_config`(5)

# BUP

Part of the `bup`(1) suite.
