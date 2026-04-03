#!/usr/bin/env python3
"""Run giskill eval cases through Claude CLI and grade assertions with the same session."""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


def log(msg):
    """Print interactive progress line."""
    print(msg, flush=True)


def parse_args():
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Run skill evals using Claude CLI.")
    parser.add_argument("--evals", default="evals/evals.json", help="Path to evals.json.")
    parser.add_argument("--out-dir", default="evals/results/latest", help="Output directory for run.")
    parser.add_argument("--claude-bin", default="claude", help="Claude CLI binary.")
    parser.add_argument("--model", default="", help="Optional model override.")
    parser.add_argument(
        "--permission-mode",
        default="bypassPermissions",
        choices=["default", "acceptEdits", "auto", "bypassPermissions", "dontAsk", "plan"],
        help="Claude permission mode.",
    )
    parser.add_argument(
        "--allowed-tools",
        default="Bash(bq:*) Bash(gcloud:*)",
        help="Claude allowedTools override.",
    )
    parser.add_argument(
        "--safe-mode",
        action="store_true",
        help="Do not pass --dangerously-skip-permissions.",
    )
    return parser.parse_args()


def load_evals(evals_path):
    """Load eval config."""
    data = json.loads(evals_path.read_text(encoding="utf-8"))
    skill_name = data["skill_name"]
    cases = data["evals"]
    if not skill_name or not cases:
        raise ValueError("evals.json must contain non-empty skill_name and evals.")
    for case in cases:
        assertions = case.get("assertions", [])
        if not isinstance(assertions, list) or not all(isinstance(a, str) for a in assertions):
            raise ValueError(f"Case '{case.get('id')}' assertions must be a list of strings.")
    return skill_name, cases


def build_skill_prompt(skill_name, prompt):
    """Build slash-command prompt for Claude."""
    prompt = prompt.strip()
    if prompt.startswith("/"):
        return prompt
    return f"/{skill_name} {prompt}"


def run_claude_stream(
    claude_bin,
    model,
    prompt,
    permission_mode,
    allowed_tools,
    safe_mode,
    resume_session_id="",
):
    """Run Claude in stream-json mode and return events + final result event."""
    cmd = [claude_bin, "-p", "--verbose", "--output-format", "stream-json", prompt]
    if model:
        cmd[1:1] = ["--model", model]
    if permission_mode:
        cmd[1:1] = ["--permission-mode", permission_mode]
    if allowed_tools:
        cmd[1:1] = ["--allowedTools", allowed_tools]
    if resume_session_id:
        cmd[1:1] = ["--resume", resume_session_id]
    if not safe_mode:
        cmd[1:1] = ["--dangerously-skip-permissions"]

    log(f"  -> Claude command: {' '.join(cmd[:-1])} <prompt>")
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"Claude CLI failed: {proc.stderr.strip() or proc.stdout.strip()}")

    events = []
    result_event = None
    for raw_line in proc.stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        events.append(event)
        if event.get("type") == "result":
            result_event = event

    if result_event is None:
        raise RuntimeError("Claude stream-json output did not include final result event.")

    return events, result_event


def extract_model_messages(events):
    """Extract compact assistant/model messages (skip tool results and user payloads)."""
    messages = []
    for event in events:
        if event.get("type") != "assistant":
            continue
        message = event.get("message", {})
        if not isinstance(message, dict):
            continue
        content = message.get("content", [])
        if not isinstance(content, list):
            continue

        compact_content = []
        for block in content:
            if not isinstance(block, dict):
                continue
            block_type = block.get("type")
            if block_type == "tool_use":
                compact_content.append(
                    {
                        "type": "tool_use",
                        "name": block.get("name"),
                        "input": block.get("input", {}),
                    }
                )
            elif block_type in {"text", "thinking"}:
                compact_content.append(
                    {
                        "type": block_type,
                        "text": block.get("text") or block.get("thinking", ""),
                    }
                )

        messages.append(
            {
                "id": message.get("id"),
                "role": message.get("role"),
                "content": compact_content,
            }
        )
    return messages


def parse_llm_grading(result_text, assertions):
    """Parse assertion grading JSON returned by Claude."""
    text = (result_text or "").strip()
    payload = None

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            payload = json.loads(text[start : end + 1])

    if not isinstance(payload, dict):
        raise ValueError("LLM grading output is not a JSON object.")

    results = payload.get("assertion_results")
    if not isinstance(results, list):
        raise ValueError("LLM grading output missing assertion_results array.")

    normalized = []
    for idx, assertion_text in enumerate(assertions):
        item = results[idx] if idx < len(results) and isinstance(results[idx], dict) else {}
        passed = bool(item.get("passed", False))
        evidence = str(item.get("evidence", "Missing evidence."))
        commands_run = item.get("commands_run", [])
        if not isinstance(commands_run, list):
            commands_run = []
        result_snippet = str(item.get("result_snippet", ""))
        normalized.append(
            {
                "assertion": assertion_text,
                "passed": passed,
                "evidence": evidence,
                "commands_run": commands_run,
                "result_snippet": result_snippet,
            }
        )

    passed_count = sum(1 for r in normalized if r["passed"])
    total = len(assertions)
    failed = total - passed_count
    summary = {
        "passed": passed_count,
        "failed": failed,
        "total": total,
        "pass_rate": (passed_count / total) if total else 0.0,
    }

    return {"assertion_results": normalized, "summary": summary}


