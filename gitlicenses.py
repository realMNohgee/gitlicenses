#!/usr/bin/env python3
"""gitlicenses — Scan dependency files and extract license info. Zero dependencies, pure Python stdlib."""

import argparse
import json
import os
import re
import sys
from pathlib import Path


# Built-in license database: identifier -> {name, category}
# Categories: permissive, copyleft, proprietary, other
LICENSE_DB = {
    "MIT": {"name": "MIT License", "category": "permissive"},
    "Apache-2.0": {"name": "Apache License 2.0", "category": "permissive"},
    "Apache-2.0 OR MIT": {"name": "Apache 2.0 / MIT", "category": "permissive"},
    "BSD-2-Clause": {"name": "BSD 2-Clause License", "category": "permissive"},
    "BSD-3-Clause": {"name": "BSD 3-Clause License", "category": "permissive"},
    "ISC": {"name": "ISC License", "category": "permissive"},
    "Unlicense": {"name": "The Unlicense", "category": "permissive"},
    "CC0-1.0": {"name": "Creative Commons Zero v1.0", "category": "permissive"},
    "MPL-2.0": {"name": "Mozilla Public License 2.0", "category": "copyleft"},
    "LGPL-2.1": {"name": "GNU Lesser General Public License v2.1", "category": "copyleft"},
    "LGPL-3.0": {"name": "GNU Lesser General Public License v3.0", "category": "copyleft"},
    "GPL-2.0": {"name": "GNU General Public License v2.0", "category": "copyleft"},
    "GPL-3.0": {"name": "GNU General Public License v3.0", "category": "copyleft"},
    "AGPL-3.0": {"name": "GNU Affero General Public License v3.0", "category": "copyleft"},
    "EUPL-1.2": {"name": "European Union Public License 1.2", "category": "copyleft"},
    "BSL-1.0": {"name": "Boost Software License 1.0", "category": "permissive"},
    "CC-BY-4.0": {"name": "Creative Commons Attribution 4.0", "category": "permissive"},
    "Python-2.0": {"name": "Python License 2.0", "category": "permissive"},
    "Zlib": {"name": "zlib License", "category": "permissive"},
    "WTFPL": {"name": "Do What The F*ck You Want To Public License", "category": "permissive"},
    "0BSD": {"name": "BSD Zero Clause License", "category": "permissive"},
    "BlueOak-1.0.0": {"name": "Blue Oak Model License 1.0.0", "category": "permissive"},
}

# Known license text patterns for detection
LICENSE_PATTERNS = [
    (re.compile(r'\bMIT\b', re.IGNORECASE), "MIT"),
    (re.compile(r'Apache\s*(?:License)?\s*(?:Version)?\s*2\.?0', re.IGNORECASE), "Apache-2.0"),
    (re.compile(r'BSD\s*(?:2|3)[- ]Clause', re.IGNORECASE), "BSD-3-Clause"),
    (re.compile(r'GNU\s+(?:AFFERO\s+)?GENERAL\s+PUBLIC\s+LICEN[CS]E.*Version\s*3', re.IGNORECASE), "GPL-3.0"),
    (re.compile(r'GNU\s+GENERAL\s+PUBLIC\s+LICEN[CS]E.*Version\s*2', re.IGNORECASE), "GPL-2.0"),
    (re.compile(r'GNU\s+AFFERO\s+GENERAL\s+PUBLIC\s+LICEN[CS]E', re.IGNORECASE), "AGPL-3.0"),
    (re.compile(r'GNU\s+LESSER\s+GENERAL\s+PUBLIC\s+LICEN[CS]E.*Version\s*3', re.IGNORECASE), "LGPL-3.0"),
    (re.compile(r'GNU\s+LESSER\s+GENERAL\s+PUBLIC\s+LICEN[CS]E.*Version\s*2', re.IGNORECASE), "LGPL-2.1"),
    (re.compile(r'Mozilla\s+Public\s+License.*2\.?0', re.IGNORECASE), "MPL-2.0"),
    (re.compile(r'ISC\s+License', re.IGNORECASE), "ISC"),
    (re.compile(r'Unlicense', re.IGNORECASE), "Unlicense"),
    (re.compile(r'CC[0O]\s+1\.?0\s+Universal', re.IGNORECASE), "CC0-1.0"),
    (re.compile(r'Boost\s+Software\s+License', re.IGNORECASE), "BSL-1.0"),
]


def detect_license_from_text(text: str) -> "str | None":
    """Detect license identifier from license file text."""
    for pattern, identifier in LICENSE_PATTERNS:
        if pattern.search(text):
            return identifier
    return None


