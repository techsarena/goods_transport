# Goods Transport — TMS on ERPNext

Transport Management System built as a first-class ERPNext / Frappe v15 app.
Manages the operational and financial lifecycle of road freight — customer
orders, vehicle trips, consignment notes (bilties), proof of delivery, driver
advances, trip expenses, and profitability — while reusing ERPNext for all
accounting, so revenue and cost flow through standard Sales Invoices,
Purchase Invoices, Journal Entries, and the GL.

Published by **Techs Arena**. MIT licensed.

---

## Design principles

- **Reuse ERPNext primitives.** Customers → `Customer`, transporters / vehicle
  owners → `Supplier`, drivers → the standard `Driver` DocType, cargo → `Item`,
  addresses/contacts → `Address`/`Contact`, vehicles → the standard `Vehicle`
  DocType (extended with transport-specific fields), accounting → standard
  Sales Invoice / Purchase Invoice / Journal Entry / Payment Entry.
- **No direct GL writes.** Every accounting side-effect goes through a real
  ERPNext transaction so audit, reversal, and reporting all work the way
  accountants expect.
- **Trip is an Accounting Dimension.** Registering `Transport Trip` as an
  ERPNext Accounting Dimension causes ERPNext to auto-add a `transport_trip`
  Link field on every accounting transaction DocType and their child rows,
  and tags every GL Entry with it — so trip-level P&L reports read straight
  from the GL and always reconcile against operational figures.
- **Order / Trip / Bilty are separate concepts.**
  - **Order** = what the customer asked us to move.
  - **Trip** = one vehicle physically moving.
  - **Bilty** = one customer's consignment carried during transportation.
  - One order may need many trips; one trip may carry many customers' bilties.
- **Idempotent install.** Every setup routine (custom fields, print formats,
  workspace, dashboard, master data, accounting dimensions) is reproducible on
  `bench migrate` via patches.

---

## Feature matrix

### Operational DocTypes

| DocType | Kind | Purpose |
|---|---|---|
| `Transport Order` | submittable | Customer's request. Tracks ordered / dispatched / delivered / remaining quantities and status (`Draft → Confirmed → Partially Dispatched → Fully Dispatched → Delivered → Closed`). |
| `Transport Trip` | submittable | One vehicle's physical journey. 11-state pipeline (`Planned → Vehicle Assigned → At Loading Point → Loaded → In Transit → Arrived → Unloading → Delivered → Settled → Closed`). Snapshots vehicle/driver/transporter on submit; rolls up loaded weight and capacity utilization from linked Bilties. |
| `Bilty` | submittable | Consignment note. Header + `Bilty Item` + `Bilty Charge` child tables. Rate basis includes Per Trip / Vehicle / Ton / Kg / Package / KM / Fixed. Optional links to Order and Trip. |
| `Proof of Delivery` | submittable | One per Bilty. On submit sets Bilty `pod_status = Received` and notifies the parent Order to refresh delivered quantity. |
| `Trip Advance` | submittable | Advance paid to Driver / Employee / Supplier. On submit creates a Journal Entry (Dr Advance / Cr Cash-or-Bank) tagged with the Trip. |
| `Trip Expense` | submittable | Three payment modes: **Company Cash/Bank** (JE), **Trip Advance** (JE against the advance account, consumes the advance), **Third-Party Bill** (draft Purchase Invoice). Cancels the underlying doc on cancel. |
| `Trip Settlement` | submittable | Unique per Trip. Reconciles revenue (from Sales Invoices), cost (vehicle hire + trip expenses), and driver balance (advances − consumed − cash returned). No GL of its own. On submit locks the Trip as `Settled`. |

### Masters

`Vehicle Type`, `Transport Location`, `Transport Route`, `Transport Rate Contract`, `Trip Expense Type`.

### Child tables

`Bilty Item`, `Bilty Charge`, `Bilty Reference`.

### Extensions to standard ERPNext DocTypes

Applied via idempotent `custom_field` patches:

- **Vehicle** — `ownership_type` (Company Owned / Contracted / Attached / Market Vehicle), `vehicle_type`, `current_status`, `transporter`, `vehicle_owner`, `default_driver`, `payload_capacity`, `volume_capacity`.
- **Sales Invoice** — `bilty_references` child table listing the Bilties consolidated into the invoice.
- **Every accounting DocType (Sales/Purchase Invoice, Journal Entry Account, Payment Entry, Stock Entry, Delivery Note, POS Invoice, Purchase Order, Sales Order, Landed Cost, GL Entry, and 40+ others)** — `transport_trip` Link field, added automatically by ERPNext when the Trip accounting dimension is registered.

### Services

- `services/billing.py` — `create_sales_invoice_from_bilties(bilties)`: consolidates multiple delivered/unbilled Bilties for the same customer/company/currency into one draft Sales Invoice with one row per Bilty freight line plus one row per billable Bilty Charge. Propagates the Trip dimension to the SI header (when all bilties share a trip) and to each item row.
- `services/rates.py` — `find_matching_contract(...)`: most-specific-first Rate Contract resolution (commodity + vehicle_type → commodity → vehicle_type → route). Best-effort prefill; the rate stays editable on the Bilty.
- `services/operations.py` — `create_trip_from_order`, `create_bilty_from_trip`, `create_pod_from_bilty`, `create_transporter_purchase_invoice`. Wraps the cross-document actions the UI buttons call.

### Reports (12)

Registers: **Bilty Register**, **Unbilled Bilties**, **Active Trips**, **Transport Order Status**, **Pending POD**.

