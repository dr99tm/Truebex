"""The Truebex API package."""

import sys

# The API version, shown in /docs and recorded with server crashes.
__version__ = "2.0.0"


def _platform_without_wmi() -> None:
    """Keep `platform` off WMI on Windows.

    SQLAlchemy calls platform.machine() at import. Python 3.12 answers it with
    a WMI query that gives up after a short timeout on a busy machine and
    leaves its query thread running; the `cmd /c ver` fallback that follows
    can then kill the process with 0xC000070A
    (STATUS_THREADPOOL_HANDLE_EXCEPTION). Without WMI, platform reads `ver`
    and PROCESSOR_ARCHITECTURE, as Python 3.11 did. Production runs on Linux.
    """
    if sys.platform != "win32":
        return
    import platform

    if getattr(platform, "_uname_cache", None) is None and hasattr(platform, "_wmi_query"):

        def _no_wmi(*_keys):
            raise OSError("WMI is not used by the Truebex server")

        platform._wmi_query = _no_wmi


_platform_without_wmi()
