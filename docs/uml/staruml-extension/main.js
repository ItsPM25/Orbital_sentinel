/*
 * Orbital Sentinel OO diagram generator.
 *
 * Tools > Orbital Sentinel: Exp 6  -> Use Case diagram, Domain class diagram,
 *                                     Detection-pipeline class diagram
 * Tools > Orbital Sentinel: Exp 8  -> Package, Component and Deployment diagrams
 *
 * Every class, package and component name matches the code in
 * github.com/ItsPM25/Orbital_sentinel (backend/app, web/).
 */

const VIS = { '+': 'public', '-': 'private', '#': 'protected', '~': 'package' }

function rootModel () {
  const project = app.project.getProject()
  return project.ownedElements.find(e => e instanceof type.UMLModel) || project
}

function newDiagram (kind, parent, name) {
  return app.factory.createDiagram({
    id: kind,
    parent: parent,
    diagramInitializer: (d) => { d.name = name }
  })
}

function box (diagram, id, parent, x, y, w, h, init, extra) {
  return app.factory.createModelAndView(Object.assign({
    id: id,
    parent: parent,
    diagram: diagram,
    x1: x,
    y1: y,
    x2: x + w,
    y2: y + h,
    modelInitializer: (m) => { if (init) init(m) }
  }, extra || {}))
}

function link (diagram, id, tail, head, init) {
  return app.factory.createModelAndView({
    id: id,
    parent: tail.model,
    diagram: diagram,
    tailView: tail,
    tailModel: tail.model,
    headView: head,
    headModel: head.model,
    x1: tail.left + tail.width / 2,
    y1: tail.top + tail.height / 2,
    x2: head.left + head.width / 2,
    y2: head.top + head.height / 2,
    modelInitializer: (m) => { if (init) init(m) }
  })
}

function named (name, stereotype, doc) {
  return (m) => {
    m.name = name
    if (stereotype) m.stereotype = stereotype
    if (doc) m.documentation = doc
  }
}

// Splits "a: T, b: Map<K,V>" on top-level commas only.
function splitTop (s) {
  const out = []
  let depth = 0
  let cur = ''
  for (const ch of s) {
    if (ch === '<' || ch === '[' || ch === '(') depth++
    if (ch === '>' || ch === ']' || ch === ')') depth--
    if (ch === ',' && depth === 0) {
      out.push(cur)
      cur = ''
    } else {
      cur += ch
    }
  }
  if (cur.trim()) out.push(cur)
  return out.map(p => p.trim()).filter(Boolean)
}

function nameType (s) {
  const i = s.indexOf(':')
  if (i < 0) return { name: s.trim(), type: '' }
  return { name: s.slice(0, i).trim(), type: s.slice(i + 1).trim() }
}

// "-name: Type = default"  or  "+op(a: T, b: U): R"
function addMembers (cls, list) {
  list.forEach((raw) => {
    const vis = VIS[raw[0]] || 'public'
    const body = VIS[raw[0]] ? raw.slice(1).trim() : raw.trim()
    const paren = body.indexOf('(')
    if (paren < 0) {
      const nt = nameType(body)
      let t = nt.type
      let dv = null
      const eq = t.indexOf('=')
      if (eq >= 0) {
        dv = t.slice(eq + 1).trim()
        t = t.slice(0, eq).trim()
      }
      app.factory.createModel({
        id: 'UMLAttribute',
        parent: cls,
        field: 'attributes',
        modelInitializer: (a) => {
          a.name = nt.name
          a.type = t
          a.visibility = vis
          if (dv !== null) a.defaultValue = dv
        }
      })
      return
    }
    const close = body.lastIndexOf(')')
    const opName = body.slice(0, paren).trim()
    const params = splitTop(body.slice(paren + 1, close)).map(nameType)
    const ret = body.slice(close + 1).replace(/^\s*:/, '').trim()
    const op = app.factory.createModel({
      id: 'UMLOperation',
      parent: cls,
      field: 'operations',
      modelInitializer: (o) => {
        o.name = opName
        o.visibility = vis
      }
    })
    params.forEach((p) => {
      app.factory.createModel({
        id: 'UMLParameter',
        parent: op,
        field: 'parameters',
        modelInitializer: (x) => {
          x.name = p.name
          x.type = p.type
          x.direction = 'in'
        }
      })
    })
    if (ret) {
      app.factory.createModel({
        id: 'UMLParameter',
        parent: op,
        field: 'parameters',
        modelInitializer: (x) => {
          x.name = ''
          x.type = ret
          x.direction = 'return'
        }
      })
    }
  })
}

function addLiterals (en, names) {
  names.forEach((n) => {
    app.factory.createModel({
      id: 'UMLEnumerationLiteral',
      parent: en,
      field: 'literals',
      modelInitializer: (l) => { l.name = n }
    })
  })
}

