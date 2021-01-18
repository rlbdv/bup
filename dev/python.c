#define _LARGEFILE64_SOURCE 1
#define PY_SSIZE_T_CLEAN 1
#undef NDEBUG
#include "../config/config.h"

// According to Python, its header has to go first:
//   http://docs.python.org/2/c-api/intro.html#include-files
#include <Python.h>

#if PY_MAJOR_VERSION > 2
#define bup_py_main Py_BytesMain
# else
#define bup_py_main Py_Main
#endif

int main(int argc, char **argv)
{
    return bup_py_main (argc, argv);
}
