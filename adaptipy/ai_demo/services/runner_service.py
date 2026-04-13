import os
import requests

def check_user_code(code, expected_output):
    try:
        runner_url = os.environ["RUNNER_URL"]
        runner_secret = os.environ["SECRET_PASSPHRASE"]
        print("RUNNER_URL:", runner_url)
        print("RUNNER_SECRET present:", bool(runner_secret))

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
        print("RUNNER STATUS:", response.status_code)
        print("RUNNER BODY:", response.text)
        data = response.json()

        stdout = (data.get("stdout") or "").strip()
        stderr = (data.get("stderr") or "").strip()
        exit_code = data.get("exitCode", 1)

        correct = (exit_code == 0) and (stdout == expected_output.strip())

        print("DEBUG stdout repr:", repr(stdout))
        print("DEBUG expected repr:", repr(expected_output.strip()))
        print("DEBUG exitCode:", exit_code)
        

        return correct, stdout, stderr

    except requests.Timeout:
        return False, "", "Execution service timed out."
    except Exception as e:
        return False, "", f"Execution error: {e}"