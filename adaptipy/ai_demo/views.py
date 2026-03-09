from django.http import JsonResponse
from django.shortcuts import render
import subprocess
import tempfile
import os, json, re
from dotenv import load_dotenv
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.decorators import login_required
from ai_demo.models import TopicProgress, TopicProficiency, UserLearningProfile, UserNotebook
from .proficiencies import ensure_proficiency_rows, apply_decay_if_needed, update_proficiency, choose_next_topic, get_proficiencies
from django.db import connection
from ai_demo.models import ALL_TOPICS
from django.views.decorators.csrf import csrf_exempt
from ai_demo.utils.ruff_linter import get_ruff_feedback
from ai_demo.utils.ollama_client import ollama_generate


load_dotenv()

TOPICS = ALL_TOPICS
SM2_TOPICS = ["loops", "strings", "arrays", "recursion", "conditionals", "variables"]
USE_SM2 = False



def generate_hint_openai(problem: str, expected_output: str, code: str, stdout: str, stderr: str, correct: bool) -> str:
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        instructions = (
            "You are a tutor helping a beginner learn Python and analysing and evaluating their Python problems.\n"
            "Rules:\n"
            "- Do NOT provide the full solution.\n"
            "- Do NOT provide a complete corrected code listing.\n"
            "- Give a targeted hint.\n"
            "- If correct, give 1–2 improvements (style/readability/edge cases) without rewriting everything.\n"
            "- Be concise and beginner-friendly.\n"
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

Program stderr (if any):
{stderr}

Was the output correct? {correct}
"""

        response = client.chat.completions.create(
            model=os.getenv("OPENAI_HINT_MODEL", "gpt-3.5-turbo"),
            messages=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=220,
            temperature=0.4,
        )

        text = (response.choices[0].message.content or "").strip()
        return text or "Try comparing your output to the expected output line by line."

    except Exception as e:
        return f"OPENAI ERROR: {type(e).__name__}: {e}"



def _sr_defaults_dt():
    return {
        "ef": 2.5,
        "interval": 0.0,
        "reps": 0,
        "lapses": 0,
        "due": timezone.now(),  
    }

def ensure_user_topic_rows(user):

    now = timezone.now()
    existing = set(
        TopicProgress.objects.filter(user=user).values_list("topic", flat=True)
    )
    missing = [t for t in SM2_TOPICS if t not in existing]
    if missing:
        TopicProgress.objects.bulk_create(
            [TopicProgress(user=user, topic=t, due=now) for t in missing],
            ignore_conflicts=True,
        )

def get_sr_map_db(user):

    ensure_user_topic_rows(user)

    rows = TopicProgress.objects.filter(user=user).only(
        "topic", "ef", "interval", "reps", "lapses", "due"
    )

    sr_map = {}
    for r in rows:
        sr_map[r.topic] = {
            "ef": float(r.ef),
            "interval": float(r.interval),
            "reps": int(r.reps),
            "lapses": int(r.lapses),
            "due": r.due.isoformat(),
        }

    for t in SM2_TOPICS:
        if t not in sr_map:
            d = _sr_defaults_dt()
            sr_map[t] = {**d, "due": d["due"].isoformat()}

    return sr_map

def save_topic_state_db(user, topic, state):
    """
    Persist ONE topic state dict into DB.
    """
    due_dt = parse_due(state.get("due", timezone.now().isoformat()))
    TopicProgress.objects.update_or_create(
        user=user,
        topic=topic,
        defaults={
            "ef": float(state.get("ef", 2.5)),
            "interval": float(state.get("interval", 0.0)),
            "reps": int(state.get("reps", 0)),
            "lapses": int(state.get("lapses", 0)),
            "due": due_dt,
        },
    )




def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def parse_due(iso_str):
    try:
        dt = timezone.datetime.fromisoformat(iso_str)
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt)
        return dt
    except Exception:
        return timezone.now()


def sm2_update_state(state, grade, fast_mode=False):
    now = timezone.now()
    ef = float(state.get("ef", 2.5))
    interval = float(state.get("interval", 0.0))
    reps = int(state.get("reps", 0))
    lapses = int(state.get("lapses", 0))

    if grade < 3:
        lapses += 1
        reps = 0
        interval = 1.0
    else:
        reps += 1
        if reps == 1:
            interval = 1.0
        elif reps == 2:
            interval = 6.0
        else:
            interval = interval * ef

        ef_delta = (0.1 - (5 - grade) * (0.08 + (5 - grade) * 0.02))
        ef = clamp(ef + ef_delta, 1.3, 3.0)

    if fast_mode:
        due = now + timedelta(seconds=interval * 10)
    else:
        due = now + timedelta(days=interval)

    state.update({
        "ef": ef,
        "interval": interval,
        "reps": reps,
        "lapses": lapses,
        "due": due.isoformat(),
    })
    return state


def pick_recommended_topic(sr_map):
    now = timezone.now()
    items = [(topic, parse_due(st.get("due", now.isoformat()))) for topic, st in sr_map.items()]

    overdue = sorted([x for x in items if x[1] <= now], key=lambda x: x[1])
    if overdue:
        return overdue[0][0]

    soonest = sorted(items, key=lambda x: x[1])
    return soonest[0][0] if soonest else "loops"
        

def generate_problem_with_solution(topic: str, profs: dict) -> dict:
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        topic_prof = float(profs.get(topic, 0.0))

        prompt = f"""
Create a Python coding problem.

Main topic: {topic}
Main topic proficiency: {topic_prof}/5

CRITICAL REQUIREMENTS:
1. The problem MUST specify ALL concrete values needed to solve it.
2. For calculations, explicitly state the numbers to use (e.g., "with length 6 and width 4")
3. For data structures, EITHER:
   a) Tell the user to create the data structure with specific values, OR
   b) Provide a variable name and its contents
