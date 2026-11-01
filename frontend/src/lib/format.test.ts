import { fmt, ms, pct, UNAVAILABLE } from "./format";

test("missing values are 'unavailable', never 0", () => {
  expect(fmt(null)).toBe(UNAVAILABLE);
  expect(fmt(undefined)).toBe(UNAVAILABLE);
  expect(pct(null)).toBe(UNAVAILABLE);
  expect(ms(null)).toBe(UNAVAILABLE);
  expect(fmt(0)).toBe("0.0"); // a real zero is still shown as zero
});

test("formatting", () => {
  expect(pct(0.257)).toBe("25.7%");
  expect(ms(641.4)).toBe("641 ms");
  expect(ms(2477.6)).toBe("2.48 s");
});
