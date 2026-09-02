# Goods Transport — TMS on ERPNext

Transport Management System built as a first-class ERPNext / Frappe v15 app.
Manages the operational and financial lifecycle of road freight — customer
orders, vehicle trips, consignment notes (bilties), proof of delivery, driver
advances, trip expenses, and profitability — while reusing ERPNext for all
accounting, so revenue and cost flow through standard Sales Invoices,
Purchase Invoices, Journal Entries, and the GL.

Driver payroll is part of the same app: completed trips become trip earnings, which flow into standard HRMS salary slips with cash advances recovered from them.

Requires **frappe v15**, **erpnext v15** and **hrms v15**.

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
- Item Group: `Freight Items`
- Freight-service Items: Freight, Loading, Unloading, Toll Recovery, Detention, Documentation, Weighbridge, Labour, Night Delivery, Handling, Vehicle Hire
- Item Group: `Cargo Items` (marked as a group so users can add sub-classifications)
- Cargo-classification Items: `CARGO-CONTAINER` (Nos), `CARGO-STEEL-COIL` (Nos), `CARGO-TRANSFORMER` (Nos), `CARGO-MACHINE` (Nos), `CARGO-VEHICLE` (Nos), `CARGO-CEMENT` (Kg), `CARGO-CHEMICALS` (Kg), `CARGO-TEXTILE-GOODS` (Kg), `CARGO-FOOD-PRODUCTS` (Kg), `CARGO-GENERAL` (Kg)
- Trip Expense Types: `Fuel`, `Driver Food`, `Tyre Repair`, `Vehicle Repair`, `Traffic Challan`, `Driver Allowance`, `Other Trip Expense` — flags per the section below

---

## Cargo vs Freight vs Additional Charges

The app draws a hard line between **what is being moved** (cargo) and **what
the customer is billed for** (freight and additional charges).

| Section | Purpose | Item source |
|---|---|---|
| **Cargo** (`Bilty.items`, `Transport Order.commodity`) | Physical classification of the goods on the trip. Never invoiced as-is. | `Cargo Items` group + any descendant groups the customer adds |
| **Freight** (`Bilty.freight_item` + rate/basis) | The primary transportation service line on the Sales Invoice. | `Freight Items` group |
| **Additional Charges** (`Bilty.charges`) | Supplementary billable/internal services (loading, labour, detention…). | `Freight Items` group |

**Cargo Items** are seeded broad, non-transactional classifications:
`is_stock_item = 0`, `is_sales_item = 0`, `is_purchase_item = 0`. Shipment
specifics (container number, seal, machine serial, hazardous class, coil
count, loading instructions, …) go in the row's **Description** field, not
in the Item master:

```
Item: Transformer
Description: 20 MVA power transformer, serial TR-9087, crane required
Quantity: 1 Nos
Gross Weight: 18,000 kg

Item: Container
Description: 40-foot high-cube container, ABCD-1234567, seal 90845
Quantity: 1 Nos
Gross Weight: 24,000 kg
```

This separation is enforced two ways:

1. **Client-side** — `Bilty.items.item` and `Transport Order.commodity`
   Link pickers use a `get_query` that only returns enabled Items whose Item
   Group is `Cargo Items` or a descendant. Users don't see Freight, Labour,
   or Vehicle Hire in the cargo picker.
2. **Server-side** — `validate()` on both DocTypes calls
   `services/cargo.py :: validate_cargo_item`. This catches imports, API
   calls, background jobs, and any other write path. The error identifies
   the offending row.

Descendant Item Groups under `Cargo Items` (e.g. a user-added
`Perishables → Frozen Fish`) are accepted automatically because the check
uses the ERPNext nested-set descendants lookup.

### Migration note for existing installs

Sites that already have Bilty or Transport Order documents where the cargo
field references a non-cargo Item will fail validation on the next save.
Options:

1. Move the affected Items into the `Cargo Items` group, or
2. Create new Cargo Items via the Item Group and update the cargo rows
   before saving.

Existing **submitted** documents remain readable without change — validation
runs only on save/submit/amend, not on load.

---

## Trip Expense Types

Seven default expense classifications ship with the app so users record
actual trip costs with consistent categorisation instead of free-text
like "fuel", "Diesel", "diesel expense":

