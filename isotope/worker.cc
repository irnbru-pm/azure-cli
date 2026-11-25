#include <Python.h>
#include <mach-o/dyld.h>
#include <filesystem>
#include <limits.h>

static void check(PyStatus status) {
    if (PyStatus_Exception(status)) Py_ExitStatusException(status);
}

int main(int argc, char **argv) {
    char path[PATH_MAX];
    uint32_t size = sizeof(path);
    if (_NSGetExecutablePath(path, &size)) return 1;
    auto resources = std::filesystem::canonical(path).parent_path().parent_path() / "Resources";
    PyConfig config;
    PyConfig_InitIsolatedConfig(&config);
    config.parse_argv = 0;
    config.site_import = 0;
    config.write_bytecode = 0;
    check(PyConfig_SetBytesString(&config, &config.home, (resources / "python").c_str()));
    check(PyConfig_SetBytesString(&config, &config.program_name, path));
    check(PyConfig_SetBytesArgv(&config, argc, argv));
    check(PyConfig_SetBytesString(&config, &config.run_filename, (resources / "bootstrap.py").c_str()));
    check(Py_InitializeFromConfig(&config));
    PyConfig_Clear(&config);
    return Py_RunMain();
}
