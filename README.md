# GitLicenses 📜
![CI](https://github.com/realMNohgee/gitlicenses/actions/workflows/ci.yml/badge.svg) ![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg) ![License](https://img.shields.io/badge/license-MIT-blue.svg)

**Scan dependency files and extract license info.** Zero dependencies, pure Python stdlib.

Parse package.json, requirements.txt, pyproject.toml, go.mod, Cargo.toml, Gemfile, and pom.xml to build a complete license picture. Flags copyleft/permissive conflicts before they become legal problems.

> Part of the **Trust & Reliability Layer for Agentic AI**

## Why it exists

Understanding your dependency licenses is critical for compliance, but manual audits are tedious and error-prone. GitLicenses automates license discovery across 7+ ecosystems, detects LICENSE files, and warns about GPL/AGPL mixing with permissive code — all without installing a single npm/pip package.

## One tool, many domains

| Domain | What GitLicenses does |
|---|---|
| 📜 **Compliance** | Audit open-source license obligations before shipping |
| ⚖️ **Legal Review** | Flag copyleft conflicts (GPL + MIT in same project) |
| 🧪 **CI/CD** | Gate builds on license policy with `--check` mode |
| 📊 **Supply Chain** | Build a dependency license inventory in 2 seconds |

## Install
```bash
git clone git@github.com:realMNohgee/gitlicenses.git
cd gitlicenses
python3 gitlicenses.py --help
```

## Quick start
```bash
# Scan a project
python3 gitlicenses.py scan ./my-project

# View license breakdown
python3 gitlicenses.py licenses ./my-project

# Check for conflicts
python3 gitlicenses.py check ./my-project

# CI mode (exit 1 on conflicts)
python3 gitlicenses.py check ./my-project --check

# JSON output for dashboards
python3 gitlicenses.py licenses ./my-project --format json
```

## Supported Ecosystems
- **npm** — package.json (dependencies, devDependencies, peerDependencies)
- **Python** — requirements.txt, pyproject.toml (PEP 621 + Poetry)
- **Go** — go.mod
- **Rust** — Cargo.toml
- **Ruby** — Gemfile
- **Java** — pom.xml (Maven)

## License
MIT — see [LICENSE](LICENSE).

---
🧰 **[Tool on Hermtica Marketplace](https://hermtica.com/marketplace)**