| Expense Type | Requires Receipt | Billable by Default | Intended use |
|---|:-:|:-:|---|
| Fuel | Yes | No | Diesel, petrol, CNG, or other vehicle fuel |
| Driver Food | No | No | Meals and food provided during the Trip |
| Tyre Repair | Yes | No | Puncture repair, tyre replacement, tube, or tyre-related work |
| Vehicle Repair | Yes | No | Mechanical, electrical, roadside, or workshop repair |
| Traffic Challan | Yes | No | Traffic fines or challans incurred during the Trip |
| Driver Allowance | No | No | Actual allowance paid or consumed for the Trip |
| Other Trip Expense | Yes | No | Exceptional Trip expenses not covered by another type |

Seeded records ship with `default_expense_account` and `default_item`
empty because ERPNext Account names carry a company abbreviation and
cannot be seeded generically. Set the per-company defaults on the Trip
Expense Type record itself; the Trip Expense form only prefills the
expense account when the type's default belongs to the Trip's company.

### Payment modes → accounting document

The Payment Mode picked on a Trip Expense drives the ERPNext side-effect:

- **Company Cash/Bank** → Journal Entry, Dr Expense / Cr Cash-or-Bank, tagged with the Trip.
- **Trip Advance** → Journal Entry, Dr Expense / Cr the linked Trip Advance's advance account. Consumes the advance, which reduces the Trip Settlement's `advance_balance`.
- **Third-Party Bill** → draft Purchase Invoice to the supplier for review and submission. Cancelling the Trip Expense cancels the underlying invoice too.

### Receipt requirement

Trip Expense Types marked `requires_receipt = 1` (Fuel, Tyre Repair,
Vehicle Repair, Traffic Challan, Other Trip Expense) enforce a receipt
attachment **at submission**. Draft save without a receipt is still
allowed so ops can capture the entry in the field and attach the
document later. Error message names the type: *"A receipt is required
before submitting a Trip Expense of type Fuel."*

### Trip Advance vs Trip Expense

A **Trip Advance** is *cash issued* to a driver / employee / supplier —
it is NOT an expense on its own. It debits the advance account and
credits cash.

The expense is recognised only when a submitted **Trip Expense** with
Payment Mode = "Trip Advance" records how that advance was consumed:

```
Trip Advance issued:                        30,000
  Trip Expense - Fuel (from advance):       12,000
  Trip Expense - Driver Food (from adv):     2,000
  Trip Expense - Tyre Repair (from adv):     3,000
  ---------------------------------------------
  Consumed from advance:                    17,000
  Remaining advance balance:                13,000
```

Trip Settlement's `consumed_from_advance` = sum of Trip Expense amounts
paid via Trip Advance. `advance_balance = paid − consumed`. When the
driver returns cash, enter it in `cash_returned` on the settlement to
compute `outstanding_from_driver`.

### Planned vs actual Driver Allowance

Two related but distinct concepts intentionally kept separate:

- **`Transport Trip.driver_allowance`** — planned/budgeted allowance,
  informational only. Shown on the Trip Settlement print for comparison,
  but **NOT added into `total_cost`**.
- **Submitted Trip Expense with `expense_type = "Driver Allowance"`** —
  actual amount paid or consumed. This is what feeds `total_expenses`
  and therefore `total_cost` on the settlement.

This split guarantees the same allowance is never double-counted.
Recording an actual Driver Allowance expense of ₨3,000 on a trip whose
planned `driver_allowance = 3,000` yields `total_expenses = 3,000` —
not 6,000. The test suite
(`test_trip_expense_types.TestTripSettlementNoDoubleCount`) locks this in.

### Traffic Challan handling

Traffic Challan is seeded because it is a real cash movement that
needs Trip reconciliation, but ships with `billable_by_default = 0`.
Do not automatically pass it through as a customer charge; policy
typically splits it between company, driver, or transporter and
belongs in a separate review flow.

---

## Driver payroll

Completed trips pay the driver, through standard HRMS documents. Nothing here
writes to the GL directly — the Salary Slip does, exactly as it does for every
other employee.

```
Transport Trip  (Delivered / Settled / Closed)
       |  Driver Pay Rule resolves the rates
       v
Driver Trip Earning        one per trip, per driver
       |  Driver Payroll Run — one per month, aggregates by driver
       v
Additional Salary          earnings + one advance-recovery deduction
       |  standard HRMS Payroll Entry
       v
Salary Slip  ->  Journal Entry  ->  GL
```

### Payroll DocTypes

| DocType | Kind | Purpose |
|---|---|---|
| `Driver Pay Rule` | master | Rates and the Salary Components they post to. Scoped to a driver, a vehicle type, a route, or the whole company. |
| `Driver Trip Earning` | record | One per Trip, unique. What the driver earned and how it was computed. `Pending → Processed`. |
| `Driver Payroll Run` | submittable | One per period. Aggregates earnings by driver, sets advance recovery, posts Additional Salary records on submit. |
| `Driver Payroll Detail` | child | One row per driver. `advance_recovery` is editable. |
| `Driver Advance Recovery` | child | FIFO allocation of the recovery across the driver's open Trip Advances. |

