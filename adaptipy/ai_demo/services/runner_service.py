import os

import requests


def check_user_code(code):
    try:
        runner_url = os.environ["RUNNER_URL"]
        runner_secret = os.environ["SECRET_PASSPHRASE"]

        response = requests.post(
            f"{runner_url}/run",
            json={
                "code": code,
                "timeoutMs": 5000,
            },
            headers={
                "X-API-Token": runner_secret,
            },
            timeout=15,
        )

        data = response.json()

        stdout = (data.get("stdout") or "").strip()
        stderr = (data.get("stderr") or "").strip()
        exit_code = data.get("exitCode", 1)

        return stdout, stderr, exit_code

    except requests.Timeout:
        return "", "Execution service timed out.", 1
    except Exception as e:
        return "", f"Execution error: {e}", 1