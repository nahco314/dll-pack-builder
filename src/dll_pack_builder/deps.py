import sys
from dataclasses import dataclass
from typing import Optional, List
from pathlib import Path
import lddwrap
import globre
import lief


@dataclass
class Dependency:
    path: Optional[Path]
    name: str
    found: bool


def resolve_deps_linux(path: Path) -> List[Dependency]:
    raw_deps = lddwrap.list_dependencies(path)
    res = []
    for dep in raw_deps:
        res.append(Dependency(dep.path, dep.soname, dep.found))

    return res


def macho_resolve_placeholder(
    p_s: str,
    rpath: Optional[Path],
    loader_path: Optional[Path],
    executable_path: Optional[Path],
) -> Path:
    if "@rpath" in p_s:
        if rpath is None:
            print("cannot resolve @rpath placeholder", file=sys.stderr)
            sys.exit(1)

        p_s = p_s.replace("@rpath", str(rpath))

    if "@loader_path" in p_s:
        if loader_path is None:
            print("cannot resolve @loader_path placeholder", file=sys.stderr)
            sys.exit(1)

        p_s = p_s.replace("@loader_path", str(loader_path))

    if "@executable_path" in p_s:
        if executable_path is None:
            print("cannot resolve @executable_path placeholder", file=sys.stderr)
            sys.exit(1)

        p_s = p_s.replace("@executable_path", str(executable_path))

    return Path(p_s)


def resolve_deps_macos(
    path: Path,
    rpath: Optional[Path],
    loader_path: Optional[Path],
    executable_path: Optional[Path],
) -> List[Dependency]:
    res = []
    f_bin: lief.MachO.FatBinary = lief.MachO.parse(str(path.absolute()))

    for binary in f_bin:
        binary: lief.MachO.Binary

        rpath_cmd: Optional[lief.MachO.RPathCommand] = binary.rpath
        if rpath_cmd is not None and rpath is None:
            rpath = macho_resolve_placeholder(
                rpath_cmd.path, rpath, loader_path, executable_path
            )

        for dep in binary.libraries:
            dep: lief.MachO.DylibCommand
            dep_path = macho_resolve_placeholder(
                dep.name, rpath, loader_path, executable_path
            )

            if dep_path.name == path.name:
                continue

            if not dep_path.exists():
                print("warning: not found", dep_path, file=sys.stderr)

                # maybe system library
                # todo: we should use https://github.com/keith/dyld-shared-cache-extractor to check
                r_d = Dependency(None, dep_path.name, True)
            else:
                r_d = Dependency(dep_path, dep_path.name, True)

            res.append(r_d)

    return res


def resolve_deps(
    path: Path,
    rpath: Optional[Path],
    loader_path: Optional[Path],
    executable_path: Optional[Path],
) -> List[Dependency]:
    if sys.platform == "linux":
        return resolve_deps_linux(path)
    elif sys.platform == "darwin":
        return resolve_deps_macos(path, rpath, loader_path, executable_path)
    else:
        print(f"unsupported platform: {sys.platform}", file=sys.stderr)
        sys.exit(1)