### Four earning bases

Every basis with a non-zero rate on the matching rule is applied and summed:

| Basis | Field | Computed from |
|---|---|---|
| Flat per trip | `per_trip_amount` | one per completed Trip |
| Per KM | `rate_per_km` | `Trip.actual_distance`, else `planned_distance`, else `Transport Route.distance_km` |
| Per ton | `rate_per_ton` | `Trip.loaded_weight` ÷ 1000 (rolled up from Bilties) |
| Commission | `commission_percent` | % of submitted `Bilty.freight_amount` on the Trip |

Rules resolve most-specific-first — `driver → vehicle_type + route → vehicle_type
→ route → company default` — and honour `valid_from` / `valid_upto` against the
Trip date, so a rate revision never restates trips already run.

### Advance recovery needs no Journal Entry

`Trip Advance` debits the **Driver Advances** asset account when cash is handed
over. Three things settle it:

1. **Spent on the trip** — a submitted `Trip Expense` with `payment_mode = "Trip Advance"`.
2. **Returned in cash** — `Trip Settlement.cash_returned`, allocated across that trip's advances oldest-first.
3. **Recovered from salary** — a submitted `Driver Payroll Run`.

```
outstanding = amount − consumed − cash_returned_allocated − recovered
```

The seeded `Driver Advance Recovery` deduction component points at that same
**Driver Advances** account, so when the Salary Slip posts it credits the
account and the driver's balance clears in the GL with no manual entry.
`max_recovery_per_month` caps how much comes out of one month's salary; `0`
recovers the whole balance. The figure stays editable per driver on the run.

### Why driver pay is not in `Trip Settlement.total_cost`

`total_cost` stays vehicle hire + trip expenses — exactly what the GL holds
against the Trip accounting dimension — so the settlement keeps reconciling
with **Trip Profitability**. Driver trip pay reaches the GL through a monthly
Salary Slip covering many trips and carrying no Trip dimension, so it is shown
beside it as `Driver Trip Pay` and `Profit After Driver Pay` (custom fields on
Trip Settlement), never folded into `total_cost`.

### Payroll masters seeded on install

Per company, idempotently:

- **Accounts** — `Driver Advances` (Asset, under Loans and Advances) and `Driver Trip Earnings` (Expense, under Indirect Expenses).
- **Salary Components** — Driver Basic Salary, Trip Allowance, Distance Allowance, Tonnage Allowance, Freight Commission (earnings) and Driver Advance Recovery (deduction), each wired to the right account.
- **Salary Structure** — `Driver Salary Structure - {abbr}`, monthly, `Driver Basic Salary = base`, submitted.
- **Driver Pay Rule** — `Default Driver Pay - {abbr}`, all components wired, every rate at zero (a zero-rate rule earns nothing, which is the safe default).
- **Workspace** — `Driver Payroll`.

### Payroll reports (3)

