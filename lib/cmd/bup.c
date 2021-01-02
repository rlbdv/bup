
#define PY_SSIZE_T_CLEAN
#define _GNU_SOURCE  // asprintf
#undef NDEBUG

#include <libgen.h>
#include <limits.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

#include <Python.h>

static void
msg(FILE* f, const char * const msg, ...)
{
    if (fputs("bup: ", f) == EOF)
        exit(3);
    va_list ap;
    va_start(ap, msg);;
    if (vfprintf(f, msg, ap) < 0)
        exit(3);
    va_end(ap);
}

static int prog_argc = 0;
static char **prog_argv = NULL;

static PyObject*
get_argv(PyObject *self, PyObject *args)
{
    if (!PyArg_ParseTuple(args, ""))
	return NULL;

    PyObject *result = PyList_New(prog_argc);
    for (int i = 0; i < prog_argc; i++)
        PyList_SET_ITEM(result, i, PyBytes_FromString(prog_argv[i]));
    return result;
}

static PyMethodDef bup_main_methods[] = {
    {"argv", get_argv, METH_VARARGS,
     "Return the program's current argv array as a list of byte strings." },
    {NULL, NULL, 0, NULL}
};

#if PY_MAJOR_VERSION >= 3

static struct PyModuleDef bup_main_module_def = {
    .m_base = PyModuleDef_HEAD_INIT,
    .m_name = "bup_main",
    .m_doc = "Built-in bup module providing direct access to argv.",
    .m_size = -1,
    .m_methods = bup_main_methods
};

PyMODINIT_FUNC
PyInit_bup_main(void) {
    return PyModule_Create(&bup_main_module_def);
}

static void
setup_bup_main_module(void) {
    if (PyImport_AppendInittab("bup_main", PyInit_bup_main) == -1) {
        msg(stderr, "unable to register bup_main module\n");
        exit(2);
    }
}

#endif // PY_MAJOR_VERSION >= 3

static char *find_in_path(const char * const name, const char * const path)
{
    char *result = NULL;
    char *tmp_path = strdup(path);
    assert(tmp_path);
    const char *elt;
    while ((elt = strtok(tmp_path, ":")) != NULL) {
        char *candidate;
        int rc = asprintf(&candidate, "%s/%s", elt, name);
        assert(rc >= 0);
        struct stat st;
        rc = stat(candidate, &st);
        if (rc != 0) {
            switch (errno) {
                case EACCES: case ELOOP: case ENOENT: case ENAMETOOLONG:
                case ENOTDIR:
                    break;
                default:
                    msg(stderr, "cannot stat %s: %s\n",
                        candidate, strerror(errno));
                    free(tmp_path);
                    free(candidate);
                    exit(2);
                    break;
            }
        } else if (S_ISREG(st.st_mode)) {
            if (access(candidate, X_OK) == 0) {
                result = candidate;
                break;
            }
            switch (errno) {
                case EACCES: case ELOOP: case ENOENT: case ENAMETOOLONG:
                case ENOTDIR:
                    break;
                default:
                    msg(stderr, "cannot determine executability of %s: %s\n",
                        candidate, strerror(errno));
                    free(tmp_path);
                    free(candidate);
                    exit(2);
                    break;
            }
        }
        free(candidate);
    }
    free(tmp_path);
    return result;
}

static char *find_exe_parent(const char * const argv_0)
{
    char *candidate = NULL;
    const char * const slash = index(argv_0, '/');
    if (slash) {
        candidate = strdup(argv_0);
        assert(candidate);
    } else {
        const char * const env_path = getenv("PATH");
        if (!env_path) {
            msg(stderr,
                "no PATH and executable isn't relative or absolute: %s\n",
                argv_0);
            exit(2);
        }
        char *path_exe = find_in_path(argv_0, env_path);
        if (path_exe) {
            char * abs_exe = realpath(path_exe, NULL);
            if (!abs_exe) {
                msg(stderr, "cannot resolve path (%s): %s\n",
                    strerror(errno), path_exe);
                free(path_exe);
                exit(2);
            }
            free(path_exe);
            candidate = abs_exe;
        }
    }
    if (!candidate)
        return NULL;

    char * const abs_exe = realpath(candidate, NULL);
    if (!abs_exe) {
        msg(stderr, "cannot resolve path (%s): %s\n",
            strerror(errno), candidate);
        free(candidate);
        exit(2);
    }
    free(candidate);
    char * const abs_parent = strdup(dirname(abs_exe));
    assert(abs_parent);
    free(abs_exe);
    return abs_parent;
}

#if defined(__APPLE__) && defined(__MACH__)

static char *exe_parent_dir(const char * const argv_0) {
    char path[4096];  // FIXME
    uint32_t size = sizeof(path);
    if(_NSGetExecutablePath(path, &size) !=0) {
        msg(stderr, "unable to find executable path\n");
        exit(2);
    }
    char * abs_exe = realpath(path, NULL);
    if (!abs_exe) {
        msg(stderr, "cannot resolve path (%s): %s\n", strerror(errno), path);
        exit(2);
    }
    char * const abs_parent = strdup(dirname(abs_exe));
    assert(abs_parent);
    free(abs_exe);
    return abs_parent;
}

