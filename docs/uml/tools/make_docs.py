"""Build the Exp 6 and Exp 8 lab documents (Word) from the StarUML captures.

Uses the Exp 5 document as the template so fonts, margins and heading styles match.
Run from the repo root:  python docs/uml/tools/make_docs.py
"""

from copy import deepcopy
from pathlib import Path

import docx
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt

ROOT = Path(__file__).resolve().parents[3]
DOCS = ROOT / "docs"
UML = DOCS / "uml"
TEMPLATE = DOCS / "state_transition_diagram.docx"
DATE = "22nd October, 2026"
REPO = "https://github.com/ItsPM25/Orbital_sentinel"
FULL_WIDTH = Inches(6.27)


# --------------------------------------------------------------------------- helpers

def new_document():
    d = docx.Document(str(TEMPLATE))
    body = d.element.body
    for el in list(body):
        if el.tag != qn("w:sectPr"):
            body.remove(el)
    return d


def shade(cell, fill="F1F5F9"):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    tc_pr.append(shd)


def borders(table):
    tbl_pr = table._tbl.tblPr
    b = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        e = OxmlElement(f"w:{edge}")
        e.set(qn("w:val"), "single")
        e.set(qn("w:sz"), "4")
        e.set(qn("w:space"), "0")
        e.set(qn("w:color"), "auto")
        b.append(e)
    tbl_pr.append(b)


def table(d, header, rows, widths=None, size=10):
    t = d.add_table(rows=1, cols=len(header))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    borders(t)
    for i, h in enumerate(header):
        c = t.rows[0].cells[i]
        c.text = ""
        r = c.paragraphs[0].add_run(h)
        r.bold = True
        r.font.size = Pt(size)
        shade(c)
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ""
            r = cells[i].paragraphs[0].add_run(str(v))
            r.font.size = Pt(size)
    if widths:
        for row in t.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = Inches(w)
    d.add_paragraph()
    return t


def info_table(d, mdj):
    rows = [
        ("Student name", "Pushkar Kumar Mishra"),
        ("Reg. number", "24BPS1128"),
        ("Course ", "BCSE301P"),
        ("Date of submission", DATE),
        ("StarUML project file", mdj),
        ("Source code", REPO),
    ]
    table(d, ["Field", "Value"], rows, widths=[2.6, 3.6], size=11)


def para(d, text, bold_lead=None, size=None, align=None):
    p = d.add_paragraph()
    if bold_lead:
        r = p.add_run(bold_lead)
        r.bold = True
        if size:
            r.font.size = Pt(size)
    r = p.add_run(text)
    if size:
        r.font.size = Pt(size)
    if align is not None:
        p.alignment = align
    return p


def bullets(d, items):
    for it in items:
        d.add_paragraph(it, style="List Paragraph").paragraph_format.left_indent = Inches(0.25)


def numbered(d, items):
    for i, it in enumerate(items, 1):
        p = d.add_paragraph()
        p.paragraph_format.left_indent = Inches(0.25)
        p.add_run(f"{i}. ").bold = True
        p.add_run(it)


def figure(d, path, caption, width=FULL_WIDTH):
    p = d.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.keep_with_next = True
    p.add_run().add_picture(str(path), width=width)
    c = d.add_paragraph()
    c.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = c.add_run(caption)
    r.italic = True
    r.font.size = Pt(10)


def keep_headings_with_next(d):
    for p in d.paragraphs:
        if p.style.name.startswith("Heading"):
            p.paragraph_format.keep_with_next = True


def header_block(d, title, lines):
    d.add_heading(title, level=1)
    p = d.add_paragraph()
    for i, (k, v) in enumerate(lines):
        if i:
            p.add_run("\n")
        p.add_run(k).bold = True
        p.add_run(" " + v)


def checklist(d, items):
    for it in items:
        d.add_paragraph("☑  " + it, style="List Paragraph")


# --------------------------------------------------------------------------- Exp 6

