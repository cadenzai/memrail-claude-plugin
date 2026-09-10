"""Exercise published examples against a local Memrail API + SDK checkout.

MEMRAIL_API_ROOT=/path/to/memrail_api /path/to/api/.venv/bin/python -m unittest discover -s tests -v
No server credentials or network operations are used.
"""
import ast
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "memrail"
API = Path(os.environ["MEMRAIL_API_ROOT"]).resolve()
sys.path[:0] = [str(API / "soma-ami-python-sdk"), str(API)]

from memrail import AsyncAMIClient
from memrail.serializers import deserialize_selected_item
from src.core.dsl import Context, evaluate_trigger_dsl, parse_trigger_dsl
from src.core.models import EmuRegistration


def blocks(path, language):
    return re.findall(r"^```" + language + r"\n(.*?)^```", path.read_text(), re.M | re.S)


class SkillExamples(unittest.TestCase):
    def test_local_reference_links(self):
        for path in SKILL.rglob("*.md"):
            for link in re.findall(r"\]\(([^)]+)\)", path.read_text()):
                if "://" in link or link.startswith("#"):
                    continue
                with self.subTest(path=path.name, link=link):
                    self.assertTrue((path.parent / link.split("#")[0]).is_file())

    def test_quick_dsl(self):
        for block in blocks(SKILL / "SKILL.md", "javascript"):
            for line in block.splitlines():
                expression = line.split("//")[0].strip()
                if expression:
                    with self.subTest(expression=expression):
                        parse_trigger_dsl(expression)

    def test_jsonl_definitions(self):
        count = 0
        for block in blocks(SKILL / "references/12-emu-jsonl-workflow.md", "jsonl"):
            for line in block.splitlines():
                data = json.loads(line)
                if "trigger" not in data:  # illustrative sync-lock records
                    continue
                with self.subTest(emu=data["emu_key"]):
                    EmuRegistration.model_validate(data)
                    parse_trigger_dsl(data["trigger"])
                    count += 1
        self.assertGreaterEqual(count, 4)

    def test_dsl_worked_examples(self):
        content = (SKILL / "references/02-dsl-reference.md").read_text()
        sections = [content.split("## Complete Examples\n", 1)[1],
                    content.split("## Quick Start\n", 1)[1].split("## Core Syntax\n", 1)[0]]
        for section in sections:
            for block in re.findall(r"^```javascript\n(.*?)^```", section, re.M | re.S):
                for group in re.split(r"\n\s*\n", block.strip()):
                    expression = " ".join(line.split("//")[0].strip() for line in group.splitlines()).strip()
                    if expression:
                        with self.subTest(expression=expression):
                            parse_trigger_dsl(expression)

    def test_complete_cookbook_definitions(self):
        count = 0
        for block in blocks(SKILL / "references/04-emu-cookbook.md", "json"):
            try:
                data = json.loads(block)
            except json.JSONDecodeError:
                continue  # explicitly labelled multi-object design fragments
            if isinstance(data, dict) and "expected_utility" in data:
                with self.subTest(emu=data["emu_key"]):
                    EmuRegistration.model_validate(data)
                    parse_trigger_dsl(data["trigger"])
                    count += 1
        self.assertGreaterEqual(count, 15)

    def test_python_reference_examples_compile(self):
        for filename in ("05-sdk-integration-python.md", "09-tool-registry-executors.md"):
            for index, block in enumerate(blocks(SKILL / "references" / filename, "python")):
                with self.subTest(file=filename, block=index):
                    compile(block, filename, "exec", flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)

    def test_python_builder_examples_run(self):
        namespace = {}
        for block in blocks(SKILL / "references/05-sdk-integration-python.md", "python"):
            exec(compile(block, "python-reference", "exec"), namespace)
        self.assertEqual(namespace["context"][2].source, "ml")
        self.assertEqual(namespace["email_sent"].anchor.object.id, "E-456")

    def test_combined_execution_example(self):
        block = next(b for b in blocks(SKILL / "references/09-tool-registry-executors.md", "python")
                     if "async def process_receipt" in b)
        namespace = {}
        exec(block, namespace)

        async def exercise(dry_run, mode="auto", lifecycle="active"):
            async with AsyncAMIClient(api_key="test", org="test", workspace="test",
                                      project="support", use_env=False) as client:
                client.decide = AsyncMock(return_value=SimpleNamespace(selected=[
                    deserialize_selected_item({
                        "id": "emu-receipt", "emu_key": "support.receipt", "emu_version": 1,
                        "activation_id": "activation-test", "lifecycle_state": lifecycle,
                        "policy": {"mode": mode},
                        "payload": {"type": "tool_call", "intent": "FORMAT_RECEIPT", "tool": {
                            "tool_id": "format_receipt", "version": "1.0.0",
                            "args": {"receipt_id": "R-123"}, "side_effect": False,
                        }},
                    })]))
                client.ack_decisions = AsyncMock(return_value=[])
                result = await namespace["process_receipt"](client, dry_run=dry_run)
                if dry_run:
                    self.assertEqual(result.execution_results, [])
                    client.ack_decisions.assert_not_called()
                else:
                    execution = result.execution_results[0]
                    expected = mode == "auto" and lifecycle == "active"
                    self.assertEqual(execution.was_executed, expected)
                    if expected:
                        self.assertEqual(execution.output, {"text": "Receipt R-123"})

        for dry_run, mode, lifecycle in [(True, "auto", "active"), (False, "auto", "active"),
                (False, "require_human", "active"), (False, "advisory", "active"),
                (False, "auto", "canary"), (False, "auto", "inactive")]:
            with self.subTest(dry_run=dry_run, mode=mode, lifecycle=lifecycle):
                asyncio.run(exercise(dry_run, mode, lifecycle))

    def test_missing_input_semantics(self):
        context = Context({}, {}, [], current_time=datetime(2026, 9, 10, tzinfo=timezone.utc))
        for expression, expected in [
            ("state.user.verified == true", False),
            ("NOT state.user.verified", True),
            ("state.user.verified EXISTS AND NOT state.user.verified", False),
            ("COUNT event.user.failed.login IN 'PT0.5S' == 0", True),
        ]:
            with self.subTest(expression=expression):
                self.assertEqual(evaluate_trigger_dsl(expression, context), expected)


if __name__ == "__main__":
    unittest.main()
