from django.urls import path
from . import views

urlpatterns = [
    path("", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),

    path("mechanic/", views.mechanic_dashboard, name="mechanic_dashboard"),
    path("repair/<uuid:repair_id>/", views.repair_detail, name="repair_detail"),
    path("checkpoint/<uuid:checkpoint_id>/capture/", views.capture_step, name="capture_step"),
    path("repair/<uuid:repair_id>/additional-work/new/", views.additional_work_request_create, name="additional_work_request_create"),
    path("repair/<uuid:repair_id>/finish/", views.finish_repair, name="finish_repair"),

    path("insurer/", views.insurer_dashboard, name="insurer_dashboard"),
    path("insurer/repair/<uuid:repair_id>/", views.insurer_repair_detail, name="insurer_repair_detail"),
    path("insurer/additional-work/<uuid:work_id>/review/", views.review_additional_work, name="review_additional_work"),
]