function setView (view, props) {
  Object.keys(props).forEach((k) => { app.engine.setProperty(view, k, props[k]) })
}

function assoc (d, whole, part, o) {
  return link(d, 'UMLAssociation', whole, part, (m) => {
    if (o.name) m.name = o.name
    m.end1.multiplicity = o.m1 || ''
    m.end2.multiplicity = o.m2 || ''
    if (o.agg) m.end1.aggregation = o.agg
    if (o.role2) m.end2.name = o.role2
    if (o.nav) m.end2.navigable = 'navigable'
  })
}

function dep (d, from, to, stereotype, name) {
  const v = link(d, 'UMLDependency', from, to, (m) => {
    if (stereotype) m.stereotype = stereotype
    if (name) m.name = name
  })
  if (name) setView(v, { showVisibility: false })
  return v
}

function note (d, x, y, w, h, text) {
  const v = new type.UMLNoteView()
  v._parent = d
  v.wordWrap = true
  v.autoResize = false
  v.text = text
  v.initialize(null, x, y, x + w, y + h)
  app.engine.addViews(d, [v])
  return v
}

/* ------------------------------------------------------------------ */
/* Exp 6: Use case diagram                                             */
/* ------------------------------------------------------------------ */

function buildUseCase (owner) {
  const d = newDiagram('UMLUseCaseDiagram', owner, 'Use Case Diagram')
  const UCW = 230
  const UCH = 48
  const L = 360
  const M = 640
  const row = (i) => 50 + i * 82

  box(d, 'UMLUseCaseSubject', owner, 320, 15, 600, 940, named('Orbital Sentinel'))

  const uc = {}
  const put = (key, x, i, doc) => {
    uc[key] = box(d, 'UMLUseCase', owner, x, row(i), UCW, UCH, named(key, null, doc))
  }
  put('Log in', L, 0, 'Sign in with e-mail and password; a signed httpOnly cookie carries the role (SRS 5.3).')
  put('View risk-ranked alerts', L, 1, 'REQ-16: alert list ordered by risk with verdict, severity and attributed channel.')
  put('Inspect satellite health', L, 2, 'REQ-15/17: health panel with verdict, risk, score and attributed channels.')
  put('Track fleet on 3D globe', L, 3, 'REQ-12..14: real positions from TLE + SGP4, coloured by risk.')
  put('Acknowledge alert', L, 4, 'AlertRaised -> Acknowledged (state diagram, Exp 5).')
  put('View accuracy metrics', L, 5, 'REQ-5/11: precision, recall, F1, FPR with and without the persistence filter.')
  put('Browse detection log', L, 6, 'REQ-18: every detection with timestamp, score, channel, severity and outcome.')
  put('View trained models', L, 7, 'Model registry (MDL-LSTM-100-80).')
  put('Start/stop monitoring session', L, 8, 'Starts the per-satellite replay -> LSTM -> lifecycle pipeline.')
  put('Configure thresholds', L, 9, 'REQ-8/9: persistence N and severity threshold per satellite.')
  put('Import dataset', L, 10, 'REQ-1: register the NASA SMAP/MSL channels.')
  put('View telemetry chart', M, 1.7, 'REQ-17: telemetry plot with flagged ranges shaded.')
  put('Change simulation speed', M + 40, 4.4, 'Live / 10x / 60x / 300x simulation clock.')
  put('Fetch TLE data', M, 3.15, 'REQ-12: download TLEs from CelesTrak, cached for 2 h.')

  const actor = (name, x, y, doc, stereo) =>
    box(d, 'UMLActor', owner, x, y, 40, 72, named(name, stereo, doc))
  const user = actor('User', 140, 150, 'Any signed-in person (abstract).')
  const analyst = actor('Analyst', 50, 360, 'Operator who watches and acknowledges alerts.')
  const evaluator = actor('Evaluator', 220, 510, 'Read-only reviewer of results, logs and metrics.')
  const admin = actor('Administrator', 130, 760, 'Runs monitoring, sets thresholds, imports data.')
  const celestrak = actor('CelesTrak', 980, 285, 'External system: public TLE (GP) API.', 'external system')
  app.engine.setProperty(user.model, 'isAbstract', true)

  link(d, 'UMLGeneralization', analyst, user)
  link(d, 'UMLGeneralization', evaluator, user)
  link(d, 'UMLGeneralization', admin, analyst)
  link(d, 'UMLGeneralization', admin, evaluator)

  const a = (act, key) => link(d, 'UMLAssociation', act, uc[key])
  ;['Log in', 'View risk-ranked alerts', 'Inspect satellite health', 'Track fleet on 3D globe'].forEach(k => a(user, k))
  a(analyst, 'Acknowledge alert')
  ;['View accuracy metrics', 'Browse detection log', 'View trained models'].forEach(k => a(evaluator, k))
  ;['Start/stop monitoring session', 'Configure thresholds', 'Import dataset'].forEach(k => a(admin, k))
  a(celestrak, 'Fetch TLE data')

  link(d, 'UMLInclude', uc['Track fleet on 3D globe'], uc['Fetch TLE data'])
  link(d, 'UMLExtend', uc['Inspect satellite health'], uc['View risk-ranked alerts'])
  link(d, 'UMLExtend', uc['Inspect satellite health'], uc['Track fleet on 3D globe'])
  link(d, 'UMLExtend', uc['View telemetry chart'], uc['Inspect satellite health'])
  link(d, 'UMLExtend', uc['Change simulation speed'], uc['Track fleet on 3D globe'])
  return d
}