**Driver Earnings Register** (every trip earning with its basis breakdown and
payroll status), **Driver Advance Recovery Status** (issued / spent on trip /
recovered from salary / outstanding, per driver), **Driver Cost Per Trip**
(driver pay against the trip's freight revenue, amount and percentage).

### Running a month

1. Trips reaching **Delivered** become `Driver Trip Earning` records.
2. Open a **Driver Payroll Run** for the month → **Fetch Trip Earnings** (it rescans the period, so trips missed by the live hook are still caught).
3. Review gross earnings, adjust `advance_recovery` to spread a deduction over more months.
4. **Submit** — Additional Salary records are created; earnings become `Processed`.
5. Run the normal **Payroll Entry** for the same period.

Cancelling a run cancels its Additional Salaries (refused if a Salary Slip has
already paid them), releases the earnings back to `Pending`, and reopens any
advance it cleared.

### Payroll guard rails

- A driver with no linked `Employee` blocks the run by name, rather than failing inside Additional Salary.
- Market-vehicle drivers have no Employee, so they generate no earning at all — they are paid by the vehicle owner out of the hire.
- Inactive employees, a payroll date before joining, and a missing Salary Structure Assignment are caught before submit.
- Recovery above the outstanding balance is rejected on client and server.
- Cancelling a Trip whose earning is `Processed` is refused; a `Pending` earning is voided.
- One earning per Trip, enforced by a unique constraint — regenerating recomputes in place.

---

## Demo dataset

A seeder builds a complete Pakistani goods-transport company — three months of
operations and two months of processed payroll:

```bash
bench --site <site> execute goods_transport.demo.seed_all.run
```

| Command | What it does |
|---|---|
| `goods_transport.demo.reset.run` | Cancels and deletes every transaction; keeps masters |
| `goods_transport.demo.seed_masters.run` | Fiscal years, accounts, holiday list, locations, routes, vehicles, drivers + employees, pay rules, rate contracts |
| `goods_transport.demo.seed_operations.run` | Orders, trips, bilties, advances, expenses, PODs, sales invoices, hire bills, settlements |
| `goods_transport.demo.seed_collections.run` | Customer payments, so receivables age realistically |
| `goods_transport.demo.seed_payroll.run` | Driver Payroll Runs + Payroll Entries for completed months |

Deterministic (fixed seed) and deliberately leaves the **current month
unprocessed** — trips in every pipeline stage and Pending trip earnings — so
payroll can be run live in front of an audience. Edit `goods_transport/demo/data.py`
to change the fleet, customers, drivers, routes or cargo mix.

## Tests

```bash
bench --site <site> run-tests --app goods_transport
```

Ten payroll tests cover rule resolution and validity windows, the four earning
bases, the no-Employee and not-yet-delivered guards, idempotent regeneration,
advance outstanding arithmetic, the recovery cap, over-recovery rejection, and a
full run submit/cancel cycle.

> On a site holding real data, note that `run-tests` fires ERPNext's
> `before_tests` hook, which clears Item Prices and enables all admin roles.

---

## Roles and users

### Transport User role

Seeded on install / migrate by `setup/install_transport_user.py` (and its
v1_3 patch). Grants full operational access to the transport lifecycle
end-to-end — including the accounting documents the flow produces — and
nothing else:

- **Full lifecycle** (read/write/create/submit/cancel/amend): every
  transport DocType (Transport Order, Transport Trip, Bilty + child rows,
  Proof of Delivery, Trip Advance, Trip Expense, Trip Settlement, all
  transport masters).
- **Full lifecycle** on the accounting docs those actions produce:
  Sales Invoice, Purchase Invoice, Journal Entry, Payment Entry.
- **Read + write + create**: Customer, Supplier, Vehicle, Driver, Item,
  Address, Contact.
- **Read-only**: Company, Currency, UOM, Country, Account, Cost Center,
  Item Group, Supplier Group, Customer Group, Territory, Fiscal Year,
  Print Format, Report.
- **Desk essentials**: File, Comment, ToDo, Note.

Everything else in the desk (Sales Order, Delivery Note, Purchase Order,
Employee, Payroll, Manufacturing, System Settings, DocType, Role, User…)
is blocked at the DocType permission layer — the user cannot list, read,
create, or edit them, from either the desk or the API.

The seeder also attaches the role to the `Goods Transport` workspace so
those users see it in their sidebar.

### Hiding other apps' workspaces from the sidebar

DocType permissions block *access* to Selling / Buying / Stock / Accounting
etc., but Frappe workspaces are public by default and still show up in the
sidebar — visually cluttering the desk for a transport-only user. The user
script populates `User.block_modules` with every module *except* Goods
Transport, so the sidebar collapses down to just what the user works with.
Any newly installed app on the bench is picked up automatically the next
time the script runs for that user.

### Creating a user in production

The seeder never creates User records — that would be dangerous on a
running site. Use the shipped script:

```bash
bench --site <site> execute goods_transport.scripts.create_transport_user.execute \
    --kwargs '{"email": "ops1@mycompany.com", "full_name": "Ops One"}'
```

Optional kwargs:

- `send_welcome_email` (default `false`) — set `true` if outgoing email is configured.
- `reset_password_link` (default `true`) — when no welcome email is sent
  and the user is newly created, the script prints a one-time
  `/update-password?key=…` URL you can share.
- `extra_roles` — pass e.g. `["System Manager"]` if you want a
  demo/administrative user; leave empty for a transport-only user.
- `hide_non_transport_modules` (default `true`) — populates
  `User.block_modules` so only the Goods Transport workspace shows in the
  sidebar. Set `false` to keep every module visible.
- `keep_visible_modules` — list of extra module names to keep visible,
  e.g. `["HR"]` if you also want the user to see HRMS workspaces.

The script is idempotent — safe to re-run on the same email to reapply
role and block_modules; if the user already exists no other data is
touched.

---

## Install

Requires a Frappe / ERPNext v15 bench.

```bash
cd ~/frappe-bench
bench get-app https://github.com/techsarena/goods_transport.git
bench --site <your-site> install-app hrms          # required by the payroll layer
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