4. For conditionals, state the exact conditions and values
5. The problem should be solvable with ONLY the information provided

Rules:
- Must use print() for output only.
- Do NOT use input(), file I/O, imports, or external libraries.
- The program must be fully self-contained and executable.
- All values must be hard-coded as variables or literals in the code.
- Keep intended solution under 15 lines.
- Output should be simple values, NOT formatted strings unless explicitly requested.
- If main topic proficiency is 0, include a brief introductory lesson with a small example.

FORMATTING GUIDELINES:
1. For list problems: "Create a list called 'numbers' containing [4, 2, 9, 7, 5, 1] and print the sum of squares."
2. For variable problems: "Assign 10 to variable x and 20 to variable y, then print their sum."
3. For calculation problems: "Calculate 6 * 4 and print the result."
4. DO NOT expect formatted output like "The sum is: 24" unless explicitly part of the problem.
5. When showing expected output, show JUST the value, e.g., "24" not "The result is 24"

BAD EXAMPLE (vague): "Write a Python program to calculate the area of a rectangle."
BAD EXAMPLE (ambiguous list): "You have a list of integers [4, 2, 9, 7, 5, 1]. Write a Python program that computes and prints the sum of the squares."
BAD EXAMPLE (formatted assumption): "Print the sum with a message like 'Sum: 24'"

GOOD EXAMPLE (clear): "Create a list called 'numbers' containing [4, 2, 9, 7, 5, 1]. Compute and print the sum of the squares of all numbers in the list."
GOOD EXAMPLE (clear): "Assign length = 6 and width = 4, then calculate and print the area of the rectangle."
GOOD EXAMPLE (simple output): "Print the result of 6 * 4."

Return ONLY valid JSON with keys:
- problem (string) - specific problem with concrete values
- explanation (string) - how to solve it
- expected_output (string) - exact expected output (e.g., "24" or "[1, 2, 3]")
- general_hints (array of strings)
- subtopics_used (array of strings)
- subtopic_hints (object)
- lesson (string) // ONLY if main topic proficiency is 0

