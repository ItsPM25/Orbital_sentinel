# Orbital Sentinel — Test Build (Experiment 9)

This is the smallest working version of Orbital Sentinel. It exists only so Selenium IDE (functional tests) and JMeter (load tests) have a real app to run against. All data is mock data held in memory. The ML detector, TLE fetching, the 3D globe, and Supabase are not included yet.

Entity names follow the ER diagram in `docs/ER_diagram.docx`: `Satellite`, `Detection`, `Alert`, `User`. Alert states follow `docs/state_transition_diagram.docx`: `AlertRaised` → `Acknowledged`. See `lib/entities.ts`.

## Run
```
npm install
npm run dev        # http://localhost:3000
```
Test login: `analyst@orbitalsentinel.test` / `sentinel123`

## API
| Method | Path | Result |
|---|---|---|
| POST | `/api/login` | body `{"email","password"}` → 200 `{user}` and an `os_session` cookie, or 401 |
| GET | `/api/alerts` | 200, the risk-ranked alert list (highest `riskLevel` first) |
| POST | `/api/alerts/:id/acknowledge` | 200 with the updated alert, or 404 (ids `ALT-001`…`ALT-008`) |
| GET/POST | `/api/reset` | restores the mock data (use it before each test run) |

## Selenium IDE (Task 1)
1. Start the app with `npm run dev`.
2. In Selenium IDE, open `testing/OrbitalSentinel.side` and click **Run all tests**.
3. Record the results in `testing/TEST_CASES.md` and take screenshots.

Stable locators for recording new tests: `id=email`, `id=password`, `id=loginBtn`, `id=loginError`, `id=alertTable`, `id=alertCount`, `id=ack-ALT-00N`, `id=status-ALT-00N`, `id=logoutBtn`.

## JMeter (Task 2)
Run load tests against the production build, which gives realistic numbers:
```
npm run build && npm start
```
- GUI: open `testing/OrbitalSentinel.jmx`, click Start, and read the **Summary Report** and **Aggregate Report**.
- CLI with HTML report:
  ```
  jmeter -n -t testing/OrbitalSentinel.jmx -l results.jtl -e -o jmeter-report
  ```
  Override the load with `-Jusers=100 -Jrampup=20 -Jloops=10 -Jhost=localhost -Jport=3000`.
