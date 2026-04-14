document.addEventListener("DOMContentLoaded", function () {
    const tabs = document.querySelectorAll(".role-tab");
    const selectedRole = document.getElementById("selectedRole");
    const insurerFields = document.getElementById("insurerFields");
    const stoFields = document.getElementById("stoFields");
    const mechanicFields = document.getElementById("mechanicFields");
    const getCodeBtn = document.getElementById("getCodeBtn");
    const smsBlock = document.getElementById("smsBlock");

    if (tabs.length && selectedRole) {
        const hideAllSections = () => {
            insurerFields?.classList.add("hidden");
            stoFields?.classList.add("hidden");
            mechanicFields?.classList.add("hidden");
        };

        tabs.forEach(tab => {
            tab.addEventListener("click", function () {
                tabs.forEach(btn => btn.classList.remove("active"));
                this.classList.add("active");

                hideAllSections();
                selectedRole.value = this.dataset.role;

                if (smsBlock) {
                    smsBlock.classList.add("hidden");
                }

                if (this.dataset.role === "insurer") {
                    insurerFields?.classList.remove("hidden");
                } else if (this.dataset.role === "sto") {
                    stoFields?.classList.remove("hidden");
                } else {
                    mechanicFields?.classList.remove("hidden");
                }
            });
        });
    }

    if (getCodeBtn && smsBlock) {
        getCodeBtn.addEventListener("click", function () {
            smsBlock.classList.remove("hidden");
        });
    }

    const syncToast = document.getElementById("syncToast");
    if (syncToast) {
        syncToast.classList.remove("hidden");
        setTimeout(() => {
            syncToast.classList.add("hidden");
        }, 2000);
    }
    const previewBindings = [
        { inputId: "id_photo_1", previewId: "preview_1" },
        { inputId: "id_photo_2", previewId: "preview_2" },
        { inputId: "id_photo_3", previewId: "preview_3" },

        { inputId: "id_photo_1", previewId: "work_preview_1" },
        { inputId: "id_photo_2", previewId: "work_preview_2" },
        { inputId: "id_photo_3", previewId: "work_preview_3" },
    ];

    previewBindings.forEach(item => {
        const input = document.getElementById(item.inputId);
        const preview = document.getElementById(item.previewId);

        if (!input || !preview) return;

        input.addEventListener("change", function () {
            const file = this.files && this.files[0];
            if (!file) return;

            const reader = new FileReader();
            reader.onload = function (e) {
                preview.classList.add("has-image");
                preview.innerHTML = `<img src="${e.target.result}" alt="Загруженное изображение">`;
            };
            reader.readAsDataURL(file);
        });
    });
        document.querySelectorAll(".rating-stars").forEach(el => {
        const percent = parseFloat(el.dataset.rating) || 0;
        const stars = Math.round(percent / 20);

        let result = "";
        for (let i = 0; i < 5; i++) {
            result += i < stars ? "★" : "☆";
        }

        el.textContent = result;
    });
});