import { afterEach, describe, expect, it, vi } from "vitest";
import { address, api, size } from "./api";
describe("display values", () => {
  it("labels real addresses and file sizes", () => {
    expect(address(4198400)).toBe("0x00401000");
    expect(size(2048)).toBe("2.0 KB");
  });
});
describe("API failures", () => {
  afterEach(() => vi.unstubAllGlobals());
  it("shows actionable backend errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 422,
        json: async () => ({
          error: {
            code: "UNSUPPORTED_ARCHITECTURE",
            message: "Only x86-64 ELF is supported.",
          },
        }),
      }),
    );
    await expect(api("/binaries")).rejects.toThrow(
      "Only x86-64 ELF is supported.",
    );
  });
  it("handles empty deletion responses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, status: 204 }),
    );
    await expect(
      api("/binaries/id", { method: "DELETE" }),
    ).resolves.toBeUndefined();
  });
});
