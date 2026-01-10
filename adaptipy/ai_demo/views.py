from django.http import JsonResponse
from django.shortcuts import render
import subprocess
import tempfile
import os
from dotenv import load_dotenv
import json
from django.utils import timezone
from datetime import timedelta

load_dotenv()

TOPICS = ["loops", "strings", "arrays", "recursion", "conditionals", "variables"]


def _sr_defaults():
    return {
        "ef": 2.5,
        "interval": 0.0,
        "reps": 0,
        "lapses": 0,
        "due": timezone.now().isoformat()
    }


def get_sr_map(session, topics):
    sr = session.get("sm2_sr")
    if not isinstance(sr, dict):
        sr = {}

    changed = False
    for t in topics:
        if t not in sr:
            sr[t] = _sr_defaults()
            changed = True

    if changed:
        session["sm2_sr"] = sr
    return sr


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


def generate_problem_with_solution(concept="loops"):
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You create Python coding problems that use PRINT statements."},
                {"role": "user", "content": f"""Create a simple Python problem about {concept}.

Return JSON:
{{"problem": "...", "expected_output": "..."}}"""}
            ],
            max_tokens=150,
            temperature=0.7
        )

        data = json.loads(response.choices[0].message.content.strip())
        return data["problem"], data["expected_output"]

    except Exception:
        fallback = {
            "loops": ("Print numbers 1 to 5", "1\n2\n3\n4\n5"),
            "strings": ("Print each character in hello", "h\ne\nl\nl\no"),
            "arrays": ("Print each element in [1,2,3]", "1\n2\n3"),
            "recursion": ("Print numbers 5 to 1", "5\n4\n3\n2\n1"),
            "conditionals": ("Print even if 4 is even", "even"),
            "variables": ("Set x=10 and print it", "10")
        }
        return fallback[concept]


def evaluate_code_quality(code, problem):
    return "Review your logic and syntax carefully."


def check_user_code(code, expected_output):
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            path = f.name

        result = subprocess.run(['python3', path], capture_output=True, text=True, timeout=5)
        os.unlink(path)

        output = result.stdout.strip()
        return result.returncode == 0 and output == expected_output.strip(), output
    except Exception:
        return False, ""


def coding_demo(request):

    if request.method == "POST" and "reset_progress" in request.POST:
        request.session.pop("sm2_sr", None)
        request.session.pop("due_practice_topic", None)
        request.session.pop("due_practice_problem", None)
        request.session.pop("due_practice_expected", None)
        
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


    sr_map = get_sr_map(request.session, TOPICS)
    recommended_topic = pick_recommended_topic(sr_map)

    selected_topic = request.session.get("selected_topic", recommended_topic)
    if selected_topic not in TOPICS:
        selected_topic = recommended_topic

    if request.method == "POST" and "select_topic" in request.POST:
        selected_topic = request.POST.get("topic", recommended_topic)
        request.session["selected_topic"] = selected_topic
        request.session.pop("current_problem", None)
        request.session.pop("current_expected_output", None)

    if request.method == "POST" and "new_problem" in request.POST:
        request.session.pop("current_problem", None)
        request.session.pop("current_expected_output", None)

    if "current_problem" not in request.session:
        ai_problem, expected_output = generate_problem_with_solution(selected_topic)
        request.session["current_problem"] = ai_problem
        request.session["current_expected_output"] = expected_output
    else:
        ai_problem = request.session["current_problem"]
        expected_output = request.session["current_expected_output"]

    if request.method == "POST" and "code" in request.POST:
        user_code = request.POST.get("code", "")
        correct, output = check_user_code(user_code, expected_output)

        if "run_code" in request.POST:
            result = f"Output:\n{output}"

        elif "submit_code" in request.POST:
            fast_mode = os.getenv("SR_FAST_MODE") == "1"
            grade = 5 if correct else 1
            sr_map[selected_topic] = sm2_update_state(sr_map[selected_topic], grade, fast_mode)
            request.session["sm2_sr"] = sr_map
            result = "Correct!" if correct else "Incorrect"
            if not correct:
                evaluation_feedback = evaluate_code_quality(user_code, ai_problem)

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
            p, e = generate_problem_with_solution(due_practice_topic)
            request.session["due_practice_problem"] = p
            request.session["due_practice_expected"] = e

        due_practice_problem = request.session["due_practice_problem"]

        if request.method == "POST" and ("due_run_code" in request.POST or "due_submit_code" in request.POST):
            due_user_code = request.POST.get("due_code", "")
            correct, output = check_user_code(due_user_code, request.session["due_practice_expected"])

            if "due_run_code" in request.POST:
                due_result = f"Output:\n{output}"

            elif "due_submit_code" in request.POST:
                grade = 5 if correct else 1
                sr_map[due_practice_topic] = sm2_update_state(sr_map[due_practice_topic], grade, fast_mode)
                request.session["sm2_sr"] = sr_map
                due_result = "Correct!" if correct else "Incorrect"
                if not correct:
                    due_evaluation_feedback = evaluate_code_quality(due_user_code, due_practice_problem)
                request.session.pop("due_practice_problem", None)
                request.session.pop("due_practice_expected", None)

    due_practice_open = bool(request.session.get("due_practice_open", False))



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
        "due_practice_open": due_practice_open,
    })


def recommend_problem(request):
    weak_area = request.GET.get("weakness", "loops")
    return JsonResponse({"recommended_topic": weak_area})
