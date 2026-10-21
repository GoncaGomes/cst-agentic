"""THROWAWAY: read-only exact-process observations for the native-free round."""

from __future__ import annotations

import ctypes
from ctypes import wintypes

import win32api
import win32event
import win32process

KERNEL = ctypes.WinDLL("kernel32", use_last_error=True)


class Entry(ctypes.Structure):
    _fields_ = [
        ("size", wintypes.DWORD),
        ("usage", wintypes.DWORD),
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


def snapshot() -> dict[int, dict]:
    handle = KERNEL.CreateToolhelp32Snapshot(2, 0)
    if handle == ctypes.c_void_p(-1).value:
        raise RuntimeError("process_snapshot_failed")
    entries = {}
    try:
        entry = Entry()
        entry.size = ctypes.sizeof(entry)
        if not KERNEL.Process32FirstW(handle, ctypes.byref(entry)):
            raise RuntimeError("process_first_failed")
        while True:
            entries[entry.pid] = {
                "pid": entry.pid,
                "parent_pid": entry.parent_pid,
                "executable_basename": entry.exe,
            }
            if not KERNEL.Process32NextW(handle, ctypes.byref(entry)):
                if ctypes.get_last_error() != 18:
                    raise RuntimeError("process_next_failed")
                break
    finally:
        if not KERNEL.CloseHandle(handle):
            raise RuntimeError("snapshot_close_failed")
    return entries


class ExactProcess:
    def __init__(self, pid: int) -> None:
        self.handle = win32api.OpenProcess(0x1000 | 0x100000, False, pid)
        times = win32process.GetProcessTimes(self.handle)
        self.creation_time = times["CreationTime"].isoformat()

    def alive(self) -> bool:
        result = win32event.WaitForSingleObject(self.handle, 0)
        if result not in (0, 258):
            raise RuntimeError("exact_handle_wait_failed")
        return result == 258

    def close(self) -> None:
        self.handle.Close()


def discover(launcher: int, handles: dict[int, ExactProcess], facts: list[dict]) -> None:
    """Select only descendants of held, still-live handles; never command lines."""
    entries = snapshot()
    if launcher not in handles:
        handles[launcher] = ExactProcess(launcher)
        facts.append({**entries[launcher], "creation_time": handles[launcher].creation_time})
    for _ in range(12):
        added = False
        parents = {pid for pid, handle in handles.items() if handle.alive()}
        for pid, entry in entries.items():
            if pid in handles or entry["parent_pid"] not in parents:
                continue
            try:
                handle = ExactProcess(pid)
            except Exception as error:
                # A process may exit between snapshot and opening its handle.
                # Keep that coverage gap explicit, never claim it was observed dead.
                facts.append({**entry, "handle_open_error_type": type(error).__name__})
                continue
            handles[pid] = handle
            facts.append({**entry, "creation_time": handle.creation_time})
            added = True
        if not added:
            return
    raise RuntimeError("unexpected_process_chain_depth")
