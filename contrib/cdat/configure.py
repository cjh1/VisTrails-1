import os
import sipconfig
from PyQt4 import pyqtconfig


from distutils import sysconfig

vcs_so = '%s/vcs/_vcs.so' % sysconfig.get_python_lib()
vcs_inc = '%s/vcs/Include' % sysconfig.get_python_lib()

## vcs_so = '/Users/hvo/src/uvcdat/cdatBuild/lib/python2.7/site-packages/vcs/_vcs.so'
## vcs_inc = '/Users/hvo/src/uvcdat/cdat/Packages/vcs/Include'


# The name of the SIP build file generated by SIP and used by the build
# system.
build_file = "pyqtscripting.sbf"

# Get the PyQt configuration information.
config = pyqtconfig.Configuration()

# Get the extra SIP flags needed by the imported qt module.  Note that
# this normally only includes those flags (-x and -t) that relate to SIP's
# versioning system.
qt_sip_flags = config.pyqt_sip_flags

os.system("rm -rf cdatwrap")
os.mkdir("cdatwrap")
os.system("touch cdatwrap/__init__.py")

# Run SIP to generate the code.  Note that we tell SIP where to find the qt
# module's specification files using the -I flag.
os.system(" ".join([ \
    config.sip_bin, \
    "-c", "cdatwrap", \
    "-b", build_file, \
    "-I", config.pyqt_sip_dir, \
    qt_sip_flags, \
    "cdat.sip" \
]))

# Create the Makefile.  The QtModuleMakefile class provided by the
# pyqtconfig module takes care of all the extra preprocessor, compiler and
# linker flags needed by the Qt library.
makefile = pyqtconfig.QtGuiModuleMakefile(
    dir="cdatwrap",
    configuration=config,
    build_file='../' + build_file
)

# Add the library we are wrapping.  The name doesn't include any platform
# specific prefixes or extensions (e.g. the "lib" prefix on UNIX, or the
# ".dll" extension on Windows).
#makefile.extra_libs = ["vcs"]
import cdat_info
makefile.CFLAGS.append("-I%s/include" % cdat_info.externals)
makefile.CFLAGS.append("-I%s" % vcs_inc)
makefile.CFLAGS.append("-I%s/.." % sysconfig.get_python_inc())

makefile.CXXFLAGS.append("-I%s/include" % cdat_info.externals)
makefile.CXXFLAGS.append("-I%s" % vcs_inc)
makefile.CXXFLAGS.append("-I%s/.." % sysconfig.get_python_inc())

cwd = os.getcwd()
makefile.LFLAGS.append("-Wl,-rpath,%s/cdatwrap" % cwd)

# Generate the Makefile itself.
makefile.generate()
os.chdir("cdatwrap")
os.system("make clean")
os.system("MACOSX_DEPLOYMENT_TARGET=10.6 make -j")
os.system("make install")
