import os
import uuid
from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.core.files.storage import default_storage
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.db import connection

def get_additional_work_media_map(work_ids):
    if not work_ids:
        return {}

    media_map = {work_id: [] for work_id in work_ids}

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT awrm.request_id, ma.id, ma.file_url
            FROM additional_work_request_media awrm
            JOIN media_attachments ma ON ma.id = awrm.media_attachment_id
            WHERE awrm.request_id = ANY(%s)
            """,
            [work_ids],
        )
        rows = cursor.fetchall()

    for request_id, media_id, file_url in rows:
        media_map.setdefault(request_id, []).append({
            "id": media_id,
            "file_url": file_url,
        })

    return media_map

from .forms import (
    AdditionalWorkRequestForm,
    CapturePhotoForm,
    LoginForm,
    ReviewAdditionalWorkForm,
    ScanPartForm,
)
from .models import (
    AdditionalWorkRequest,
    AppUser,
    MediaAttachment,
    Part,
    RepairCheckpoint,
    RepairOrder,
)


def get_current_user(request):
    user_id = request.session.get("app_user_id")
    if not user_id:
        return None
    try:
        return AppUser.objects.select_related("organization").get(id=user_id, is_active=True)
    except AppUser.DoesNotExist:
        return None


def require_roles(*allowed_roles):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            user = get_current_user(request)
            if not user:
                return redirect("login")
            if user.role not in allowed_roles:
                return HttpResponseForbidden("Нет доступа")
            request.app_user = user
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def save_uploaded_file(uploaded_file, subdir="uploads"):
    filename = f"{subdir}/{uuid.uuid4()}_{uploaded_file.name}"
    saved_name = default_storage.save(filename, uploaded_file)
    return f"{settings.MEDIA_URL}{saved_name}"


def create_media_attachment(repair, checkpoint, user, uploaded_file):
    file_url = save_uploaded_file(uploaded_file, "repair_media")
    return MediaAttachment.objects.create(
        repair_order=repair,
        checkpoint=checkpoint,
        uploaded_by_user=user,
        file_url=file_url,
        file_type="photo",
        mime_type=getattr(uploaded_file, "content_type", "image/jpeg"),
        timestamp_utc=timezone.now(),
        created_at=timezone.now(),
    )


def get_repair_progress(repair):
    checkpoints = list(repair.checkpoints.all())
    total_steps = len(checkpoints)
    completed_steps = sum(1 for item in checkpoints if item.status == "completed")
    progress = int((completed_steps / total_steps) * 100) if total_steps else 0
    return total_steps, completed_steps, progress


def all_required_steps_completed(repair):
    required_steps = repair.checkpoints.filter(Q(requires_photo=True) | Q(requires_qr_scan=True))
    return not required_steps.exclude(status="completed").exists()


def login_view(request):
    current_user = get_current_user(request)
    if current_user:
        if current_user.role == "insurer_manager":
            return redirect("insurer_dashboard")
        return redirect("mechanic_dashboard")

    form = LoginForm()

    if request.method == "POST":
        role = (request.POST.get("role") or "").strip()

        if role == "insurer":
            email = (request.POST.get("insurer_email") or "").strip().lower()
            password = (request.POST.get("insurer_password") or "").strip()

            if not email or not password:
                messages.error(request, "Заполни логин и пароль.")
                return render(request, "core/login.html", {"form": form})

            user = (
                AppUser.objects.filter(
                    email__iexact=email,
                    role="insurer_manager",
                    is_active=True,
                )
                .select_related("organization")
                .first()
            )

            if not user:
                messages.error(request, "Пользователь страховой не найден.")
                return render(request, "core/login.html", {"form": form})

        elif role == "sto":
            email = (request.POST.get("sto_email") or "").strip().lower()
            password = (request.POST.get("sto_password") or "").strip()

            if not email or not password:
                messages.error(request, "Заполни логин и пароль.")
                return render(request, "core/login.html", {"form": form})

            user = (
                AppUser.objects.filter(
                    email__iexact=email,
                    role="sto_admin",
                    is_active=True,
                )
                .select_related("organization")
                .first()
            )

            if not user:
                messages.error(request, "Пользователь СТО не найден.")
                return render(request, "core/login.html", {"form": form})

        elif role == "mechanic":
            phone = (request.POST.get("phone") or "").strip()
            sms_code = (request.POST.get("sms_code") or "").strip()

            if not phone or not sms_code:
                messages.error(request, "Введи номер телефона и SMS-код.")
                return render(request, "core/login.html", {"form": form})

            user = (
                AppUser.objects.filter(
                    phone=phone,
                    role="mechanic",
                    is_active=True,
                )
                .select_related("organization")
                .first()
            )

            if not user:
                messages.error(request, "Механик не найден.")
                return render(request, "core/login.html", {"form": form})

        else:
            messages.error(request, "Выбери роль для входа.")
            return render(request, "core/login.html", {"form": form})

        request.session["app_user_id"] = str(user.id)
        request.session["app_user_role"] = user.role
        request.session["app_user_name"] = user.full_name
        request.session["app_org_id"] = str(user.organization_id) if user.organization_id else ""

        user.last_login_at = timezone.now()
        user.save(update_fields=["last_login_at"])

        if user.role == "insurer_manager":
            return redirect("insurer_dashboard")
        return redirect("mechanic_dashboard")

    return render(request, "core/login.html", {"form": form})


def logout_view(request):
    request.session.flush()
    return redirect("login")


@require_roles("mechanic", "sto_admin", "system_admin")
def mechanic_dashboard(request):
    user = request.app_user

    repairs = (
        RepairOrder.objects
        .select_related("organization_sto", "assigned_mechanic_user")
        .prefetch_related("checkpoints")
        .filter(assigned_mechanic_user=user)
        .exclude(status="closed")
        .order_by("-created_at")
    )

    repair_cards = []
    for repair in repairs:
        total_steps, completed_steps, progress_percent = get_repair_progress(repair)
        vin_short = repair.vin[-4:] if repair.vin else "----"

        repair_cards.append({
            "id": repair.id,
            "car_title": repair.insurance_case_number or "Дело без номера",
            "vin_short": vin_short,
            "status": repair.get_status_display(),
            "progress_percent": progress_percent,
            "completed_steps": completed_steps,
            "total_steps": total_steps,
            "steps_range": range(total_steps if total_steps > 0 else 6),
            "is_completed": repair.status == "completed",
        })

    mechanic_name = user.full_name.split()[0] if user.full_name else "Механик"

    return render(
        request,
        "core/mechanic_dashboard.html",
        {
            "mechanic_name": mechanic_name,
            "repair_cards": repair_cards,
        },
    )


@require_roles("mechanic", "sto_admin", "system_admin")
def repair_detail(request, repair_id):
    user = request.app_user
    repair = get_object_or_404(
        RepairOrder.objects.select_related(
            "organization_sto",
            "organization_insurer",
            "assigned_mechanic_user"
        ).prefetch_related(
            "checkpoints__media_attachments",
            "checkpoints__parts",
            "additional_work_requests",
        ),
        id=repair_id,
        assigned_mechanic_user=user,
    )

    checkpoint_cards = []
    checkpoints = repair.checkpoints.all().order_by("order_index")

    for checkpoint in checkpoints:
        media_items = list(checkpoint.media_attachments.all())
        parts = list(checkpoint.parts.all()) if hasattr(checkpoint, "parts") else []

        checkpoint_cards.append({
            "id": checkpoint.id,
            "name": checkpoint.name,
            "status": checkpoint.get_status_display(),
            "is_completed": checkpoint.status == "completed",
            "requires_qr_scan": checkpoint.requires_qr_scan,
            "media_items": media_items,
            "parts": parts,
        })

    additional_requests = list(repair.additional_work_requests.all())
    work_media_map = get_additional_work_media_map([work.id for work in additional_requests])

    for work in additional_requests:
        work.media_items = work_media_map.get(work.id, [])

    can_finish = all_required_steps_completed(repair)

    return render(
        request,
        "core/repair_detail.html",
        {
            "repair": repair,
            "checkpoint_cards": checkpoint_cards,
            "additional_requests": additional_requests,
            "all_required_completed": can_finish,
        },
    )


@require_roles("mechanic", "sto_admin", "system_admin")
def capture_step(request, checkpoint_id):
    user = request.app_user
    checkpoint = get_object_or_404(
        RepairCheckpoint.objects.select_related("repair_order", "repair_order__assigned_mechanic_user"),
        id=checkpoint_id,
        repair_order__assigned_mechanic_user=user,
    )
    repair = checkpoint.repair_order

    if checkpoint.requires_qr_scan:
        form = ScanPartForm(request.POST or None)
        mode = "scan"

        if request.method == "POST" and form.is_valid():
            Part.objects.create(
                repair_order=repair,
                checkpoint=checkpoint,
                scanned_by_user=user,
                qr_code_value=form.cleaned_data["qr_code_value"],
                part_number=form.cleaned_data.get("part_number"),
                part_name=form.cleaned_data.get("part_name"),
                is_original=False,
                verification_status="pending",
                scanned_at=timezone.now(),
                created_at=timezone.now(),
                updated_at=timezone.now(),
            )
            checkpoint.status = "completed"
            checkpoint.completed_by_user = user
            checkpoint.completed_at = timezone.now()
            checkpoint.updated_at = timezone.now()
            checkpoint.save(update_fields=["status", "completed_by_user", "completed_at", "updated_at"])

            if repair.status == "created":
                repair.status = "in_progress"
                repair.updated_at = timezone.now()
                repair.save(update_fields=["status", "updated_at"])

            messages.success(request, "Запчасть отсканирована, этап выполнен.")
            return redirect("repair_detail", repair_id=repair.id)

    else:
        form = CapturePhotoForm(request.POST or None, request.FILES or None)
        mode = "photo"

        if request.method == "POST" and form.is_valid():
            files = [
                form.cleaned_data.get("photo_1"),
                form.cleaned_data.get("photo_2"),
                form.cleaned_data.get("photo_3"),
            ]
            files = [item for item in files if item]

            if not files:
                messages.error(request, "Загрузи хотя бы одно фото.")
            else:
                for uploaded_file in files:
                    create_media_attachment(repair, checkpoint, user, uploaded_file)

                checkpoint.status = "completed"
                checkpoint.completed_by_user = user
                checkpoint.completed_at = timezone.now()
                checkpoint.updated_at = timezone.now()
                checkpoint.save(update_fields=["status", "completed_by_user", "completed_at", "updated_at"])

                if repair.status == "created":
                    repair.status = "in_progress"
                    repair.updated_at = timezone.now()
                    repair.save(update_fields=["status", "updated_at"])

                messages.success(request, "Фото добавлены, этап выполнен.")
                return redirect("repair_detail", repair_id=repair.id)

    return render(
        request,
        "core/capture_step.html",
        {
            "repair": repair,
            "checkpoint": checkpoint,
            "form": form,
            "mode": mode,
        },
    )


@require_roles("mechanic", "sto_admin", "system_admin")
def additional_work_request_create(request, repair_id):
    user = request.app_user
    repair = get_object_or_404(
        RepairOrder.objects.select_related("assigned_mechanic_user", "organization_insurer"),
        id=repair_id,
        assigned_mechanic_user=user,
    )

    form = AdditionalWorkRequestForm(request.POST or None, request.FILES or None)

    if request.method == "POST" and form.is_valid():
        work = AdditionalWorkRequest.objects.create(
            repair_order=repair,
            requested_by_user=user,
            title=form.cleaned_data["title"],
            description=form.cleaned_data["description"],
            estimated_cost=form.cleaned_data["estimated_cost"],
            status="pending",
            requested_at=timezone.now(),
            created_at=timezone.now(),
            updated_at=timezone.now(),
        )

        files = [
            form.cleaned_data.get("photo_1"),
            form.cleaned_data.get("photo_2"),
            form.cleaned_data.get("photo_3"),
        ]
        files = [item for item in files if item]

        for uploaded_file in files:
            media = create_media_attachment(repair, None, user, uploaded_file)

            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO additional_work_request_media (request_id, media_attachment_id)
                    VALUES (%s, %s)
                    """,
                    [str(work.id), str(media.id)],
                )

        repair.status = "waiting_approval"
        repair.updated_at = timezone.now()
        repair.save(update_fields=["status", "updated_at"])

        messages.success(request, "Запрос на дополнительные работы отправлен.")
        return redirect("repair_detail", repair_id=repair.id)

    return render(
        request,
        "core/additional_work_request.html",
        {
            "repair": repair,
            "form": form,
        },
    )


