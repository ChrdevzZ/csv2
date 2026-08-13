# Verification dependencies

This directory contains source snapshots used only by CSV2's tests and
benchmarks. Normal CSV2 configuration does not parse or build them, and none of
their targets or files are installed or exported.

| Dependency | Version | Exact source | License | Local patches |
| --- | --- | --- | --- | --- |
| Catch2 | 3.15.3 | signed tag `95d8a61b089317bec800c7cc4c64064cbcb3802d`, commit `8b08d4d79514f45f7e4ce2a607ac9c94e920d1bb` | BSL-1.0 | none |
| Google Benchmark | 1.9.5 | tag/commit `192ef10025eb2c4cdd392bc502f0c852196baa48` | Apache-2.0 | none |

The committed snapshots are intentionally smaller than the upstream archives.
Catch2 retains the split library sources and required CMake modules. Google
Benchmark retains its library sources, public headers, build modules and
license. Upstream tests, examples, documentation, CI configuration and
development tools are excluded from both snapshots.

`manifest.json` records upstream provenance, the release archive SHA-256, the
canonical snapshot SHA-256, the license, and the exact file-list path. Run the
offline integrity check from the repository root:

```bash
python3 tools/vendor/update_verification_dependencies.py check
```

Normal CMake configuration and CI never access the network. A maintainer may
explicitly download and stage a new archive with the same tool; the command
requires `--allow-network`, verifies the manifest hash, and writes only to an
explicit empty staging directory. Review the staged tree and update the
manifest and whitelist before replacing a committed snapshot.

Patches, if ever required, belong in `patches/` as separate files and must be
listed in the manifest with an upstream issue and rationale. Direct,
unrecorded edits to a vendored snapshot are not permitted.
