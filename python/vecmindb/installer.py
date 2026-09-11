"""Zero-config memory wiring for mainstream agent tools (installer, plan ③).

One command generates the corrected, scope-guarded memory rules for every
detected agent tool, so users never hand-write them:

    python -m vecmindb.installer --dir .

The generated rules reference the MCP server by name only — API keys are
never written into rule files; the MCP connection itself stays configured
by each tool's own settings.

Generated rules differ from the hand-written originals in two ways:
- they are scope-guarded (retrieve only for project-related questions,
  never project memory context onto unrelated topics), and
- they are gate-aware (the server-side relevance gate returns "no
  relevant memory" for unrelated queries; no client-side thresholding).

Sections are idempotent: repeated runs replace the marked section only
and never touch surrounding content.
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger("vecmindb.installer")

START_MARKER = "<!-- vecmindb-memory:start -->"
END_MARKER = "<!-- vecmindb-memory:end -->"

RULE_BODY = """## VecminDB 记忆协议（自动生成，勿手改）

- **检索**：回答与项目/工作相关的问题前，先调用 `search_memory`（top_k 3~5）检索相关记忆；命中则在回答中引用并标注来源。服务端有相关性门槛（`memory.search_min_score`）：无关话题会返回"无相关记忆"，此时直接回答，**绝不把已存记忆语境投射到无关问题**。
- **沉淀**：回答结束后，调用 `store_memory` 写入本轮摘要：`text` 为一句话（关键事实/结论/决策）；涉及长期约束、客户要求、架构决策、命名约定时设 `is_factual:true`（强锚定、豁免遗忘）；纯寒暄/简单确认不写。
- **诚实**：写入或检索失败时在回答中如实报告，不假装成功。"""


def merge_section(existing: str, body: str) -> str:
    """Inserts or replaces the marked section; never touches the rest."""
    if START_MARKER in existing and END_MARKER in existing:
        head = existing[: existing.index(START_MARKER)]
        tail = existing[existing.index(END_MARKER) + len(END_MARKER) :]
        return head + START_MARKER + "\n" + body + "\n" + END_MARKER + tail
    base = existing.rstrip()
    joiner = "\n\n" if base else ""
    return base + joiner + START_MARKER + "\n" + body + "\n" + END_MARKER + "\n"


def apply_file(path: Path, body: str, *, dry_run: bool) -> bool:
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    merged = merge_section(existing, body)
    if merged == existing:
        return False
    if dry_run:
        print(f"[dry-run] would update {path}")
        return True
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(merged, encoding="utf-8")
    print(f"[ok] updated {path}")
    return True


def detect_targets(project_dir: Path, home: Path, *, all_tools: bool) -> List[Tuple[str, Path]]:
    """Returns (tool, rule-file) pairs for every detected agent tool."""
    targets: List[Tuple[str, Path]] = []

    # Claude Code: project instructions file.
    if all_tools or (project_dir / "CLAUDE.md").exists() or (home / ".claude").exists():
        targets.append(("claude-code", project_dir / "CLAUDE.md"))

    # Cursor: project rules directory.
    if all_tools or (project_dir / ".cursor").exists():
        targets.append(("cursor", project_dir / ".cursor" / "rules" / "vecmindb-memory.mdc"))

    # WorkBuddy: project-level agent rules.
    if all_tools or (project_dir / ".workbuddy").exists():
        targets.append(("workbuddy", project_dir / ".workbuddy" / "AGENTS.md"))

    return targets


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="vecmindb-memory-init",
        description="Auto-generate scope-guarded VecminDB memory rules for detected agent tools.",
    )
    parser.add_argument("--dir", default=".", help="project directory (default: current)")
    parser.add_argument("--all", action="store_true", help="write rules for all supported tools")
    parser.add_argument(
        "--workbuddy-user",
        action="store_true",
        help="also update the user-level WorkBuddy profile (~/.workbuddy/USER.md) with the "
        "project-conditional rule (fixes the every-conversation projection leak)",
    )
    parser.add_argument("--dry-run", action="store_true", help="print changes without writing")
    args = parser.parse_args(argv)

    project_dir = Path(args.dir).resolve()
    home = Path.home()
    targets = detect_targets(project_dir, home, all_tools=args.all)

    changed = False
    for tool, path in targets:
        try:
            changed |= apply_file(path, RULE_BODY, dry_run=args.dry_run)
        except OSError as exc:
            print(f"[skip] {path}: {exc}", file=sys.stderr)

    if args.workbuddy_user:
        user_file = home / ".workbuddy" / "USER.md"
        try:
            changed |= apply_file(user_file, RULE_BODY, dry_run=args.dry_run)
        except OSError as exc:
            print(f"[skip] {user_file}: {exc}", file=sys.stderr)

    if not targets and not args.workbuddy_user:
        print("[info] no supported agent tool detected; pass --all to force-generate.")

    print(
        "[next] configure the vecmindb MCP server in each tool's own settings "
        "(endpoint + API key live there, never in rule files)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
