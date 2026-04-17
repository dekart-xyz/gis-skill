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
        "--case",
        default="",
        help="Run only one case by id from evals.json.",
    )
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
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Delete output directory before run.",
    )
    parser.add_argument(
        "--show-io",
        dest="show_io",
        action="store_true",
        help="Print live Claude input/output trace for each eval turn (default: enabled).",
    )
    parser.add_argument(
        "--no-show-io",
        dest="show_io",
        action="store_false",
        help="Disable live Claude IO trace.",
    )
    parser.set_defaults(show_io=True)
    parser.add_argument(
        "--io-max-chars",
        type=int,
        default=1000,
        help="Max chars per printed IO block when --show-io is enabled.",
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


def short_text(value, max_chars):
    """Return a compact single-line preview with bounded length."""
    if value is None:
        return ""
    text = str(value).replace("\n", "\\n")
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "...<truncated>"


def print_event_trace(event, io_max_chars):
    """Print concise per-event trace line for stream-json events."""
    event_type = event.get("type")
    if event_type == "assistant":
        message = event.get("message", {})
        for block in message.get("content", []):
            if not isinstance(block, dict):
                continue
            block_type = block.get("type")
            if block_type == "text":
                log(f"    [assistant:text] {short_text(block.get('text', ''), io_max_chars)}")
            elif block_type == "thinking":
                log(f"    [assistant:thinking] {short_text(block.get('thinking', ''), io_max_chars)}")
            elif block_type == "tool_use":
                name = block.get("name", "")
                tool_input = block.get("input", {})
                command = tool_input.get("command") if isinstance(tool_input, dict) else ""
                if command:
                    log(f"    [assistant:tool_use:{name}] {short_text(command, io_max_chars)}")
                else:
                    log(
                        "    [assistant:tool_use:"
                        f"{name}] {short_text(json.dumps(tool_input, ensure_ascii=False), io_max_chars)}"
                    )
    elif event_type == "user":
        tool_result = event.get("tool_use_result")
        if isinstance(tool_result, dict):
            stdout = short_text(tool_result.get("stdout", ""), io_max_chars)
            stderr = short_text(tool_result.get("stderr", ""), io_max_chars)
            if stdout:
                log(f"    [tool:stdout] {stdout}")
            if stderr:
                log(f"    [tool:stderr] {stderr}")
    elif event_type == "result":
        log(f"    [result:{event.get('subtype', 'unknown')}]")
        log(f"    [result:text] {short_text(event.get('result', ''), io_max_chars)}")


def run_claude_stream(
    claude_bin,
    model,
    prompt,
    permission_mode,
    allowed_tools,
    safe_mode,
    resume_session_id="",
    show_io=False,
    io_max_chars=1000,
    turn_name="run",
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
    if show_io:
        log(f"  -> [{turn_name}] Prompt:")
        log(f"     {prompt}")

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    events = []
    result_event = None
    stdout_lines = []
    for raw_line in proc.stdout:
        stdout_lines.append(raw_line)
        line = raw_line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        events.append(event)
        if show_io:
            print_event_trace(event, io_max_chars)
        if event.get("type") == "result":
            result_event = event

    stderr_text = proc.stderr.read() if proc.stderr else ""
    return_code = proc.wait()
    if return_code != 0:
        fallback_out = "".join(stdout_lines).strip()
        raise RuntimeError(f"Claude CLI failed: {stderr_text.strip() or fallback_out}")

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


def collect_benchmark_from_disk(out_dir):
    """Aggregate benchmark summary from all case grading.json files on disk."""
    case_summaries = []
    total_assertions = 0
    total_passed = 0

    for case_dir in sorted(p for p in out_dir.iterdir() if p.is_dir()):
        grading_path = case_dir / "grading.json"
        if not grading_path.exists():
            continue
        try:
            grading = json.loads(grading_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        summary = grading.get("summary", {})
        passed = int(summary.get("passed", 0))
        total = int(summary.get("total", 0))
        failed = int(summary.get("failed", max(total - passed, 0)))
        pass_rate = float(summary.get("pass_rate", (passed / total) if total else 0.0))

        case_summaries.append(
            {
                "id": case_dir.name,
                "passed": passed,
                "failed": failed,
                "total": total,
                "pass_rate": pass_rate,
            }
        )
        total_assertions += total
        total_passed += passed

    return case_summaries, total_passed, total_assertions


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
    if args.case:
        cases = [c for c in cases if c.get("id") == args.case]
        if not cases:
            print(f"Case not found: {args.case}", file=sys.stderr)
            return 2
    log(f"  -> Skill: {skill_name}")
    log(f"  -> Cases: {len(cases)}")

    log("[3/5] Preparing output directory...")
    if args.clean and out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    log(f"  -> Output: {out_dir}")

    total_tokens = []
    durations_ms = []

    log("[4/5] Running eval cases...")
    for case in cases:
        case_id = case["id"]
        case_dir = out_dir / case_id
        if case_dir.exists():
            shutil.rmtree(case_dir)
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
            show_io=args.show_io,
            io_max_chars=args.io_max_chars,
            turn_name=f"{case_id}:generation",
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
            show_io=args.show_io,
            io_max_chars=args.io_max_chars,
            turn_name=f"{case_id}:grading",
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

    case_summaries, total_passed, total_assertions = collect_benchmark_from_disk(out_dir)

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