Financial (GL-based): **Trip Profitability**, **Customer Profitability**, **Route Profitability**, **Transporter Performance**, **Vehicle Trip History**.

Analysis: **Trip Expense Analysis** (group by type/mode/trip/vehicle/driver), **Driver Advance Settlement** (paid vs consumed vs returned).

All profitability figures come from `tabGL Entry` grouped by `transport_trip`, joined to `tabAccount.root_type` for Income vs Expense classification. Numbers reconcile against Trip Settlement to the last unit.

### Print formats (5)

Standard Jinja print formats (custom, editable in the Print Format Builder): **Bilty**, **Trip Sheet**, **Transport Order**, **Proof of Delivery**, **Trip Settlement**.

### Workspace & dashboard

Public workspace at `/app/goods-transport` with:
- 5 number cards: Active Trips, Pending POD, Unbilled Bilties, Unsettled Trips, MTD Trip Revenue
- 1 bar chart: Trip Revenue by Month
- 5 cards (Operations, Trip Finance, Masters, Commercial, Reports) surfacing every DocType and report

### Master data seeded on install

- Supplier Group: `Transporter`
- Item Group: `Freight Services`
- Items: Freight, Loading, Unloading, Toll Recovery, Detention, Documentation, Weighbridge, Labour, Night Delivery, Handling, Vehicle Hire

---

## Install

Requires a Frappe / ERPNext v15 bench.

```bash
cd ~/frappe-bench
bench get-app https://github.com/techsarena/goods_transport.git
bench --site <your-site> install-app goods_transport
```

On a fresh install the `after_install` hook runs the full setup routine:
seeds masters, applies custom fields, installs print formats, registers the
Trip accounting dimension, installs dashboard number cards + chart, and
publishes the workspace.

On an existing site, `bench migrate` runs the same setup functions through
the patches listed in `patches.txt`, so upgrades converge to the same state.

---

## Typical workflow

1. Book a **Transport Order** for the customer (route, commodity, quantity,
   rate, POD requirement).
2. Create a **Transport Trip** from the Order form for each vehicle
   allocated. The Trip form has a `Create → Bilty` button and a
   `Create → Transporter Purchase Invoice` action once submitted.
3. Add a **Bilty** for each shipment on the trip (may or may not reference
   a Transport Order — some trips are ad-hoc). The Bilty inherits vehicle,
   driver, transporter from the Trip and route/parties from the Order.
4. When the vehicle is loaded and running, use `Advance Status` on the Trip
   to move through the pipeline (`In Transit → Arrived → Delivered`).
5. Optionally pay a **Trip Advance** to the driver and book **Trip Expenses**
   against it (Diesel from advance, Toll from advance, Repair from company
   cash — each posts the correct Journal Entry, tagged with the Trip).
6. When delivered, record **Proof of Delivery** from the Bilty form
   (auto-populates delivered quantity, updates Bilty status, propagates to
   the Order's delivered rollup).
7. From the Bilty form or the Bilty list view, run `Create Sales Invoice`
   to consolidate delivered/unbilled bilties into one draft Sales Invoice
   per customer. Review and submit.
8. Once delivered, create a **Trip Settlement** from the Trip form. It
   reads revenue from SIs, cost from Trip + Trip Expenses, and driver
   balance from Trip Advances. On submit it locks the Trip as `Settled`.
9. The **Trip Profitability** report cross-checks the Settlement's numbers
   against the GL by dimension — the two must agree.

---

## Architecture notes

- `install.py` is the single install entry point (`after_install` hook).
  It calls, in order: `install_transport_masters` → `install_transport_custom_fields`
  → `install_all_print_formats` → `install_transport_accounting_dimensions`
  → `install_transport_dashboard` → `install_goods_transport_workspace`.
- `patches.txt` lists the same routines as post-model-sync patches so
  `bench migrate` reproduces the state on any existing site.
- Every setup function is idempotent and safe to re-run.
- Bilty controller notifies parent Order and parent Trip on submit / update
  after submit / cancel, so rollups (Order.dispatched_quantity,
  Trip.loaded_weight) stay in sync without background jobs.
- POD controller updates the Bilty (`pod_status = Received`, `status = POD Received`)
  and calls `Order.refresh_progress()` to update the delivered quantity.
- Trip Expense mode "Trip Advance" reads the advance's `advance_account` and
  posts a JE that debits the expense and credits that advance account —
  effectively "consuming" the advance. The Trip Settlement's
  `consumed_from_advance` figure is `SUM(Trip Expense.amount WHERE payment_mode='Trip Advance')`.
- `services/billing.py` guards against mixing customers, companies, or
  currencies on a single Sales Invoice and refuses if any Bilty is already
  linked to an invoice.

---

## Commit history

Development is tracked in ~9 semantic commits on `develop`:

1. `feat: transport masters (Vehicle Type, Location, Route, Rate Contract)`
2. `feat: Bilty consignment note with items and charges`
3. `feat: Bilty billing (multi-bilty Sales Invoice consolidation)`
4. `feat: transport operations spine (Order, Trip, POD)`
5. `feat: register Transport Trip as accounting dimension`
6. `feat: trip finance (advance, expense, settlement) + Trip Profitability report`
7. `feat: print formats, master seeder, operational and management reports`
8. `feat: goods transport workspace with KPI cards and chart`
9. `chore: wire install-time orchestration (after_install, fixtures, patches)`
10. `docs: README with feature list, install, and usage`

---

## License

MIT.
