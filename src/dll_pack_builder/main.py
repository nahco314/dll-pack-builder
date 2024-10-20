import json
import os
import sys
from collections import defaultdict
from typing import Any
import lddwrap
import typer
from pathlib import Path
import shutil
import re


app = typer.Typer()


@app.command()
def find(path: Path) -> None:
    for p in path.iterdir():
        if p.is_file() and (p.suffix == ".so" or p.suffix == ".dll" or p.suffix == ".dylib"):
            print(p)
            break


@app.command()
def local(dll: Path, output: Path, target_triple: str, gh_repo: str, gh_tag: str) -> None:
    dll_infos = {}
    st = [dll]

    # collect all dependencies by DFS
    while st:
        p = st.pop()

        if p in dll_infos:
            continue

        deps = lddwrap.list_dependencies(p)
        use_deps = []

        for d in deps:
            if not d.found:
                print(f"not found: {d.soname}", file=sys.stderr)
                print(
                    "try specifying the library path in an environment variable such as LD_LIBRARY_PATH",
                    file=sys.stderr,
                )
                exit(1)

            # if it is virtual so, we don't care
            if d.path is None:
                continue

            st.append(d.path)
            use_deps.append(d)

        dll_infos[p] = use_deps

    for p, deps in dll_infos.items():
        shutil.copy(p, output / f"{target_triple}.{p.name}")

        json_content = {
            "spec-version": "1.0.0",
            "manifest": {
                "platforms": {
                    target_triple: {
                        "name": p.name,
                        "url": f"https://github.com/{gh_repo}/releases/download/{gh_tag}/{target_triple}.{p.name}",
                        "dependencies": [],
                    }
                }
            },
        }

        for dep in deps:
            json_content["manifest"]["platforms"][target_triple]["dependencies"].append(
                {
                    "type": "dllpack",
                    "url": f"https://github.com/{gh_repo}/releases/download/{gh_tag}/{dep.path.name}.dllpack",
                }
            )

        with open(output / f"{p.name}.{target_triple}.dllpack-local", "w") as f:
            json.dump(json_content, f, indent=4)


def object_merge(base: Any, other: Any) -> Any:
    if isinstance(base, dict) and isinstance(other, dict):
        for k, v in other.items():
            if k in base:
                object_merge(base[k], v)
            else:
                base[k] = v
    elif isinstance(base, list) and isinstance(other, list):
        base.extend(other)
    else:
        assert base == other


@app.command()
def merge(output: Path) -> None:
    dllpack_locals = defaultdict(dict)
    rm_list = []

    for p in output.iterdir():
        m = re.fullmatch(r"(.*)\.(.*?)\.dllpack-local", p.name)
        if m:
            object_merge(dllpack_locals[m.group(1)], json.load(p.open()))
            rm_list.append(p)

    for p in rm_list:
        os.remove(p)

    for name, content in dllpack_locals.items():
        with open(output / f"{name}.dllpack", "w") as f:
            json.dump(content, f, indent=4)


def main():
    app()


if __name__ == "__main__":
    main()