@require_roles("mechanic", "sto_admin", "system_admin")
def finish_repair(request, repair_id):
    if request.method != "POST":
        return redirect("repair_detail", repair_id=repair_id)

    user = request.app_user
    repair = get_object_or_404(
        RepairOrder.objects.select_related("assigned_mechanic_user"),
        id=repair_id,
        assigned_mechanic_user=user,
    )

    if not all_required_steps_completed(repair):
        messages.error(request, "Нельзя завершить ремонт: не все обязательные этапы выполнены.")
        return redirect("repair_detail", repair_id=repair.id)

    repair.status = "completed"
    repair.completed_at = timezone.now()
    repair.updated_at = timezone.now()
    repair.save(update_fields=["status", "completed_at", "updated_at"])

    messages.success(request, "Ремонт завершён.")
    return redirect("mechanic_dashboard")


@require_roles("insurer_manager", "system_admin")
def insurer_dashboard(request):
    user = request.app_user

    repairs = (
        RepairOrder.objects
        .select_related("organization_sto", "organization_insurer")
        .prefetch_related("checkpoints")
        .filter(organization_insurer=user.organization)
        .order_by("-created_at")
    )

    search_query = (request.GET.get("q") or "").strip()
    status_filter = (request.GET.get("status") or "").strip()
    sto_filter = (request.GET.get("sto") or "").strip()

    if search_query:
        repairs = repairs.filter(
            Q(vin__icontains=search_query) |
            Q(insurance_case_number__icontains=search_query)
        )

    if status_filter:
        repairs = repairs.filter(status=status_filter)

    if sto_filter:
        repairs = repairs.filter(organization_sto_id=sto_filter)

    repair_cards = []
    for repair in repairs:
        _, _, progress = get_repair_progress(repair)
        repair_cards.append({
            "id": repair.id,
            "sto": repair.organization_sto,
            "vin": repair.vin,
            "status": repair.get_status_display(),
            "start_date": repair.created_at,
            "progress": progress,
        })

    stos = (
        RepairOrder.objects
        .filter(organization_insurer=user.organization)
        .values_list("organization_sto__id", "organization_sto__name")
        .distinct()
    )

    pending_requests_count = AdditionalWorkRequest.objects.filter(
        repair_order__organization_insurer=user.organization,
        status="pending",
    ).count()

    return render(
        request,
        "core/insurer_dashboard.html",
        {
            "repair_cards": repair_cards,
            "stos": stos,
            "pending_requests_count": pending_requests_count,
        },
    )