#else // not macos

#ifdef __FreeBSD__
const char proc_self[] = "/proc/curproc/file";
#elif defined(__NetBSD__)
const char proc_self[] = "/proc/curproc/exe";
#elif defined(__linux__)
const char proc_self[] = "/proc/self/exe";
#elif defined(__sun) || defined (sun)
const char proc_self[] = "/proc/self/path/a.out";
#else
const char * const proc_self = NULL;
#endif

static char *exe_parent_dir(const char * const argv_0)
{
    if (proc_self != NULL) {
        char path[4096];  // FIXME
        int len = readlink(proc_self, path, sizeof(path));
        if (len == sizeof(path)) {
            msg(stderr, "unable to resolve symlink %s: %s\n", proc_self);
            exit(2);
        }
        if (len != -1) {
            path[len] = '\0';
            return strdup(dirname(path));
        }
        switch (errno) {
            case ENOENT: case EACCES: case EINVAL: case ELOOP: case ENOTDIR:
            case ENAMETOOLONG:
                break;
            default:
                msg(stderr, "cannot resolve %s: %s\n", path, strerror(errno));
                exit(2);
                break;
        }
    }
    return find_exe_parent(argv_0);
}

#endif // not macos

static void
setenv_or_die(const char *name, const char *value)
{
    int rc = setenv(name, value, 1);
    if (rc != 0) {
        msg(stderr, "setenv %s=%s failed (%s)\n", name, value, strerror(errno));
        exit(2);
    }
}

static void
prepend_lib_to_pythonpath(const char * const exec_path,
                          const char * const relative_path)
{
    char *parent = exe_parent_dir(exec_path);
    assert(parent);
    char *bupmodpath;
    int rc = asprintf(&bupmodpath, "%s/%s", parent, relative_path);
    assert(rc >= 0);
    struct stat st;
    rc = stat(bupmodpath, &st);
    if (rc != 0) {
        msg(stderr, "cannot find lib dir (%s): %s\n",
            strerror(errno), bupmodpath);
        exit(2);
    }
    if (!S_ISDIR(st.st_mode))
    {
        msg(stderr, "lib path is not dir: %s\n", bupmodpath);
        exit(2);
    }
    // FIXME: set some other way?
    char *curpypath = getenv("PYTHONPATH");
    if (curpypath) {
        char *path;
        int rc = asprintf(&path, "%s:%s", bupmodpath, curpypath);
        assert(rc >= 0);
        setenv_or_die("PYTHONPATH", path);
        free(path);
    } else {
        setenv_or_die("PYTHONPATH", bupmodpath);
    }

    free(bupmodpath);
    free(parent);
}

#if PY_MAJOR_VERSION > 2
#define bup_py_main Py_BytesMain
# else
#define bup_py_main Py_Main
#endif

#if defined(BUP_DEV_BUP_PYTHON) && defined(BUP_DEV_BUP_EXEC)
# error "Both BUP_DEV_BUP_PYTHON and BUP_DEV_BUP_EXEC are defined"
#endif

#ifdef BUP_DEV_BUP_PYTHON

int main(int argc, char **argv)
{
    fprintf(stderr, "py: %s\n", argv[0]);
    prepend_lib_to_pythonpath(argv[0], "../lib");
    prog_argc = argc;
    prog_argv = argv;
    setup_bup_main_module();
    return bup_py_main (argc, argv);
}

#elif defined(BUP_DEV_BUP_EXEC)

int main(int argc, char **argv)
{
    fprintf(stderr, "exec: %s\n", argv[0]);
    prepend_lib_to_pythonpath(argv[0], "../lib");
    prog_argc = argc - 1;
    prog_argv = argv + 1;
    setup_bup_main_module();
    if (argc == 1)
        return bup_py_main (1, argv);
    // This can't handle a script with a name like "-c", but that's
    // python's problem, not ours.
    return bup_py_main (2, argv);
}

#else // normal bup command

int main(int argc, char **argv)
{
    int i;
    for (i = 0; i < argc; i++)
        fprintf(stderr, "bup[%d]: %s\n", i, argv[i]);
    prepend_lib_to_pythonpath(argv[0], "..");
    prog_argc = argc;
    prog_argv = argv;
    setup_bup_main_module();
    Py_Initialize();
    int status = 0;
    if (PyRun_SimpleString("import bup.main; bup.main.main()") != 0) {
        // Only reached if SystemExit  didn't readh the top level.
        msg(stderr, "execution of bup.main.main() failed\n");
        status = 2;
    }
#if PY_MAJOR_VERSION < 3
    Py_Finalize();
#else
    if (Py_FinalizeEx() != 0) {
        msg(stderr, "python shutdown failed\n");
        status = 2;
    }
#endif
    return status;
}

#endif // normal bup command