def build_exp6():
    d = new_document()
    img = UML / "exp6"
    header_block(d, "Experiment 6: Object-Oriented Design – Use Case Model and Class Model", [
        ("Tool used:", "StarUML 7.1.1"),
        ("Diagram types:", "UML Use Case Diagram, UML Class Diagram (domain model and detection pipeline)"),
        ("Subject system:", "Orbital Sentinel – Satellite Telemetry Anomaly Detection System"),
    ])
    info_table(d, "docs/uml/Exp6_UseCase_Class.mdj")

    d.add_heading("1. Aim", level=2)
    d.add_paragraph(
        "To analyse the problem statement of the Orbital Sentinel system and design its object-oriented "
        "models: a Use Case Diagram that captures who uses the system and for what, and a Class Diagram "
        "that captures the classes, their attributes and operations, and the relationships between them.")

    d.add_heading("2. Problem Statement", level=2)
    d.add_paragraph(
        "Satellites stream telemetry from thousands of sensor channels, far more than an operator can watch. "
        "Orbital Sentinel learns what normal telemetry looks like for each channel with a small LSTM network, "
        "replays NASA's expert-labelled SMAP/MSL telemetry through those models and flags readings that deviate "
        "from what the model expected. Each anomaly is attributed to the channel that caused it, filtered so that "
        "one-off spikes do not raise alarms (persistence filter), given a severity and a 1–10 risk level, and "
        "ranked across the fleet. Analysts see a risk-ranked alert list, a health panel with the telemetry chart, "
        "and a live 3D globe that shows five real satellites at their current positions computed from public "
        "orbital data (TLEs from CelesTrak). Administrators run the monitoring sessions and set thresholds; "
        "evaluators review accuracy metrics and the detection log.")
    d.add_paragraph(
        "System boundary: everything inside the Orbital Sentinel web application and its FastAPI backend. "
        "CelesTrak (the public TLE service) is outside the boundary and is modelled as a secondary actor. "
        "The system detects anomalies; it does not forecast failures, and health telemetry is a replay.")

    d.add_heading("3. Identified Actors", level=2)
    table(d, ["Actor", "Type", "Description"], [
        ("User", "Abstract primary actor", "Any signed-in person. Holds the use cases every role can perform "
         "(log in, view alerts, inspect health, track the fleet)."),
        ("Analyst", "Primary actor (specialises User)", "Operator who watches the alert list and acknowledges alerts."),
        ("Evaluator", "Primary actor (specialises User)", "Read-only reviewer of accuracy metrics, the detection log and the trained models."),
        ("Administrator", "Primary actor (specialises Analyst and Evaluator)", "Runs monitoring sessions, sets thresholds and imports the dataset; inherits everything an Analyst and an Evaluator can do."),
        ("CelesTrak", "Secondary actor «external system»", "Public GP API that supplies Two-Line Element sets (TLEs) for the satellites."),
    ], widths=[1.2, 1.7, 3.3])

    d.add_heading("4. List of Use Cases", level=2)
    table(d, ["ID", "Use case", "Actor(s)", "Description", "SRS ref."], [
        ("UC-01", "Log in", "User", "Sign in with e-mail and password; a signed httpOnly cookie carries the role.", "SRS 5.3"),
        ("UC-02", "View risk-ranked alerts", "User", "Alert list ordered by risk with verdict, severity and attributed channel.", "REQ-16"),
        ("UC-03", "Inspect satellite health", "User", "Health panel: verdict, risk, anomaly score, attributed channels.", "REQ-15"),
        ("UC-04", "View telemetry chart", "(extends UC-03)", "Telemetry plot with flagged ranges shaded; channel selector.", "REQ-17"),
        ("UC-05", "Track fleet on 3D globe", "User", "Real positions from TLE + SGP4, coloured by risk.", "REQ-12–14"),
        ("UC-06", "Change simulation speed", "(extends UC-05)", "Live / 10× / 60× / 300× globe clock.", "REQ-13"),
        ("UC-07", "Fetch TLE data", "CelesTrak (included by UC-05)", "Download TLEs, cache them for 2 h, fall back to a bundled snapshot.", "REQ-12"),
        ("UC-08", "Acknowledge alert", "Analyst", "Moves an alert from AlertRaised to Acknowledged (Exp 5 state machine).", "REQ-16"),
        ("UC-09", "View accuracy metrics", "Evaluator", "Precision, recall, F1 and FPR, with and without the persistence filter.", "REQ-5, REQ-11"),
        ("UC-10", "Browse detection log", "Evaluator", "Every detection with timestamp, score, channel, severity and outcome.", "REQ-18"),
        ("UC-11", "View trained models", "Evaluator", "Model registry (MDL-LSTM-100-80, 81 channels).", "REQ-3"),
        ("UC-12", "Start/stop monitoring session", "Administrator", "Starts the per-satellite replay → LSTM → lifecycle pipeline.", "REQ-1–4"),
        ("UC-13", "Configure thresholds", "Administrator", "Persistence N and severity threshold per satellite.", "REQ-8, REQ-9"),
        ("UC-14", "Import dataset", "Administrator", "Register the NASA SMAP/MSL channels against the satellites.", "REQ-1"),
    ], widths=[0.55, 1.45, 1.2, 2.3, 0.8], size=9)

    d.add_heading("5. Use Case Relationships", level=2)
    table(d, ["Relationship", "From", "To", "Meaning"], [
        ("Association", "Actors", "Their use cases", "The actor initiates the use case (14 associations)."),
        ("«include»", "Track fleet on 3D globe", "Fetch TLE data", "The globe always needs current TLEs."),
        ("«extend»", "Inspect satellite health", "View risk-ranked alerts", "Optional drill-down from an alert row."),
        ("«extend»", "Inspect satellite health", "Track fleet on 3D globe", "Optional: clicking a satellite on the globe opens its panel."),
        ("«extend»", "View telemetry chart", "Inspect satellite health", "Optional: open the chart from the health panel."),
        ("«extend»", "Change simulation speed", "Track fleet on 3D globe", "Optional change of the globe clock."),
        ("Generalization", "Analyst, Evaluator", "User", "Both roles inherit the common signed-in use cases."),
        ("Generalization", "Administrator", "Analyst, Evaluator", "The Administrator can do everything the other two roles can."),
    ], widths=[1.1, 1.6, 1.6, 2.0], size=9)

    d.add_heading("6. Use Case Diagram", level=2)
    figure(d, img / "Exp6_UseCase.jpg", "Figure 1: Use Case Diagram – Orbital Sentinel", width=Inches(5.6))

    d.add_heading("7. Identified Classes", level=2)
    d.add_paragraph("Nouns in the problem statement and the ER diagram (Exp 4) became the domain (entity) classes; "
                    "the processing steps became the pipeline (control) classes. Every class maps to real code.")
    table(d, ["Class", "Kind", "Responsibility", "Code"], [
        ("Satellite", "Entity", "A monitored spacecraft with its TLE and proxy flag.", "models/tables.py"),
        ("Channel", "Entity", "One telemetry sensor channel of a satellite.", "models/tables.py"),
        ("TelemetryReading", "Entity", "One timestamped value of a channel.", "models/tables.py"),
        ("DetectionModel", "Entity", "A trained detector (weights path, hyper-parameters).", "models/tables.py"),
        ("Detection", "Entity", "One scored anomalous window (score, severity, outcome).", "models/tables.py"),
        ("Attribution", "Entity", "Share of a detection blamed on one channel (top 3).", "models/tables.py"),
        ("Alert", "Entity", "An alert raised from a confirmed detection; carries the alert state.", "models/tables.py"),
        ("User", "Entity", "A person with one Role and an argon2 password hash.", "models/tables.py"),
        ("MonitoringConfig", "Entity", "Persistence N and severity threshold set for a satellite.", "models/tables.py"),
        ("Role, AlertStatus, SeverityLevel, DetectionOutcome", "Enumerations", "Fixed value sets; the names match the SRS and the Exp 5 state diagram.", "models/tables.py"),
        ("SessionRegistry", "Control", "Starts, stops and lists running monitoring sessions.", "services/sessions.py"),
        ("MonitoringSession", "Control", "Runs replay → score → lifecycle → store → publish for one satellite.", "pipeline/session.py"),
        ("ReplaySource, Normaliser, Windower", "Control", "Replay the dataset as a time-ordered stream of windows.", "pipeline/ingest.py"),
        ("Detector «interface»", "Interface", "score(window) → ChannelScores; lets stages be swapped and mocked.", "pipeline/detect.py"),
        ("LstmDetector, ScriptedDetector", "Control", "Real LSTM detector, and the test double used by pytest.", "pipeline/detect.py"),
        ("LstmPredictor", "Control", "PyTorch network: 2 LSTM layers × 80 units + linear head.", "pipeline/lstm.py"),
        ("StreamingThreshold", "Control", "Non-parametric dynamic threshold over the last 2,100 errors.", "pipeline/detect.py"),
        ("DetectionLifecycle", "Control", "The Exp 5 state machine (persistence filter, Confirmed/Suppressed).", "pipeline/lifecycle.py"),
        ("TelemetryWindow, ChannelScores", "Data (value objects)", "Data passed between the pipeline stages.", "pipeline/types.py"),
        ("Explain «utility»", "Utility", "Attribution, severity, risk label, fleet ranking.", "pipeline/explain/"),
        ("EventBus", "Control", "In-process publish/subscribe for live (SSE) updates.", "services/events.py"),
        ("CelesTrakClient «utility»", "Boundary", "Fetches and caches TLEs from the external CelesTrak API.", "tracking/celestrak.py"),
    ], widths=[1.6, 0.9, 2.6, 1.2], size=9)

    d.add_heading("8. Class Diagram", level=2)
    d.add_paragraph("The class model is split into two diagrams in the same StarUML project so each stays readable: "
                    "the domain model (persistent entities) and the detection pipeline (behaviour). The Satellite "
                    "class appears on both diagrams as the same model element.")
    figure(d, img / "Exp6_Class_Domain.jpg", "Figure 2: Class Diagram – Domain Model")
    figure(d, img / "Exp6_Class_Pipeline.jpg", "Figure 3: Class Diagram – Detection Pipeline")

    d.add_heading("9. Relationships in the Class Model", level=2)
    table(d, ["From", "To", "Type", "Multiplicity", "Meaning"], [
        ("Satellite", "Channel", "Composition", "1 → 1..*", "A channel cannot exist without its satellite."),
        ("Channel", "TelemetryReading", "Composition", "1 → *", "Readings belong to one channel."),
        ("Detection", "Attribution", "Composition", "1 → 0..3", "Up to three blamed channels per detection."),
        ("Satellite", "MonitoringConfig", "Aggregation", "1 → *", "Config history is kept; only the newest row is active."),
        ("Satellite", "Detection", "Association", "1 → *", "Detections are made for a satellite."),
        ("DetectionModel", "Detection", "Association", "1 → *", "Each detection records the model that produced it."),
        ("Attribution", "Channel", "Association (directed)", "* → 1", "Each attribution blames one channel."),
        ("Detection", "Alert", "Association", "1 → 0..1", "A confirmed detection raises at most one alert."),
        ("User", "Alert", "Association", "0..1 → *", "The user who acknowledged the alert."),
        ("User", "MonitoringConfig", "Association", "1 → *", "The administrator who set the config."),
        ("SessionRegistry", "MonitoringSession", "Aggregation", "1 → 0..*", "The registry holds the running sessions."),
        ("ReplaySource", "Normaliser, Windower", "Composition", "1 → 1..* / 1", "Ingestion helpers owned by the source."),
        ("LstmDetector", "LstmPredictor, StreamingThreshold", "Composition", "1 → 1..*", "One predictor and one threshold per channel."),
        ("LstmDetector, ScriptedDetector", "Detector", "Realization", "–", "Both implement the Detector interface."),
        ("LstmPredictor", "torch.nn.Module", "Inheritance (generalization)", "–", "The network is a PyTorch module."),
        ("MonitoringSession", "Explain, EventBus", "Dependency «use»", "–", "Called per window; not stored as fields."),
        ("Detector", "TelemetryWindow / ChannelScores", "Dependency «use» / «create»", "–", "Input and output of score()."),
        ("CelesTrakClient", "Satellite", "Dependency «update»", "–", "Writes fetched TLEs to the satellite row."),
    ], widths=[1.3, 1.5, 1.2, 0.8, 1.6], size=9)

    d.add_heading("10. Brief Explanation of Design Decisions", level=2)
    for lead, text in [
        ("Abstract User actor. ", "All three roles share the signed-in use cases, so they sit on an abstract User actor. "
         "Analyst and Evaluator specialise User, and Administrator specialises both, which matches the server-side "
         "role checks (require_roles) without drawing duplicate association lines."),
        ("Log in as its own use case. ", "Authentication is shown once, on User, instead of 13 «include» arrows from "
         "every use case; the rule that every request needs a session is enforced by the server on each call."),
        ("Include vs extend. ", "Fetching TLEs is mandatory for the globe, so it is «include». Opening the health panel, "
         "the telemetry chart and changing the clock speed are optional user choices, so they are «extend»."),
        ("Names traced to earlier experiments. ", "Entity names are the ER diagram's (Exp 4) and the alert states are the "
         "state diagram's (Exp 5), so the design can be followed straight into the code."),
        ("Encapsulation. ", "Entity attributes are private (–) and are changed only through operations such as "
         "Alert.acknowledge() and Alert.escalate(), which enforce the AlertRaised → Acknowledged → Resolved order."),
        ("Abstraction through an interface. ", "MonitoringSession depends on the Detector interface, not on the LSTM. "
         "ScriptedDetector realises the same interface, so the whole pipeline is unit-tested without a trained model."),
        ("Composition only where lifetimes are bound. ", "Channels, readings and attributions are destroyed with their owner, "
         "so they are compositions; monitoring configs keep their history, so the satellite only aggregates them."),
        ("Multivalued attributes. ", "missionTags and contactEmails are shown as String[*] attributes; the database stores "
         "them in separate tables only to satisfy first normal form, which is an implementation detail."),
        ("No duplicate classes. ", "Stateless helper functions (attribution, severity, ranking, CelesTrak access) are grouped "
         "into «utility» classes rather than invented as separate objects."),
    ]:
        para(d, text, bold_lead=lead)

    d.add_heading("11. Full-Screen Screenshots (with timestamp)", level=2)
    d.add_paragraph("Screenshots of StarUML with the project open; the Windows taskbar clock shows the date and time.")
    figure(d, img / "Exp6_UseCase_screenshot.jpg", "Figure 4: Use Case Diagram open in StarUML, with system timestamp")
    figure(d, img / "Exp6_Class_Domain_screenshot.jpg", "Figure 5: Domain Class Diagram open in StarUML, with system timestamp")
    figure(d, img / "Exp6_Class_Pipeline_screenshot.jpg", "Figure 6: Detection Pipeline Class Diagram open in StarUML, with system timestamp")

    d.add_heading("12. Submission Checklist", level=2)
    checklist(d, [
        "Problem statement analysed and system boundary identified (Section 2)",
        "Actors identified, including a secondary external system (Section 3)",
        "Use cases listed and traced to the SRS requirements (Section 4)",
        "Use Case Diagram with association, include, extend and generalization (Figure 1)",
        "Classes identified with attributes and operations (Section 7)",
        "Class Diagram with association, aggregation, composition, inheritance, realization and dependency (Figures 2, 3)",
        "Design decisions explained (Section 10)",
        "Timestamp screenshots attached (Section 11)",
        "StarUML project file saved (docs/uml/Exp6_UseCase_Class.mdj)",
    ])

    d.add_heading("13. Result", level=2)
    d.add_paragraph(
        "The Use Case Model and the Class Model of the Orbital Sentinel system were designed in StarUML using standard "
        "UML notation. The use case diagram shows 5 actors and 14 use cases with association, include, extend and "
        "generalization relationships. The class model shows 9 entity classes, 4 enumerations and 16 pipeline classes "
        "(plus the torch.nn.Module library class) with their attributes, operations and all required relationship types. Every class name matches the "
        "implementation in the project repository.")
    keep_headings_with_next(d)
    out = DOCS / "Exp6_use_case_and_class_diagram.docx"
    d.save(str(out))
    return out


