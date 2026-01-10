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
                {"role": "system", "content": "You create Python coding problems that use PRINT statements. The expected output should match what print() would display."},
                {"role": "user", "content": f"""Create a simple Python problem about {concept} that uses print() statements.

                Return format:
                {{
                    "problem": "Clear problem description here",
                    "expected_output": "The exact output that print() would show"
                }}

                IMPORTANT: The expected output should be multiple lines if multiple print() statements are used.

                Example:
                {{
                    "problem": "Write a loop that prints even numbers from 1 to 10",
                    "expected_output": "2\\n4\\n6\\n8\\n10"
                }}"""}
            ],
            max_tokens=150,
            temperature=0.7
        )

        result_text = response.choices[0].message.content.strip()
        result = json.loads(result_text)

        problem = result.get('problem', 'Write a loop that prints even numbers from 1 to 10')
        expected_output = result.get('expected_output', '2\n4\n6\n8\n10')

        print(f"AI Generated - Problem: {problem}")
        print(f"AI Generated - Expected: {repr(expected_output)}")

        return problem, expected_output

    except Exception as e:
        print(f"OpenAI failed: {e}")
        fallback_problems = {
            "loops": ("Write a loop that prints numbers 1 to 5", "1\n2\n3\n4\n5"),
            "strings": ("Print each character of 'hello' on separate lines", "h\ne\nl\nl\no"),
            "arrays": ("Create a list [1,2,3] and print each element", "1\n2\n3"),
            "recursion": ("Print numbers from 5 down to 1", "5\n4\n3\n2\n1"),
            "conditionals": ("Print 'even' if 4 is even, 'odd' otherwise", "even"),
            "variables": ("Create a variable x=10 and print it", "10")
        }
        return fallback_problems.get(concept, ("Write a loop that prints numbers 1 to 5", "1\n2\n3\n4\n5"))

def evaluate_code_quality(code, problem_description):
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": """You are a helpful coding assistant. Give VERY VAGUE hints when students have errors.

                RULES:
                - NEVER give the solution or write code
                - NEVER point to specific lines
                - NEVER mention specific variable names
                - Keep hints to 1-2 sentences max
                - Be encouraging and positive

                Examples of good vague hints:
                - "Remember that indentation is important in Python"
                - "Check your syntax when writing loops and conditionals"
                - "Make sure you're using the right data types"
                - "Think about the order of your operations"
                - "Double-check your variable assignments"
                - "Consider if you need any conditional statements"
                - "Remember what each loop iteration should do"

                Examples of BAD hints (too specific):
                - "You forgot a colon on line 3"
                - "Change 'x' to 'y'"
                - "Use a for loop instead of while"
                - "Add print statements here"
                """},
                {"role": "user", "content": f"""Problem: {problem_description}

                Student's code (which has an error):
                ```python
                {code}
                ```

                Please provide a brief, vague hint to help them think about the problem differently."""}
            ],
            max_tokens=100,
            temperature=0.3
        )

        feedback = response.choices[0].message.content.strip()
        return feedback

    except Exception as e:
        print(f"OpenAI evaluation failed: {e}")
        return "Keep trying! Review the basics and try again."

def check_user_code(code, expected_output):
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_file = f.name

        result = subprocess.run(['python3', temp_file], capture_output=True, text=True, timeout=5)

        os.unlink(temp_file)

        user_output = result.stdout.strip()
        expected_clean = expected_output.strip()

        is_correct = result.returncode == 0 and user_output == expected_clean

        return is_correct, user_output

    except Exception as e:
        print(f"Code check exception: {e}")
        return False, ""

def coding_demo(request):
    result = None
    user_code = ""
    evaluation_feedback = None

    sr_map = get_sr_map(request.session, TOPICS)
    recommended_topic = pick_recommended_topic(sr_map)

    selected_topic = request.session.get('selected_topic')
    if selected_topic not in TOPICS:
        selected_topic = recommended_topic

    if request.method == 'POST' and 'select_topic' in request.POST:
        selected_topic = request.POST.get('topic', recommended_topic)
        if selected_topic not in TOPICS:
            selected_topic = recommended_topic
        request.session['selected_topic'] = selected_topic
        request.session.pop('current_problem', None)
        request.session.pop('current_expected_output', None)

    if request.method == 'POST' and 'new_problem' in request.POST:
        request.session.pop('current_problem', None)
        request.session.pop('current_expected_output', None)

    if 'current_problem' not in request.session or 'current_expected_output' not in request.session:
        ai_problem, expected_output = generate_problem_with_solution(selected_topic)
        request.session['current_problem'] = ai_problem
        request.session['current_expected_output'] = expected_output
    else:
        ai_problem = request.session['current_problem']
        expected_output = request.session['current_expected_output']

    if request.method == 'POST' and 'code' in request.POST:
        user_code = request.POST.get('code', '')
        if user_code:
            is_correct, user_output = check_user_code(user_code, expected_output)

            if 'run_code' in request.POST:
                result = f"Output:\n{user_output if user_output else 'No output'}"

            elif 'submit_code' in request.POST:
                fast_mode = (os.getenv("SR_FAST_MODE") == "1")

                if is_correct:
                    result = f"Correct! Your output:\n{user_output}"

                    sr_map[selected_topic] = sm2_update_state(sr_map[selected_topic], grade=5, fast_mode=fast_mode)
                    request.session["sm2_sr"] = sr_map

                    request.session.pop('current_problem', None)
                    request.session.pop('current_expected_output', None)
                else:
                    result = f"Not quite right. Your output:\n{user_output if user_output else 'No output'}"

                    sr_map[selected_topic] = sm2_update_state(sr_map[selected_topic], grade=1, fast_mode=fast_mode)
                    request.session["sm2_sr"] = sr_map

                    evaluation_feedback = evaluate_code_quality(user_code, request.session['current_problem'])

    return render(request, 'coding_demo.html', {
        'result': result,
        'user_code': user_code,
        'ai_problem': ai_problem,
        'topics': TOPICS,
        'selected_topic': selected_topic,
        'recommended_topic': recommended_topic,
        'evaluation_feedback': evaluation_feedback,
        'sr_map': sr_map
})

def recommend_problem(request):
    weak_area = request.GET.get('weakness', 'loops')
    return JsonResponse({
        'weakness': weak_area,
        'recommended_topic': weak_area,
        'message': f'Try practicing {weak_area} problems!'
    })