IMPORTANT: The expected_output should be the exact string that print() would output, without extra formatting unless explicitly required by the problem.
"""

        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Return strict JSON only. No markdown."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=500,
            temperature=0.7,
        )

        raw = (response.choices[0].message.content or "").strip()
        data = json.loads(raw)

        return {
            "problem": data.get("problem", ""),
            "expected_output": data.get("expected_output", ""),
            "explanation": data.get("explanation", ""),
            "general_hints": data.get("general_hints", []),
            "subtopics_used": data.get("subtopics_used", []),
            "subtopic_hints": data.get("subtopic_hints", {}),
            "lesson": data.get("lesson", ""),
        }

    except Exception:
        # Keep your fallbacks exactly as safety
        SM2_FALLBACKS = {
            "loops": ("Print numbers 1 to 5", "1\n2\n3\n4\n5"),
            "strings": ("Print each character in hello", "h\ne\nl\nl\no"),
            "arrays": ("Print each element in [1,2,3]", "1\n2\n3"),
            "recursion": ("Print numbers 5 to 1", "5\n4\n3\n2\n1"),
            "conditionals": ("Print even if 4 is even", "even"),
            "variables": ("Set x = 10 and print it", "10"),
        }

        NEW_FALLBACKS = {
            "print_basics": ("Use print() to display the message Hello World.", "Hello World"),
            "variables": ("Create a variable x with value 5 and print it.", "5"),
            "primitive_data_types": ("Print an integer, a float, and a string, each on a new line.", "1\n2.5\nhello"),
            "simple_operators": ("Print the result of 3 + 4.", "7"),
            "lists": ("Create a list [1, 2, 3] and print it.", "[1, 2, 3]"),
            "conditionals": ("If x = 3, print 'odd'.", "odd"),
            "while_loops": ("Use a while loop to print numbers 1 to 3.", "1\n2\n3"),
            "for_loops": ("Use a for loop to print numbers 1 to 3.", "1\n2\n3"),
            "strings_advanced": ("Print the length of the string 'hello'.", "5"),
            "basic_edge_cases": ("Print the result of dividing 10 by 1.", "10.0"),
            "dictionaries": ("Create a dictionary with key 'a' and value 1, then print it.", "{'a': 1}"),
            "functions": ("Define a function that prints 'hi' and call it.", "hi"),
            "all_loops_advanced": ("Print numbers 1 to 5 using any loop.", "1\n2\n3\n4\n5"),
        }

        p, e = (
            SM2_FALLBACKS.get(topic)
            or NEW_FALLBACKS.get(topic)
            or (f"Write a short Python program about {topic} that prints a simple result.", "OK")
        )

        lesson = ""
        if float(profs.get(topic, 0.0)) == 0.0:
            lesson = "Intro: try printing a simple value first (e.g., print(1)) and then build from there."

        return {
            "problem": p,
            "expected_output": e,
            "explanation": "",
            "general_hints": [],
            "subtopics_used": [],
            "subtopic_hints": {},
            "lesson": lesson,
        }




def evaluate_code_quality(code, problem):
    return "Review your logic and syntax carefully."


def check_user_code(code, expected_output):


    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            path = f.name

        result = subprocess.run(['python3', path], capture_output=True, text=True, timeout=5)
        os.unlink(path)

        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()
        correct = (result.returncode == 0) and (stdout == expected_output.strip())
        print("DEBUG stdout repr:", repr(stdout))
        print("DEBUG expected repr:", repr(expected_output.strip()))
        print("DEBUG returncode:", result.returncode)
        return correct, stdout, stderr
    except subprocess.TimeoutExpired:
        return False, "", "Time limit exceeded (timeout)."
    except Exception as e:
        return False, "", f"Execution error: {e}"
    


@login_required
def save_notebook(request):
    """Simple notebook save endpoint"""
    if request.method == 'POST':
        content = request.POST.get('content', '')

        # Get or create notebook
        notebook, created = UserNotebook.objects.get_or_create(
            user=request.user,
            defaults={'content': content}
        )

        # Update if not newly created
        if not created:
            notebook.content = content
            notebook.save()

        return JsonResponse({
            'success': True,
            'message': 'Notebook saved'
        })

    return JsonResponse({'success': False, 'error': 'POST only'}, status=400)


@login_required
def coding_demo(request):
    ensure_proficiency_rows(request.user)
    days_decayed = apply_decay_if_needed(request.user)
    profs = get_proficiencies(request.user)
    wants_new_problem = (request.method == "POST" and "new_problem" in request.POST)
    print("DECAY APPLIED:", days_decayed)
    print(connection.vendor)

    ruff_feedback = None

    notebook, created = UserNotebook.objects.get_or_create(
            user=request.user,
            defaults={'content': 'Welcome to your Python notebook!\n\nWrite notes, code snippets, or anything you want to remember here.\n\n- Notes are saved automatically when you click away.\n- Use this space for anything helpful!'}
        )

    if request.method == "POST" and "reset_progress" in request.POST:
        TopicProgress.objects.filter(user=request.user).delete()

        TopicProficiency.objects.filter(user=request.user).update(
            proficiency=0.0,
            last_practiced_at=None,
        )
        UserLearningProfile.objects.filter(user=request.user).update(
            last_topic="",
            last_decay_applied_at=timezone.now(),
        )


        request.session.pop("due_practice_topic", None)
        request.session.pop("due_practice_problem", None)
        request.session.pop("due_practice_expected", None)
        request.session.pop("current_problem_json", None)
        request.session.pop("show_explanation", None)
        request.session.pop("active_topic", None)

        
    result = None
    user_code = ""
    evaluation_feedback = None

    if request.method == "POST" and (
        "due_run_code" in request.POST or
        "due_submit_code" in request.POST or
        "due_new_problem" in request.POST or
        "due_code" in request.POST
    ):
        request.session["due_practice_open"] = True
    elif request.method == "POST" and (
        "run_code" in request.POST or
        "submit_code" in request.POST or
        "select_topic" in request.POST or
        "new_problem" in request.POST or
        "code" in request.POST
    ):
        request.session["due_practice_open"] = False


    if USE_SM2:
        sr_map = get_sr_map_db(request.user)
        recommended_topic = pick_recommended_topic(sr_map)
    else:
        sr_map = {}
        profs = get_proficiencies(request.user)

    if request.method == "POST" and "new_problem" in request.POST:
        request.session.pop("current_problem_json", None)
        request.session.pop("show_explanation", None)
        request.session.pop("active_topic", None)
    active_topic = request.session.get("active_topic")
    if not active_topic:
        active_topic = choose_next_topic(request.user, profs)
        request.session["active_topic"] = active_topic

    selected_topic = active_topic
    recommended_topic = active_topic

    if "current_problem_json" not in request.session:
        problem_json = generate_problem_with_solution(selected_topic, profs)
        request.session["current_problem_json"] = problem_json
    else:
        problem_json = request.session["current_problem_json"]

    ai_problem = problem_json.get("problem", "")
    expected_output = problem_json.get("expected_output", "")
    lesson = problem_json.get("lesson", "")
    explanation = problem_json.get("explanation", "")


    if request.method == "POST" and "i_dont_understand" in request.POST:
        request.session["show_explanation"] = True

    show_explanation = bool(request.session.get("show_explanation", False))

    if request.method == "POST" and "code" in request.POST:
        user_code = request.POST.get("code", "")
        correct, output, stderr = check_user_code(user_code, expected_output)


        if "run_code" in request.POST:
            result = f"Output:\n{output}"

        elif "submit_code" in request.POST:
            user_code = request.POST.get("code", "")
            correct, output, stderr = check_user_code(user_code, expected_output)
            ruff_feedback = get_ruff_feedback(user_code)

            if USE_SM2 and selected_topic in SM2_TOPICS:
                fast_mode = os.getenv("SR_FAST_MODE") == "1"
                grade = 5 if correct else 1
                sr_map[selected_topic] = sm2_update_state(sr_map[selected_topic], grade, fast_mode)
                save_topic_state_db(request.user, selected_topic, sr_map[selected_topic])

            delta = 1.0 if correct else -0.25
            update_proficiency(request.user, topic=selected_topic, delta=delta)

            result = "Correct!" if correct else "Incorrect"

            if not correct:
                evaluation_feedback = generate_hint_openai(
                    problem=ai_problem,
                    expected_output=expected_output,
                    code=user_code,
                    stdout=output,
                    stderr=stderr,
                    correct=correct,
                )



    if USE_SM2:
        now = timezone.now()
        fast_mode = os.getenv("SR_FAST_MODE") == "1"
        soon_delta = timedelta(seconds=90) if fast_mode else timedelta(days=2)

        due_now, due_soon, due_later = [], [], []

        for topic, state in sr_map.items():
            due_dt = parse_due(state["due"])
            item = {"topic": topic, "state": state}
            if due_dt <= now:
                due_now.append(item)
            elif due_dt <= now + soon_delta:
                due_soon.append(item)
            else:
                due_later.append(item)

        due_practice_topic = None
        due_practice_problem = None
        due_user_code = ""
        due_result = None
        due_evaluation_feedback = None

        if due_now:
            new_due_topic = due_now[0]["topic"]

            due_practice_topic = request.session.get("due_practice_topic")
            if due_practice_topic != new_due_topic:
                due_practice_topic = new_due_topic
                request.session["due_practice_topic"] = due_practice_topic
                request.session.pop("due_practice_problem", None)
                request.session.pop("due_practice_expected", None)

            if request.method == "POST" and "due_new_problem" in request.POST:
                request.session.pop("due_practice_problem", None)
                request.session.pop("due_practice_expected", None)

            if "due_practice_problem" not in request.session or "due_practice_expected" not in request.session:
                problem_json_due = generate_problem_with_solution(due_practice_topic, profs)
                request.session["due_practice_problem"] = problem_json_due.get("problem", "")
                request.session["due_practice_expected"] = problem_json_due.get("expected_output", "")

            due_practice_problem = request.session["due_practice_problem"]

            if request.method == "POST" and ("due_run_code" in request.POST or "due_submit_code" in request.POST):
                due_user_code = request.POST.get("due_code", "")
                correct, output, stderr = check_user_code(due_user_code, request.session["due_practice_expected"])

                if "due_run_code" in request.POST:
                    due_result = f"Output:\n{output}"

                elif "due_submit_code" in request.POST:
                    grade = 5 if correct else 1
                    sr_map[due_practice_topic] = sm2_update_state(sr_map[due_practice_topic], grade, fast_mode)
                    save_topic_state_db(request.user, due_practice_topic, sr_map[due_practice_topic])
                    due_result = "Correct!" if correct else "Incorrect"
                    if not correct:
                        due_evaluation_feedback = generate_hint_openai(
                            problem=due_practice_problem,
                            expected_output=request.session["due_practice_expected"],
                            code=due_user_code,
                            stdout=output,
                            stderr=stderr,
                            correct=correct,
                        )
                    request.session.pop("due_practice_problem", None)
                    request.session.pop("due_practice_expected", None)
                    

        due_practice_open = bool(request.session.get("due_practice_open", False))
    else:
        due_now, due_soon, due_later = [], [], []
        due_practice_topic = None
        due_practice_problem = None
        due_user_code = ""
        due_result = None
        due_evaluation_feedback = None
        due_practice_open = False


    proficiency_debug = (
        TopicProficiency.objects
        .filter(user=request.user)
        .order_by("topic")
    )


    return render(request, "coding_demo.html", {
        "result": result,
        "user_code": user_code,
        "ai_problem": ai_problem,
        "topics": TOPICS,
        "selected_topic": selected_topic,
        "recommended_topic": recommended_topic,
        "evaluation_feedback": evaluation_feedback,
        "sr_map": sr_map,
        "due_now": due_now,
        "due_soon": due_soon,
        "due_later": due_later,
        "due_practice_topic": due_practice_topic,
        "due_practice_problem": due_practice_problem,
        "due_user_code": due_user_code,
        "due_result": due_result,
        "due_evaluation_feedback": due_evaluation_feedback,
        "due_practice_open": due_practice_open,
        "days_decayed": days_decayed,
        "proficiency_debug": proficiency_debug,
        "lesson": lesson,
        "explanation": explanation,
        "show_explanation": show_explanation,
        "expected_output": expected_output,
        "notebook_content": notebook.content,
        "ruff_feedback": ruff_feedback,
    })


def recommend_problem(request):
    weak_area = request.GET.get("weakness", "loops")
    return JsonResponse({"recommended_topic": weak_area})

def home(request):
    return render(request, "home.html")

@login_required
def notebook_page(request):
    notebook, _ = UserNotebook.objects.get_or_create(
        user=request.user,
        defaults={"content": ""}
    )
    return render(request, "notebook.html", {"notebook": notebook})



@login_required
def test_ollama(request):
    try:
        response = ollama_generate("Generate a coding problem about lists for a beginner")
        return JsonResponse({"ollama_response": response})
    except Exception as e:
        return JsonResponse({"error": str(e)})