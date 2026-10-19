# Orbital Sentinel — Experiment 9 Test Cases

**Application under test:** Orbital Sentinel (Next.js web app on http://localhost:3001, FastAPI backend on :8000). Exp 9 originally ran against the test build on :3000.
**Test user:** `analyst@orbitalsentinel.test` / `sentinel123` (role: Analyst / Operator)
**Traceability:** SRS REQ-16 (risk-ordered alert list); ER entities SATELLITE, DETECTION, ALERT, USER; state diagram transition AlertRaised → Acknowledged.

## Task 1 — Functional test cases (Selenium IDE, `OrbitalSentinel.side`)

| TC ID | Module | Description | Steps | Test Data | Expected Result | Actual Result | Status |
|---|---|---|---|---|---|---|---|
| TC01 | Login | Valid login opens the dashboard | 1. Open /login 2. Enter email and password 3. Click Login | analyst@orbitalsentinel.test / sentinel123 | The browser goes to /dashboard; the alert table and the title "Alerts" are shown | | |
| TC02 | Login | Wrong password is rejected | 1. Open /login 2. Enter a valid email and a wrong password 3. Click Login | analyst@orbitalsentinel.test / wrongpass | The error "Invalid email or password" is shown; the user stays on /login | | |
| TC03 | Login | Empty fields are validated | 1. Open /login 2. Click Login with both fields empty | (blank) | The error "Email and password are required" is shown | | |
| TC04 | Dashboard | Alerts are listed in risk order (REQ-16) | 1. Log in 2. Check the alert table | 8 mock alerts | "8 alerts" is shown; row 1 is ALT-001 with risk level "10" and band "Critical"; the last row is ALT-005 | | |
| TC05 | Alert | Acknowledging an alert updates its status | 1. Log in 2. Click Acknowledge on ALT-001 | ALT-001 | Status changes from AlertRaised to Acknowledged; the button becomes disabled | | |
| TC06 | Session | Logout, then direct dashboard access is blocked | 1. Log in 2. Click Logout 3. Open /dashboard directly | — | After logout the login page is shown; opening /dashboard redirects to /login and no alert table is shown | | |
| TC07 | Roles (Phase 4) | An Analyst cannot reach the admin page | 1. Log in as Analyst 2. Open /admin directly | analyst@orbitalsentinel.test / sentinel123 | Sent back to the dashboard; the admin page's title is never shown (client-side role check, SRS 5.3) | | |
| TC08 | Drill-down (Phase 4, REQ-17) | Clicking a satellite name on an alert opens its health panel | 1. Log in 2. Click the satellite name on the top alert | — | The health panel for SMAP opens (title "SMAP"), showing its verdict and risk level | | |
| TC09 | Globe (Phase 5, REQ-15) | Clicking a satellite on the globe opens the health-panel drawer | 1. Log in 2. Navigate to /globe 3. Wait for the globe to load (`#globeCanvas` visible) 4. Click the first satellite chip in the satellite list fallback (`#sat-list-SAT-001`) or click the canvas point labelled SAT-001 | SAT-001 (SMAP) | The health-panel drawer (`#healthDrawer-SAT-001`) appears and shows the satellite name; the close button (`#drawerClose`) hides it again | | |

## Task 2 — Performance test (JMeter, `OrbitalSentinel.jmx`)

**Configuration:** 50 threads (users), 10 s ramp-up, 10 loops, so 1,500 requests in total (500 per endpoint).

| Endpoint | Samples | Avg (ms) | Min (ms) | Max (ms) | 90% Line (ms) | Error % | Throughput (req/s) |
|---|---|---|---|---|---|---|---|
| POST /api/login | | | | | | | |
| GET /api/alerts | | | | | | | |
| POST /api/alerts/:id/acknowledge | | | | | | | |
| **TOTAL** | | | | | | | |

Fill the table from JMeter's **Aggregate Report** / **Summary Report** listeners, or from the HTML dashboard generated with `-e -o`.
