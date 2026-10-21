"""THROWAWAY read-only Windows exact-handle observation. No kills or UI reads."""

from __future__ import annotations

import ctypes
from ctypes import wintypes

KERNEL = ctypes.WinDLL("kernel32", use_last_error=True)


class Entry(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("pid", wintypes.DWORD),
        ("heap", ctypes.c_size_t),
        ("module", wintypes.DWORD),
        ("threads", wintypes.DWORD),
        ("parent_pid", wintypes.DWORD),
        ("priority", wintypes.LONG),
        ("flags", wintypes.DWORD),
        ("exe", wintypes.WCHAR * 260),
    ]


KERNEL.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
KERNEL.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
KERNEL.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(Entry)]
KERNEL.Process32NextW.argtypes = KERNEL.Process32FirstW.argtypes
KERNEL.CloseHandle.argtypes = [wintypes.HANDLE]
KERNEL.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
KERNEL.OpenProcess.restype = wintypes.HANDLE
KERNEL.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
KERNEL.WaitForSingleObject.restype = wintypes.DWORD
KERNEL.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
KERNEL.IsProcessInJob.argtypes = [wintypes.HANDLE, wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL)]


def checked(value, category: str):
    if not value:
        raise RuntimeError(category + "_winerror_" + str(ctypes.get_last_error()))
    return value


def snapshot() -> dict[int, dict]:
    handle = KERNEL.CreateToolhelp32Snapshot(2, 0)
    if handle == ctypes.c_void_p(-1).value:
        checked(False, "snapshot")
    result = {}
    try:
        entry = Entry()
        entry.dwSize = ctypes.sizeof(entry)
        checked(KERNEL.Process32FirstW(handle, ctypes.byref(entry)), "process_first")
        while True:
            result[entry.pid] = {
                "pid": entry.pid,
                "parent_pid": entry.parent_pid,
                "executable_basename": entry.exe,
            }
            if not KERNEL.Process32NextW(handle, ctypes.byref(entry)):
                if ctypes.get_last_error() != 18:
                    checked(False, "process_next")
                break
    finally:
        checked(KERNEL.CloseHandle(handle), "snapshot_close")
    return result


class Handle:
    def __init__(self, pid: int) -> None:
        self.value = checked(KERNEL.OpenProcess(0x1000 | 0x100000, False, pid), "open_process")

    def alive(self) -> bool:
        value = KERNEL.WaitForSingleObject(self.value, 0)
        if value not in (0, 258):
            raise RuntimeError("process_wait_failed")
        return value == 258

    def facts(self) -> dict:
        times = [wintypes.FILETIME() for _ in range(4)]
        checked(
            KERNEL.GetProcessTimes(self.value, *(ctypes.byref(t) for t in times)), "process_times"
        )
        inside = wintypes.BOOL()
        checked(KERNEL.IsProcessInJob(self.value, None, ctypes.byref(inside)), "any_job")
        return {
            "creation_filetime": times[0].dwLowDateTime | times[0].dwHighDateTime << 32,
            "in_any_job": bool(inside.value),
        }

    def close(self) -> None:
        checked(KERNEL.CloseHandle(self.value), "process_handle_close")
