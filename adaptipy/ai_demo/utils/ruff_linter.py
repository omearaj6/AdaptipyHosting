import subprocess
import json


def run_ruff_analysis(code: str) -> str:
    """
    Run Ruff analysis on Python code with preview mode enabled.
    Returns formatted output for display.
    """
    try:
        result = subprocess.run(
            [
                "ruff",
                "check",
                "--select",
                "ALL",
                "--preview",
                "--output-format",
                "json",
                "-",
            ],
            input=code,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
        )

        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()

        # Ruff found issues
        if result.returncode == 1 and stdout:
            return format_ruff_output(stdout)

        # No issues found
        if result.returncode == 0:
            return "✅ No issues found!"

        # Ruff execution error
        if result.returncode > 1:
            return f"⚠️ Ruff error:\n{stderr}"

        return "⚠️ Ruff ran but produced no output."

    except subprocess.TimeoutExpired:
        return "⚠️ Ruff analysis timed out."
    except Exception as e:
        return f"⚠️ Ruff analysis failed: {str(e)}"

def format_ruff_output(raw_output: str) -> str:
    """
    Format Ruff JSON output for display.
    """
    try:
        issues = json.loads(raw_output)
    except json.JSONDecodeError:
        return "⚠️ Failed to parse Ruff output."

    if not issues:
        return "✅ No issues found!"

    formatted = ["🔍 Code Analysis:"]

    for issue in issues:
        rule = issue.get("code")
        message = issue.get("message")
        location = issue.get("location", {})
        line = location.get("row")
        col = location.get("column")

        formatted.append(
            f"  {rule} {message} --> line {line}, char {col}"
        )

    return "\n".join(formatted)

def get_ruff_feedback(code: str) -> str:
    """
    Main function to call from Django views.
    """
    return run_ruff_analysis(code)
