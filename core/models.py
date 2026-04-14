import uuid
from django.db import models


class Organization(models.Model):
    ORGANIZATION_TYPES = [
        ("insurer", "Страховая компания"),
        ("sto", "СТО"),
    ]

    CRM_SYNC_STATUSES = [
        ("not_synced", "Не синхронизировано"),
        ("pending", "Ожидает"),
        ("synced", "Синхронизировано"),
        ("failed", "Ошибка"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    short_name = models.CharField(max_length=50, blank=True, null=True)
    type = models.CharField(max_length=20, choices=ORGANIZATION_TYPES)
    tax_id = models.CharField(max_length=20, blank=True, null=True)
    legal_address = models.CharField(max_length=500, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    rating = models.DecimalField(max_digits=2, decimal_places=1, blank=True, null=True)
    is_active = models.BooleanField(default=True)

    crm_external_id = models.CharField(max_length=100, blank=True, null=True)
    crm_sync_status = models.CharField(max_length=20, choices=CRM_SYNC_STATUSES, default="not_synced")
    crm_payload = models.JSONField(blank=True, null=True)

    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        db_table = "organizations"
        managed = False
        verbose_name = "Организация"
        verbose_name_plural = "Организации"

    def __str__(self):
        return self.short_name or self.name


class AppUser(models.Model):
    USER_ROLES = [
        ("insurer_manager", "Менеджер страховой"),
        ("sto_admin", "Администратор СТО"),
        ("mechanic", "Механик"),
        ("system_admin", "Системный администратор"),
    ]

    CRM_SYNC_STATUSES = [
        ("not_synced", "Не синхронизировано"),
        ("pending", "Ожидает"),
        ("synced", "Синхронизировано"),
        ("failed", "Ошибка"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    password_hash = models.CharField(max_length=255)
    full_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, blank=True, null=True)
    role = models.CharField(max_length=30, choices=USER_ROLES)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        db_column="organization_id",
        related_name="users",
    )
    avatar_url = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    last_login_at = models.DateTimeField(blank=True, null=True)

    crm_external_id = models.CharField(max_length=100, blank=True, null=True)
    crm_sync_status = models.CharField(max_length=20, choices=CRM_SYNC_STATUSES, default="not_synced")
    crm_payload = models.JSONField(blank=True, null=True)

    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        db_table = "app_users"
        managed = False
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"

    def __str__(self):
        return self.full_name


class RepairOrder(models.Model):
    REPAIR_STATUSES = [
        ("created", "Создан"),
        ("defectoscopy", "Дефектовка"),
        ("in_progress", "В работе"),
        ("waiting_approval", "Ожидает согласования"),
        ("completed", "Завершён"),
        ("closed", "Закрыт"),
    ]

    PRIORITIES = [
        ("normal", "Обычный"),
        ("high", "Высокий"),
        ("emergency", "Срочный"),
    ]

    CRM_SYNC_STATUSES = [
        ("not_synced", "Не синхронизировано"),
        ("pending", "Ожидает"),
        ("synced", "Синхронизировано"),
        ("failed", "Ошибка"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    organization_sto = models.ForeignKey(
        Organization,
        on_delete=models.DO_NOTHING,
        db_column="organization_sto_id",
        related_name="sto_repair_orders",
    )
    organization_insurer = models.ForeignKey(
        Organization,
        on_delete=models.DO_NOTHING,
        db_column="organization_insurer_id",
        related_name="insurer_repair_orders",
    )
    assigned_mechanic_user = models.ForeignKey(
        AppUser,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        db_column="assigned_mechanic_user_id",
        related_name="assigned_repairs",
    )

    insurance_case_number = models.CharField(max_length=50)
    vin = models.CharField(max_length=17)
    customer_name = models.CharField(max_length=200, blank=True, null=True)
    customer_phone = models.CharField(max_length=20, blank=True, null=True)
    status = models.CharField(max_length=30, choices=REPAIR_STATUSES, default="created")
    priority = models.CharField(max_length=20, choices=PRIORITIES, default="normal")
    started_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    final_report_url = models.TextField(blank=True, null=True)

    crm_external_id = models.CharField(max_length=100, blank=True, null=True)
    crm_sync_status = models.CharField(max_length=20, choices=CRM_SYNC_STATUSES, default="not_synced")
    crm_payload = models.JSONField(blank=True, null=True)

    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        db_table = "repair_orders"
        managed = False
        verbose_name = "Ремонтная карта"
        verbose_name_plural = "Ремонтные карты"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.insurance_case_number} | {self.vin}"


class RepairCheckpoint(models.Model):
    CHECKPOINT_STATUSES = [
        ("pending", "Ожидает"),
        ("completed", "Выполнен"),
        ("skipped", "Пропущен"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    repair_order = models.ForeignKey(
        RepairOrder,
        on_delete=models.CASCADE,
        db_column="repair_order_id",
        related_name="checkpoints",
    )
    checkpoint_template_id = models.UUIDField(blank=True, null=True)
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=500, blank=True, null=True)
    order_index = models.IntegerField()
    status = models.CharField(max_length=20, choices=CHECKPOINT_STATUSES, default="pending")
    requires_photo = models.BooleanField(default=False)
    requires_qr_scan = models.BooleanField(default=False)
    completed_by_user = models.ForeignKey(
        AppUser,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        db_column="completed_by_user_id",
        related_name="completed_checkpoints",
    )
    completed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        db_table = "repair_checkpoints"
        managed = False
        verbose_name = "Этап ремонта"
        verbose_name_plural = "Этапы ремонта"
        ordering = ["order_index"]

    def __str__(self):
        return f"{self.order_index}. {self.name}"


class MediaAttachment(models.Model):
    FILE_TYPES = [
        ("photo", "Фото"),
        ("video", "Видео"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    repair_order = models.ForeignKey(
        RepairOrder,
        on_delete=models.CASCADE,
        db_column="repair_order_id",
        related_name="media_attachments",
    )
    checkpoint = models.ForeignKey(
        RepairCheckpoint,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        db_column="checkpoint_id",
        related_name="media_attachments",
    )
    uploaded_by_user = models.ForeignKey(
        AppUser,
        on_delete=models.DO_NOTHING,
        db_column="uploaded_by_user_id",
        related_name="uploaded_media",
    )
    file_url = models.TextField()
    file_type = models.CharField(max_length=10, choices=FILE_TYPES, default="photo")
    mime_type = models.CharField(max_length=50, blank=True, null=True)
    geotag_lat = models.DecimalField(max_digits=10, decimal_places=8, blank=True, null=True)
    geotag_lng = models.DecimalField(max_digits=11, decimal_places=8, blank=True, null=True)
    timestamp_utc = models.DateTimeField()
    hash_sha256 = models.CharField(max_length=64, blank=True, null=True)
    created_at = models.DateTimeField()

    class Meta:
        db_table = "media_attachments"
        managed = False
        verbose_name = "Медиафайл"
        verbose_name_plural = "Медиафайлы"

    def __str__(self):
        return self.file_url


class Part(models.Model):
    VERIFICATION_STATUSES = [
        ("pending", "Ожидает проверки"),
        ("verified", "Подтверждена"),
        ("suspicious", "Подозрительная"),
        ("rejected", "Отклонена"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    repair_order = models.ForeignKey(
        RepairOrder,
        on_delete=models.CASCADE,
        db_column="repair_order_id",
        related_name="parts",
    )
    checkpoint = models.ForeignKey(
        RepairCheckpoint,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        db_column="checkpoint_id",
        related_name="parts",
    )
    scanned_by_user = models.ForeignKey(
        AppUser,
        on_delete=models.DO_NOTHING,
        db_column="scanned_by_user_id",
        related_name="scanned_parts",
    )
    qr_code_value = models.CharField(max_length=255)
    part_number = models.CharField(max_length=100, blank=True, null=True)
    part_name = models.CharField(max_length=200, blank=True, null=True)
    is_original = models.BooleanField(default=False)
    verification_status = models.CharField(max_length=20, choices=VERIFICATION_STATUSES, default="pending")
    verification_comment = models.CharField(max_length=500, blank=True, null=True)
    scanned_at = models.DateTimeField()
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        db_table = "parts"
        managed = False
        verbose_name = "Запчасть"
        verbose_name_plural = "Запчасти"

    def __str__(self):
        return self.part_name or self.qr_code_value


class AdditionalWorkRequest(models.Model):
    REQUEST_STATUSES = [
        ("pending", "Ожидает согласования"),
        ("approved", "Одобрено"),
        ("rejected", "Отклонено"),
        ("cancelled", "Отменено"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    repair_order = models.ForeignKey(
        RepairOrder,
        on_delete=models.CASCADE,
        db_column="repair_order_id",
        related_name="additional_work_requests",
    )
    requested_by_user = models.ForeignKey(
        AppUser,
        on_delete=models.DO_NOTHING,
        db_column="requested_by_user_id",
        related_name="requested_additional_works",
    )
    reviewed_by_user = models.ForeignKey(
        AppUser,
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        db_column="reviewed_by_user_id",
        related_name="reviewed_additional_works",
    )
    title = models.CharField(max_length=200)
    description = models.CharField(max_length=2000)
    estimated_cost = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=REQUEST_STATUSES, default="pending")
    reviewer_comment = models.CharField(max_length=1000, blank=True, null=True)
    requested_at = models.DateTimeField()
    reviewed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        db_table = "additional_work_requests"
        managed = False
        verbose_name = "Запрос на доп. работы"
        verbose_name_plural = "Запросы на доп. работы"
        ordering = ["-requested_at"]

    def __str__(self):
        return self.title