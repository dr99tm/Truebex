"""Crash symbolication against the private Breakpad symbols (PF14).

Two sources of frames, best first:
1. the minidump, through rust-minidump's `minidump-stackwalk --json`
   (MIT / Apache-2.0; installed in the API image) with the .sym files of the
   report's app version laid out as a Breakpad symbol store;
2. the callstack the app sent: raw `Module+0xOFFSET` frames are looked up in
   the FUNC / PUBLIC records of the module's .sym file.

Frames read `Module!Function+0xOFFSET` once named, `Module+0xOFFSET` otherwise.
"""

import bisect
import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

RAW_FRAME_RE = re.compile(r"^(?P<module>[^!+\s]+)\+(?P<offset>0x[0-9A-Fa-f]+)$")


@dataclass
class SymbolTable:
    module: str  # the debug file (PDB) name, e.g. Truebex-CadCore.pdb
    debug_id: str
    code_file: str | None  # the DLL / EXE the frames name
    funcs: list[tuple[int, int, str]] = field(default_factory=list)  # (address, size, name)
    publics: list[tuple[int, str]] = field(default_factory=list)

    def lookup(self, address: int) -> tuple[str, int] | None:
        """(function name, offset into it) for a module-relative address."""
        starts = [f[0] for f in self.funcs]
        i = bisect.bisect_right(starts, address) - 1
        if i >= 0:
            start, size, name = self.funcs[i]
            if start <= address < start + max(size, 1):
                return name, address - start
        starts = [p[0] for p in self.publics]
        j = bisect.bisect_right(starts, address) - 1
        if j >= 0:
            return self.publics[j][1], address - self.publics[j][0]
        return None


def parse_sym(text: str) -> SymbolTable:
    """Parse a Breakpad .sym file (MODULE, INFO CODE_ID, FUNC, PUBLIC records)."""
    table: SymbolTable | None = None
    for line in text.splitlines():
        if line.startswith("MODULE "):
            parts = line.split(" ", 4)
            if len(parts) != 5:
                break
            table = SymbolTable(module=parts[4].strip(), debug_id=parts[3].strip(), code_file=None)
        elif table is None:
            break
        elif line.startswith("INFO CODE_ID "):
            parts = line.split(" ")
            if len(parts) >= 4:
                table.code_file = parts[3].strip()
        elif line.startswith("FUNC "):
            parts = line.split(" ", 4)
            if parts[1] == "m":  # "FUNC m <addr> …" marks a multiple-symbol function
                parts = line.split(" ", 5)[1:]
            try:
                table.funcs.append((int(parts[1], 16), int(parts[2], 16), parts[4].strip()))
            except (IndexError, ValueError):
                continue
        elif line.startswith("PUBLIC "):
            parts = line.split(" ", 3)
            if parts[1] == "m":
                parts = line.split(" ", 4)[1:]
            try:
                table.publics.append((int(parts[1], 16), parts[3].strip()))
            except (IndexError, ValueError):
                continue
    if table is None or not re.fullmatch(r"[0-9A-Fa-f]{33,40}", table.debug_id):
        raise ValueError("Not a Breakpad symbol file (no MODULE line).")
    if table.code_file is None and table.module.lower().endswith(".pdb"):
        table.code_file = table.module[:-4] + ".dll"
    table.funcs.sort()
    table.publics.sort()
    return table


def symbolicate_frames(frames: list[str], tables: dict[str, SymbolTable]) -> tuple[list[str], bool]:
    """Name the raw frames whose module has a table (keyed by code file,
    lower case). Returns the frames and whether any changed."""
    out, changed = [], False
    for frame in frames:
        m = RAW_FRAME_RE.match(frame)
        table = tables.get(m.group("module").lower()) if m else None
        hit = table.lookup(int(m.group("offset"), 16)) if table else None
        if hit:
            name, offset = hit
            out.append(f"{m.group('module')}!{name}+{hex(offset)}")
            changed = True
        else:
            out.append(frame)
    return out, changed


def parse_stackwalk_json(data: dict) -> list[str]:
    """The crashing thread's frames from `minidump-stackwalk --json`."""
    frames = []
    for f in (data.get("crashing_thread") or {}).get("frames", []):
        module = f.get("module") or "unknown"
        if f.get("function"):
            frames.append(f"{module}!{f['function']}+{f.get('function_offset') or '0x0'}")
        else:
            frames.append(f"{module}+{f.get('module_offset') or f.get('offset') or '0x0'}")
    return frames


def stackwalk_available(binary: str) -> str | None:
    return shutil.which(binary)


def run_stackwalk(binary: str, minidump: bytes, symbols: dict[str, bytes]) -> list[str] | None:
    """Run the stackwalker over `minidump` with `symbols` ({store path: .sym
    bytes}, Breakpad layout). None when it is missing or fails."""
    exe = stackwalk_available(binary)
    if not exe:
        return None
    with tempfile.TemporaryDirectory(prefix="truebex-sym-") as tmp:
        root = Path(tmp)
        dump = root / "crash.dmp"
        dump.write_bytes(minidump)
        for rel, data in symbols.items():
            path = root / "symbols" / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        try:
            proc = subprocess.run(
                [exe, "--json", "--symbols-path", str(root / "symbols"), str(dump)],
                capture_output=True,
                timeout=120,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        if proc.returncode != 0:
            return None
        try:
            frames = parse_stackwalk_json(json.loads(proc.stdout))
        except ValueError:
            return None
        return frames or None