def build_assertion_prompt(assertions):
    """Build follow-up prompt asking Claude to grade assertions in same session."""
    assertions_json = json.dumps(assertions, ensure_ascii=False, indent=2)
    return (
        "Now validate the assertions below for your previous answer in this same session.\n"
        "Rules:\n"
        "1. For EACH assertion, actively validate it.\n"
        "2. If validation requires data checks, run bq queries yourself.\n"
        "3. If you cannot validate an assertion, mark it passed=false.\n"
        "4. Output ONLY valid JSON.\n"
        "5. JSON format:\n"
        "{\n"
        '  "assertion_results": [\n'
        "    {\n"
        '      "assertion": "<string>",\n'
        '      "passed": true,\n'
        '      "evidence": "<short evidence>",\n'
        '      "commands_run": ["<command1>", "<command2>"],\n'
        '      "result_snippet": "<short stdout/result snippet>"\n'
        "    }\n"
        "  ],\n"
        '  "summary": {"passed": 0, "failed": 0, "total": 0, "pass_rate": 0.0}\n'
        "}\n\n"
        f"Assertions:\n{assertions_json}\n"
    )


def main():
    """Run eval suite and write artifacts."""
    args = parse_args()
    evals_path = Path(args.evals).resolve()
    out_dir = Path(args.out_dir).resolve()

    log("[1/5] Checking Claude CLI...")
    claude_path = shutil.which(args.claude_bin)
    if not claude_path:
        print(f"Claude binary not found: {args.claude_bin}", file=sys.stderr)
        return 2
    log(f"  -> Claude binary: {claude_path}")

    log("[2/5] Loading eval definitions...")
    skill_name, cases = load_evals(evals_path)
    log(f"  -> Skill: {skill_name}")
    log(f"  -> Cases: {len(cases)}")

    log("[3/5] Preparing output directory...")
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    log(f"  -> Output: {out_dir}")

    total_assertions = 0
    total_passed = 0
    case_summaries = []
    total_tokens = []
    durations_ms = []

    log("[4/5] Running eval cases...")
    for case in cases:
        case_id = case["id"]
        case_dir = out_dir / case_id
        case_dir.mkdir(parents=True, exist_ok=True)

        log(f"- Case: {case_id}")
        skill_prompt = build_skill_prompt(skill_name, case["prompt"])
        log(f"  -> Prompt: {skill_prompt}")

        gen_events, gen_result = run_claude_stream(
            claude_path,
            args.model,
            skill_prompt,
            args.permission_mode,
            args.allowed_tools,
            args.safe_mode,
        )
        session_id = gen_result.get("session_id", "")
        output_text = gen_result.get("result", "")

        assertions = case.get("assertions", [])
        assertion_prompt = build_assertion_prompt(assertions)
        log("  -> Running same-session assertion grading...")
        grade_events, grade_result = run_claude_stream(
            claude_path,
            args.model,
            assertion_prompt,
            args.permission_mode,
            args.allowed_tools,
            args.safe_mode,
            resume_session_id=session_id,
        )

        # Artifact writes
        (case_dir / "prompt.txt").write_text(skill_prompt + "\n", encoding="utf-8")
        (case_dir / "output.md").write_text(output_text + "\n", encoding="utf-8")
        (case_dir / "assertion_prompt.txt").write_text(assertion_prompt + "\n", encoding="utf-8")
        (case_dir / "events.ndjson").write_text(
            "\n".join(json.dumps(e, ensure_ascii=True) for e in (gen_events + grade_events)) + "\n",
            encoding="utf-8",
        )

        combined_messages = extract_model_messages(gen_events) + extract_model_messages(grade_events)
        (case_dir / "model_messages.json").write_text(
            json.dumps(combined_messages, indent=2),
            encoding="utf-8",
        )
        (case_dir / "generation_result_event.json").write_text(
            json.dumps(gen_result, indent=2),
            encoding="utf-8",
        )
        (case_dir / "assertion_result_event.json").write_text(
            json.dumps(grade_result, indent=2),
            encoding="utf-8",
        )

        grading = parse_llm_grading(grade_result.get("result", ""), assertions)
        (case_dir / "grading.json").write_text(json.dumps(grading, indent=2), encoding="utf-8")

        summary = grading["summary"]
        log(
            "  -> Assertions: "
            f"{summary['passed']}/{summary['total']} passed "
            f"(pass_rate={summary['pass_rate']:.2f})"
        )

        total_assertions += summary["total"]
        total_passed += summary["passed"]
        case_summaries.append({"id": case_id, **summary})

        # Cost/time accounting from both generation and grading turns
        for result_event in (gen_result, grade_result):
            usage = result_event.get("usage", {})
            input_tokens = usage.get("input_tokens")
            output_tokens = usage.get("output_tokens")
            if isinstance(input_tokens, int) and isinstance(output_tokens, int):
                total_tokens.append(input_tokens + output_tokens)
            duration_ms = result_event.get("duration_ms")
            if isinstance(duration_ms, int):
                durations_ms.append(duration_ms)

    benchmark = {
        "skill_name": skill_name,
        "cases": case_summaries,
        "summary": {
            "passed_assertions": total_passed,
            "total_assertions": total_assertions,
            "pass_rate": (total_passed / total_assertions) if total_assertions else 0.0,
            "avg_tokens_per_turn": (sum(total_tokens) / len(total_tokens)) if total_tokens else None,
            "avg_duration_ms_per_turn": (sum(durations_ms) / len(durations_ms)) if durations_ms else None,
        },
    }
    (out_dir / "benchmark.json").write_text(json.dumps(benchmark, indent=2), encoding="utf-8")

    log("[5/5] Final summary:")
    print(json.dumps(benchmark["summary"], indent=2), flush=True)
    if total_passed == total_assertions:
        log("Result: PASS (all assertions passed)")
    else:
        log("Result: FAIL (some assertions failed)")
    return 0 if total_passed == total_assertions else 1


if __name__ == "__main__":
    raise SystemExit(main())
