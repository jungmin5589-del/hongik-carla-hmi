"""Resolve local crash RVAs using the bundled PDB; no symbol-server connection."""
import ctypes as c
from ctypes import wintypes as w
from pathlib import Path

dll = c.WinDLL("dbghelp")
k = c.WinDLL("kernel32", use_last_error=True)
process = k.GetCurrentProcess()
dll.SymInitializeW.argtypes = [w.HANDLE, w.LPCWSTR, w.BOOL]
dll.SymInitializeW.restype = w.BOOL
dll.SymLoadModuleExW.argtypes = [w.HANDLE, w.HANDLE, w.LPCWSTR, w.LPCWSTR, c.c_uint64, w.DWORD, c.c_void_p, w.DWORD]
dll.SymLoadModuleExW.restype = c.c_uint64
dll.SymSetOptions(0x10 | 0x4 | 0x80000)  # LOAD_LINES, DEFERRED_LOADS, NO_PROMPTS
folder = Path(r"C:\CARLA_0.9.16\CarlaUE4\Binaries\Win64")
if not dll.SymInitializeW(process, str(folder), False):
    raise c.WinError()
base = dll.SymLoadModuleExW(process, None, str(folder / "CarlaUE4-Win64-Shipping.exe"), None, 0x10000000, 0, None, 0)
print("module", hex(base), flush=True)
class Symbol(c.Structure):
    _fields_ = [("SizeOfStruct", w.ULONG), ("TypeIndex", w.ULONG), ("Reserved", c.c_uint64 * 2),
        ("Index", w.ULONG), ("Size", w.ULONG), ("ModBase", c.c_uint64), ("Flags", w.ULONG),
        ("Value", c.c_uint64), ("Address", c.c_uint64), ("Register", w.ULONG), ("Scope", w.ULONG),
        ("Tag", w.ULONG), ("NameLen", w.ULONG), ("MaxNameLen", w.ULONG), ("Name", c.c_char * 2048)]
dll.SymFromAddr.argtypes = [w.HANDLE, c.c_uint64, c.POINTER(c.c_uint64), c.POINTER(Symbol)]
for offset in [0x3430b4b, 0x86e757, 0x85f8ce, 0x27f8a52, 0x3021dfe, 0x2ae1af1]:
    sym = Symbol()
    sym.SizeOfStruct = Symbol.Name.offset + 1
    # SYMBOL_INFO size includes alignment padding, regardless of variable name storage.
    sym.SizeOfStruct = 88
    sym.MaxNameLen = 2048
    displacement = c.c_uint64()
    ok = dll.SymFromAddr(process, base + offset, c.byref(displacement), c.byref(sym))
    print(hex(offset), sym.Name.decode(errors="replace") if ok else "unresolved", flush=True)
