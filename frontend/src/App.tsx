import { useCallback, useEffect, useRef, useState } from "react";
import type { DragEvent, ReactNode } from "react";
import {
  ArrowDownToLine,
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  Binary as BinaryIcon,
  Check,
  ChevronRight,
  CircleHelp,
  Clock3,
  Cpu,
  FileCode2,
  FlaskConical,
  FolderOpen,
  GitCompareArrows,
  Info,
  Layers3,
  LoaderCircle,
  LockKeyhole,
  PanelLeftClose,
  Plug,
  Plus,
  ScanLine,
  Search,
  ShieldCheck,
  Terminal,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import { address, api, post, size } from "./api";
import type {
  Binary,
  Capabilities,
  Comparison,
  Experiment,
  FunctionDetail,
  Job,
  Page,
  QueryResult,
  ResearchStatus,
  Summary,
} from "./api";
import Evidence from "./components/Evidence";

type Tab = "workspace" | "compare" | "research" | "integrations";
const labels: Record<Tab, string> = {
  workspace: "Workspace",
  compare: "Compare binaries",
  research: "Research",
  integrations: "Integrations",
};
const icons: Record<Tab, typeof Layers3> = {
  workspace: Layers3,
  compare: GitCompareArrows,
  research: FlaskConical,
  integrations: Plug,
};
const running = (status: string) => ["queued", "running"].includes(status);
function Status({ value }: { value: string }) {
  return (
    <span className={`status status-${value}`}>
      {running(value) ? (
        <LoaderCircle size={11} className="spin" />
      ) : value === "completed" ? (
        <span className="status-dot" />
      ) : null}
      {value === "completed"
        ? "Ready"
        : value[0].toUpperCase() + value.slice(1)}
    </span>
  );
}
function SectionHeading({
  eyebrow,
  title,
  description,
  children,
}: {
  eyebrow: string;
  title: string;
  description: string;
  children?: ReactNode;
}) {
  return (
    <div className="section-heading">
      <div>
        <span className="eyebrow">{eyebrow}</span>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {children && <div>{children}</div>}
    </div>
  );
}
function Metric({
  label,
  value,
  icon: Icon,
  note,
}: {
  label: string;
  value: string | number;
  icon: typeof Layers3;
  note: string;
}) {
  return (
    <div className="metric">
      <div>
        <span>{label}</span>
        <Icon size={16} />
      </div>
      <strong>{value}</strong>
      <small>{note}</small>
    </div>
  );
}

export default function App() {
  const [tab, setTab] = useState<Tab>("workspace");
  const [binaries, setBinaries] = useState<Binary[]>([]),
    [jobs, setJobs] = useState<Job[]>([]);
  const [caps, setCaps] = useState<Capabilities | null>(null),
    [online, setOnline] = useState(false);
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [selected, setSelected] = useState<Binary | null>(null);
  const [source, setSource] = useState(""),
    [target, setTarget] = useState(""),
    [query, setQuery] = useState("");
  const [showJobs, setShowJobs] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const report = useCallback(
    (e: unknown) => setError(e instanceof Error ? e.message : String(e)),
    [],
  );
  const refresh = useCallback(async () => {
    try {
      const [bs, js, cs] = await Promise.all([
        api<Page<Binary>>("/binaries?limit=100"),
        api<Page<Job>>("/jobs?limit=100"),
        api<Capabilities>("/capabilities"),
      ]);
      setBinaries(bs.items);
      setJobs(js.items);
      setCaps(cs);
      setOnline(true);
      setSelected((old) =>
        old ? (bs.items.find((b) => b.id === old.id) ?? null) : null,
      );
    } catch {
      setOnline(false);
    }
  }, []);
  useEffect(() => {
    void refresh();
    const timer = setInterval(() => void refresh(), 1800);
    return () => clearInterval(timer);
  }, [refresh]);
  useEffect(() => {
    const ready = binaries.filter((b) => b.status === "completed");
    if (!source && ready[0]) setSource(ready[0].id);
    if (!target && ready[1]) setTarget(ready[1].id);
  }, [binaries, source, target]);
  const upload = async (file: File) => {
    setBusy(true);
    setError("");
    try {
      const form = new FormData();
      form.append("file", file);
      const result = await api<{ binary: Binary }>("/binaries", {
        method: "POST",
        body: form,
      });
      await refresh();
      setSelected(result.binary);
      setTab("workspace");
    } catch (e) {
      report(e);
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };
  const demo = async () => {
    setBusy(true);
    setError("");
    try {
      await post("/demo");
      await refresh();
    } catch (e) {
      report(e);
    } finally {
      setBusy(false);
    }
  };
  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file) void upload(file);
  };
  const activeJobs = jobs.filter((j) => running(j.state));
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a
          href="#"
          className="brand"
          onClick={(e) => {
            e.preventDefault();
            setTab("workspace");
            setSelected(null);
          }}
        >
          <span className="brand-mark">
            <ScanLine size={24} />
          </span>
          <span>
            RECON<small>BINARY INTELLIGENCE</small>
          </span>
        </a>
        <div className="sidebar-label">ANALYSIS</div>
        <nav>
          {(Object.keys(labels) as Tab[]).map((key) => {
            const Icon = icons[key];
            return (
              <button
                key={key}
                className={tab === key ? "nav-item active" : "nav-item"}
                onClick={() => {
                  setTab(key);
                  if (key === "workspace") setSelected(null);
                }}
              >
                <Icon size={18} />
                {labels[key]}
                {key === "workspace" && binaries.length > 0 && (
                  <span className="nav-count">{binaries.length}</span>
                )}
              </button>
            );
          })}
        </nav>
        <div className="sidebar-divider" />
        <div className="sidebar-label">
          RECENT BINARIES <span>{binaries.length}</span>
        </div>
        <div className="recent-list">
          {binaries.slice(0, 6).map((b) => (
            <button
              key={b.id}
              className={
                selected?.id === b.id && tab === "workspace" ? "selected" : ""
              }
              onClick={() => {
                setSelected(b);
                setTab("workspace");
              }}
            >
              <FileCode2 size={15} />
              <span>{b.filename}</span>
              <i className={`tiny-dot ${b.status}`} />
            </button>
          ))}
          {!binaries.length && <p>Imported binaries will appear here.</p>}
        </div>
        <div className="sidebar-bottom">
          <div className="local-card">
            <ShieldCheck size={18} />
            <div>
              Local by default<small>Your binaries stay on this machine.</small>
            </div>
          </div>
          <button className="connection" onClick={() => setShowJobs((v) => !v)}>
            <i className={online ? "green-light" : "red-light"} />
            <span>
              {online ? "Local engine connected" : "Engine unavailable"}
            </span>
            <span className="version">v0.1</span>
          </button>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            <PanelLeftClose size={17} />
            <span>RECON</span>
            <ChevronRight size={13} />
            <strong>{labels[tab]}</strong>
          </div>
          <div className="topbar-right">
            <span className="offline-label">
              <LockKeyhole size={12} />
              LOCAL WORKSPACE
            </span>
            <button
              className="jobs-button"
              onClick={() => setShowJobs((v) => !v)}
            >
              <Clock3 size={16} />
              <span>Tasks</span>
              {activeJobs.length > 0 && <b>{activeJobs.length}</b>}
            </button>
            <span className="avatar">A</span>
          </div>
        </header>
        <main>
          {error && (
            <div className="error-banner" role="alert">
              <Info size={16} />
              <span>{error}</span>
              <button aria-label="Dismiss error" onClick={() => setError("")}>
                <X size={15} />
              </button>
            </div>
          )}
          {!online && (
            <div className="notice">
              <Terminal size={15} />
              Waiting for the local engine. Start it with{" "}
              <code>recon serve</code>.
            </div>
          )}
          {tab === "workspace" &&
            (selected ? (
              <BinaryExplorer
                binary={selected}
                jobs={jobs}
                onBack={() => setSelected(null)}
                report={report}
                onCompare={(id) => {
                  setSource(selected.id);
                  setQuery(id);
                  setTab("compare");
                }}
                refresh={refresh}
              />
            ) : (
              <Workspace
                binaries={binaries}
                busy={busy}
                caps={caps}
                onImport={() => fileRef.current?.click()}
                onDrop={onDrop}
                onDemo={() => void demo()}
                onOpen={setSelected}
                report={report}
                refresh={refresh}
              />
            ))}
          {tab === "compare" && (
            <Compare
              binaries={binaries}
              caps={caps}
              source={source}
              target={target}
              query={query}
              setSource={(id) => {
                setSource(id);
                setQuery("");
              }}
              setTarget={setTarget}
              setQuery={setQuery}
              report={report}
              refresh={refresh}
            />
          )}
          {tab === "research" && (
            <Research
              caps={caps}
              jobs={jobs}
              report={report}
              refresh={refresh}
            />
          )}
          {tab === "integrations" && <Integrations caps={caps} />}
        </main>
        <footer className="main-footer">
          <span>
            <ShieldCheck size={12} />
            Static analysis only. Imported programs are never executed.
          </span>
          <span>
            RECON <span className="muted">/</span>{" "}
            {caps?.analyzer_version ?? "native engine"}
          </span>
        </footer>
      </div>
      <input
        ref={fileRef}
        type="file"
        aria-label="Import binary file"
        className="visually-hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) void upload(file);
        }}
      />
      {showJobs && (
        <div className="drawer-shade" onClick={() => setShowJobs(false)}>
          <aside className="jobs-drawer" onClick={(e) => e.stopPropagation()}>
            <div className="panel-header">
              <h2>Background tasks</h2>
              <button
                className="icon-button"
                aria-label="Close tasks"
                onClick={() => setShowJobs(false)}
              >
                <X size={18} />
              </button>
            </div>
            <p className="muted">
              Task status is saved between service restarts.
            </p>
            {jobs.length === 0 && <p className="empty-copy">No tasks yet.</p>}
            {jobs.map((j) => (
              <div className="job-item" key={j.id}>
                <div>
                  <strong>
                    {j.kind === "analysis"
                      ? "Binary analysis"
                      : j.kind === "comparison"
                        ? "Function comparison"
                        : j.kind === "train"
                          ? "Model training"
                          : "Evaluation"}
                  </strong>
                  <Status value={j.state} />
                </div>
                <small className="mono muted">
                  {j.id.slice(0, 12)} · {j.phase}
                </small>
                {running(j.state) && (
                  <div className="progress-bar">
                    <i style={{ width: `${Math.max(8, j.progress * 100)}%` }} />
                  </div>
                )}
                {j.error && (
                  <p className="job-error">
                    {j.error_code}: {j.error}
                  </p>
                )}
                {running(j.state) && (
                  <button
                    className="text-button"
                    onClick={() =>
                      void post(`/jobs/${j.id}/cancel`)
                        .then(refresh)
                        .catch(report)
                    }
                  >
                    {j.cancel_requested
                      ? "Cancellation requested"
                      : "Cancel task"}
                  </button>
                )}
              </div>
            ))}
          </aside>
        </div>
      )}
    </div>
  );
}

