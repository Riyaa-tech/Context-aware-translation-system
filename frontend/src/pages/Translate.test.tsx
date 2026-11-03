import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, vi } from "vitest";
import App from "../App";
import { StateProvider } from "../state";
import TranslatePage from "./Translate";

// The backend is MOCKED here (fetch stub). Real-model behaviour is covered by the backend's real-model tests.
const LANGS = {
  languages: [{ code: "eng_Latn", name: "English" }, { code: "hin_Deva", name: "Hindi" }, { code: "deu_Latn", name: "German" }],
  directions: [
    { source: "eng_Latn", target: "hin_Deva", status: "enabled" }, { source: "hin_Deva", target: "eng_Latn", status: "enabled" },
    { source: "eng_Latn", target: "deu_Latn", status: "enabled" }, { source: "deu_Latn", target: "eng_Latn", status: "enabled" },
    { source: "hin_Deva", target: "deu_Latn", status: "planned" }, { source: "deu_Latn", target: "hin_Deva", status: "planned" },
  ],
};
const enhanced = (translation: string) => ({
  condition: "D_idiom_paraphrase+context_selected", source_text: "x", translation, source_lang: "eng_Latn", target_lang: "hin_Deva",
  status: "ok", controller_decision: "INTERVENE", nllb_input: "x", record: {}, events: [], model_id: "m", model_revision: "r",
});
const reply = (status: number, body: unknown) =>
  Promise.resolve({ ok: status < 400, status, statusText: "", text: () => Promise.resolve(JSON.stringify(body)) });

let fetchMock: ReturnType<typeof vi.fn>;
let translateReply: () => Promise<unknown>;

