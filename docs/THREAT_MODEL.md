# Threat model

The main untrusted input is a locally imported binary: headers, section extents,
symbols, code bytes and filenames are attacker-controlled. Native parsers themselves
remain an attack surface. RECON's supported deployment is a single-user loopback
service, not a public upload endpoint.

## Controls

- Original filenames never become storage paths or executable commands. Artifacts
  use generated IDs/content hashes. Traversal, control characters and NULs are rejected.
- Streamed request bodies are counted before multipart parsing. Upload, section,
  function, instruction, queue, CPU, wall-clock, memory and output budgets are bounded.
- User binaries are never executed, loaded as libraries, or passed to a shell.
  All tool commands use argument arrays. Only known source fixtures are compiled.
- Parsing happens in a separate process. macOS sandbox-exec denies network access
  and writes outside temporary output. On macOS RSS is monitored because RLIMIT_AS
  is ineffective. Linux uses RLIMIT_AS; both platforms use CPU/file/descriptor limits.
- A worker audit hook denies Python network and subprocess operations after parser
  imports. This is defense in depth, not protection against arbitrary native code.
- The service binds to 127.0.0.1, validates Host/Origin, and sets restrictive browser
  headers. External AI providers are absent. Local data is ignored by Git.
- SQL queries are parameterized through SQLAlchemy. Reports escape CSV formula
  prefixes from untrusted symbols. React escapes symbol text; no raw HTML is injected.
- Model weights use safetensors. Artifact/schema/hash mismatches fail with diagnostics.
  Writes are atomic; incomplete worker output is never admitted as completed analysis.

## Residual limits

The macOS worker retains read access needed by its interpreter and native libraries;
it is not a minimal read-only mount namespace. Linux resource limits do not themselves
deny native filesystem/network syscalls. For potentially hostile files, use a dedicated
unprivileged VM/container with no secrets, no network and a disposable writable data
directory. That stronger deployment has not been validated here.

REA/Ghidra can create analysis projects and spawn provider processes. REA is disabled
by default, has an explicit per-investigation consent gate, bounded output/deadline,
and uses a configured trusted executable. Full provider OS isolation and a genuine
Ghidra run remain unverified. Provider output is evidence, never instructions to execute.

The application has no multi-user identity, tenant isolation, remote authentication,
or public deployment mode. Do not expose it by changing the bind address. Only one
server/trainer per data directory is supported. Static similarity is not a malware
verdict, recovered source code, or proof of equivalent semantics.
