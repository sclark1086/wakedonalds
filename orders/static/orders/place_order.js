// Place order button on the checkout page (SRS UC1). Sends the pickup or
// delivery choice to the order API, then opens the order's tracking page.
// The server builds the order from the customer's cart, so no prices are sent.
(function () {
    const button = document.getElementById("wd-place-order");
    const errorEl = document.querySelector("[data-place-error]");
    if (!button || !window.WDFulfillment) return;

    const csrf = (document.querySelector("[name=csrfmiddlewaretoken]") || {}).value || "";
    const label = button.textContent;

    function showError(message) {
        errorEl.textContent = message || "";
    }

    function setBusy(busy) {
        button.disabled = busy;
        button.textContent = busy ? "Placing order…" : label;
    }

    button.addEventListener("click", async () => {
        showError("");
        if (!WDFulfillment.isValid()) return;

        setBusy(true);
        try {
            const res = await fetch(button.dataset.placeUrl, {
                method: "POST",
                credentials: "same-origin",
                headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
                body: JSON.stringify(WDFulfillment.getPayload()),
            });
            const body = await res.json().catch(() => ({}));

            if (res.status === 201) {
                window.location.assign(body.tracking_url);
                return;
            }
            if (res.status === 401 || res.status === 403) {
                showError("Please log in to place your order.");
            } else if (res.status === 422) {
                WDFulfillment.showServerErrors(body.errors);
                showError("Please fix the highlighted fields.");
            } else {
                const errors = body.errors || {};
                showError(errors.cart || "Something went wrong placing your order. Please try again.");
            }
        } catch (err) {
            showError("We couldn't reach the server. Check your connection and try again.");
        }
        setBusy(false);
    });
})();
