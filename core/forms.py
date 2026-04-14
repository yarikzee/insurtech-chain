from django import forms


class LoginForm(forms.Form):
    role = forms.ChoiceField(
        choices=[
            ("insurer", "Страховая"),
            ("sto", "СТО"),
            ("mechanic", "Механик"),
        ]
    )
    email = forms.EmailField(required=False)
    password = forms.CharField(required=False, widget=forms.PasswordInput)
    phone = forms.CharField(required=False)
    sms_code = forms.CharField(required=False)


class CapturePhotoForm(forms.Form):
    photo_1 = forms.ImageField(required=False)
    photo_2 = forms.ImageField(required=False)
    photo_3 = forms.ImageField(required=False)
    geotag_enabled = forms.BooleanField(required=False, initial=True)


class ScanPartForm(forms.Form):
    qr_code_value = forms.CharField(label="Артикул / QR-код", max_length=255)
    part_name = forms.CharField(label="Название детали", max_length=200, required=False)
    part_number = forms.CharField(label="Номер детали", max_length=100, required=False)


class AdditionalWorkRequestForm(forms.Form):
    title = forms.CharField(label="Название работ", max_length=200)
    description = forms.CharField(
        label="Комментарий",
        widget=forms.Textarea(attrs={"rows": 5}),
        max_length=2000,
    )
    estimated_cost = forms.DecimalField(label="Стоимость", min_value=0, decimal_places=2, max_digits=12)

    photo_1 = forms.ImageField(required=False)
    photo_2 = forms.ImageField(required=False)
    photo_3 = forms.ImageField(required=False)


class ReviewAdditionalWorkForm(forms.Form):
    reviewer_comment = forms.CharField(
        label="Комментарий",
        required=False,
        widget=forms.Textarea(attrs={"rows": 4}),
        max_length=1000,
    )