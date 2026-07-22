from __future__ import annotations

import runpy
from pathlib import Path

root = Path(__file__).resolve().parents[1]
v4 = root / "scripts/apply_sz_cninfo_parser_fix_v4.py"
v3 = root / "scripts/apply_sz_cninfo_parser_fix_v3.py"
runpy.run_path(str(v4), run_name="__main__")
v4.unlink(missing_ok=True)
v3.write_text("from __future__ import annotations\n", encoding="utf-8")