function Workspace({
  binaries,
  busy,
  caps,
  onImport,
  onDrop,
  onDemo,
  onOpen,
  report,
  refresh,
}: {
  binaries: Binary[];
  busy: boolean;
  caps: Capabilities | null;
  onImport: () => void;
  onDrop: (e: DragEvent) => void;
  onDemo: () => void;
  onOpen: (b: Binary) => void;
  report: (e: unknown) => void;
  refresh: () => Promise<void>;
}) {
  const [search, setSearch] = useState(""),
    [dragging, setDragging] = useState(false),
    [deleteId, setDeleteId] = useState("");
  const visible = binaries.filter((b) =>
    b.filename.toLowerCase().includes(search.toLowerCase()),
  );
  const ready = binaries.filter((b) => b.status === "completed");
  const totalFunctions = ready.reduce(
    (n, b) =>
      n +
      Number((b.metadata_json as Record<string, unknown>).function_count ?? 0),
    0,
  );
  return (
    <>
      <SectionHeading
        eyebrow="YOUR LOCAL LAB"
        title="Binary workspace"
        description="Inspect the code. Follow the evidence. Understand what changed."
      >
        <button className="button primary" onClick={onImport} disabled={busy}>
          <Plus size={16} />
          Import binary
        </button>
      </SectionHeading>
      <div className="metrics-grid">
        <Metric
          label="Imported binaries"
          value={binaries.length.toString().padStart(2, "0")}
          icon={Layers3}
          note="Stored on this machine"
        />
        <Metric
          label="Functions discovered"
          value={totalFunctions.toLocaleString()}
          icon={BinaryIcon}
          note="From completed analyses"
        />
        <Metric
          label="Analysis engine"
          value="x86-64"
          icon={Cpu}
          note="ELF · Native static analysis"
        />
      </div>
      <div
        className={`upload-zone ${dragging ? "dragging" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          setDragging(false);
          onDrop(e);
        }}
      >
        <div className="upload-grid-art">
          <div />
          <div />
          <div />
          <div />
        </div>
        <span className="upload-icon">
          {busy ? (
            <LoaderCircle size={28} className="spin" />
          ) : (
            <Upload size={28} />
          )}
        </span>
        <h2>
          {busy ? "Importing your binary…" : "A closer look starts here."}
        </h2>
        <p>
          Drop a compiled binary to discover its functions, instructions, and
          control flow.
        </p>
        <button className="button secondary" onClick={onImport} disabled={busy}>
          <FolderOpen size={15} />
          Choose a file
          <ArrowUpRight size={14} />
        </button>
        <span className="upload-format">
          ELF x86-64 <i /> Up to {size(caps?.max_upload_bytes ?? 33554432)}{" "}
          <i /> Never executed
        </span>
      </div>
      <div className="demo-callout">
        <span className="demo-icon">
          <FlaskConical size={19} />
        </span>
        <div>
          <strong>Start with a known pair.</strong>
          <p>
            Explore the same C program compiled at O0 and O2. Real binaries,
            real analysis.
          </p>
        </div>
        <button className="button ghost" onClick={onDemo} disabled={busy}>
          Load demo
          <ArrowRight size={15} />
        </button>
      </div>
      <section className="binary-section">
        <div className="section-toolbar">
          <h2>
            Your binaries <span className="count-tag">{binaries.length}</span>
          </h2>
          <div className="search-box">
            <Search size={15} />
            <input
              aria-label="Filter binaries"
              placeholder="Filter binaries…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            <kbd>/</kbd>
          </div>
        </div>
        <div className="table-wrap">
          <table className="binary-table">
            <thead>
              <tr>
                <th>FILE NAME</th>
                <th>ARCHITECTURE</th>
                <th>SIZE</th>
                <th>STATUS</th>
                <th>IMPORTED</th>
                <th>
                  <span className="visually-hidden">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {visible.map((b) => (
                <tr key={b.id}>
                  <td>
                    <button className="file-link" onClick={() => onOpen(b)}>
                      <span className="file-icon">
                        <FileCode2 size={18} />
                      </span>
                      <span>
                        <strong>{b.filename}</strong>
                        <small className="mono">{b.sha256.slice(0, 16)}…</small>
                      </span>
                    </button>
                  </td>
                  <td>
                    <span className="tag">
                      {b.metadata_json.architecture ?? "ELF x86-64"}
                    </span>
                  </td>
                  <td className="mono muted">{size(b.size)}</td>
                  <td>
                    <Status value={b.status} />
                  </td>
                  <td className="muted">
                    {new Date(b.imported_at).toLocaleDateString(undefined, {
                      month: "short",
                      day: "numeric",
                    })}
                  </td>
                  <td>
                    {deleteId === b.id ? (
                      <div className="inline-confirm">
                        <button
                          className="text-button danger"
                          onClick={() =>
                            void api(`/binaries/${b.id}`, { method: "DELETE" })
                              .then(() => {
                                setDeleteId("");
                                return refresh();
                              })
                              .catch(report)
                          }
                        >
                          Delete file + artifacts
                        </button>
                        <button
                          className="icon-button"
                          aria-label="Keep binary"
                          onClick={() => setDeleteId("")}
                        >
                          <X size={13} />
                        </button>
                      </div>
                    ) : (
                      <button
                        className="icon-button muted"
                        aria-label={`Delete ${b.filename}`}
                        onClick={() => setDeleteId(b.id)}
                        disabled={running(b.status)}
                      >
                        <Trash2 size={15} />
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!visible.length && (
            <div className="table-empty">
              <Layers3 size={25} />
              <strong>
                {search
                  ? "No files match your search"
                  : "Your workspace is ready"}
              </strong>
              <p>
                {search
                  ? "Try another filename."
                  : "Import a binary or load the demo pair to begin."}
              </p>
            </div>
          )}
        </div>
        <div className="table-caption">
          <span>
            {visible.length} {visible.length === 1 ? "binary" : "binaries"}
          </span>
          <span>
            <LockKeyhole size={11} />
            Local storage · No cloud uploads
          </span>
        </div>
      </section>
    </>
  );
}

function BinaryExplorer({
  binary,
  jobs,
  onBack,
  onCompare,
  report,
  refresh,
}: {
  binary: Binary;
  jobs: Job[];
  onBack: () => void;
  onCompare: (id: string) => void;
  report: (e: unknown) => void;
  refresh: () => Promise<void>;
}) {
  const [functions, setFunctions] = useState<Summary[]>([]),
    [total, setTotal] = useState(0),
    [offset, setOffset] = useState(0),
    [search, setSearch] = useState(""),
    [detail, setDetail] = useState<FunctionDetail | null>(null),
    [provider, setProvider] = useState<Record<string, unknown> | null>(null);
  const [investigating, setInvestigating] = useState(false);
  useEffect(() => {
    let active = true;
    if (binary.status === "completed")
      void api<Page<Summary>>(
        `/binaries/${binary.id}/functions?limit=50&offset=${offset}&search=${encodeURIComponent(search)}`,
      )
        .then((p) => {
          if (active) {
            setFunctions(p.items);
            setTotal(p.total);
          }
        })
        .catch(report);
    return () => {
      active = false;
    };
  }, [binary.id, binary.status, offset, search, report]);
  useEffect(() => {
    setDetail(null);
    setSearch("");
    setOffset(0);
    setProvider(null);
  }, [binary.id]);
  useEffect(() => {
    if (!detail && functions[0])
      void api<FunctionDetail>(`/functions/${functions[0].id}`)
        .then(setDetail)
        .catch(report);
  }, [functions, detail, report]);
  const latest = jobs.find((j) => j.resource_id === binary.id);
  return (
    <>
      <button className="back-button" onClick={onBack}>
        <ArrowLeft size={14} />
        All binaries
      </button>
      <SectionHeading
        eyebrow="BINARY EXPLORER"
        title={binary.filename}
        description={`${size(binary.size)} · ELF x86-64 · SHA-256 ${binary.sha256.slice(0, 20)}…`}
      >
        <div className="export-actions">
          <Status value={binary.status} />
          {binary.status === "completed" && (
            <a
              className="button secondary"
              href={`/api/v1/reports/${binary.id}/export`}
              download
            >
              <ArrowDownToLine size={14} />
              Export analysis
            </a>
          )}
        </div>
      </SectionHeading>
      {binary.status !== "completed" ? (
        <div className="processing-state">
          {running(binary.status) ? (
            <LoaderCircle className="spin" size={30} />
          ) : (
            <Info size={30} />
          )}
          <h2>
            {running(binary.status)
              ? "Extracting static evidence…"
              : "Analysis did not complete"}
          </h2>
          <p>
            {latest?.error ??
              "Your binary is in the local analysis queue. It will never be executed."}
          </p>
          {running(binary.status) && latest && (
            <button
              className="button secondary"
              onClick={() =>
                void post(`/jobs/${latest.id}/cancel`)
                  .then(refresh)
                  .catch(report)
              }
            >
              Cancel analysis
            </button>
          )}
          {!running(binary.status) && (
            <button
              className="button secondary"
              onClick={() =>
                void post(`/binaries/${binary.id}/reanalyze`)
                  .then(refresh)
                  .catch(report)
              }
            >
              Retry analysis
            </button>
          )}
        </div>
      ) : (
        <>
          <div className="binary-meta-strip">
            <span>
              <BinaryIcon size={14} />
              {total} functions
            </span>
            <span>
              <ScanLine size={14} />
              {binary.metadata_json.sections?.length ?? 0} sections
            </span>
            <span>
              <Clock3 size={14} />
              {binary.metadata_json.duration_seconds?.toFixed(3)}s analysis
            </span>
            <span className="mono">
              ENTRY {address(binary.metadata_json.entry_point ?? 0)}
            </span>
          </div>
          <div className="explorer-layout">
            <aside className="function-list">
              <div className="panel-header">
                <h3>Functions</h3>
                <span className="count-tag">{total}</span>
              </div>
              <div className="search-box">
                <Search size={14} />
                <input
                  aria-label="Search functions"
                  placeholder="Name, address, mnemonic…"
                  value={search}
                  onChange={(e) => {
                    setSearch(e.target.value);
                    setOffset(0);
                  }}
                />
              </div>
              <div className="function-items">
                {functions.map((f) => (
                  <button
                    key={f.id}
                    className={detail?.id === f.id ? "selected" : ""}
                    onClick={() => {
                      setProvider(null);
                      void api<FunctionDetail>(`/functions/${f.id}`)
                        .then(setDetail)
                        .catch(report);
                    }}
                  >
                    <span>
                      <strong>{f.name}</strong>
                      <small>{address(f.address)}</small>
                    </span>
                    <small>
                      {f.instruction_count}
                      <span>ins</span>
                    </small>
                  </button>
                ))}
                {!functions.length && (
                  <p className="empty-copy">No matching functions.</p>
                )}
              </div>
              <div className="pagination">
                <button
                  disabled={!offset}
                  onClick={() => setOffset((n) => Math.max(0, n - 50))}
                  aria-label="Previous functions"
                >
                  <ArrowLeft size={14} />
                </button>
                <span>
                  {total ? offset + 1 : 0}–{Math.min(offset + 50, total)} of{" "}
                  {total}
                </span>
                <button
                  disabled={offset + 50 >= total}
                  onClick={() => setOffset((n) => n + 50)}
                  aria-label="Next functions"
                >
                  <ArrowRight size={14} />
                </button>
              </div>
            </aside>
            <div>
              <Evidence detail={detail} />
              {detail && (
                <div className="function-actions">
                  <button
                    className="button primary"
                    onClick={() => onCompare(detail.id)}
                  >
                    <GitCompareArrows size={15} />
                    Find similar functions
                  </button>
                  <button
                    className="button secondary"
                    disabled={investigating}
                    onClick={() => {
                      if (
                        !window.confirm(
                          "Request an optional local REA/Ghidra investigation of this function? It may create an analysis database. The target will not be executed. If the provider is unavailable, native evidence will be returned.",
                        )
                      )
                        return;
                      setInvestigating(true);
                      void post<Record<string, unknown>>(
                        `/functions/${detail.id}/investigate`,
                        { consent: true },
                      )
                        .then(setProvider)
                        .catch(report)
                        .finally(() => setInvestigating(false));
                    }}
                  >
                    {investigating ? (
                      <LoaderCircle size={14} className="spin" />
                    ) : (
                      <Plug size={14} />
                    )}
                    Investigate with REA
                  </button>
                </div>
              )}
              {provider && (
                <div className="notice provider-result">
                  <Info size={15} />
                  <div>
                    <strong>
                      {provider.fallback
                        ? "Native fallback evidence"
                        : "REA evidence collected"}
                    </strong>
                    <p>
                      {String(
                        (
                          provider.provider_error as
                            | { message?: string }
                            | undefined
                        )?.message ??
                          "Provider output is saved with version, addresses, and provenance. It does not affect similarity scores.",
                      )}
                    </p>
                    {Boolean(provider.pseudocode) && (
                      <pre>{String(provider.pseudocode)}</pre>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
          <p className="subtle-note">
            <CircleHelp size={13} />
            Function boundaries and control flow may be incomplete. Inspect the
            evidence before drawing conclusions.
          </p>
        </>
      )}
    </>
  );
}

function Compare({
  binaries,
  caps,
  source,
  target,
  query,
  setSource,
  setTarget,
  setQuery,
  report,
  refresh,
}: {
  binaries: Binary[];
  caps: Capabilities | null;
  source: string;
  target: string;
  query: string;
  setSource: (id: string) => void;
  setTarget: (id: string) => void;
  setQuery: (id: string) => void;
  report: (e: unknown) => void;
  refresh: () => Promise<void>;
}) {
  const ready = binaries.filter((b) => b.status === "completed");
  const [method, setMethod] = useState("hybrid"),
    [threshold, setThreshold] = useState(0.65),
    [topK, setTopK] = useState(5),
    [loading, setLoading] = useState(false);
  const [comparison, setComparison] = useState<Comparison | null>(null),
    [history, setHistory] = useState<Comparison[]>([]),
    [selected, setSelected] = useState<QueryResult | null>(null);
  const [left, setLeft] = useState<FunctionDetail | null>(null),
    [right, setRight] = useState<FunctionDetail | null>(null),
    [matchId, setMatchId] = useState("");
  const [queries, setQueries] = useState<Summary[]>([]);
  useEffect(() => {
    void api<Page<Comparison>>("/comparisons")
      .then((p) => setHistory(p.items))
      .catch(report);
  }, [report, comparison?.status]);
  useEffect(() => {
    if (source)
      void api<Page<Summary>>(`/binaries/${source}/functions?limit=100`)
        .then((p) => setQueries(p.items))
        .catch(report);
  }, [source, report]);
  useEffect(() => {
    if (!comparison || !running(comparison.status)) return;
    const timer = setInterval(() => {
      void api<Comparison>(`/comparisons/${comparison.id}`)
        .then((c) => {
          setComparison(c);
          if (c.result) {
            setSelected(c.result.results[0] ?? null);
            setMatchId(c.result.results[0]?.matches[0]?.function_id ?? "");
          }
        })
        .catch(report);
    }, 700);
    return () => clearInterval(timer);
  }, [comparison, report]);
  useEffect(() => {
    let active = true;
    setLeft(null);
    setRight(null);
    if (selected) {
      void api<FunctionDetail>(`/functions/${selected.query_function_id}`)
        .then((f) => {
          if (active) setLeft(f);
        })
        .catch(report);
      setMatchId(selected.matches[0]?.function_id ?? "");
    }
    return () => {
      active = false;
    };
  }, [selected, report]);
  useEffect(() => {
    let active = true;
    setRight(null);
    if (matchId)
      void api<FunctionDetail>(`/functions/${matchId}`)
        .then((f) => {
          if (active) setRight(f);
        })
        .catch(report);
    return () => {
      active = false;
    };
  }, [matchId, report]);
  const start = async () => {
    setLoading(true);
    try {
      const response = await post<{ comparison: Comparison }>("/comparisons", {
        source_binary_id: source,
        target_binary_id: target,
        query_function_id: query || null,
        method,
        top_k: topK,
        threshold,
      });
      setComparison(response.comparison);
      setSelected(null);
      setLeft(null);
      setRight(null);
      await refresh();
    } catch (e) {
      report(e);
    } finally {
      setLoading(false);
    }
  };
  const loadHistory = async (id: string) => {
    try {
      const c = await api<Comparison>(`/comparisons/${id}`);
      setComparison(c);
      setSelected(c.result?.results[0] ?? null);
    } catch (e) {
      report(e);
    }
  };
  const result = comparison?.result;
  return (
    <>
      <SectionHeading
        eyebrow="FUNCTION SIMILARITY"
        title="See what carries over."
        description="Compare two builds and inspect the evidence behind each candidate match."
      />
      {ready.length < 2 && (
        <div className="notice">
          <Info size={16} />
          Import or load at least two binaries and wait for analysis to finish.
        </div>
      )}
      <section className="comparison-form">
        <div className="binary-select-pair">
          <label>
            <span className="eyebrow">01 / SOURCE BINARY</span>
            <select
              aria-label="Source binary"
              value={source}
              onChange={(e) => setSource(e.target.value)}
            >
              <option value="">Select a binary</option>
              {ready.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.filename}
                </option>
              ))}
            </select>
          </label>
          <GitCompareArrows size={22} />
          <label>
            <span className="eyebrow">02 / TARGET BINARY</span>
            <select
              aria-label="Target binary"
              value={target}
              onChange={(e) => setTarget(e.target.value)}
            >
              <option value="">Select a binary</option>
              {ready.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.filename}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="comparison-settings">
          <label>
            Method
            <select
              aria-label="Similarity method"
              value={method}
              onChange={(e) => setMethod(e.target.value)}
            >
              <option value="hybrid">Combined baseline</option>
              <option value="opcode">Opcode histogram</option>
              <option value="ngram">Instruction n-grams</option>
              <option value="structure">CFG structure</option>
              <option value="neural" disabled={!caps?.neural.available}>
                Neural encoder{!caps?.neural.available ? " · no weights" : ""}
              </option>
            </select>
          </label>
          <label>
            Query function
            <select
              aria-label="Query function"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            >
              <option value="">All functions</option>
              {queries.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.name}
                </option>
              ))}
            </select>
          </label>
          <label className="threshold-label">
            Threshold <span className="mono">{threshold.toFixed(2)}</span>
            <input
              aria-label="Similarity threshold"
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={threshold}
              onChange={(e) => setThreshold(Number(e.target.value))}
            />
          </label>
          <label>
            Top k
            <select
              aria-label="Top candidates"
              value={topK}
              onChange={(e) => setTopK(Number(e.target.value))}
            >
              <option>5</option>
              <option>10</option>
              <option>20</option>
            </select>
          </label>
          <button
            className="button primary"
            disabled={
              !source ||
              !target ||
              loading ||
              Boolean(comparison && running(comparison.status))
            }
            onClick={() => void start()}
          >
            {loading || (comparison && running(comparison.status)) ? (
              <LoaderCircle className="spin" size={15} />
            ) : (
              <ScanLine size={15} />
            )}
            Compare functions
          </button>
        </div>
      </section>
      <div className="comparison-history">
        <span className="muted">Previous comparison</span>
        <select
          aria-label="Previous comparison"
          value={comparison?.id ?? ""}
          onChange={(e) => void loadHistory(e.target.value)}
        >
          <option value="">Choose a saved comparison</option>
          {history.map((c) => (
            <option key={c.id} value={c.id}>
              {c.id.slice(0, 8)} · {String(c.config_json.method)} · {c.status}
            </option>
          ))}
        </select>
      </div>
      {comparison && running(comparison.status) && (
        <div className="processing-state">
          <LoaderCircle className="spin" size={25} />
          <h2>Ranking candidate functions…</h2>
          <p>The comparison is running locally. Its results will be saved.</p>
        </div>
      )}
      {comparison && ["failed", "cancelled"].includes(comparison.status) && (
        <div className="notice">
          Comparison {comparison.status}. Open Tasks for diagnostics.
        </div>
      )}
      {result && (
        <>
          <div className="results-heading">
            <div>
              <span className="eyebrow">COMPARISON RESULTS</span>
              <h2>
                {result.query_count} queries <span className="muted">/</span>{" "}
                {result.candidate_count} candidates
              </h2>
              <p className="mono muted">
                {result.model_version} · {result.retrieval_seconds.toFixed(3)}s
                retrieval
              </p>
            </div>
            <div className="export-actions">
              <a
                className="button secondary"
                href={`/api/v1/reports/${comparison!.id}/export?format=json`}
                download
              >
                <ArrowDownToLine size={14} />
                JSON
              </a>
              <a
                className="button secondary"
                href={`/api/v1/reports/${comparison!.id}/export?format=csv`}
                download
              >
                CSV
              </a>
            </div>
          </div>
          <div className="notice">
            <Info size={15} />
            Scores indicate similarity, not probability or proven equivalence. A
            candidate above the threshold still needs review.
          </div>
          <div className="match-layout">
            <aside className="query-list">
              <div className="panel-header">
                <h3>Query functions</h3>
                <span className="count-tag">{result.results.length}</span>
              </div>
              {result.results.map((q) => (
                <button
                  key={q.query_function_id}
                  className={
                    selected?.query_function_id === q.query_function_id
                      ? "selected"
                      : ""
                  }
                  onClick={() => setSelected(q)}
                >
                  <div>
                    <strong>{q.name}</strong>
                    <small className="mono">{address(q.address)}</small>
                  </div>
                  <span
                    className={q.state === "unknown" ? "tag unknown" : "tag"}
                  >
                    {q.state === "unknown"
                      ? "Unknown"
                      : q.matches[0]?.similarity_score.toFixed(3)}
                  </span>
                </button>
              ))}
            </aside>
            <section className="candidate-panel">
              <div className="panel-header">
                <h3>
                  Ranked candidates{" "}
                  {selected && (
                    <span className="muted">for {selected.name}</span>
                  )}
                </h3>
                <span className="eyebrow">COSINE / BASELINE SCORE</span>
              </div>
              {selected?.matches.map((m) => (
                <button
                  key={m.function_id}
                  className={`candidate-row ${matchId === m.function_id ? "selected" : ""}`}
                  onClick={() => setMatchId(m.function_id)}
                >
                  <span className="rank-number">
                    {String(m.rank).padStart(2, "0")}
                  </span>
                  <span className="candidate-name">
                    <strong>{m.name}</strong>
                    <small className="mono">{address(m.address)}</small>
                  </span>
                  <span className="score-track">
                    <i
                      style={{
                        width: `${Math.max(0, m.similarity_score) * 100}%`,
                      }}
                    />
                  </span>
                  <strong className="mono score-value">
                    {m.similarity_score.toFixed(3)}
                  </strong>
                  <span
                    className={m.accepted ? "match-flag" : "match-flag low"}
                  >
                    {m.accepted ? "Review" : "Below threshold"}
                  </span>
                  <ChevronRight size={14} />
                </button>
              ))}
            </section>
          </div>
          <div className="side-by-side">
            <div>
              <div className="side-label">
                <span className="source-dot" />
                SOURCE FUNCTION
              </div>
              <Evidence detail={left} compact />
            </div>
            <div>
              <div className="side-label">
                <span className="target-dot" />
                CANDIDATE FUNCTION
              </div>
              <Evidence detail={right} compact />
            </div>
          </div>
        </>
      )}
      {!comparison && (
        <div className="comparison-empty">
          <GitCompareArrows size={38} />
          <h2>Two builds. One investigation.</h2>
          <p>
            Choose your binaries and a similarity method to find candidate
            matches.
          </p>
          <span className="subtle-note">
            Source names and debug labels are never used as matching features.
          </span>
        </div>
      )}
    </>
  );
}

function Research({
  caps,
  jobs,
  report,
  refresh,
}: {
  caps: Capabilities | null;
  jobs: Job[];
  report: (e: unknown) => void;
  refresh: () => Promise<void>;
}) {
  const [status, setStatus] = useState<ResearchStatus | null>(null),
    [experiments, setExperiments] = useState<Experiment[]>([]),
    [epochs, setEpochs] = useState(30),
    [busy, setBusy] = useState(false),
    [details, setDetails] = useState<Experiment | null>(null);
  useEffect(() => {
    void Promise.all([
      api<ResearchStatus>("/research/status"),
      api<Page<Experiment>>("/experiments"),
    ])
      .then(([s, e]) => {
        setStatus(s);
        setExperiments(e.items);
      })
      .catch(report);
  }, [jobs, report]);
  const start = async (kind: string) => {
    setBusy(true);
    try {
      await post(`/experiments/${kind}`, { epochs, seed: 42, resume: false });
      await refresh();
    } catch (e) {
      report(e);
    } finally {
      setBusy(false);
    }
  };
  const training = jobs.some(
    (j) => ["train", "evaluate"].includes(j.kind) && running(j.state),
  );
  return (
    <>
      <SectionHeading
        eyebrow="REPRODUCIBLE EXPERIMENTS"
        title="Measure before you trust."
        description="Build labeled datasets, train locally, and compare models against simple baselines."
      />
      <div className="metrics-grid">
        <Metric
          label="Verified samples"
          value={status?.sample_count ?? 0}
          icon={Layers3}
          note="Source-linked compiled functions"
        />
        <Metric
          label="Source projects"
          value={Object.keys(status?.projects ?? {}).length}
          icon={FileCode2}
          note="Separated before pair generation"
        />
        <Metric
          label="Model"
          value={caps?.neural.available ? "Installed" : "Baseline only"}
          icon={Cpu}
          note={caps?.neural.model_version ?? "Neural training is optional"}
        />
      </div>
      <div className="research-grid">
        <section className="research-card">
          <span className="step-number">01</span>
          <h2>Ground-truth dataset</h2>
          <p>
            Use pinned, licensed source revisions and record compiler settings.
            Project-level splits keep training separate from final evaluation.
          </p>
          {status?.dataset_available ? (
            <div className="project-splits">
              {Object.entries(status.projects).map(([name, split]) => (
                <div key={name}>
                  <FileCode2 size={14} />
                  <strong>{name}</strong>
                  <span className="tag">{split.join(", ")}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="command-block">
              <span>Build the research dataset locally</span>
              <code>recon dataset build</code>
              <small>
                Downloads pinned source on first use. Analysis stays local.
              </small>
            </div>
          )}
          <span className="step-state">
            <Check size={13} />
            {status?.dataset_available
              ? "Dataset is available"
              : "Dataset generation is a separate CLI step"}
          </span>
        </section>
        <section className="research-card">
          <span className="step-number">02</span>
          <h2>Train a compact encoder</h2>
          <p>
            A shared-weight model learns normalized function embeddings on CPU.
            Checkpoints are selected using validation projects.
          </p>
          <label className="epoch-input">
            Maximum epochs
            <input
              type="number"
              min="1"
              max="200"
              value={epochs}
              onChange={(e) => setEpochs(Number(e.target.value))}
            />
          </label>
          <button
            className="button primary"
            disabled={
              busy ||
              training ||
              !status?.dataset_available ||
              epochs < 1 ||
              epochs > 200
            }
            onClick={() => void start("train")}
          >
            <FlaskConical size={15} />
            Train on CPU
          </button>
          <small className="muted">
            Fixed seed 42 · early stopping · no paid API
          </small>
        </section>
        <section className="research-card">
          <span className="step-number">03</span>
          <h2>Evaluate held-out projects</h2>
          <p>
            Measure Recall@1/5/10, MRR, false matches, and ranking time. Keep
            negative findings and baseline comparisons in the report.
          </p>
          <div className="evaluation-tags">
            <span>Recall@k</span>
            <span>MRR</span>
            <span>False matches</span>
          </div>
          <button
            className="button secondary"
            disabled={busy || training || !status?.dataset_available}
            onClick={() => void start("evaluate")}
          >
            <ScanLine size={15} />
            Run evaluation
          </button>
          <small className="muted">
            Use after model selection is complete.
          </small>
        </section>
      </div>
      {status?.missing_toolchains.length ? (
        <div className="notice">
          <Info size={15} />
          <span>
            Missing toolchains: {status.missing_toolchains.join("; ")}. Results
            do not establish cross-compiler performance.
          </span>
        </div>
      ) : null}
      <div className="section-toolbar">
        <h2>Experiment history</h2>
        <span className="muted">
          Configs, seeds, metrics, and provenance are saved.
        </span>
      </div>
      <div className="table-wrap">
        <table className="binary-table">
          <thead>
            <tr>
              <th>EXPERIMENT</th>
              <th>TYPE</th>
              <th>STATUS</th>
              <th>CREATED</th>
              <th>REPORT</th>
            </tr>
          </thead>
          <tbody>
            {experiments.map((e) => (
              <tr key={e.id}>
                <td className="mono">{e.id.slice(0, 12)}</td>
                <td>{e.kind}</td>
                <td>
                  <Status value={e.status} />
                </td>
                <td>{new Date(e.created_at).toLocaleString()}</td>
                <td>
                  {e.status === "completed" && (
                    <button
                      className="text-button"
                      onClick={() =>
                        void api<Experiment>(`/experiments/${e.id}`)
                          .then(setDetails)
                          .catch(report)
                      }
                    >
                      View report
                      <ArrowUpRight size={13} />
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!experiments.length && (
          <div className="table-empty">
            <FlaskConical size={24} />
            <strong>No recorded experiments yet</strong>
            <p>
              Training and evaluation are optional. Baseline analysis is ready
              independently.
            </p>
          </div>
        )}
      </div>
      {details && (
        <section className="report-panel">
          <div className="panel-header">
            <h3>Experiment report</h3>
            <a
              className="button secondary"
              href={`/api/v1/reports/${details.id}/export`}
              download
            >
              <ArrowDownToLine size={14} />
              Export JSON
            </a>
          </div>
          <pre>{JSON.stringify(details.result, null, 2)}</pre>
        </section>
      )}
    </>
  );
}

function Integrations({ caps }: { caps: Capabilities | null }) {
  return (
    <>
      <SectionHeading
        eyebrow="ANALYSIS PROVIDERS"
        title="More evidence, when you need it."
        description="Native analysis is always available. Optional providers add supporting evidence independently of similarity scores."
      />
      <div className="integration-grid">
        {caps?.providers.map((p) => (
          <section className="integration-card" key={p.id}>
            <span
              className={`integration-symbol ${p.id === "native" ? "native" : ""}`}
            >
              {p.id === "native" ? <Cpu size={25} /> : <Plug size={25} />}
            </span>
            <div className="integration-title">
              <h2>{p.id === "native" ? "Native analysis" : "REA + Ghidra"}</h2>
              <span className={p.available ? "status status-completed" : "tag"}>
                {p.available
                  ? "Available"
                  : p.enabled
                    ? "Unavailable"
                    : "Optional · disabled"}
              </span>
            </div>
            <p>{p.reason}</p>
            <div className="integration-facts">
              <span>Runs locally</span>
              <span>
                {p.id === "native" ? "LIEF + Capstone" : "Pinned REA 6.8.0"}
              </span>
              <span>
                {p.id === "native"
                  ? "Assembly + control flow"
                  : "Optional function evidence"}
              </span>
            </div>
            {p.id !== "native" && (
              <p className="integration-note">
                Installation and configuration require your approval. See{" "}
                <code>docs/REA_INTEGRATION.md</code> for the setup plan. RECON
                falls back to native evidence if REA is missing or fails.
              </p>
            )}
          </section>
        ))}
      </div>
      <div className="privacy-panel">
        <ShieldCheck size={26} />
        <div>
          <h2>Your evidence stays in your workspace.</h2>
          <p>
            Core analysis and function matching use local tools and local
            storage. No external AI provider is configured. Optional AI
            explanations would need a separate, explicit configuration.
          </p>
        </div>
      </div>
    </>
  );
}
