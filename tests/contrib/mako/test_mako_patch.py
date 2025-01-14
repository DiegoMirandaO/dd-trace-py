# This test script was automatically generated by the contrib-patch-tests.py
# script. If you want to make changes to it, you should make sure that you have
# removed the ``_generated`` suffix from the file name, to prevent the content
# from being overwritten by future re-generations.

from ddtrace.contrib.internal.mako.patch import get_version
from ddtrace.contrib.internal.mako.patch import patch


try:
    from ddtrace.contrib.internal.mako.patch import unpatch
except ImportError:
    unpatch = None
from tests.contrib.patch import PatchTestCase


class TestMakoPatch(PatchTestCase.Base):
    __integration_name__ = "mako"
    __module_name__ = "mako"
    __patch_func__ = patch
    __unpatch_func__ = unpatch
    __get_version__ = get_version

    def assert_module_patched(self, mako):
        pass

    def assert_not_module_patched(self, mako):
        pass

    def assert_not_module_double_patched(self, mako):
        pass