@require_roles("insurer_manager", "system_admin")
def insurer_repair_detail(request, repair_id):
    user = request.app_user
    repair = get_object_or_404(
        RepairOrder.objects.select_related(
            "organization_sto",
            "organization_insurer",
            "assigned_mechanic_user"
        ).prefetch_related(
            "checkpoints__media_attachments",
            "additional_work_requests",
        ),
        id=repair_id,
        organization_insurer=user.organization,
    )

    active_tab = request.GET.get("tab", "steps")
    _, _, progress = get_repair_progress(repair)

    checkpoint_cards = []
    for checkpoint in repair.checkpoints.all().order_by("order_index"):
        media_items = list(checkpoint.media_attachments.all())
        checkpoint_cards.append({
            "name": checkpoint.name,
            "status": checkpoint.get_status_display(),
            "is_completed": checkpoint.status == "completed",
            "media_items": media_items,
            "completed_at": checkpoint.completed_at,
        })

    additional_requests = list(repair.additional_work_requests.all())
    work_media_map = get_additional_work_media_map([work.id for work in additional_requests])

    for work in additional_requests:
        work.media_items = work_media_map.get(work.id, [])
    review_form = ReviewAdditionalWorkForm()

    return render(
        request,
        "core/insurer_repair_detail.html",
        {
            "repair": repair,
            "checkpoint_cards": checkpoint_cards,
            "additional_requests": additional_requests,
            "review_form": review_form,
            "active_tab": active_tab,
            "rating_percent": progress,
        },
    )