# --------------------------------------------------------------------------- Exp 8

def build_exp8():
    d = new_document()
    img = UML / "exp8"
    header_block(d, "Experiment 8: OO Design – Package, Component and Deployment Models", [
        ("Tool used:", "StarUML 7.1.1"),
        ("Diagram types:", "UML Package Diagram, UML Component Diagram, UML Deployment Diagram"),
        ("Subject system:", "Orbital Sentinel – Satellite Telemetry Anomaly Detection System"),
    ])
    info_table(d, "docs/uml/Exp8_Package_Component_Deployment.mdj")

    d.add_heading("1. Aim", level=2)
    d.add_paragraph(
        "To model the implementation and physical architecture of the Orbital Sentinel system: the packages of the "
        "code base and their dependencies (Package Diagram), the major software components and their interfaces "
        "(Component Diagram), and the hardware nodes, execution environments and deployed artefacts with the "
        "communication paths between them (Deployment Diagram).")

    d.add_heading("2. System Overview", level=2)
    d.add_paragraph(
        "Orbital Sentinel is a web application with two parts. The frontend (Next.js 15 + React 19, port 3001) "
        "shows the alert dashboard, the health panel and a 3D globe. The backend (FastAPI on Python 3.12, port 8000) "
        "replays NASA SMAP/MSL telemetry through per-channel LSTM models, decides which windows are anomalous, explains "
        "and ranks them, stores the results in SQLite and pushes live updates to the browser with Server-Sent Events. "
        "Satellite positions are computed in the browser from TLEs that the backend fetches from CelesTrak.")

    d.add_heading("3. Task 1 – Package and Component Model", level=2)
    d.add_heading("3.1 Major functional modules", level=3)
    table(d, ["Module (package)", "Folder", "Function"], [
        ("web.app", "web/app", "Pages: login, alerts dashboard, globe, satellites, health panel, evaluation, administration."),
        ("web.components", "web/components", "Shared UI: app shell, page header, risk meter, shadcn/ui widgets."),
        ("web.lib", "web/lib", "Typed API client, SSE hook, request coalescing, SGP4 helpers, risk colours."),
        ("backend.app.api", "backend/app/api", "REST + SSE routers (auth, alerts, satellites, detections, ranking, stream, sessions, admin, evaluation, tle)."),
        ("backend.app.schemas", "backend/app/schemas", "Pydantic request/response models (camelCase JSON)."),
        ("backend.app.services", "backend/app/services", "sessions: running-session registry; events: publish/subscribe bus."),
        ("backend.app.pipeline", "backend/app/pipeline", "Dataset, ingest, LSTM, training, detection, lifecycle, monitoring session, fleet split."),
        ("backend.app.pipeline.explain", "backend/app/pipeline/explain", "Attribution, severity and risk ranking (the novelty layer)."),
        ("backend.app.tracking", "backend/app/tracking", "CelesTrak client, TLE cache and bundled snapshot."),
        ("backend.app.evaluation", "backend/app/evaluation", "Metrics, baseline report, persistence-filter (REQ-11) reports."),
        ("backend.app.models", "backend/app/models", "SQLAlchemy tables, one class per ER entity."),
        ("backend.app.core", "backend/app/core", "db (SQLite, WAL), security (argon2, signed cookie, roles), settings (OS_* variables)."),
        ("ml.spike", "ml/spike", "Phase 1 model-selection spike (throwaway prototype)."),
    ], widths=[1.8, 1.7, 2.8], size=9)

    d.add_heading("3.2 Package Diagram", level=3)
    figure(d, img / "Exp8_Package.jpg", "Figure 1: Package Diagram – Orbital Sentinel")
    d.add_paragraph("Each dashed arrow is a dependency: the source package imports the target package. The table lists "
                    "every dependency found in the code; the imports of core.settings and core.db by several packages "
                    "are left off the drawing to keep it readable.")
    table(d, ["Package", "Depends on", "Why"], [
        ("web.app", "web.components, web.lib", "Pages are built from shared components and call the API client."),
        ("web.components", "web.lib", "Components use the risk helpers and formatters."),
        ("web.lib", "backend.app.api (HTTP/JSON + SSE)", "The only link between frontend and backend is HTTP through the /api rewrite."),
        ("api", "schemas, services.sessions, services.events, pipeline, tracking, models, core.security/db/settings", "Routers validate input, call services and return schemas."),
        ("schemas", "models, pipeline.explain", "Response models are built from ORM rows and ranking results."),
        ("services.sessions", "pipeline, models, core", "Starts MonitoringSession tasks."),
        ("pipeline", "services.events, models, core.db, core.settings", "Writes detections and alerts, and publishes live events."),
        ("evaluation", "pipeline, core.settings", "Re-uses the live scoring code to measure accuracy."),
        ("tracking", "models", "Caches fetched TLEs on the satellite rows."),
        ("models", "core.db", "Tables extend the declarative Base."),
        ("core.security", "models", "Loads the signed-in User."),
        ("ml.spike", "pipeline (dataset)", "The spike loads the same dataset files."),
    ], widths=[1.4, 2.4, 2.5], size=9)

    d.add_heading("3.3 Component Diagram", level=3)
    figure(d, img / "Exp8_Component.jpg", "Figure 2: Component Diagram – Orbital Sentinel")
    table(d, ["Component", "Provides", "Requires / uses", "Realised by"], [
        ("UI Pages", "–", "Globe Renderer, Orbit Propagator, API Client, Live Stream Hook", "web/app"),
        ("Globe Renderer", "–", "–", "globe.gl 2.46 + three.js 0.186"),
        ("Orbit Propagator", "–", "–", "web/lib/sgp4.ts (satellite.js)"),
        ("API Client", "–", "REST (HTTP/JSON)", "web/lib/api.ts"),
        ("Live Stream Hook", "–", "SSE /api/stream", "web/lib/useStream.ts"),
        ("REST API Routers", "REST (HTTP/JSON), SSE /api/stream", "ISessionControl, ORM Session, Auth & Roles, Event Bus, TLE Tracker, Evaluation", "backend/app/api"),
        ("Auth & Roles", "–", "–", "core/security.py"),
        ("Session Manager", "ISessionControl", "Detector", "services/sessions.py"),
        ("Detection Pipeline", "Detector", "IEventPublish, ORM Session, Explain Engine, Model Store, Telemetry Dataset", "pipeline/"),
        ("Explain Engine", "–", "–", "pipeline/explain/"),
        ("Event Bus", "IEventPublish", "–", "services/events.py"),
        ("TLE Tracker", "–", "GP API (HTTPS), ORM Session", "tracking/celestrak.py"),
        ("Evaluation", "–", "Detection Pipeline", "evaluation/"),
        ("Persistence (ORM)", "ORM Session", "SQLite Database", "models/ + core/db.py"),
        ("SQLite Database «database»", "–", "–", "backend/orbital.db (WAL)"),
        ("Model Store, Telemetry Dataset «file»", "–", "–", "models/, data/"),
        ("CelesTrak «external»", "GP API (HTTPS)", "–", "celestrak.org"),
    ], widths=[1.5, 1.3, 2.2, 1.3], size=9)
    d.add_paragraph("Provided interfaces are drawn as lollipops (realization) and required interfaces as sockets "
                    "(dependency). Interfaces sit where one part of the system could be replaced: the Detector "
                    "interface lets a different model replace the LSTM, and the ORM Session lets Postgres replace SQLite "
                    "(OS_DATABASE_URL).")

    d.add_heading("4. Task 2 – Deployment Model", level=2)
    d.add_heading("4.1 Nodes and execution environments", level=3)
    table(d, ["Node", "Stereotype", "Contains"], [
        ("Analyst Workstation", "«device»", "Web Browser (Chrome / Firefox) «executionEnvironment»"),
        ("Application Host (Windows 11 laptop: i5-13420H, 12 logical CPUs, 16 GB RAM)", "«device»",
         "Node.js 22 runtime, Python 3.12 venv (Uvicorn), Local file system «executionEnvironment»"),
        ("CelesTrak Server", "«device» (external)", "GP API web service"),
        ("Kaggle", "«device» (external, one-off)", "Dataset mirror"),
        ("GitHub", "«device» (external)", "Repository and Actions CI runners"),
    ], widths=[2.4, 1.4, 2.5], size=9)

    d.add_heading("4.2 Deployed artifacts", level=3)
    table(d, ["Artifact", "Deployed on", "Notes"], [
        ("Next.js client bundle (JS), globe.gl + three.js, satellite.js (SGP4)", "Web Browser", "Downloaded from the Next.js server; SGP4 runs every frame in the browser."),
        ("web (Next.js server :3001)", "Node.js 22 runtime", "Production build (next start); rewrites /api/* to port 8000."),
        ("backend.app (FastAPI :8000)", "Python 3.12 venv", "REST + SSE, monitoring sessions."),
        ("PyTorch 2.14 CPU runtime", "Python 3.12 venv", "Inference capped at 2 threads per process."),
        ("MDL-LSTM-100-80 (81 .pt files)", "Python 3.12 venv (models/ folder)", "One LSTM per labelled channel, about 29 MB."),
        ("orbital.db (SQLite, WAL)", "Local file system", "Config (D1) and log (D2) data stores."),
        ("data/ SMAP-MSL .npy (248 MB)", "Local file system", "NASA expert-labelled telemetry, replayed."),
        ("GP API (gp.php)", "CelesTrak Server", "TLE source."),
        ("nasa-anomaly-detection-dataset-smap-msl", "Kaggle", "Downloaded once by scripts/get_data.*"),
        ("Actions runners (Ubuntu, Windows)", "GitHub", "ci.yml: ruff, pytest, tsc, next build."),
    ], widths=[2.3, 1.7, 2.3], size=9)

    d.add_heading("4.3 Communication paths", level=3)
    table(d, ["Between", "Protocol", "Purpose"], [
        ("Analyst Workstation ↔ Application Host", "HTTP :3001 (JSON + SSE)", "Pages, API calls and live events."),
        ("Node.js runtime ↔ Python venv", "HTTP localhost:8000", "Next.js forwards /api/* to FastAPI (same origin for the browser)."),
        ("Application Host ↔ CelesTrak Server", "HTTPS", "TLE download, cached 2 h, 5 s timeout, 10 min back-off."),
        ("Application Host ↔ Kaggle", "HTTPS", "One-off dataset download."),
        ("Application Host ↔ GitHub", "HTTPS", "git push; CI runs on every push."),
    ], widths=[2.4, 1.6, 2.3], size=9)

    d.add_heading("4.4 Deployment Diagram", level=3)
    figure(d, img / "Exp8_Deployment.jpg", "Figure 3: Deployment Diagram – Orbital Sentinel")
    d.add_paragraph("The note on the diagram records the honest deployment: this is a proof of concept, so in the demo "
                    "the workstation and the application host are the same laptop and the browser opens "
                    "http://localhost:3001.")

    d.add_heading("5. Procedure Followed", level=2)
    numbered(d, [
        "Opened StarUML and created a new project (saved as docs/uml/Exp8_Package_Component_Deployment.mdj).",
        "Created a Package Diagram; added the web, backend.app and ml packages with their sub-packages, arranged in layers.",
        "Connected packages with dependency relationships taken from the actual import statements in the code.",
        "Created a Component Diagram; added the browser, backend, data and external components.",
        "Added provided interfaces (lollipop) and required interfaces (socket), plus «use» and «read» dependencies.",
        "Created a Deployment Diagram; added the device nodes for the workstation, the application host and the external services.",
        "Placed the execution environments inside the nodes and the artifacts inside the execution environments.",
        "Connected the nodes with communication paths labelled with their protocol.",
        "Checked notation and relationships, re-arranged elements so that no line crosses a box, and saved the project.",
    ])
    d.add_paragraph("Element creation was scripted through StarUML's extension API (source in "
                    "docs/uml/staruml-extension/main.js) so that every name matches the code exactly; the layout was "
                    "then checked and adjusted in StarUML.")

    d.add_heading("6. Design Notes", level=2)
    for lead, text in [
        ("Layering. ", "Dependencies point downwards: api → services/pipeline → models → core. The browser reaches "
         "the backend only through the HTTP interface, never through shared code."),
        ("Cycles made visible and narrowed. ", "At package level there are two import cycles (pipeline ↔ services and "
         "models ↔ core). Drawing the sub-packages shows that each is really between different modules "
         "(pipeline → services.events while services.sessions → pipeline; models → core.db while core.security → models), "
         "so no single module depends on itself. Moving events into its own top-level package would remove the cycle entirely."),
        ("main.py is not drawn. ", "backend/app/main.py is a module (the FastAPI entry point that wires the routers), not a "
         "package, so it is not shown on the package diagram."),
        ("Replaceable components. ", "The Detector and ORM Session interfaces are the planned replacement points "
         "(a different model; Postgres instead of SQLite)."),
    ]:
        para(d, text, bold_lead=lead)

    d.add_heading("7. Full-Screen Screenshots (with timestamp)", level=2)
    d.add_paragraph("Screenshots of StarUML with the project open; the Windows taskbar clock shows the date and time.")
    figure(d, img / "Exp8_Package_screenshot.jpg", "Figure 4: Package Diagram open in StarUML, with system timestamp")
    figure(d, img / "Exp8_Component_screenshot.jpg", "Figure 5: Component Diagram open in StarUML, with system timestamp")
    figure(d, img / "Exp8_Deployment_screenshot.jpg", "Figure 6: Deployment Diagram open in StarUML, with system timestamp")

    d.add_heading("8. Submission Checklist", level=2)
    checklist(d, [
        "Major functional modules identified (Section 3.1)",
        "Package Diagram with packages and dependencies (Figure 1)",
        "Component Diagram with components, interfaces and dependencies (Figure 2)",
        "Hardware/environment nodes identified (Section 4.1)",
        "Deployment Diagram with devices, execution environments, deployed artifacts and communication paths (Figure 3)",
        "UML notation and relationships checked",
        "StarUML project saved (docs/uml/Exp8_Package_Component_Deployment.mdj)",
        "Timestamp screenshots attached (Section 7)",
    ])

    d.add_heading("9. Result", level=2)
    d.add_paragraph(
        "The Package, Component and Deployment models of the Orbital Sentinel system were designed in StarUML. The package "
        "diagram shows 3 top-level packages and 19 sub-packages with their real import dependencies; the component diagram "
        "shows 18 components and 7 interfaces; the deployment diagram shows 5 device nodes, 4 execution environments, "
        "12 deployed artifacts and 5 communication paths. Together they describe how the code is organised, how the "
        "running parts talk to each other, and where each part runs.")
    keep_headings_with_next(d)
    out = DOCS / "Exp8_package_component_deployment.docx"
    d.save(str(out))
    return out


if __name__ == "__main__":
    for path in (build_exp6(), build_exp8()):
        print("wrote", path)
