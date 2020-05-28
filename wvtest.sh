
if [ -z "$BASH_VERSION" ]; then
    echo "Depends on bash" 1>&2
    exit 2
fi

_wvtop="$(pwd)"

wvmktempdir ()
{
    local script_name="$(basename $0)"
    mkdir -p "$_wvtop/t/tmp" || exit $?
    mktemp -d "$_wvtop/t/tmp/$script_name-XXXXXXX" || exit $?
}

wvmkmountpt ()
{
    local script_name="$(basename $0)"
    mkdir -p "$_wvtop/t/mnt" || exit $?
    mktemp -d "$_wvtop/t/mnt/$script_name-XXXXXXX" || exit $?
}

_wvtest_count=0

_wvtapmsg ()
{
    echo "$@" 1>&2
}

_wvinfo ()
{
    echo "$@" 1>&2
}

_wvdiag ()
{
    echo "# $@" | tr '\n' ' '
    echo
}

# we don't quote $text in case it contains newlines; newlines
# aren't allowed in test output.  However, we set -f so that
# at least shell glob characters aren't processed.
_wvtextclean()
{
    ( set -f; echo $* )
}

declare -a _wvbtstack

_wvpushcall()
{
    _wvbtstack[${#_wvbtstack[@]}]="$*"
}

_wvpopcall()
{
    unset _wvbtstack[$((${#_wvbtstack[@]} - 1))]
}

_wvbacktrace()
{
    local i loc
    local call=$((${#_wvbtstack[@]} - 1))
    for ((i=0; i <= ${#FUNCNAME[@]}; i++)); do
	local name="${FUNCNAME[$i]}"
	if test "${name:0:2}" == WV; then
            loc="${BASH_SOURCE[$i+1]}:${BASH_LINENO[$i]}"
	    echo "called from $loc ${FUNCNAME[$i]} ${_wvbtstack[$call]}" 1>&2
	    ((call--))
	fi
    done
}

_wvfind_caller()
{
    wvcaller_file=${BASH_SOURCE[2]}
    wvcaller_line=${BASH_LINENO[1]}
}

_wvreport()
{
    local rc="$1"
    local text=$(_wvtextclean "$2")
    ((_wvtest_count++)) || true
    if test "$rc" -eq 0; then
        _wvtapmsg "ok $_wvtest_count $wvcaller_file:$wvcaller_line($rc) $text"
    else
        _wvtapmsg "not ok $_wvtest_count $wvcaller_file:$wvcaller_line($rc) $text"
	_wvbacktrace
    fi
}


WVSTART()
{
    _wvfind_caller
    _wvdiag "$wvcaller_file: $*"
}

# FIXME: maybe factor out common code, via some more stack elision

WVPASS()
{
    local test_txt="$*"
    _wvpushcall "$@"
    _wvfind_caller
    if "$@"; then
	_wvpopcall
        _wvreport 0 "$test_txt"
    else
        local rc="$?"
        _wvreport "$rc" "$test_txt"
        exit "$rc"
    fi
}

# FIXME: share with WVPASS?

WVFAIL()
{
    local test_txt="$*"
    _wvpushcall "$@"
    _wvfind_caller
    if ! "$@"; then
	_wvpopcall
        _wvreport 0 "$test_txt"
    else
        local rc="$?"
        _wvreport "$rc"
        exit "$rc"
    fi
}

WVPASSEQ()
{
    _wvpushcall "$@"
    _wvfind_caller
    if test "$#" -ne 2; then
        _wvreport 2 "exactly 2 arguments"
        exit 2
    fi
    _wvinfo "Comparing:"
    _wvinfo "$1"
    _wvinfo "--"
    _wvinfo "$2"
    if test "$1" = "$2"; then
        _wvreport 0 "$(printf "%q = %q" "$1" "$2")"
    else
        _wvreport 1 "$(printf "%q = %q" "$1" "$2")"
    fi
    _wvpopcall
}

WVPASSNE()
{
    _wvpushcall "$@"
    _wvfind_caller
    if test "$#" -ne 2; then
        _wvreport 2 "exactly 2 arguments"
        exit 2
    fi
    _wvinfo "Comparing:"
    _wvinfo "$1"
    _wvinfo "--"
    _wvinfo "$2"
    if test ! "$1" = "$2"; then
        _wvreport 0 "$(printf "%q = %q" "$1" "$2")"
    else
        _wvreport 1 "$(printf "%q = %q" "$1" "$2")"
    fi
    _wvpopcall
}

WVDIE()
{
    local text=$(_wvtextclean "$@")
    _wvpushcall "$@"
    _wvfind_caller
    _wvdiag "$wvcaller_file:$wvcaller_line $text"
    exit 2
}

WVFINISH ()
{
    _wvtapmsg "1..$_wvtest_count"
}
