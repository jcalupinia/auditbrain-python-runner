import { describe, it, expect } from "vitest";
import { tarifa } from "../engine.js";

describe("smoke", () => {
  it("tarifa tramo exento", () => {
    expect(tarifa(50000)).toBe(0);
    expect(tarifa(500000)).toBe(0.0075);
  });
});
