// Checkout pickup/delivery selector — Sprint 2, feature 2.2.
//
// Public hooks for the place-order task:
//   WDFulfillment.setSubtotal("14.97")   when the cart total changes
//   WDFulfillment.isValid()              before submitting (shows inline errors)
//   WDFulfillment.getPayload()           merge into the order request body
(function () {
    const root = document.getElementById("wd-fulfillment");
    if (!root) return;

    const $ = (sel) => document.querySelector(sel);
    const csrf = (document.querySelector("[name=csrfmiddlewaretoken]") || {}).value || "";
    const state = { options: null, subtotal: Number(root.dataset.subtotal || 0), errors: {}, timer: null };
    const money = (n) => "$" + Number(n).toFixed(2);

    const selectedType = () => (root.querySelector("input[name=fulfillment_type]:checked") || {}).value || "pickup";

    function getPayload() {
        const payload = { fulfillment_type: selectedType(), contact_phone: $("#wd-phone").value };
        if (payload.fulfillment_type === "delivery") {
            payload.address = {
                street: $("#wd-street").value,
                unit: $("#wd-unit").value,
                city: $("#wd-city").value,
                state: $("#wd-state").value,
                zip: $("#wd-zip").value,
                instructions: $("#wd-instructions").value,
            };
        }
        return payload;
    }

    // DRF errors can be nested (address.zip) or lists; flatten to one message per field.
    function flatten(errors) {
        const out = {};
        Object.entries(errors || {}).forEach(([key, val]) => {
            if (Array.isArray(val)) out[key] = String(val[0]);
            else if (val && typeof val === "object") Object.assign(out, flatten(val));
            else if (val) out[key] = String(val);
        });
        return out;
    }

    function showErrors(errors) {
        state.errors = errors;
        document.querySelectorAll("[data-error]").forEach((el) => {
            const msg = errors[el.dataset.error] || "";
            el.textContent = msg;
            const input = el.parentElement.querySelector("input:not([type=radio])");
            if (input) input.setAttribute("aria-invalid", msg ? "true" : "false");
        });
    }

    function renderTotals(t) {
        $("[data-total=subtotal]").textContent = money(t.subtotal);
        $("[data-total=delivery_fee]").textContent = Number(t.delivery_fee) === 0 ? "Free" : money(t.delivery_fee);
        $("[data-total=tax]").textContent = money(t.tax);
        $("[data-total=total_price]").textContent = money(t.total_price);
    }

    // Instant local preview; the server quote below is the source of truth.
    function preview() {
        const o = state.options;
        if (!o) return;
        const delivery = selectedType() === "delivery";
        const freeAt = o.free_delivery_minimum === null ? null : Number(o.free_delivery_minimum);
        const fee = delivery && !(freeAt !== null && state.subtotal >= freeAt) ? Number(o.delivery_fee) : 0;
        const tax = Math.round(state.subtotal * Number(o.tax_rate) * 100) / 100;
        renderTotals({ subtotal: state.subtotal, delivery_fee: fee, tax, total_price: state.subtotal + fee + tax });

        const hint = $("[data-free-hint]");
        const away = freeAt === null ? 0 : freeAt - state.subtotal;
        hint.hidden = !(delivery && away > 0);
        hint.textContent = "Add " + money(Math.max(away, 0)) + " more for free delivery.";

        const minutes = delivery ? o.delivery_minutes : o.pickup_minutes;
        $("[data-ready]").textContent = (delivery ? "Arrives" : "Ready") + " in about " + minutes + " min.";
    }

    function onTypeChange() {
        const delivery = selectedType() === "delivery";
        $("#wd-address").hidden = !delivery;
        $("[data-row=delivery]").hidden = !delivery;
        $("[data-phone-hint]").textContent = delivery
            ? "(required so the driver can reach you)"
            : "(optional, for a text when it's ready)";
        showErrors({});
        preview();
    }

    function requestQuote() {
        clearTimeout(state.timer);
        state.timer = setTimeout(async () => {
            if (selectedType() === "delivery" && !$("#wd-zip").value.trim()) return;
            try {
                const res = await fetch(root.dataset.quoteUrl, {
                    method: "POST",
                    headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
                    body: JSON.stringify({ ...getPayload(), subtotal: state.subtotal.toFixed(2) }),
                });
                const data = await res.json();
                if (res.ok) { showErrors({}); renderTotals(data); }
                else showErrors(flatten(data.errors));
            } catch (err) {
                console.error("Quote request failed", err);
            }
        }, 400);
    }

    function isValid() {
        const p = getPayload();
        const errors = {};
        if (p.fulfillment_type === "delivery") {
            const a = p.address;
            if (!a.street.trim()) errors.street = "Enter a street address.";
            if (!a.city.trim()) errors.city = "Enter a city.";
            if (!/^[A-Za-z]{2}$/.test(a.state.trim())) errors.state = "Enter a 2-letter state code.";
            if (!/^\d{5}(-\d{4})?$/.test(a.zip.trim())) errors.zip = "Enter a 5-digit ZIP code.";
            if (!p.contact_phone.trim()) errors.contact_phone = "Add a phone number so the driver can reach you.";
        }
        const merged = { ...state.errors, ...errors };
        showErrors(merged);
        const firstBad = document.querySelector("[aria-invalid=true]");
        if (firstBad) firstBad.focus();
        return Object.keys(merged).length === 0;
    }

    async function init() {
        try {
            const res = await fetch(root.dataset.optionsUrl);
            state.options = await res.json();
        } catch (err) {
            showErrors({ fulfillment_type: "Pickup and delivery options didn't load. Refresh the page to try again." });
            return;
        }
        const o = state.options;
        $("[data-meta=pickup]").textContent = "Ready in about " + o.pickup_minutes + " min";
        $("[data-meta=delivery]").textContent = "About " + o.delivery_minutes + " min, " + money(o.delivery_fee) + " fee";
        root.querySelector("input[value=pickup]").disabled = !o.pickup_enabled;
        root.querySelector("input[value=delivery]").disabled = !o.delivery_enabled;
        if (!o.pickup_enabled && o.delivery_enabled) root.querySelector("input[value=delivery]").checked = true;
        onTypeChange();
    }

    root.querySelectorAll("input[name=fulfillment_type]").forEach((r) =>
        r.addEventListener("change", () => { onTypeChange(); requestQuote(); }));
    ["#wd-zip", "#wd-street", "#wd-city", "#wd-state", "#wd-phone"].forEach((sel) =>
        $(sel).addEventListener("input", requestQuote));

    const continueBtn = $("#wd-continue");
    if (continueBtn) continueBtn.addEventListener("click", () => {
        if (isValid()) console.log("Fulfillment payload ready:", getPayload());
    });

    window.WDFulfillment = {
        setSubtotal(value) { state.subtotal = Number(value); preview(); requestQuote(); },
        getPayload,
        isValid,
    };

    init();
})();