/* ------------------------------------------------------------------ */
/* Exp 6: Class diagrams                                               */
/* ------------------------------------------------------------------ */

function cls (d, pkg, name, x, y, w, members, opts) {
  opts = opts || {}
  const v = box(d, opts.kind || 'UMLClass', pkg, x, y, w, 40, (m) => {
    m.name = name
    if (opts.stereotype) m.stereotype = opts.stereotype
    if (opts.abstract) m.isAbstract = true
    if (opts.doc) m.documentation = opts.doc
  })
  if (opts.literals) addLiterals(v.model, opts.literals)
  if (members) addMembers(v.model, members)
  return v
}

function buildDomain (owner) {
  const pkg = app.factory.createModel({ id: 'UMLPackage', parent: owner, modelInitializer: m => { m.name = 'domain (backend/app/models)' } })
  const d = newDiagram('UMLClassDiagram', pkg, 'Class Diagram - Domain Model')
  const C = [30, 330, 650, 980, 1300]
  const R = [30, 400, 760]

  const role = cls(d, pkg, 'Role', C[0], R[0], 160, null, { kind: 'UMLEnumeration', literals: ['Analyst', 'Administrator', 'Evaluator'] })
  const user = cls(d, pkg, 'User', C[1], R[0], 250, [
    '-userId: String', '-firstName: String', '-lastName: String', '-role: Role',
    '-passwordHash: String', '-contactEmails: String[*]',
    '+verifyPassword(password: String): Boolean', '+hasRole(roles: Role[*]): Boolean', '+fullName(): String'
  ])
  const cfg = cls(d, pkg, 'MonitoringConfig', C[2], R[0], 260, [
    '-configId: String', '-persistenceThreshold: Integer = 3', '-severityThreshold: Float = 0.5',
    '-updatedAt: DateTime', '-isActive: Boolean',
    '+supersede(): void'
  ])
  const sat = cls(d, pkg, 'Satellite', C[3], R[0], 250, [
    '-satelliteId: String', '-name: String', '-noradId: Integer', '-tleLine1: String', '-tleLine2: String',
    '-tleFetchedAt: DateTime', '-currentStatus: String', '-isProxy: Boolean', '-telemetrySource: String', '-missionTags: String[*]',
    '+isTleStale(): Boolean', '+currentRiskLevel(): Integer'
  ])
  const chan = cls(d, pkg, 'Channel', C[4], R[0], 230, [
    '-channelId: String', '-channelName: String', '-unit: String', '-description: String',
    '-datasetChanId: String', '-spacecraft: String',
    '+loadSeries(split: String): Float[*]'
  ])
  const alertStatus = cls(d, pkg, 'AlertStatus', C[0], R[1], 160, null, { kind: 'UMLEnumeration', literals: ['AlertRaised', 'Acknowledged', 'Resolved'] })
  const alert = cls(d, pkg, 'Alert', C[1], R[1], 250, [
    '-alertId: String', '-riskLevel: Integer', '-status: AlertStatus', '-createdAt: DateTime',
    '-acknowledgedAt: DateTime', '-resolvedAt: DateTime',
    '+acknowledge(by: User): void', '+escalate(riskLevel: Integer): void', '+resolve(): void', '+riskBand(): SeverityLevel'
  ])
  const det = cls(d, pkg, 'Detection', C[2], R[1], 260, [
    '-detectionId: String', '-timestamp: DateTime', '-anomalyScore: Float', '-severityLevel: SeverityLevel',
    '-persistenceCount: Integer', '-windowStart: Integer', '-windowEnd: Integer', '-outcome: DetectionOutcome',
    '+isAnomaly(): Boolean', '+isConfirmed(): Boolean'
  ])
  const attr = cls(d, pkg, 'Attribution', C[3], R[1], 250, [
    '-attributionId: String', '-contributionScore: Float',
    '+asPercent(): Float'
  ])
  const reading = cls(d, pkg, 'TelemetryReading', C[4], R[1], 230, [
    '-readingId: Integer', '-timestamp: DateTime', '-value: Float', '-split: String', '-isLabeledAnomaly: Boolean',
    '+isValid(): Boolean'
  ])
  const severity = cls(d, pkg, 'SeverityLevel', C[0], R[2], 160, null, { kind: 'UMLEnumeration', literals: ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'] })
  const outcome = cls(d, pkg, 'DetectionOutcome', C[1], R[2], 170, null, { kind: 'UMLEnumeration', literals: ['Suppressed', 'Confirmed'] })
  const model = cls(d, pkg, 'DetectionModel', C[2], R[2], 260, [
    '-modelId: String', '-modelName: String', '-modelType: String', '-threshold: Float',
    '-trainedAt: DateTime', '-artifactPath: String', '-hyperparams: JSON',
    '+loadWeights(chanId: String): LstmPredictor'
  ])

  assoc(d, sat, chan, { m1: '1', m2: '1..*', agg: 'composite', name: 'has' })
  assoc(d, chan, reading, { m1: '1', m2: '*', agg: 'composite', name: 'records' })
  assoc(d, sat, det, { m1: '1', m2: '*', name: 'monitored by' })
  assoc(d, model, det, { m1: '1', m2: '*', name: 'produces' })
  assoc(d, det, attr, { m1: '1', m2: '0..3', agg: 'composite', name: 'explained by' })
  assoc(d, attr, chan, { m1: '*', m2: '1', name: 'blames', nav: true })
  assoc(d, det, alert, { m1: '1', m2: '0..1', name: 'raises' })
  assoc(d, user, alert, { m1: '0..1', m2: '*', name: 'acknowledges' })
  assoc(d, user, cfg, { m1: '1', m2: '*', name: 'sets' })
  assoc(d, sat, cfg, { m1: '1', m2: '*', agg: 'shared', name: 'configured by' })
  dep(d, user, role, null)
  dep(d, alert, alertStatus, null)
  dep(d, det, severity, null)
  dep(d, det, outcome, null)
  return d
}

function buildPipeline (owner) {
  const pkg = app.factory.createModel({ id: 'UMLPackage', parent: owner, modelInitializer: m => { m.name = 'pipeline (backend/app/pipeline, services, tracking)' } })
  const d = newDiagram('UMLClassDiagram', pkg, 'Class Diagram - Detection Pipeline')

  const registry = cls(d, pkg, 'SessionRegistry', 560, 20, 250, [
    '-running: Map<String,MonitoringSession>',
    '+startSession(satelliteId: String, modelId: String): MonitoringSession',
    '+stopSession(satelliteId: String): Boolean', '+listRunning(): String[*]'
  ], { doc: 'services/sessions.py' })
  const session = cls(d, pkg, 'MonitoringSession', 560, 230, 300, [
    '-satelliteId: String', '-modelId: String', '-persistenceN: Integer', '-severityThreshold: Float',
    '-counters: SessionCounters',
    '+run(): SessionCounters', '+runAsync(windowsPerSecond: Float): SessionCounters', '+stop(): void',
    '-processWindow(window: TelemetryWindow): void'
  ], { doc: 'pipeline/session.py' })
  const explain = cls(d, pkg, 'Explain', 20, 250, 330, [
    '+attribute(scores: ChannelScores): List<Attribution>',
    '+computeSeverity(score: Float, persistence: Integer, threshold: Float): SeverityLevel',
    '+riskLabel(risk: Integer): SeverityLevel', '+rankSatellites(): List<SatelliteRanking>'
  ], { stereotype: 'utility', doc: 'pipeline/explain/' })
  const bus = cls(d, pkg, 'EventBus', 990, 250, 260, [
    '-subscribers: Queue[*]',
    '+subscribe(): Queue', '+unsubscribe(queue: Queue): void', '+publish(event: String, satelliteId: String, data: JSON): void'
  ], { doc: 'services/events.py' })

  const replay = cls(d, pkg, 'ReplaySource', 20, 560, 250, [
    '-satelliteId: String', '-chanIds: String[*]',
    '+windows(): Iterator<TelemetryWindow>', '+length(): Integer'
  ], { doc: 'pipeline/ingest.py' })
  const lifecycle = cls(d, pkg, 'DetectionLifecycle', 400, 560, 300, [
    '-state: State', '-persistenceN: Integer', '-consecutive: Integer',
    '+processWindow(malformed: Boolean, score: Float, threshold: Float): WindowResult',
    '+userAck(): WindowResult', '+resolve(monitoringActive: Boolean): WindowResult'
  ], { doc: 'pipeline/lifecycle.py - the Exp 5 state machine' })
  const detector = cls(d, pkg, 'Detector', 990, 560, 280, [
    '+score(window: TelemetryWindow): ChannelScores'
  ], { kind: 'UMLInterface', doc: 'Python Protocol in pipeline/detect.py' })
  const win = cls(d, pkg, 'TelemetryWindow', 1400, 540, 260, [
    '+satelliteId: String', '+startIndex: Integer', '+endIndex: Integer', '+arrays: Map<String,Array>',
    '+timestamp: DateTime', '+malformed: Boolean'
  ], { doc: 'pipeline/types.py' })

  const norm = cls(d, pkg, 'Normaliser', 20, 830, 170, ['-mode: String', '+fit(train: Array): Normaliser', '+transform(data: Array): Array'])
  const windower = cls(d, pkg, 'Windower', 220, 830, 170, ['-history: Integer = 100', '-step: Integer = 70', '+starts(n: Integer): Integer[*]'])
  const scripted = cls(d, pkg, 'ScriptedDetector', 560, 830, 240, ['-script: Float[*]', '+score(window: TelemetryWindow): ChannelScores'], { doc: 'Test double used by the pytest suite.' })
  const lstm = cls(d, pkg, 'LstmDetector', 990, 830, 280, [
    '-channels: Map<String,ChannelState>', '+chanIds(): String[*]', '+score(window: TelemetryWindow): ChannelScores'
  ])
  const scores = cls(d, pkg, 'ChannelScores', 1400, 830, 260, [
    '+perChannel: Map<String,Float>', '+satelliteScore: Float', '+threshold: Float = 1.0',
    '+isAnomaly: Boolean', '+flaggedChannels: String[*]'
  ])

  const celestrak = cls(d, pkg, 'CelesTrakClient', 20, 1100, 280, [
    '-cacheHours: Integer = 2', '-timeoutSeconds: Integer = 5', '-backoffMinutes: Integer = 10',
    '+fetchDue(satellites: Satellite[*]): Map<Integer,TLE>', '+applyFetched(satellite: Satellite): Boolean', '+tlePayload(satellite: Satellite): JSON'
  ], { stereotype: 'utility', doc: 'tracking/celestrak.py' })
  const predictor = cls(d, pkg, 'LstmPredictor', 860, 1100, 260, [
    '-lstm: LSTM = 2 x 80 units', '-head: Linear = 80 -> 10', '+forward(x: Tensor): Tensor'
  ], { doc: 'pipeline/lstm.py' })
  const thresh = cls(d, pkg, 'StreamingThreshold', 1260, 1100, 250, [
    '-valueRange: Float', '-window: Integer = 2100', '-batch: Integer = 70', '+update(errors: Array): StepDecision'
  ], { doc: 'Non-parametric dynamic threshold (Hundman et al. 2018).' })
  const nnModule = cls(d, pkg, 'torch.nn.Module', 860, 1320, 260, ['+forward(x: Tensor): Tensor'], { stereotype: 'library', abstract: true })

  // Re-use the Satellite element from the domain model.
  let satView = null
  try {
    const satModel = app.repository.select('@UMLClass[name=Satellite]')[0]
    if (satModel) {
      satView = app.factory.createViewOf({ model: satModel, diagram: d, x: 440, y: 1110 })
      setView(satView, { suppressAttributes: true, suppressOperations: true, width: 230, height: 70 })
    }
  } catch (e) { console.error(e) }

  assoc(d, registry, session, { m1: '1', m2: '0..*', agg: 'shared', name: 'runs' })
  assoc(d, session, replay, { m1: '1', m2: '1', nav: true })
  assoc(d, session, lifecycle, { m1: '1', m2: '1', nav: true })
  assoc(d, session, detector, { m1: '*', m2: '1', nav: true })
  assoc(d, replay, norm, { m1: '1', m2: '1..*', agg: 'composite' })
  assoc(d, replay, windower, { m1: '1', m2: '1', agg: 'composite' })
  assoc(d, lstm, predictor, { m1: '1', m2: '1..*', agg: 'composite', role2: 'one per channel' })
  assoc(d, lstm, thresh, { m1: '1', m2: '1..*', agg: 'composite', role2: 'one per channel' })
  link(d, 'UMLInterfaceRealization', lstm, detector)
  link(d, 'UMLInterfaceRealization', scripted, detector)
  link(d, 'UMLGeneralization', predictor, nnModule)
  dep(d, session, explain, 'use')
  dep(d, session, bus, 'use')
  dep(d, detector, win, 'use')
  dep(d, detector, scores, 'create')
  if (satView) dep(d, celestrak, satView, 'update')

  setView(detector, { stereotypeDisplay: 'label', suppressAttributes: true, suppressOperations: false })
  return d
}

/* ------------------------------------------------------------------ */
/* Exp 8: Package diagram                                              */
/* ------------------------------------------------------------------ */

function pkgBox (d, parent, name, x, y, w, h, doc, stereo) {
  return box(d, 'UMLPackage', parent, x, y, w, h, named(name, stereo, doc))
}

function buildPackages (owner) {
  const d = newDiagram('UMLPackageDiagram', owner, 'Package Diagram')

  // web/
  const web = pkgBox(d, owner, 'web (Next.js 15 + React 19)', 20, 20, 330, 470, 'Frontend, served on port 3001.')
  const wApp = pkgBox(d, web.model, 'app (pages)', 60, 90, 160, 70, 'login, dashboard, globe, satellites, evaluation, admin')
  const wComp = pkgBox(d, web.model, 'components', 60, 230, 160, 70, 'app-shell, page-header, risk, ui (shadcn)')
  const wLib = pkgBox(d, web.model, 'lib', 140, 370, 160, 70, 'api.ts, useStream, useCoalesced, sgp4.ts, risk.ts')

  // ml/
  const ml = pkgBox(d, owner, 'ml', 20, 700, 330, 170, 'Machine-learning experiments')
  const spike = pkgBox(d, ml.model, 'spike', 120, 775, 140, 70, 'Phase 1 model-selection spike (throwaway prototype, Increment 0)')

  // backend/app
  const be = pkgBox(d, owner, 'backend.app (FastAPI, Python 3.12)', 420, 20, 980, 880, 'Backend, served on port 8000. Entry module: main.py')
  const bTrack = pkgBox(d, be.model, 'tracking', 680, 200, 150, 70, 'CelesTrak client, TLE cache, bundled snapshot')
  const bApi = pkgBox(d, be.model, 'api', 460, 420, 150, 70, 'routers: auth, alerts, satellites, detections, ranking, stream, sessions, admin, evaluation, tle')
  const bSchemas = pkgBox(d, be.model, 'schemas', 460, 560, 150, 70, 'Pydantic request/response models')
  const bServices = pkgBox(d, be.model, 'services', 860, 170, 330, 170, 'Runtime services')
  const sEvents = pkgBox(d, bServices.model, 'events', 880, 240, 130, 70, 'SSE publish/subscribe bus')
  const sSessions = pkgBox(d, bServices.model, 'sessions', 1040, 240, 130, 70, 'Monitoring session registry')
  const bPipe = pkgBox(d, be.model, 'pipeline', 860, 400, 360, 160, 'dataset, ingest, lstm, train, detect, lifecycle, session, fleet, import_dataset')
  pkgBox(d, bPipe.model, 'explain', 1060, 470, 140, 70, 'attribution, severity, ranking')
  const bEval = pkgBox(d, be.model, 'evaluation', 1260, 440, 120, 70, 'metrics, baseline report, REQ-11 reports')
  const bModels = pkgBox(d, be.model, 'models', 680, 700, 150, 70, 'SQLAlchemy tables, one class per ER entity')
  const bCore = pkgBox(d, be.model, 'core', 860, 650, 520, 210, 'settings, db, security')
  const cDb = pkgBox(d, bCore.model, 'db', 880, 770, 130, 70, 'SQLite engine (WAL), session factory, Base')
  pkgBox(d, bCore.model, 'settings', 1040, 770, 130, 70, 'OS_* environment settings')
  const cSec = pkgBox(d, bCore.model, 'security', 1220, 700, 130, 70, 'argon2 hashing, signed cookie, require_roles')

  dep(d, wApp, wComp)
  dep(d, wApp, wLib)
  dep(d, wComp, wLib)
  dep(d, wLib, bApi, null, 'HTTP/JSON + SSE')
  dep(d, spike, bPipe)

  dep(d, bApi, bTrack)
  dep(d, bApi, bSchemas)
  dep(d, bApi, sSessions)
  dep(d, bApi, bPipe)
  dep(d, bApi, bModels)
  dep(d, bApi, cSec)
  dep(d, bSchemas, bModels)
  dep(d, bSchemas, bPipe)
  dep(d, bTrack, bModels)
  dep(d, sSessions, bPipe)
  dep(d, bPipe, sEvents)
  dep(d, bPipe, bModels)
  dep(d, bPipe, cDb)
  dep(d, bEval, bPipe)
  dep(d, bModels, cDb)
  dep(d, cSec, bModels)
  return d
}

/* ------------------------------------------------------------------ */
/* Exp 8: Component diagram                                            */
/* ------------------------------------------------------------------ */

function buildComponents (owner) {
  const d = newDiagram('UMLComponentDiagram', owner, 'Component Diagram')
  const comp = (name, x, y, w, doc, stereo) => box(d, 'UMLComponent', owner, x, y, w || 190, 60, named(name, stereo, doc))
  const iface = (name, x, y, doc) => {
    const v = box(d, 'UMLInterface', owner, x, y, 30, 30, named(name, null, doc))
    setView(v, { stereotypeDisplay: 'icon' })
    return v
  }
  const provides = (c, i) => link(d, 'UMLInterfaceRealization', c, i)
  const requires = (c, i) => dep(d, c, i, null)

  // Browser
  const pages = comp('UI Pages', 520, 30, 200, 'web/app: login, dashboard, globe, satellites, evaluation, admin')
  const globe = comp('Globe Renderer', 40, 150, 190, 'globe.gl 2.46 + three.js 0.186 (WebGL)')
  const sgp4 = comp('Orbit Propagator', 280, 150, 190, 'web/lib/sgp4.ts using satellite.js (SGP4)')
  const client = comp('API Client', 760, 150, 190, 'web/lib/api.ts (typed fetch client)')
  const stream = comp('Live Stream Hook', 1000, 150, 190, 'web/lib/useStream.ts + useCoalesced.ts')
  dep(d, pages, globe, 'use')
  dep(d, pages, sgp4, 'use')
  dep(d, pages, client, 'use')
  dep(d, pages, stream, 'use')

  const iRest = iface('REST (HTTP/JSON)', 840, 290, '/api/* routes, JSON in camelCase')
  const iSse = iface('SSE /api/stream', 1080, 290, 'detection, alert.created, alert.updated, ranking events')
  requires(client, iRest)
  requires(stream, iSse)

  // Backend
  const api = comp('REST API Routers', 900, 400, 200, 'backend/app/api (FastAPI)')
  provides(api, iRest)
  provides(api, iSse)
  const auth = comp('Auth & Roles', 1200, 400, 170, 'core/security.py: argon2, signed cookie, require_roles')
  dep(d, api, auth, 'use')

  const iSession = iface('ISessionControl', 700, 420, 'start_session / stop_session / list_running')
  const mgr = comp('Session Manager', 440, 400, 190, 'services/sessions.py')
  provides(mgr, iSession)
  requires(api, iSession)

  const iDetector = iface('Detector', 360, 560, 'score(window) -> ChannelScores (Python Protocol)')
  const pipe = comp('Detection Pipeline', 40, 540, 220, 'ingest -> LSTM -> dynamic threshold -> lifecycle (pipeline/)')
  provides(pipe, iDetector)
  requires(mgr, iDetector)

  const explain = comp('Explain Engine', 40, 400, 220, 'pipeline/explain: attribution, severity, ranking')
  dep(d, pipe, explain, 'use')

  const iPublish = iface('IEventPublish', 800, 650, 'publish(event, satelliteId, data)')
  const bus = comp('Event Bus', 900, 560, 190, 'services/events.py (in-process pub/sub)')
  provides(bus, iPublish)
  requires(pipe, iPublish)
  dep(d, api, bus, 'subscribe')

  const tle = comp('TLE Tracker', 1200, 560, 170, 'tracking/celestrak.py: 2 h cache, 5 s timeout, 10 min backoff')
  dep(d, api, tle, 'use')
  const evalc = comp('Evaluation', 390, 690, 190, 'evaluation/: metrics, baseline, REQ-11 reports')
  dep(d, api, evalc, 'use')
  dep(d, evalc, pipe, 'use')

  const iOrm = iface('ORM Session', 760, 760, 'SQLAlchemy 2 Session')
  const orm = comp('Persistence (ORM)', 900, 740, 190, 'models/ + core/db.py (SQLAlchemy 2, Alembic)')
  provides(orm, iOrm)
  requires(api, iOrm)
  requires(pipe, iOrm)
  requires(tle, iOrm)

  // Data and external
  const db = comp('SQLite Database', 900, 900, 190, 'backend/orbital.db, WAL mode', 'database')
  const store = comp('Model Store', 40, 860, 220, 'models/MDL-LSTM-100-80: 81 .pt weight files', 'file')
  const data = comp('Telemetry Dataset', 300, 860, 220, 'data/: NASA SMAP/MSL .npy + labeled_anomalies.csv', 'file')
  dep(d, orm, db, 'use')
  dep(d, pipe, store, 'read')
  dep(d, pipe, data, 'read')

  const iTle = iface('GP API (HTTPS)', 1270, 760, 'https://celestrak.org/NORAD/elements/gp.php')
  const ct = comp('CelesTrak', 1200, 880, 170, 'External TLE provider', 'external')
  provides(ct, iTle)
  requires(tle, iTle)
  return d
}

/* ------------------------------------------------------------------ */
/* Exp 8: Deployment diagram                                           */
/* ------------------------------------------------------------------ */

function buildDeployment (owner) {
  const d = newDiagram('UMLDeploymentDiagram', owner, 'Deployment Diagram')
  const node = (parent, name, stereo, x, y, w, h, doc) => box(d, 'UMLNode', parent, x, y, w, h, named(name, stereo, doc))
  const artifact = (parent, name, x, y, w, doc) => {
    const v = box(d, 'UMLArtifact', parent, x, y, w || 200, 45, named(name, null, doc))
    setView(v, { stereotypeDisplay: 'decoration' })
    return v
  }
  const path = (a, b, name) => {
    const v = link(d, 'UMLCommunicationPath', a, b, (m) => { m.name = name })
    setView(v, { showVisibility: false })
    return v
  }

  const ws = node(owner, 'Analyst Workstation', 'device', 20, 40, 380, 430, 'Any PC or laptop on the network (in the demo: the same laptop).')
  const browser = node(ws.model, 'Web Browser (Chrome / Firefox)', 'executionEnvironment', 45, 110, 320, 340, 'WebGL-capable browser')
  artifact(browser.model, 'Next.js client bundle (JS)', 70, 175, 260, 'React 19 pages, shadcn/ui, Recharts')
  artifact(browser.model, 'globe.gl + three.js', 70, 265, 260, 'WebGL globe renderer')
  artifact(browser.model, 'satellite.js (SGP4)', 70, 355, 260, 'Orbit propagation every frame')

  const host = node(owner, 'Application Host (Windows 11 laptop)', 'device', 500, 40, 520, 900, 'Reference machine: Intel i5-13420H, 12 logical CPUs, 16 GB RAM')
  const nodeRt = node(host.model, 'Node.js 22 runtime', 'executionEnvironment', 530, 110, 460, 140, 'next start (production build)')
  artifact(nodeRt.model, 'web (Next.js server :3001)', 560, 175, 300, 'Serves pages; rewrites /api/* to :8000')
  const py = node(host.model, 'Python 3.12 venv (Uvicorn)', 'executionEnvironment', 530, 300, 460, 330, 'uvicorn app.main:app --port 8000')
  artifact(py.model, 'backend.app (FastAPI :8000)', 560, 365, 300, 'REST + SSE, monitoring sessions')
  artifact(py.model, 'PyTorch 2.14 CPU runtime', 560, 455, 300, '2 inference threads per process')
  artifact(py.model, 'MDL-LSTM-100-80 (81 .pt files)', 560, 545, 300, 'models/ folder')
  const fs = node(host.model, 'Local file system', 'executionEnvironment', 530, 670, 460, 250, 'NTFS disk')
  artifact(fs.model, 'orbital.db (SQLite, WAL)', 560, 735, 300, 'D1 Config + D2 Log')
  artifact(fs.model, 'data/ SMAP-MSL .npy (248 MB)', 560, 825, 300, 'NASA expert-labelled telemetry')

  const ct = node(owner, 'CelesTrak Server', 'device', 1120, 40, 370, 200, 'celestrak.org (external)')
  artifact(ct.model, 'GP API (gp.php, TLE format)', 1145, 130, 310, 'Public orbital elements')
  const kg = node(owner, 'Kaggle', 'device', 1120, 330, 370, 240, 'kaggle.com (external, one-off)')
  artifact(kg.model, 'nasa-anomaly-detection-dataset-smap-msl', 1145, 480, 310, 'Mirror of the Telemanom dataset (about 86 MB zipped)')
  const gh = node(owner, 'GitHub', 'device', 1120, 640, 370, 200, 'github.com/ItsPM25/Orbital_sentinel')
  artifact(gh.model, 'Actions runners (Ubuntu, Windows)', 1145, 730, 310, 'ci.yml: ruff, pytest, tsc, next build')

  path(ws, host, 'HTTP :3001 (JSON + SSE)')
  path(nodeRt, py, 'HTTP localhost:8000 (/api rewrite)')
  path(host, ct, 'HTTPS (TLE, cached 2 h)')
  path(host, kg, 'HTTPS (dataset download, one-off)')
  path(host, gh, 'HTTPS (git push, CI)')

  note(d, 20, 520, 380, 120, 'Proof of concept: in the demo every node except CelesTrak, Kaggle and GitHub runs on one laptop, and the browser opens http://localhost:3001. Health telemetry is a replay; only orbital positions are live.')
  return d
}

/* ------------------------------------------------------------------ */

function run (label, builder) {
  try {
    const first = builder()
    app.diagrams.setCurrentDiagram(first)
    app.diagrams.repaint()
  } catch (err) {
    console.error(err)
    app.dialogs.showErrorDialog('Failed: ' + (err.stack || err.message || err))
  }
}

function exp6 () {
  run('Exp 6', () => {
    const owner = rootModel()
    app.engine.setProperty(app.project.getProject(), 'name', 'Orbital Sentinel - Exp 6')
    const uc = buildUseCase(owner)
    buildDomain(owner)
    buildPipeline(owner)
    return uc
  })
}

function exp8 () {
  run('Exp 8', () => {
    const owner = rootModel()
    app.engine.setProperty(app.project.getProject(), 'name', 'Orbital Sentinel - Exp 8')
    const p = buildPackages(owner)
    buildComponents(owner)
    buildDeployment(owner)
    return p
  })
}

function init () {
  app.commands.register('orbital-oo:exp6', exp6, 'Orbital Sentinel: Exp 6 diagrams')
  app.commands.register('orbital-oo:exp8', exp8, 'Orbital Sentinel: Exp 8 diagrams')
}

exports.init = init
