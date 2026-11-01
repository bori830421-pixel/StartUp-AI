"""规则锁正反回归，只操作独立临时目录，不修改真实规则或重封指纹。"""
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from skill_check import REPO, check_rule_lock


def main() -> int:
    source = json.loads((REPO / "docs/rule-lock.json").read_text(encoding="utf-8"))
    passed = 0
    with tempfile.TemporaryDirectory(prefix="startup-rule-lock-") as folder:
        root = Path(folder)
        for rel in source["files"]:
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(REPO / rel, target)
        manifest = root / "docs/rule-lock.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)

        def write(data):
            manifest.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

        def expect(label, should_fail):
            nonlocal passed
            errors = check_rule_lock(root)
            assert bool(errors) == should_fail, (label, errors)
            passed += 1
            print(f"PASS {label}")

        write(source)
        expect("approved baseline", False)
        protected = root / "references/operating-model.md"
        original = protected.read_text(encoding="utf-8")
        protected.write_bytes(original.replace("\n", "\r\n").encode("utf-8"))
        expect("CRLF checkout preserves text fingerprint", False)
        protected.write_text(original + "\nchanged\n", encoding="utf-8")
        expect("changed protected rule", True)
        protected.unlink()
        expect("missing protected file", True)
        protected.write_text(original, encoding="utf-8")
        reduced = dict(source, files=dict(source["files"]))
        del reduced["files"]["references/checkup-scorecard.md"]
        write(reduced)
        expect("removed required protection", True)
        escaped = dict(source, files=dict(source["files"], **{"../escape.md": "0" * 64}))
        write(escaped)
        expect("path traversal", True)
        for label, invalid in [("empty entries", {"files": {}}),
                               ("invalid root type", []),
                               ("invalid fingerprint type", {"files": {"x": 1}})]:
            write(invalid)
            expect(label, True)
        manifest.write_text("{broken", encoding="utf-8")
        expect("malformed manifest", True)
        manifest.unlink()
        expect("missing manifest", True)
    print(f"{passed} rule lock checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
