from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render

from ai_demo.models import UserNotebook


@login_required
def save_notebook(request):
    if request.method == "POST":
        content = request.POST.get("content", "")

        notebook, created = UserNotebook.objects.get_or_create(
            user=request.user,
            defaults={"content": content},
        )

        if not created:
            notebook.content = content
            notebook.save()

        return JsonResponse({
            "success": True,
            "message": "Notebook saved",
        })

    return JsonResponse({"success": False, "error": "POST only"}, status=400)


@login_required
def notebook_page(request):
    notebook, _ = UserNotebook.objects.get_or_create(
        user=request.user,
        defaults={"content": ""},
    )
    return render(request, "notebook.html", {"notebook": notebook})