import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


BITRIX_FIELDS = {
    "vin": "UF_CRM_1777816676864",
    "insurance_case_number": "UF_CRM_1777816720706",
    "sto": "UF_CRM_1777816733252",
    "mechanic": "UF_CRM_1777817086598",
    "additional_work": "UF_CRM_1777817166257",
    "priority": "UF_CRM_1777817192933",
    "comment": "UF_CRM_1777817217235",
    "started_at": "UF_CRM_1777817618812",
    "completed_at": "UF_CRM_1777820443443",
}


BITRIX_STAGE_MAP = {
    "created": "NEW",
    "defectoscopy": "PREPARATION",
    "in_progress": "PREPARATION",
    "waiting_approval": "UC_JHORWS",
    "completed": "WON",
    "closed": "LOSE",
}


BITRIX_PRIORITY_MAP = {
    "normal": "53",
    "high": "55",
    "emergency": "57",
}


BITRIX_ADDITIONAL_WORK_MAP = {
    "none": "45",
    "pending": "47",
    "approved": "49",
    "rejected": "51",
}


def _get_webhook_url():
    webhook_url = getattr(settings, "BITRIX24_WEBHOOK_URL", "").strip()
    if not webhook_url:
        raise RuntimeError("BITRIX24_WEBHOOK_URL is not configured")

    return webhook_url.rstrip("/") + "/"


def _call_bitrix(method, payload):
    url = _get_webhook_url() + method + ".json"

    data = urllib.parse.urlencode(payload, doseq=True).encode("utf-8")

    request = urllib.request.Request(
        url=url,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            response_data = response.read().decode("utf-8")
            result = json.loads(response_data)
    except urllib.error.HTTPError as error:
        error_body = error.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Bitrix24 HTTP error: {error.code}; {error_body}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"Bitrix24 connection error: {error}") from error

    if "error" in result:
        raise RuntimeError(f"Bitrix24 API error: {result.get('error_description') or result.get('error')}")

    return result.get("result")


def _format_date(value):
    if not value:
        return ""

    local_value = timezone.localtime(value)
    return local_value.strftime("%Y-%m-%d")


def _get_additional_work_status(repair):
    last_request = repair.additional_work_requests.order_by("-created_at").first()

    if not last_request:
        return "none"

    if last_request.status == "cancelled":
        return "none"

    return last_request.status


def _create_contact_for_repair(repair):
    full_name = repair.customer_name or "Клиент без имени"
    phone = repair.customer_phone or ""

    payload = {
        "fields[NAME]": full_name,
        "fields[PHONE][0][VALUE]": phone,
        "fields[PHONE][0][VALUE_TYPE]": "WORK",
    }

    return _call_bitrix("crm.contact.add", payload)


def sync_repair_to_bitrix(repair):
    """
    Создаёт или обновляет сделку Bitrix24 на основе repair_orders.
    ID сделки сохраняется в repair.crm_external_id.
    """

    repair.crm_sync_status = "pending"
    repair.crm_payload = {"started_at": timezone.now().isoformat()}
    repair.save(update_fields=["crm_sync_status", "crm_payload"])

    try:
        contact_id = None

        if not repair.crm_external_id:
            contact_id = _create_contact_for_repair(repair)

        additional_work_status = _get_additional_work_status(repair)

        fields = {
            "fields[TITLE]": f"{repair.insurance_case_number} — Ремонт автомобиля",
            "fields[STAGE_ID]": BITRIX_STAGE_MAP.get(repair.status, "NEW"),
            f"fields[{BITRIX_FIELDS['vin']}]": repair.vin,
            f"fields[{BITRIX_FIELDS['insurance_case_number']}]": repair.insurance_case_number,
            f"fields[{BITRIX_FIELDS['sto']}]": str(repair.organization_sto),
            f"fields[{BITRIX_FIELDS['mechanic']}]": (
                repair.assigned_mechanic_user.full_name
                if repair.assigned_mechanic_user
                else ""
            ),
            f"fields[{BITRIX_FIELDS['additional_work']}]": BITRIX_ADDITIONAL_WORK_MAP.get(additional_work_status, "45"),
            f"fields[{BITRIX_FIELDS['priority']}]": BITRIX_PRIORITY_MAP.get(repair.priority, "53"),
            f"fields[{BITRIX_FIELDS['comment']}]": _build_comment(repair, additional_work_status),
            f"fields[{BITRIX_FIELDS['started_at']}]": _format_date(repair.started_at),
            f"fields[{BITRIX_FIELDS['completed_at']}]": _format_date(repair.completed_at),
        }
        if contact_id:
            fields["fields[CONTACT_ID]"] = contact_id

        if repair.crm_external_id:
            _call_bitrix(
                "crm.deal.update",
                {
                    "id": repair.crm_external_id,
                    **fields,
                },
            )
            deal_id = repair.crm_external_id
        else:
            deal_id = _call_bitrix("crm.deal.add", fields)

        repair.crm_external_id = str(deal_id)
        repair.crm_sync_status = "synced"
        repair.crm_payload = {
            "deal_id": deal_id,
            "contact_id": contact_id,
            "synced_at": timezone.now().isoformat(),
        }
        repair.save(update_fields=["crm_external_id", "crm_sync_status", "crm_payload"])

        return deal_id

    except Exception as error:
        logger.exception("Bitrix24 sync failed for repair %s", repair.id)

        repair.crm_sync_status = "failed"
        repair.crm_payload = {
            "error": str(error),
            "failed_at": timezone.now().isoformat(),
        }
        repair.save(update_fields=["crm_sync_status", "crm_payload"])

        raise


def _build_comment(repair, additional_work_status):
    additional_work_labels = {
        "none": "Дополнительных работ нет.",
        "pending": "Есть запрос на согласование дополнительных работ.",
        "approved": "Дополнительные работы одобрены.",
        "rejected": "Дополнительные работы отклонены.",
    }

    return (
        f"Ремонт из MVP InsurTech Chain.\n"
        f"Статус ремонта: {repair.get_status_display()}.\n"
        f"Приоритет: {repair.get_priority_display()}.\n"
        f"{additional_work_labels.get(additional_work_status, '')}"
    )