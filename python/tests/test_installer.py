"""Unit tests for the zero-config memory-rule installer."""

import tempfile
import unittest
from pathlib import Path

from vecmindb.installer import (
    END_MARKER,
    START_MARKER,
    apply_file,
    detect_targets,
    main,
    merge_section,
)


class TestMergeSection(unittest.TestCase):
    def test_insert_into_empty(self) -> None:
        merged = merge_section("", "body")
        self.assertIn(START_MARKER, merged)
        self.assertIn("body", merged)

    def test_insert_appends_to_existing_content(self) -> None:
        merged = merge_section("# 我的项目说明\n", "body")
        self.assertTrue(merged.startswith("# 我的项目说明\n"))
        self.assertIn("body", merged)

    def test_rerun_replaces_not_duplicates(self) -> None:
        once = merge_section("", "v1")
        twice = merge_section(once, "v2")
        self.assertEqual(twice.count(START_MARKER), 1)
        self.assertEqual(twice.count(END_MARKER), 1)
        self.assertIn("v2", twice)
        self.assertNotIn("v1", twice)

    def test_surrounding_content_never_touched(self) -> None:
        original = "# 标题\n\n自定义内容\n\n尾部\n"
        merged = merge_section(original, "body")
        self.assertIn("# 标题", merged)
        self.assertIn("自定义内容", merged)
        self.assertIn("尾部", merged)  # the section appends after existing content


class TestApplyAndDetect(unittest.TestCase):
    def test_apply_file_dry_run_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "AGENTS.md"
            apply_file(path, "body", dry_run=True)
            self.assertFalse(path.exists())

    def test_apply_file_creates_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "AGENTS.md"
            self.assertTrue(apply_file(path, "body", dry_run=False))
            self.assertFalse(apply_file(path, "body", dry_run=False))  # unchanged -> no-op

    def test_detect_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            (home / ".claude").mkdir(parents=True)
            targets = detect_targets(root, home, all_tools=False)
            names = [t for t, _ in targets]
            self.assertIn("claude-code", names)
            self.assertNotIn("cursor", names)
            self.assertNotIn("workbuddy", names)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            home.mkdir()
            (root / ".workbuddy").mkdir()
            targets = detect_targets(root, home, all_tools=False)
            names = [t for t, _ in targets]
            self.assertIn("workbuddy", names)
            self.assertNotIn("claude-code", names)

    def test_detect_all_tools(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            home.mkdir()
            targets = detect_targets(root, home, all_tools=True)
            names = {t for t, _ in targets}
            self.assertEqual(names, {"claude-code", "cursor", "workbuddy"})


class TestMainCli(unittest.TestCase):
    def test_main_all_creates_rules(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            code = main(["--dir", str(root), "--all"])
            self.assertEqual(code, 0)
            self.assertTrue((root / "CLAUDE.md").exists())
            self.assertTrue((root / ".cursor" / "rules" / "vecmindb-memory.mdc").exists())
            self.assertTrue((root / ".workbuddy" / "AGENTS.md").exists())
            body = (root / "CLAUDE.md").read_text(encoding="utf-8")
            self.assertIn("search_memory", body)
            self.assertIn("is_factual", body)

    def test_main_dry_run_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            code = main(["--dir", str(root), "--all", "--dry-run"])
            self.assertEqual(code, 0)
            self.assertFalse((root / "CLAUDE.md").exists())


if __name__ == "__main__":
    unittest.main()