def parse_package_json(filepath: Path) -> list[dict]:
    """Parse package.json for dependencies and their licenses."""
    deps = []
    try:
        data = json.loads(filepath.read_text())
    except (json.JSONDecodeError, OSError):
        return deps

    # Check top-level license field
    top_license = data.get("license") or (data.get("licenses", [{}])[0].get("type") if isinstance(data.get("licenses"), list) else None)

    all_deps = {}
    all_deps.update(data.get("dependencies", {}))
    all_deps.update(data.get("devDependencies", {}))
    all_deps.update(data.get("peerDependencies", {}))

    for name, version in all_deps.items():
        deps.append({
            "name": name,
            "version": version,
            "ecosystem": "npm",
            "license": top_license if top_license else "unknown",
            "license_category": LICENSE_DB.get(top_license, {}).get("category", "unknown") if top_license else "unknown",
            "file": str(filepath),
        })

    return deps


def parse_requirements_txt(filepath: Path) -> list[dict]:
    """Parse requirements.txt for dependencies."""
    deps = []
    try:
        text = filepath.read_text()
    except OSError:
        return deps

    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        # Handle: package==version, package>=version, etc.
        match = re.match(r'^([a-zA-Z0-9_\-\.]+)\s*([><=!~].*)?$', line)
        if match:
            deps.append({
                "name": match.group(1),
                "version": (match.group(2) or "").strip(),
                "ecosystem": "pypi",
                "license": "unknown",
                "license_category": "unknown",
                "file": str(filepath),
            })
    return deps


def parse_pyproject_toml(filepath: Path) -> list[dict]:
    """Parse pyproject.toml for dependencies (basic TOML parsing without tomllib for older Python)."""
    deps = []
    try:
        text = filepath.read_text()
    except OSError:
        return deps

    # Simple regex-based parsing for project.dependencies
    in_deps = False
    for line in text.splitlines():
        line = line.strip()
        if re.match(r'^dependencies\s*=\s*\[', line):
            in_deps = True
            # Check for inline list
            inner = re.search(r'\[(.+)\]', line)
            if inner:
                for dep in re.findall(r'"([^"]+)"', inner.group(1)):
                    deps.append({
                        "name": dep.split()[0] if dep.split() else dep,
                        "version": "",
                        "ecosystem": "pypi",
                        "license": "unknown",
                        "license_category": "unknown",
                        "file": str(filepath),
                    })
                in_deps = False
            continue

        if in_deps:
            if line == "]":
                in_deps = False
                continue
            dep_match = re.match(r'"([^"]+)"', line)
            if dep_match:
                dep_str = dep_match.group(1)
                deps.append({
                    "name": dep_str.split()[0] if dep_str.split() else dep_str,
                    "version": "",
                    "ecosystem": "pypi",
                    "license": "unknown",
                    "license_category": "unknown",
                    "file": str(filepath),
                })

    # Also check poetry-style [tool.poetry.dependencies]
    in_poetry = False
    for line in text.splitlines():
        if re.match(r'\[tool\.poetry\.dependencies\]', line):
            in_poetry = True
            continue
        if in_poetry:
            if line.startswith("["):
                in_poetry = False
                continue
            m = re.match(r'^([a-zA-Z0-9_\-\.]+)\s*=', line)
            if m:
                deps.append({
                    "name": m.group(1),
                    "version": "",
                    "ecosystem": "pypi",
                    "license": "unknown",
                    "license_category": "unknown",
                    "file": str(filepath),
                })

    return deps


def parse_go_mod(filepath: Path) -> list[dict]:
    """Parse go.mod for dependencies."""
    deps = []
    try:
        text = filepath.read_text()
    except OSError:
        return deps

    in_require = False
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("require ("):
            in_require = True
            continue
        if in_require:
            if line == ")":
                in_require = False
                continue
            parts = line.split()
            if len(parts) >= 2:
                deps.append({
                    "name": parts[0],
                    "version": parts[1],
                    "ecosystem": "go",
                    "license": "unknown",
                    "license_category": "unknown",
                    "file": str(filepath),
                })

    return deps


def parse_cargo_toml(filepath: Path) -> list[dict]:
    """Parse Cargo.toml for dependencies."""
    deps = []
    try:
        text = filepath.read_text()
    except OSError:
        return deps

    in_deps = False
    section = None
    for line in text.splitlines():
        line = line.strip()
        if re.match(r'\[dependencies\]', line):
            in_deps = True
            section = "dependencies"
            continue
        if re.match(r'\[dev-dependencies\]', line):
            in_deps = True
            section = "dev-dependencies"
            continue
        if re.match(r'\[build-dependencies\]', line):
            in_deps = True
            section = "build-dependencies"
            continue
        if in_deps and line.startswith("[") and line != "[dependencies]" and line != "[dev-dependencies]" and line != "[build-dependencies]":
            in_deps = False
            continue
        if in_deps and line:
            m = re.match(r'^([a-zA-Z0-9_\-]+)\s*=', line)
            if m:
                deps.append({
                    "name": m.group(1),
                    "version": "",
                    "ecosystem": "cargo",
                    "license": "unknown",
                    "license_category": "unknown",
                    "file": str(filepath),
                })

    return deps


