"""Stable ZIP entries for byte-reproducible Office packages."""

from __future__ import annotations

import zipfile


def write_stable(zf: zipfile.ZipFile, name: str, data: str | bytes) -> None:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.create_system = 3  # Keep archives byte-identical on Windows and Unix.
    info.compress_type = zipfile.ZIP_DEFLATED
    zf.writestr(info, data)
