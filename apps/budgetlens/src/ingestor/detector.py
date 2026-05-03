from __future__ import annotations
from typing import Literal


def detect_format(file_bytes: bytes) -> Literal["chase", "boa"]:
    first_line = file_bytes.decode("utf-8", errors="replace").split("\n")[0]
    if "Transaction Date" in first_line and "Post Date" in first_line:
        return "chase"
    if first_line.strip().startswith("Description,,"):
        return "boa"
    raise ValueError(
        "Unrecognized CSV format. Expected a Chase or Bank of America export.\n\n"
        "Chase exports start with: Transaction Date,Post Date,Description,...\n"
        "BOA exports start with: Description,,Summary Amt."
    )
