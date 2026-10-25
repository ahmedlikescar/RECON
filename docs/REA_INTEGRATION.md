# Optional REA integration

The adapter was developed against **rea-agents 6.8.0**, upstream commit
`f69c52a1cf3940ed1999fcc0859a75dbb913d684`, MIT licensed. Sources inspected:

- [Official repository](https://github.com/morluto/rea)
- [Installation contract at the pinned revision](https://github.com/morluto/rea/blob/f69c52a1cf3940ed1999fcc0859a75dbb913d684/docs/installation.md)
- [CLI contract](https://github.com/morluto/rea/blob/f69c52a1cf3940ed1999fcc0859a75dbb913d684/docs/cli.md)
- [Native investigation](https://github.com/morluto/rea/blob/f69c52a1cf3940ed1999fcc0859a75dbb913d684/docs/native-investigation.md)
- [Function dossier schema](https://github.com/morluto/rea/blob/f69c52a1cf3940ed1999fcc0859a75dbb913d684/src/domain/hopperValues.ts)

REA is disabled by default. No REA setup, Ghidra/Java installation, MCP registration,
or changes to the owner's agent settings have been performed.

## Reviewable setup plan

The engineering specification section 20.2 says: “Run setup only with user approval.”
This plan is documentation for that approval, not evidence that setup has run.

1. Confirm Node is supported by 6.8.0: ^22.23.4, ^24.22.1, or >=26.12.1. The
   development runtime is Node 24.22.1; no global runtime replacement is needed.
2. Review an official Ghidra 12.1.x installation and a JDK within that installation's
   declared Java bounds. Upstream setup does not install Ghidra or the JDK.
3. After approval, use the official pinned setup entry point:

   ```sh
   npx rea-agents@6.8.0 setup
   ```

   Review its displayed changes before accepting. Setup can register MCP tools and
   workflow instructions in agent configuration; RECON does not need a global
   registration just to call an existing trusted `rea` executable.
4. With an installed executable, verify `rea --version --json`, `rea doctor --json`,
   `rea providers --json`, and `rea capabilities --json`. Preserve diagnostics.
5. Configure RECON only after the installation is verified:

   ```sh
   export RECON_REA_ENABLED=true
   export RECON_REA_COMMAND=/absolute/path/to/rea
   export RECON_GHIDRA_PATH=/absolute/path/to/ghidra_12.1.4_PUBLIC
   # Ensure node and the selected JDK are on PATH / JAVA_HOME.
   recon serve
   ```

   The adapter sets `GHIDRA_INSTALL_DIR`, selects the Ghidra provider explicitly,
   strips unrelated credential environment variables, and sets a 512 MiB Java heap.

## Runtime behavior and provenance

An investigator must approve the selected function investigation in the UI.
Only inspected static CLI commands are used: `capabilities`, `inspect`, and
`function ... --procedure=0xADDRESS --provider ghidra --json`. No target execution,
patching, or dynamic observation command is exposed. No shell is used.

The function dossier must be complete `analyze_function` Evidence. Procedure address
is checked against the requested function. RECON preserves the complete record,
provider/version, source hash, source range, assembly, optional pseudocode, references,
limitations and collection time. Missing pseudocode is null. No external AI narrative
provider is configured. Similarity scores remain independent.

Missing dependencies, incompatible version, invalid JSON/schema, address mismatch,
timeout or excessive output return native evidence with a provider diagnostic.
Output is bounded at 16 MiB and the process group has a deadline. These checks do
not establish full native provider sandbox isolation; see `THREAT_MODEL.md`.

## Verification status

Pinned-contract normalization, address mismatch, disabled/missing provider and
timeout fallback tests pass using explicitly labeled synthetic provider records
plus actual native disassembly. This is not a real REA/Ghidra integration run.
Installing and running the pinned provider, validating its actual health/capability
envelope, and a separate direct Ghidra-only adapter remain follow-up work. Do not
claim those acceptance tests have passed.