def parse_gemfile(filepath: Path) -> list[dict]:
    """Parse Gemfile for dependencies."""
    deps = []
    try:
        text = filepath.read_text()
    except OSError:
        return deps

    gem_pattern = re.compile(r'^\s*gem\s+["\']([^"\']+)["\']')
    for line in text.splitlines():
        m = gem_pattern.match(line)
        if m:
            deps.append({
                "name": m.group(1),
                "version": "",
                "ecosystem": "rubygems",
                "license": "unknown",
                "license_category": "unknown",
                "file": str(filepath),
            })
    return deps


def parse_pom_xml(filepath: Path) -> list[dict]:
    """Parse pom.xml for dependencies (simple XML regex parsing)."""
    deps = []
    try:
        text = filepath.read_text()
    except OSError:
        return deps

    # Simple dependency extraction from XML
    dep_blocks = re.findall(r'<dependency>(.*?)</dependency>', text, re.DOTALL)
    for block in dep_blocks:
        gid = re.search(r'<groupId>(.*?)</groupId>', block)
        aid = re.search(r'<artifactId>(.*?)</artifactId>', block)
        ver = re.search(r'<version>(.*?)</version>', block)
        name = f"{gid.group(1)}:{aid.group(1)}" if gid and aid else "unknown"
        version = ver.group(1) if ver else ""
        deps.append({
            "name": name,
            "version": version,
            "ecosystem": "maven",
            "license": "unknown",
            "license_category": "unknown",
            "file": str(filepath),
        })
    return deps


# Map of known manifest files to parsers
MANIFEST_FILES = {
    "package.json": parse_package_json,
    "requirements.txt": parse_requirements_txt,
    "pyproject.toml": parse_pyproject_toml,
    "go.mod": parse_go_mod,
    "Cargo.toml": parse_cargo_toml,
    "Gemfile": parse_gemfile,
    "pom.xml": parse_pom_xml,
}


def scan_directory(directory: Path) -> list[dict]:
    """Recursively scan a directory for dependency manifest files."""
    all_deps = []

    for root, dirs, files in os.walk(directory):
        # Skip hidden directories and common non-project dirs
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("node_modules", "__pycache__", "vendor", "target", ".git")]

        for fname in files:
            if fname in MANIFEST_FILES:
                filepath = Path(root) / fname
                parser = MANIFEST_FILES[fname]
                try:
                    deps = parser(filepath)
                    all_deps.extend(deps)
                except Exception:
                    pass

    # Also look for LICENSE files
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("node_modules", "__pycache__", "vendor", "target", ".git")]
        for fname in files:
            if fname.upper().startswith("LICENSE") or fname.upper() == "COPYING":
                filepath = Path(root) / fname
                try:
                    text = filepath.read_text()
                    detected = detect_license_from_text(text)
                    if detected:
                        # Apply detected license to deps in same directory
                        parent = str(filepath.parent)
                        for dep in all_deps:
                            dep_parent = str(Path(dep["file"]).parent)
                            if dep_parent == parent or dep_parent.startswith(parent + os.sep):
                                dep["license"] = detected
                                dep["license_category"] = LICENSE_DB.get(detected, {}).get("category", "unknown")
                except Exception:
                    pass

    return all_deps


def cmd_scan(args):
    """Handle the 'scan' subcommand."""
    directory = Path(args.directory)
    if not directory.is_dir():
        print(f"Error: '{args.directory}' is not a directory", file=sys.stderr)
        return 1

    deps = scan_directory(directory)

    if args.format == "json":
        output = {
            "directory": str(directory),
            "total_dependencies": len(deps),
            "dependencies": deps,
            "manifest_files_found": list(set(d["file"] for d in deps))
        }
        print(json.dumps(output, indent=2))
    else:
        manifests = set(d["file"] for d in deps)
        print(f"Scanning: {directory}")
        print(f"Manifest files found: {len(manifests)}")
        for mf in sorted(manifests):
            count = sum(1 for d in deps if d["file"] == mf)
            print(f"  {mf} → {count} dependencies")
        print(f"\nTotal dependencies: {len(deps)}")
        if deps:
            print()
            for d in deps[:50]:
                lic = d.get("license", "unknown")
                print(f"  {d['name']:40s} {d['version']:15s} [{d['ecosystem']:10s}] {lic}")
            if len(deps) > 50:
                print(f"  ... and {len(deps) - 50} more")

    return 0


