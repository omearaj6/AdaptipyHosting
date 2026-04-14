from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from ai_demo.models import TopicProficiency, UserLearningProfile, UserNotebook
from .proficiencies import ensure_proficiency_rows, apply_decay_if_needed, update_proficiency, choose_next_topic, get_proficiencies
from ai_demo.models import ALL_TOPICS
from ai_demo.utils.ruff_linter import get_ruff_feedback
from ai_demo.services.runner_service import check_user_code
from ai_demo.services.ai_service import generate_problem_with_solution
from ai_demo.utils.codestral_client import codestral_analyse

TOPICS = ALL_TOPICS



@login_required
def save_theme(request):
    """Save user's editor theme preference"""
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        theme = request.POST.get('theme', '')
        if theme in ['vs-dark', 'vs']:
            profile, created = UserLearningProfile.objects.get_or_create(user=request.user)
            profile.editor_theme = theme
            profile.save()
            return JsonResponse({'success': True, 'theme': theme})
    return JsonResponse({'success': False}, status=400)


def reset_user_progress(user, session):
    TopicProficiency.objects.filter(user=user).update(
        proficiency=0.0,
        last_practiced_at=None,
    )
    UserLearningProfile.objects.filter(user=user).update(
        last_topic="",
        last_decay_applied_at=timezone.now(),
    )

    session.pop("current_problem_json", None)
    session.pop("show_explanation", None)
    session.pop("active_topic", None)
    session.pop("current_problem_awarded", None)





def get_or_create_user_notebook(user):
    return UserNotebook.objects.get_or_create(
        user=user,
        defaults={
            'content': 'Welcome to your Python notebook!\n\nWrite notes, code snippets, or anything you want to remember here.\n\n- Notes are saved automatically when you click away.\n- Use this space for anything helpful!'
        }
    )

def get_user_theme(user):
    if hasattr(user, "learning_profile"):
        return user.learning_profile.editor_theme
    return "vs-dark"

def reset_current_problem(session):
    session.pop("current_problem_json", None)
    session.pop("show_explanation", None)
    session.pop("active_topic", None)
    session.pop("current_problem_awarded", None)



def get_active_topic(request, profs):
    active_topic = request.session.get("active_topic")
    if not active_topic:
        active_topic = choose_next_topic(request.user, profs)
        request.session["active_topic"] = active_topic
    return active_topic


def get_or_create_problem(session, topic, profs):
    if "current_problem_json" not in session:
        problem_json = generate_problem_with_solution(topic, profs)
        session["current_problem_json"] = problem_json
        session["current_problem_awarded"] = False
    else:
        problem_json = session["current_problem_json"]

    return problem_json



def handle_explanation_request(request):
    if request.method == "POST" and "i_dont_understand" in request.POST:
        request.session["show_explanation"] = True
    return bool(request.session.get("show_explanation", False))


def get_chart_data(user):
    profs = get_proficiencies(user)
    chart_labels = ALL_TOPICS
    chart_values = [float(profs.get(topic, 0.0)) for topic in chart_labels]
    return chart_labels, chart_values


@login_required
def coding_demo(request):
    ensure_proficiency_rows(request.user)
    days_decayed = apply_decay_if_needed(request.user)
    profs = get_proficiencies(request.user)


    user_theme = get_user_theme(request.user)

    ruff_feedback = None

    notebook, created = get_or_create_user_notebook(request.user)

    if request.method == "POST" and "reset_progress" in request.POST:
        reset_user_progress(request.user, request.session)


    result = None
    result_type = None
    user_code = ""
    evaluation_feedback = None





    if request.method == "POST" and "new_problem" in request.POST:
        reset_current_problem(request.session)

    active_topic = get_active_topic(request, profs)

    selected_topic = active_topic

    problem_json = get_or_create_problem(request.session, selected_topic, profs)

    ai_problem = problem_json.get("problem", "")
    expected_output = problem_json.get("expected_output", "")
    lesson = problem_json.get("lesson", "")
    explanation = problem_json.get("explanation", "")


    show_explanation = handle_explanation_request(request)

    if request.method == "POST" and "code" in request.POST:
        user_code = request.POST.get("code", "")
        _, output, stderr = check_user_code(user_code, expected_output)

        if "run_code" in request.POST:
            result = f"\n{output}"
            result_type = "run"

        elif "submit_code" in request.POST:
            ruff_feedback = get_ruff_feedback(user_code)

            analysis = codestral_analyse(
                problem=ai_problem,
                lesson=lesson,
                expected_output=expected_output,
                code=user_code,
                stdout=output,
                stderr=stderr,
                ruff_feedback=ruff_feedback,
            )

            ai_correct = analysis.get("correct", False)
            delta = float(analysis.get("delta", -0.5))
            evaluation_feedback = analysis.get("feedback", "")

            already_awarded = request.session.get("current_problem_awarded", False)

            if ai_correct:
                if not already_awarded:
                    update_proficiency(request.user, topic=selected_topic, delta=1.0)
                    request.session["current_problem_awarded"] = True
                    result = "Correct!"
                else:
                    result = "Correct! Proficiency already awarded."
                result_type = "success"
            else:
                update_proficiency(request.user, topic=selected_topic, delta=delta)
                result = "Incorrect"
                result_type = "error"

    proficiency_debug = (
        TopicProficiency.objects
        .filter(user=request.user)
        .order_by("topic")
    )

    chart_labels, chart_values = get_chart_data(request.user)


    return render(request, "coding_demo.html", {
        "result": result,
        "user_code": user_code,
        "ai_problem": ai_problem,
        "topics": TOPICS,
        "selected_topic": selected_topic,
        "evaluation_feedback": evaluation_feedback,
        "days_decayed": days_decayed,
        "proficiency_debug": proficiency_debug,
        "lesson": lesson,
        "explanation": explanation,
        "show_explanation": show_explanation,
        "expected_output": expected_output,
        "notebook_content": notebook.content,
        "current_problem_awarded": request.session.get("current_problem_awarded", False),
        "result_type": result_type,
        "chart_labels": chart_labels,
        "chart_values": chart_values,
        "user_theme": user_theme,
    })




def home(request):
    return render(request, "home.html")

