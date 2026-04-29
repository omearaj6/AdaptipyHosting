import os
import json
import re
from dotenv import load_dotenv
from mistralai.client import Mistral

load_dotenv()

MODEL = os.getenv("MISTRAL_MODEL", "codestral-latest")


def extract_json(text: str):
    """
    Safely extract JSON from LLM response.
    Handles cases where extra text surrounds the JSON.
    """
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    return None


def codestral_analyse(
    problem: str,
    lesson: str,
    expected_output: str,
    code: str,
    stdout: str,
    stderr: str,
    ruff_feedback: str,
) -> dict:
    try:
        api_key = os.getenv("MISTRAL_API_KEY")
        if not api_key:
            raise ValueError("Missing MISTRAL_API_KEY")

        client = Mistral(api_key=api_key)

        instructions = (
            "You are a Python tutor grading a student's code.\n\n"

            "Your job:\n"
            "1. Determine if the student FOLLOWED ALL INSTRUCTIONS (not just output correctness).\n"
            "2. Detect cheating patterns (e.g. hardcoding answers instead of solving).\n"
            "3. Evaluate how wrong the solution is.\n\n"

            "Scoring rules:\n"
            "- Fully correct AND follows instructions → delta = +1\n"
            "- Incorrect → delta between -0.1 and -1\n"
            "  * Minor issue (formatting, casing) → -0.1 to -0.2\n"
            "  * Logic mistake → -0.3 to -0.5\n"
            "  * Major misunderstanding → -0.6 to -0.8\n"
            "  * Completely wrong / hardcoded / irrelevant → -0.9 to -1\n\n"
            "- Be strict about this. EVERY instruction must be followed for the solution to be correct\n\n"

            "Ruff usage rules:\n"
            "- Use Ruff feedback ONLY if it highlights real beginner-relevant issues\n"
            "- Ignore stylistic suggestions (like preferring no print statements)\n\n"

            "Feedback rules:\n"
            "- Speak in SECOND PERSON\n"
            "- If correct → brief praise\n"
            "- If correct but not optimal / convuluted-> Suggest ways to make the solution more efficient/straight forward"
            "- If slightly wrong → give a hint\n"
            "- If very wrong → explain the main issue clearly\n"
            "- DO NOT give the exact solution\n\n"
            "- Be direct but kind, do not use all caps\n\n"
            "- If the expected feedback does not match the problem, *prioritize the problem requirements* and NOT the expected output, and identify this in the feedback\n\n"
            "- If the output does not match the expected output, mark it correct ONLY IF the student followed all of the problem instructions exactly"

            "Return ONLY valid JSON.\n"
            "Do not include any text before or after the JSON.\n"
            "Do not use backticks.\n"
            "Start with { and end with }.\n\n"

            "Format:\n"
            "{\n"
            '  "correct": true/false,\n'
            '  "delta": number,\n'
            '  "feedback": "string"\n'
            "}\n"
        )

        user_msg = f"""
Lesson:
{lesson}

Problem:
{problem}

Expected Output:
{expected_output}

Student Code:
{code}

Program Output:
{stdout}

Errors:
{stderr}

Ruff Linter Feedback:
{ruff_feedback}
"""

        response = client.chat.complete(
            model=MODEL,
            messages=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=300,
            temperature=0.0,
        )

        text = (response.choices[0].message.content or "").strip()

        parsed = extract_json(text)

        if not parsed:
            print("DEBUG: Failed to parse JSON")
            print("FULL RESPONSE:", text)

            return {
                "correct": False,
                "delta": -0.4,
                "feedback": "Something went wrong analysing your code. Try again."
            }

        return parsed

    except Exception as e:
        print("CODESTRAL ERROR:", e)

        return {
            "correct": False,
            "delta": -0.5,
            "feedback": f"Error analysing code: {e}"
        }