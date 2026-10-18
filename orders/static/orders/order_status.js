// Live order tracking (3.3). Asks the server for the latest status every
// few seconds, pauses while the tab is hidden, and stops once the order is
// picked up or delivered.
(function () {
    const root = document.getElementById("wd-tracking");
    const initial = document.getElementById("wd-initial-order");
    if (!root || !initial) return;

    const POLL_MS = 5000;
    const MAX_BACKOFF_MS = 60000;
    const apiUrl = root.dataset.apiUrl;
    const $ = (sel) => root.querySelector(sel);

    let data = JSON.parse(initial.textContent);
    let delay = POLL_MS;
    let timer = null;

    const timeFmt = new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" });
    const fullFmt = new Intl.DateTimeFormat(undefined, {
        month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
    });
    const fmt = (iso, f) => (iso ? f.format(new Date(iso)) : "");

    function renderEta(d) {
        const el = $("[data-field=eta]");
        if (d.is_final || !d.estimated_ready_at) {
            el.textContent = "";
            return;
        }
        const verb = d.fulfillment_type === "delivery" ? "Estimated delivery" : "Estimated ready";
        el.textContent = `${verb} by ${fmt(d.estimated_ready_at, timeFmt)}`;
    }

    function renderSteps(d) {
        const list = $("[data-steps]");
        list.replaceChildren(...d.steps.map((step) => {
            const li = document.createElement("li");
            li.className = "step" + (step.done ? " done" : "") + (step.current ? " current" : "");
            if (step.current) li.setAttribute("aria-current", "step");

            const dot = document.createElement("span");
            dot.className = "step-dot";
            dot.setAttribute("aria-hidden", "true");

            const text = document.createElement("span");
            text.className = "step-text";
            const label = document.createElement("strong");
            label.textContent = step.label;
            const time = document.createElement("span");
            time.className = "muted step-time";
            time.textContent = fmt(step.reached_at, timeFmt);
            text.append(label, time);

            li.append(dot, text);
            return li;
        }));
    }

    function render(d) {
        $("[data-field=status_label]").textContent = d.status_label;
        $("[data-field=status_message]").textContent = d.status_message;
        renderEta(d);
        renderSteps(d);
        const created = root.querySelector("[data-time-full]");
        if (created) created.textContent = fmt(created.dataset.timeFull, fullFmt);
        $("[data-live-note]").textContent = d.is_final
            ? "This order is complete."
            : "This page updates automatically.";
        document.title = `Order #${d.order_number}: ${d.status_label} | Wakedonalds`;
    }

    function schedule() {
        clearTimeout(timer);
        if (!data.is_final && !document.hidden) timer = setTimeout(poll, delay);
    }

    async function poll() {
        try {
            const res = await fetch(apiUrl, { headers: { Accept: "application/json" } });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const next = await res.json();
            if (next.updated_at !== data.updated_at || next.status !== data.status) {
                data = next;
                render(data);
            }
            delay = POLL_MS;
        } catch (err) {
            // Network hiccup: wait longer each time, up to a minute.
            delay = Math.min(delay * 2, MAX_BACKOFF_MS);
        }
        schedule();
    }

    document.addEventListener("visibilitychange", () => {
        if (document.hidden) {
            clearTimeout(timer);
        } else if (!data.is_final) {
            poll(); // catch up right away when the customer comes back
        }
    });

    render(data);
    schedule();
})();