@require_roles("insurer_manager", "system_admin")
def review_additional_work(request, work_id):
    if request.method != "POST":
        return redirect("insurer_dashboard")

    user = request.app_user
    work = get_object_or_404(
        AdditionalWorkRequest.objects.select_related("repair_order", "repair_order__organization_insurer"),
        id=work_id,
        repair_order__organization_insurer=user.organization,
    )

    action = request.POST.get("action")
    form = ReviewAdditionalWorkForm(request.POST)

    if not form.is_valid():
        messages.error(request, "Ошибка в комментарии.")
        return redirect(f"{redirect('insurer_repair_detail', repair_id=work.repair_order.id).url}?tab=works")

    work.reviewed_by_user = user
    work.reviewed_at = timezone.now()
    work.reviewer_comment = form.cleaned_data.get("reviewer_comment")

    if action == "approve":
        work.status = "approved"
        work.repair_order.status = "in_progress"
        work.repair_order.updated_at = timezone.now()
        work.repair_order.save(update_fields=["status", "updated_at"])
        messages.success(request, "Дополнительные работы одобрены.")
    elif action == "reject":
        work.status = "rejected"
        work.repair_order.status = "in_progress"
        work.repair_order.updated_at = timezone.now()
        work.repair_order.save(update_fields=["status", "updated_at"])
        messages.success(request, "Дополнительные работы отклонены.")
    else:
        messages.error(request, "Неизвестное действие.")
        return redirect(f"{redirect('insurer_repair_detail', repair_id=work.repair_order.id).url}?tab=works")

    work.updated_at = timezone.now()
    work.save(update_fields=["reviewed_by_user", "reviewed_at", "reviewer_comment", "status", "updated_at"])

    return redirect(f"{redirect('insurer_repair_detail', repair_id=work.repair_order.id).url}?tab=works")