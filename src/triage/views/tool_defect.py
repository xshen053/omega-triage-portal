import json
import os
import uuid
from base64 import b64encode
from typing import Any, List

from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
    HttpResponseNotFound,
    HttpResponseRedirect,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, render
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from packageurl import PackageURL

from triage.models import (
    Case,
    Finding,
    Note,
    Project,
    ProjectVersion,
    Tool,
    ToolDefect,
    WorkItemState,
)
from triage.util.azure_blob_storage import ToolshedBlobStorageAccessor
from triage.util.finding_importers.sarif_importer import SARIFImporter
from triage.util.search_parser import parse_query_to_Q
from triage.util.source_viewer import path_to_graph
from triage.util.source_viewer.viewer import SourceViewer


def show_tool_defects(request: HttpRequest) -> HttpResponse:
    """Shows tool_defectsbased on a query.

    Params:
        q: query to search for, or all findings if not provided
    """
    query = request.GET.get("q", "")
    c = {
        "query": query,
        "tool_defects": ToolDefect.objects.all(),
        "tool_defect_states": WorkItemState.choices,
    }
    return render(request, "triage/tool_defect_show.html", c)


@never_cache
def show_tool_defect(request: HttpRequest, tool_defect_uuid: uuid.UUID) -> HttpResponse:
    """Shows a tool defect."""
    tool_defect = get_object_or_404(ToolDefect, uuid=tool_defect_uuid)
    context = {
        "tool_defect": tool_defect,
        "tools": Tool.objects.all(),
        "tool_defect_states": WorkItemState.choices,
    }
    return render(request, "triage/tool_defect_new.html", context)


def show_add_tool_defect(request: HttpRequest) -> HttpResponse:
    """Shows the add tool defect form."""
    finding_uuid = request.GET.get("finding_uuid")
    finding = Finding.objects.filter(uuid=finding_uuid).first()
    c = {
        "tools": Tool.objects.all(),
        "tool_defect_states": WorkItemState.choices,
        "finding": finding,
    }
    return render(request, "triage/tool_defect_new.html", c)


@require_http_methods(["POST"])
def save_tool_defect(request: HttpRequest) -> HttpResponse:
    """Saves a tool defect."""

    action = request.POST.get("action")
    if action == "create":
        tool_defect = ToolDefect()
    else:
        tool_defect = get_object_or_404(ToolDefect, uuid=request.POST["uuid"])

    tool_defect.tool = get_object_or_404(Tool, uuid=request.POST["tool"])
    tool_defect.title = request.POST["title"]
    tool_defect.state = request.POST["state"]
    note_content = request.POST.get("note_content")
    tool_defect.save()

    if note_content and note_content.strip():
        note = Note(content=note_content, created_by=request.user, updated_by=request.user)
        note.save()
        tool_defect.notes.add(note)
        tool_defect.save()

    return HttpResponseRedirect(f"/tool_defect/{tool_defect.uuid}")
