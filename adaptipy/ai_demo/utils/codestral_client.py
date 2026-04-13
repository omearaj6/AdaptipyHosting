import os
from dotenv import load_dotenv
from mistralai.client import Mistral

load_dotenv()

MODEL = os.getenv("MISTRAL_MODEL", "codestral-latest")


def codestral_analyse(
    problem: str,
    expected_output: str,
    code: str,
    stdout: str,
    stderr: str,
    correct: bool,
) -> str:
    try:
        api_key = os.getenv("MISTRAL_API_KEY")
        if not api_key:
            raise ValueError("Missing MISTRAL_API_KEY")
        client = Mistral(api_key=api_key)

        instructions = (
            "You are a tutor helping a beginner learn Python and analysing their Python code.\n"
            "Rules:\n"
            "- Do NOT provide the full solution.\n"
            "- Do NOT provide a complete corrected code listing.\n"
            "- Give one targeted hint.\n"
            "- Be concise and beginner-friendly.\n"
            "- Use the student's code, expected output, program output, runtime errors, and Ruff linter feedback.\n"
            "- Focus on the single most important issue.\n"
            "- Prefer runtime or syntax problems over style issues.\n"
            "- Return exactly three short lines in this format:\n"
            "Main issue: ...\n"
            "Explanation: ...\n"
            "Hint: ...\n"
        )

        user_msg = f"""
Problem:
{problem}

Expected output:
{expected_output}

Student code:
{code}

Program stdout:
{stdout}

Program stderr:
{stderr}

Was the output correct? {correct}

"""

        print("DEBUG: codestral_analyse() called")
        print("DEBUG: model =", MODEL)
        print("DEBUG: api key present =", bool(api_key))
        print("DEBUG: code preview =", repr(code[:120]))
        print("DEBUG: problem preview =", repr(problem[:120]))
        print("DEBUG: stderr preview =", repr(stderr[:120]))
        print("DEBUG: stdout preview =", repr(stdout[:120]))
        print("DEBUG: correct =", correct)

        response = client.chat.complete(
            model=MODEL,
            messages=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=180,
            temperature=0.2,
        )

        print("DEBUG: raw response received")
        print("DEBUG: number of choices =", len(response.choices))

        text = (response.choices[0].message.content or "").strip()
        print("DEBUG: content preview =", repr(text[:200]))

        return text or "Hint: Compare your output and error message carefully."
    
    except Exception as e:
        return f"CODESTRAL ERROR: {type(e).__name__}: {e}"