def cmd_licenses(args):
    """Handle the 'licenses' subcommand."""
    directory = Path(args.directory)
    deps = scan_directory(directory)

    # Group by license
    by_license = {}
    for d in deps:
        lic = d.get("license", "unknown")
        if lic not in by_license:
            by_license[lic] = {"count": 0, "category": d.get("license_category", "unknown"), "deps": []}
        by_license[lic]["count"] += 1
        by_license[lic]["deps"].append(d["name"])

    if args.format == "json":
        print(json.dumps(by_license, indent=2))
    else:
        print(f"License summary for: {directory}\n")
        total = len(deps)
        for lic in sorted(by_license.keys()):
            info = by_license[lic]
            pct = (info["count"] / total * 100) if total else 0
            cat = info["category"]
            print(f"  {lic:25s} {info['count']:4d} ({pct:5.1f}%)  [{cat}]")
        print(f"\n  {'─' * 50}")
        print(f"  {'Total':25s} {total:4d}")

    return 0


def cmd_check(args):
    """Handle the 'check' subcommand — check for license conflicts."""
    directory = Path(args.directory)
    deps = scan_directory(directory)

    # Identify potential conflicts: copyleft (GPL/AGPL) + permissive
    copyleft_deps = [d for d in deps if d.get("license_category") == "copyleft"]
    permissive_deps = [d for d in deps if d.get("license_category") == "permissive"]

    conflicts = []
    if copyleft_deps and permissive_deps:
        conflicts.append({
            "type": "copyleft-permissive-mix",
            "severity": "warning",
            "message": "Copyleft and permissive licenses mixed in same project",
            "copyleft": [d["name"] for d in copyleft_deps],
            "permissive": [d["name"] for d in permissive_deps],
        })

    # Check for specific GPL/AGPL conflicts
    strong_copyleft = [d for d in copyleft_deps if d.get("license") in ("GPL-2.0", "GPL-3.0", "AGPL-3.0")]
    if strong_copyleft and permissive_deps:
        conflicts.append({
            "type": "strong-copyleft-conflict",
            "severity": "error",
            "message": "GPL/AGPL licensed code combined with permissive licenses may create obligations",
            "strong_copyleft": [d["name"] for d in strong_copyleft],
            "permissive": [d["name"] for d in permissive_deps],
        })

    # Check for unknown licenses
    unknown_deps = [d for d in deps if d.get("license") == "unknown"]
    if unknown_deps:
        conflicts.append({
            "type": "unknown-licenses",
            "severity": "info",
            "message": f"{len(unknown_deps)} dependencies have unknown licenses",
            "dependencies": [d["name"] for d in unknown_deps[:20]],
        })

    if args.format == "json":
        output = {
            "directory": str(directory),
            "total_dependencies": len(deps),
            "conflicts": conflicts,
            "conflict_count": len(conflicts),
        }
        print(json.dumps(output, indent=2))
    else:
        print(f"License conflict check for: {directory}\n")
        if not conflicts:
            print("✓ No license conflicts detected")
        else:
            has_errors = any(c["severity"] == "error" for c in conflicts)
            for c in conflicts:
                prefix = "✗" if c["severity"] == "error" else "⚠" if c["severity"] == "warning" else "ℹ"
                print(f"{prefix} [{c['severity'].upper()}] {c['message']}")

        if unknown_deps:
            print(f"\n  Unknown license dependencies: {len(unknown_deps)}")

    # Exit 1 if errors found
    has_errors = any(c["severity"] == "error" for c in conflicts)
    if args.check and has_errors:
        return 1
    return 0


def main():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--format", choices=["text", "json"], default="text",
                        help="Output format (default: text)")

    p = argparse.ArgumentParser(
        description="gitlicenses — Scan dependency files and extract license info")

    sub = p.add_subparsers(dest="cmd", required=True)

    # scan
    sp_scan = sub.add_parser("scan", parents=[common],
                             help="Scan a project directory for dependency files")
    sp_scan.add_argument("directory", nargs="?", default=".",
                         help="Directory to scan (default: current directory)")

    # licenses
    sp_licenses = sub.add_parser("licenses", parents=[common],
                                 help="Show license summary")
    sp_licenses.add_argument("directory", nargs="?", default=".",
                             help="Directory to scan (default: current directory)")

    # check
    sp_check = sub.add_parser("check", parents=[common],
                              help="Check for license conflicts")
    sp_check.add_argument("directory", nargs="?", default=".",
                          help="Directory to scan (default: current directory)")
    sp_check.add_argument("--check", action="store_true",
                          help="Exit with code 1 if conflicts found (CI mode)")

    args = p.parse_args()

    if args.cmd == "scan":
        return cmd_scan(args)
    elif args.cmd == "licenses":
        return cmd_licenses(args)
    elif args.cmd == "check":
        return cmd_check(args)

    return 0


if __name__ == "__main__":
    sys.exit(main())
