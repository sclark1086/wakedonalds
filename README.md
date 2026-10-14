## Sprint 2: Pickup and Delivery (feature 2.2)

### Complete
- New `orders` app so customers can choose pickup or delivery at
  checkout (SRS UC1 step 5). Delivery adds a fee to the order total,
  checks the address against the delivery area, and each order gets an
  estimated ready time.
- Models (`orders/models.py`):
  - `Order` — based on ORDERS in the team's schema diagram, plus
    pickup/delivery type, delivery address, contact phone, subtotal,
    delivery fee, tax, total, status, and estimated ready time.
    `user` is optional so guests can order.
  - `FulfillmentSettings` — a single row holding the delivery fee,
    free-delivery threshold, delivery minimum, tax rate, and prep
    times. Defaults: $3.99 fee, free over $30, $10 minimum, 7.25% tax,
    15 min prep, +25 min for delivery.
  - `DeliveryZone` — ZIP codes the restaurant delivers to.
- Admins change fees, tax, prep times, and delivery ZIPs in `/admin/`,
  with no code changes or redeploy needed.
- Pickup and delivery orders each have their own status flow:
  - Pickup: received → in progress → ready for pickup → completed
  - Delivery: received → in progress → out for delivery → delivered
  Only staff can change a status, and only one step at a time.
- Checkout page at `/checkout/` with the pickup/delivery choice,
  delivery address form, and a live order summary. Works on phones.
- 25 automated tests in `orders/tests.py`.

### API endpoints
| Method | URL | What it does |
|---|---|---|
| GET | `/api/fulfillment/options/` | Settings the checkout page needs (fees, times, what's enabled) |
| POST | `/api/fulfillment/quote/` | Checks a pickup/delivery choice and returns subtotal, delivery fee, tax, total, and ready time |
| PATCH | `/api/orders/<id>/status/` | Staff only: moves an order to its next status |

### Not done yet (next sprint)
- Placing an order isn't built out yet. That needs the cart and
  products merged into `main`, plus an `OrderItem` model. Until then,
  `/checkout/` uses a demo subtotal, and "Continue to payment" only
  validates the form. The place-order view should reuse
  `FulfillmentSerializer` and `calculate_totals()` so pricing rules
  stay in one place.
- No text or email notification when an order is ready (UC3) yet.
- The delivery area is set by ZIP code, not by distance.
- Tax currently applies to food only, not the delivery fee. The team
  should confirm this is correct.

### Testing locally
```bash
python -m venv venv
venv\Scripts\activate          # Windows (Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```
1. Go to `http://localhost:8000/admin/`, log in, and add a ZIP code
   (for example `12345`) under **Delivery zones**.
2. Go to `http://localhost:8000/checkout/`. To try a different cart
   total, add it to the URL, e.g. `/checkout/?subtotal=35.00`.

Run the tests with:
```bash
python manage.py test orders
```