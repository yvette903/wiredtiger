import re, subprocess
from wt_platform import *

def compiler_version(cc):
    process = subprocess.Popen([cc, '--version'], stdout=subprocess.PIPE)
    (stdout, _) = process.communicate()
    return (re.search(' [0-9][0-9.]* ', stdout.decode()).group().split('.'))

std_includes = """
#include <sys/types.h>
#ifdef _WIN32
#include <inttypes.h>
#endif
#include <stdarg.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>"
#include <unistd.h>"
"""

def type_check(conf, type, size):
    if not conf.CheckType(type, std_includes):
        print('%s type not found' %(type))
        Exit (1)
    if size != 0 and conf.CheckTypeSize(type) != size:
        print('%s type found, but not %d bytes in size' %(type, size))
        Exit (1)

def wt_compiler(conf):
    env = conf.env

    # Compiler defaults to gcc.
    cc = env['CC']
    cc_gcc = cc.find('clang') == -1
    cc_version = compiler_version(cc)

    # Check for some basic types and sizes.
    # Windows doesn't have off_t, we'll fix that up later.
    # WiredTiger expects off_t and size_t to be the same size.
    # WiredTiger expects a time_t to fit into a uint64_t.
    type_check(conf, 'pid_t', 0)
    if not os_windows:
        type_check(conf, 'off_t', 8)
    type_check(conf, 'size_t', 8)
    type_check(conf, 'ssize_t', 8)
    type_check(conf, 'time_t', 8)
    type_check(conf, 'uintmax_t', 0)
    type_check(conf, 'uintptr_t', 0)

    env.Append(CPPPATH = ['.', '#src/include'])

    if os_linux:
        env.Append(CPPDEFINES = '-D_GNU_SOURCE')
    if GetOption("enable_diagnostic"):
        env.Append(CPPDEFINES = '-DHAVE_DIAGNOSTIC')
    if GetOption("enable_attach"):
        env.Append(CPPDEFINES = '-DHAVE_ATTACH')

    if GetOption("with_spinlock"):
        if GetOption("with_spinlock") == "gcc":
            env.Append(CPPDEFINES = '-DSPINLOCK_TYPE=SPINLOCK_GCC')
        if GetOption("with_spinlock") == "msvc":
            env.Append(CPPDEFINES = '-DSPINLOCK_TYPE=SPINLOCK_MSVC')
        if GetOption("with_spinlock") == "pthread":
            env.Append(CPPDEFINES = '-DSPINLOCK_TYPE=SPINLOCK_PTHREAD_MUTEX')
        if GetOption("with_spinlock") == "pthread_adaptive":
            env.Append(CPPDEFINES = '-DSPINLOCK_TYPE=SPINLOCK_PTHREAD_MUTEX_ADAPTIVE')

    # Linux requires buffers aligned to 4KB boundaries for O_DIRECT to work.
    if os_linux:
        env.Append(CPPDEFINES = '-DWT_BUFFER_ALIGNMENT_DEFAULT=4096')
    else:
        env.Append(CPPDEFINES = '-DWT_BUFFER_ALIGNMENT_DEFAULT=0')

    if conf.CheckCHeader('x86intrin.h'):
        env.Append(CPPDEFINES = '-DHAVE_X86INTRIN_H=1')

    if conf.CheckLib('dl'):
        env.Append(CPPDEFINES = '-DHAVE_LIBDL=1')
        env.Append(ADDITIONAL_LIBS = ['dl'])
    if conf.CheckLib('pthread'):
        env.Append(CPPDEFINES = '-DHAVE_LIBPTHREAD=1')
        env.Append(ADDITIONAL_LIBS = ['pthread'])

    if conf.CheckFunc('clock_gettime'):
        env.Append(CPPDEFINES = '-DHAVE_CLOCK_GETTIME=1')
    if conf.CheckFunc('fallocate'):
        env.Append(CPPDEFINES = '-DHAVE_FALLOCATE=1')
    # OS X wrongly reports that it has fdatasync.
    if not os_darwin and conf.CheckFunc('fdatasync'):
        env.Append(CPPDEFINES = '-DHAVE_FDATASYNC=1')
    if conf.CheckFunc('ftruncate'):
        env.Append(CPPDEFINES = '-DHAVE_FTRUNCATE=1')
    if conf.CheckFunc('gettimeofday'):
        env.Append(CPPDEFINES = '-DHAVE_GETTIMEOFDAY=1')
    if conf.CheckFunc('posix_fadvise'):
        env.Append(CPPDEFINES = '-DHAVE_FADVISE=1')
    if conf.CheckFunc('posix_fallocate'):
        env.Append(CPPDEFINES = '-DHAVE_FALLOCATE=1')
    if conf.CheckFunc('posix_madvise'):
        env.Append(CPPDEFINES = '-DHAVE_MADVISE=1')
    if conf.CheckFunc('posix_memalign'):
        env.Append(CPPDEFINES = '-DHAVE_MEMALIGN=1')
    if conf.CheckFunc('setrlimit'):
        env.Append(CPPDEFINES = '-DHAVE_SETRLIMIT=1')
    if conf.CheckFunc('strtouq'):
        env.Append(CPPDEFINES = '-DHAVE_STRTOUQ=1')
    if conf.CheckFunc('sync_file_range'):
        env.Append(CPPDEFINES = '-DHAVE_SYNC_FILE_RANGE=1')
    if conf.CheckFunc('timer_create'):
        env.Append(CPPDEFINES = '-DHAVE_TIMER_CREATE=1')

    cflags = ""
    if GetOption("enable_diagnostic"):
        cflags += " -g "
    if ARGUMENTS.get('CFLAGS', '').find('-O') == -1:
        cflags += " -O3 "
    if cc_gcc:
        cflags += """
            -Wall
            -Wextra
            -Werror
            -Waggregate-return
            -Wbad-function-cast
            -Wcast-align
            -Wdeclaration-after-statement
            -Wdouble-promotion
            -Wfloat-equal
            -Wformat-nonliteral
            -Wformat-security
            -Wformat=2
            -Winit-self
            -Wjump-misses-init
            -Wmissing-declarations
            -Wmissing-field-initializers
            -Wmissing-prototypes
            -Wnested-externs
            -Wold-style-definition
            -Wpacked
            -Wpointer-arith
            -Wpointer-sign
            -Wredundant-decls
            -Wshadow
            -Wsign-conversion
            -Wstrict-prototypes
            -Wswitch-enum
            -Wundef
            -Wuninitialized
            -Wunreachable-code
            -Wunused
            -Wwrite-strings
        """
        if cc_version[0] == '4':
            cflags += """
                -Wno-c11-extensions
                -Wunsafe-loop-optimizations
            """
        if cc_version[0] == '5':
            cflags += """
                -Wunsafe-loop-optimizations
            """
        if cc_version[0] == '6':
            cflags += """
                -Wunsafe-loop-optimizations
            """
        if cc_version[0] >= '5':
            cflags += """
                -Wformat-signedness
                -Wjump-misses-init
                -Wredundant-decls
                -Wunused-macros
                -Wvariadic-macros
            """
        if cc_version[0] >= '6':
            cflags += """
                -Wduplicated-cond
                -Wlogical-op
                -Wunused-const-variable=2
            """
        if cc_version[0] >= '7':
            cflags += """
                -Walloca
                -Walloc-zero
                -Wduplicated-branches
                -Wformat-overflow=2
                -Wformat-truncation=2
                -Wrestrict
            """
        if cc_version[0] >= '8':
            cflags += """
                -Wmultistatement-macros
            """
    else:
        cflags += """
            -Weverything
            -Werror
            -Wno-cast-align
            -Wno-documentation-unknown-command
            -Wno-format-nonliteral
            -Wno-packed
            -Wno-padded
            -Wno-reserved-id-macro
            -Wno-zero-length-array
        """

        # We should turn on cast-qual, but not as a fatal error: see WT-2690. For now, leave it off.
        cflags = """
            -Wno-cast-qual
        """

        # Turn off clang thread-safety-analysis, it doesn't like some of WiredTiger's code patterns.
        cflags = """
            -Wno-thread-safety-analysis
        """

        # On Centos 7.3.1611, system header files aren't compatible with -Wdisabled-macro-expansion.
        cflags = """
            -Wno-disabled-macro-expansion
        """

        # We occasionally use an extra semicolon to indicate an empty loop or conditional body.
        cflags = """
            -Wno-extra-semi-stmt
        """

        # Ignore unrecognized options.
        cflags = """
            -Wno-unknown-warning-option
        """
    env.Append(CFLAGS = cflags.split())