beforeEach(() => {
  translateReply = () => reply(200, enhanced("वह नदी के तट पर गया।"));
  fetchMock = vi.fn((url: string) => (url === "/api/languages" ? reply(200, LANGS) : translateReply()));
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => vi.unstubAllGlobals());

function renderPage() {
  return render(<MemoryRouter><StateProvider><TranslatePage /></StateProvider></MemoryRouter>);
}
const translateCalls = () => fetchMock.mock.calls.filter(([url]) => url !== "/api/languages");
const sentence = () => screen.getByLabelText("Sentence to translate");
const button = () => screen.getByRole("button", { name: /translate/i });

test("shows the empty state and disables Translate until a sentence is entered", async () => {
  renderPage();
  expect(screen.getByText("Your translation will appear here.")).toBeTruthy();
  expect(screen.getByPlaceholderText("Enter preceding context (optional)...")).toBeTruthy();
  expect(screen.getByPlaceholderText("Enter the sentence you want to translate...")).toBeTruthy();
  expect((button() as HTMLButtonElement).disabled).toBe(true);
  fireEvent.change(sentence(), { target: { value: "   " } });
  expect((button() as HTMLButtonElement).disabled).toBe(true);
});

test("sends context lines and languages to the existing enhanced endpoint and shows the real response", async () => {
  renderPage();
  fireEvent.change(screen.getByLabelText("Preceding context"), { target: { value: "  The fisherman sat beside the river.  \n\n  It was early. \n" } });
  fireEvent.change(sentence(), { target: { value: " He went to the bank. " } });
  fireEvent.click(button());
  expect(await screen.findByTestId("translation")).toBeTruthy();
  expect(screen.getByTestId("translation").textContent).toBe("वह नदी के तट पर गया।");
  const [[url, init]] = translateCalls();
  expect(url).toBe("/api/translate/enhanced");
  expect(init.method).toBe("POST");
  expect(JSON.parse(init.body)).toEqual({
    text: "He went to the bank.", source_lang: "eng_Latn", target_lang: "hin_Deva",
    context: ["The fisherman sat beside the river.", "It was early."],
    modules: ["idiom", "context"], idiom_mode: "paraphrase", context_mode: "selected",
  });
});

test("shows a loading state and ignores repeated clicks while a translation is running", async () => {
  let resolve!: (v: unknown) => void;
  translateReply = () => new Promise((r) => { resolve = r; });
  renderPage();
  fireEvent.change(sentence(), { target: { value: "Hello" } });
  const form = sentence().closest("form")!;
  fireEvent.submit(form);
  fireEvent.submit(form); // double submit before React re-renders
  expect(await screen.findByRole("status")).toBeTruthy();
  expect(screen.getAllByText("Translating…").length).toBeGreaterThan(0);
  expect((screen.getByRole("button", { name: "Translating…" }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.keyDown(sentence(), { key: "Enter", ctrlKey: true });
  expect(translateCalls()).toHaveLength(1);
  await act(async () => { resolve(await reply(200, enhanced("Hallo"))); });
  expect((await screen.findByTestId("translation")).textContent).toBe("Hallo");
});

test("shows the backend's error message when translation fails", async () => {
  translateReply = () => reply(400, { detail: "Direction hin_Deva -> deu_Latn is planned but not yet tested in this project." });
  renderPage();
  fireEvent.change(sentence(), { target: { value: "नमस्ते" } });
  fireEvent.click(button());
  expect((await screen.findByRole("alert")).textContent).toContain("planned but not yet tested");
  expect(screen.queryByTestId("translation")).toBeNull();
});

test("shows a friendly message when the server cannot be reached", async () => {
  translateReply = () => Promise.reject(new TypeError("Failed to fetch"));
  renderPage();
  fireEvent.change(sentence(), { target: { value: "Hello" } });
  fireEvent.click(button());
  expect((await screen.findByRole("alert")).textContent).toContain("Could not reach the translation server");
});

test("rejects more context sentences than the backend accepts, without calling it", async () => {
  renderPage();
  fireEvent.change(screen.getByLabelText("Preceding context"), { target: { value: Array.from({ length: 11 }, (_, i) => `Line ${i}.`).join("\n") } });
  fireEvent.change(sentence(), { target: { value: "Hello" } });
  fireEvent.click(button());
  expect((await screen.findByRole("alert")).textContent).toContain("at most 10 context sentences");
  expect(translateCalls()).toHaveLength(0);
});

test("language selection: any enabled direction, unavailable pairs disabled, swap", async () => {
  renderPage();
  const from = screen.getByLabelText("Input language") as HTMLSelectElement;
  const to = screen.getByLabelText("Output language") as HTMLSelectElement;
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/languages", expect.anything()));
  expect([...from.options].map((o) => o.text)).toEqual(["English", "Hindi", "German"]);
  fireEvent.change(from, { target: { value: "deu_Latn" } });
  await waitFor(() => expect(to.value).toBe("eng_Latn")); // German -> English is the only enabled target
  expect([...to.options].find((o) => o.value === "hin_Deva")!.disabled).toBe(true);
  fireEvent.change(from, { target: { value: "eng_Latn" } });
  fireEvent.change(to, { target: { value: "deu_Latn" } });
  fireEvent.click(screen.getByRole("button", { name: "Swap languages" }));
  expect(from.value).toBe("deu_Latn");
  expect(to.value).toBe("eng_Latn");
  fireEvent.change(sentence(), { target: { value: "Ich verstehe nur Bahnhof." } });
  fireEvent.click(button());
  await screen.findByTestId("translation");
  const body = JSON.parse(translateCalls()[0][1].body);
  expect([body.source_lang, body.target_lang]).toEqual(["deu_Latn", "eng_Latn"]);
});

test("copy button copies the translated sentence", async () => {
  const writeText = vi.fn().mockResolvedValue(undefined);
  Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
  renderPage();
  fireEvent.change(sentence(), { target: { value: "He went to the bank." } });
  fireEvent.click(button());
  await screen.findByTestId("translation");
  fireEvent.click(screen.getByRole("button", { name: "Copy" }));
  expect(writeText).toHaveBeenCalledWith("वह नदी के तट पर गया।");
  expect(await screen.findByRole("button", { name: "Copied" })).toBeTruthy();
});

test("the Translate page has no research controls; research pages are in a separate menu", () => {
  render(<MemoryRouter><App /></MemoryRouter>);
  for (const t of [/idiom mode/i, /selected context/i, /sarcasm/i, /M1|M2|M3/, /model load/i, /literal control/i]) {
    expect(screen.queryByText(t)).toBeNull();
  }
  expect(screen.getByText("Research ▾")).toBeTruthy();
  for (const label of ["Pipeline", "Experiments", "Annotate", "Dashboard"]) {
    expect(screen.getByRole("link", { name: label, hidden: true })).toBeTruthy();
  }
});
