import { mount } from "@vue/test-utils";
import { createPinia } from "pinia";
import { nextTick } from "vue";

import App from "./App.vue";


const graphResponse = {
  nodes: [
    { id: "A", label: "A", x: 80, y: 90 },
    { id: "B", label: "B", x: 250, y: 60 },
  ],
  edges: [{ id: "A-B", source: "A", target: "B", cost: 4, blocked: false }],
};


async function flushUi() {
  await Promise.resolve();
  await Promise.resolve();
  await new Promise((resolve) => window.setTimeout(resolve, 0));
  await nextTick();
}


describe("App", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("loads graph data into the controls and graph view", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/api/graph")) {
          return new Response(JSON.stringify(graphResponse), { status: 200 });
        }
        throw new Error(`Unhandled fetch: ${url}`);
      }),
    );

    const wrapper = mount(App, { global: { plugins: [createPinia()] } });
    await flushUi();

    expect(wrapper.find("[data-testid='start-node']").exists()).toBe(false);
    expect(wrapper.text()).not.toContain("Required Visits");
    expect(wrapper.text()).not.toContain("Build Query");
    expect(wrapper.text()).not.toContain("Scenario");
    expect(wrapper.get("[data-testid='planner-query']").element.tagName).toBe("TEXTAREA");
    expect(wrapper.get("[data-testid='edge-row-A-B'] input[type='number']").element.value).toBe("4");
    expect(wrapper.get("[data-testid='graph-node-A']").text()).toContain("A");
  });

  it("runs the planner and renders summary, trace, and candidates", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith("/api/graph")) {
          return new Response(JSON.stringify(graphResponse), { status: 200 });
        }
        if (url.endsWith("/api/plan") && init?.method === "POST") {
          return new Response(
            JSON.stringify({
              run_id: "run-1",
              trace_id: "trace-1",
              status: "SUCCESS",
              route: ["A", "B"],
              total_cost: 4,
              summary: "Planned route A -> B with total cost 4.",
              candidates: [
                { route: ["A", "B"], total_cost: 4, status: "ACCEPTED", rejection_reason: null },
              ],
            }),
            { status: 200 },
          );
        }
        if (url.endsWith("/api/traces/trace-1")) {
          return new Response(
            JSON.stringify({
              trace_id: "trace-1",
              run_id: "run-1",
              steps: [
                {
                  step_index: 0,
                  step_type: "planner",
                  name: "planner.mode",
                  summary: "Planner mode: anthropic_with_fallback",
                  payload: { planner_mode: "anthropic_with_fallback" },
                  highlights: {},
                  latency_ms: null,
                },
                {
                  step_index: 1,
                  step_type: "tool",
                  name: "parse_request",
                  summary: "Parsed request",
                  payload: {},
                  highlights: {},
                  latency_ms: null,
                },
              ],
            }),
            { status: 200 },
          );
        }
        throw new Error(`Unhandled fetch: ${url}`);
      }),
    );

    const wrapper = mount(App, { global: { plugins: [createPinia()] } });
    await flushUi();

    await wrapper.get("[data-testid='planner-query']").setValue("Start at A and visit B");
    await wrapper.get("[data-testid='run-planner']").trigger("click");
    await flushUi();

    expect(wrapper.get("[data-testid='summary-route']").text()).toContain("A -> B");
    expect(wrapper.get("[data-testid='planner-mode-flag']").text()).toContain("anthropic_with_fallback");
    expect(wrapper.get("[data-testid='trace-step-1']").text()).toContain("parse_request");
    expect(wrapper.get("[data-testid='candidate-0']").text()).toContain("4");
  });

  it("expands and collapses trace details inline", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith("/api/graph")) {
          return new Response(JSON.stringify(graphResponse), { status: 200 });
        }
        if (url.endsWith("/api/plan") && init?.method === "POST") {
          return new Response(
            JSON.stringify({
              run_id: "run-1",
              trace_id: "trace-1",
              status: "SUCCESS",
              route: ["A", "B"],
              total_cost: 4,
              summary: "Planned route A -> B with total cost 4.",
              candidates: [],
            }),
            { status: 200 },
          );
        }
        if (url.endsWith("/api/traces/trace-1")) {
          return new Response(
            JSON.stringify({
              trace_id: "trace-1",
              run_id: "run-1",
              steps: [
                {
                  step_index: 0,
                  step_type: "planner",
                  name: "planner.preview_problem",
                  summary: "Prepared the formal routing problem for solving.",
                  payload: { start: "A", required_visits: ["B", "C"] },
                  highlights: { focus_nodes: ["A", "B", "C"] },
                  latency_ms: 12,
                },
              ],
            }),
            { status: 200 },
          );
        }
        throw new Error(`Unhandled fetch: ${url}`);
      }),
    );

    const wrapper = mount(App, { global: { plugins: [createPinia()] } });
    await flushUi();

    await wrapper.get("[data-testid='run-planner']").trigger("click");
    await flushUi();

    expect(wrapper.text()).not.toContain("Latency: 12 ms");

    await wrapper.get("[data-testid='trace-step-0']").trigger("click");
    await flushUi();

    expect(wrapper.text()).toContain("Prepared the formal routing problem for solving.");
    expect(wrapper.text()).toContain("start");
    expect(wrapper.text()).toContain("required_visits");
    expect(wrapper.text()).toContain("focus_nodes");
    expect(wrapper.text()).toContain("B");
    expect(wrapper.text()).toContain("C");
    expect(wrapper.text()).toContain("Latency: 12 ms");

    await wrapper.get("[data-testid='trace-step-0']").trigger("click");
    await flushUi();

    expect(wrapper.text()).not.toContain("Latency: 12 ms");
  });

  it("opens and closes a raw trace modal for the selected step", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith("/api/graph")) {
          return new Response(JSON.stringify(graphResponse), { status: 200 });
        }
        if (url.endsWith("/api/plan") && init?.method === "POST") {
          return new Response(
            JSON.stringify({
              run_id: "run-1",
              trace_id: "trace-1",
              status: "SUCCESS",
              route: ["A", "B"],
              total_cost: 4,
              summary: "Planned route A -> B with total cost 4.",
              candidates: [],
            }),
            { status: 200 },
          );
        }
        if (url.endsWith("/api/traces/trace-1")) {
          return new Response(
            JSON.stringify({
              trace_id: "trace-1",
              run_id: "run-1",
              steps: [
                {
                  step_index: 0,
                  step_type: "planner",
                  name: "planner.preview_problem",
                  summary: "Prepared the formal routing problem for solving.",
                  payload: { start: "A", required_visits: ["B", "C"] },
                  highlights: { focus_nodes: ["A", "B", "C"] },
                  latency_ms: 12,
                },
              ],
            }),
            { status: 200 },
          );
        }
        throw new Error(`Unhandled fetch: ${url}`);
      }),
    );

    const wrapper = mount(App, { global: { plugins: [createPinia()] } });
    await flushUi();

    await wrapper.get("[data-testid='run-planner']").trigger("click");
    await flushUi();

    expect(wrapper.find("[data-testid='trace-raw-modal']").exists()).toBe(false);

    await wrapper.get("[data-testid='trace-raw-0']").trigger("click");
    await flushUi();

    const rawModal = document.body.querySelector("[data-testid='trace-raw-modal']");
    const rawJson = document.body.querySelector("[data-testid='trace-raw-json']");
    const rawClose = document.body.querySelector("[data-testid='trace-raw-close']");

    expect(rawModal?.textContent).toContain("Raw Trace");
    expect(rawJson?.textContent).toContain("\"name\": \"planner.preview_problem\"");
    expect(rawJson?.textContent).toContain("\"required_visits\": [");

    (rawClose as HTMLButtonElement | null)?.click();
    await flushUi();

    expect(document.body.querySelector("[data-testid='trace-raw-modal']")).toBeNull();
  });

  it("opens a raw popup for the full trace from the Trace header", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith("/api/graph")) {
          return new Response(JSON.stringify(graphResponse), { status: 200 });
        }
        if (url.endsWith("/api/plan") && init?.method === "POST") {
          return new Response(
            JSON.stringify({
              run_id: "run-1",
              trace_id: "trace-1",
              status: "SUCCESS",
              route: ["A", "B"],
              total_cost: 4,
              summary: "Planned route A -> B with total cost 4.",
              candidates: [],
            }),
            { status: 200 },
          );
        }
        if (url.endsWith("/api/traces/trace-1")) {
          return new Response(
            JSON.stringify({
              trace_id: "trace-1",
              run_id: "run-1",
              steps: [
                {
                  step_index: 0,
                  step_type: "planner",
                  name: "planner.preview_problem",
                  summary: "Prepared the formal routing problem for solving.",
                  payload: { start: "A" },
                  highlights: {},
                  latency_ms: null,
                },
              ],
            }),
            { status: 200 },
          );
        }
        throw new Error(`Unhandled fetch: ${url}`);
      }),
    );

    const wrapper = mount(App, { global: { plugins: [createPinia()] } });
    await flushUi();

    await wrapper.get("[data-testid='run-planner']").trigger("click");
    await flushUi();

    await wrapper.get("[data-testid='trace-raw-all']").trigger("click");
    await flushUi();

    const rawModal = document.body.querySelector("[data-testid='trace-raw-modal']");
    const rawJson = document.body.querySelector("[data-testid='trace-raw-json']");

    expect(rawModal?.textContent).toContain("Raw Trace");
    expect(rawJson?.textContent).toContain("\"trace_id\": \"trace-1\"");
    expect(rawJson?.textContent).toContain("\"steps\": [");
  });

  it("shows a graph-pane error when the backend graph request fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/api/graph")) {
          return new Response(JSON.stringify({ detail: "not found" }), { status: 404 });
        }
        throw new Error(`Unhandled fetch: ${url}`);
      }),
    );

    const wrapper = mount(App, { global: { plugins: [createPinia()] } });
    await flushUi();

    expect(wrapper.get("[data-testid='graph-error']").text()).toContain("Request failed for /api/graph with 404");
  });

  it("highlights the planned route edges in the graph", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith("/api/graph")) {
          return new Response(
            JSON.stringify({
              nodes: [
                { id: "A", label: "A", x: 80, y: 90 },
                { id: "B", label: "B", x: 250, y: 60 },
                { id: "C", label: "C", x: 380, y: 160 },
              ],
              edges: [
                { id: "A-B", source: "A", target: "B", cost: 4, blocked: false },
                { id: "B-C", source: "B", target: "C", cost: 3, blocked: false },
              ],
            }),
            { status: 200 },
          );
        }
        if (url.endsWith("/api/plan") && init?.method === "POST") {
          return new Response(
            JSON.stringify({
              run_id: "run-1",
              trace_id: "trace-1",
              status: "SUCCESS",
              route: ["A", "B", "C"],
              total_cost: 7,
              summary: "Planned route A -> B -> C with total cost 7.",
              candidates: [{ route: ["A", "B", "C"], total_cost: 7, status: "ACCEPTED", rejection_reason: null }],
            }),
            { status: 200 },
          );
        }
        if (url.endsWith("/api/traces/trace-1")) {
          return new Response(JSON.stringify({ trace_id: "trace-1", run_id: "run-1", steps: [] }), { status: 200 });
        }
        throw new Error(`Unhandled fetch: ${url}`);
      }),
    );

    const wrapper = mount(App, { global: { plugins: [createPinia()] } });
    await flushUi();

    await wrapper.get("[data-testid='run-planner']").trigger("click");
    await flushUi();

    const activeEdges = wrapper.findAll("[data-testid='graph-edge-active']");
    expect(activeEdges).toHaveLength(2);
  });

  it("clears the latest route, trace, and highlights when the graph is reset", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith("/api/graph")) {
          return new Response(
            JSON.stringify({
              nodes: [
                { id: "A", label: "A", x: 80, y: 90 },
                { id: "B", label: "B", x: 250, y: 60 },
                { id: "C", label: "C", x: 380, y: 160 },
              ],
              edges: [
                { id: "A-B", source: "A", target: "B", cost: 4, blocked: false },
                { id: "B-C", source: "B", target: "C", cost: 3, blocked: false },
              ],
            }),
            { status: 200 },
          );
        }
        if (url.endsWith("/api/plan") && init?.method === "POST") {
          return new Response(
            JSON.stringify({
              run_id: "run-1",
              trace_id: "trace-1",
              status: "SUCCESS",
              route: ["A", "B", "C"],
              total_cost: 7,
              summary: "Planned route A -> B -> C with total cost 7.",
              candidates: [{ route: ["A", "B", "C"], total_cost: 7, status: "ACCEPTED", rejection_reason: null }],
            }),
            { status: 200 },
          );
        }
        if (url.endsWith("/api/traces/trace-1")) {
          return new Response(
            JSON.stringify({
              trace_id: "trace-1",
              run_id: "run-1",
              steps: [
                {
                  step_index: 0,
                  step_type: "tool",
                  name: "planner.solve",
                  summary: "Solved route",
                  payload: {},
                  highlights: {},
                  latency_ms: null,
                },
              ],
            }),
            { status: 200 },
          );
        }
        if (url.endsWith("/api/graph/reset") && init?.method === "POST") {
          return new Response(JSON.stringify(graphResponse), { status: 200 });
        }
        throw new Error(`Unhandled fetch: ${url}`);
      }),
    );

    const wrapper = mount(App, { global: { plugins: [createPinia()] } });
    await flushUi();

    await wrapper.get("[data-testid='run-planner']").trigger("click");
    await flushUi();

    expect(wrapper.get("[data-testid='summary-route']").text()).toContain("A -> B -> C");
    expect(wrapper.findAll("[data-testid='graph-edge-active']")).toHaveLength(2);
    expect(wrapper.get("[data-testid='trace-step-0']").text()).toContain("planner.solve");
    expect(wrapper.get("[data-testid='candidate-0']").text()).toContain("A -> B -> C");

    const resetButton = wrapper
      .findAll("button")
      .find((button) => button.text() === "Reset Graph");

    expect(resetButton).toBeDefined();

    await resetButton!.trigger("click");
    await flushUi();

    expect(wrapper.get("[data-testid='summary-route']").text()).toContain("No route yet");
    expect(wrapper.text()).toContain("Run the planner to get a trace-grounded explanation.");
    expect(wrapper.findAll("[data-testid='graph-edge-active']")).toHaveLength(0);
    expect(wrapper.find("[data-testid='trace-step-0']").exists()).toBe(false);
    expect(wrapper.find("[data-testid='candidate-0']").exists()).toBe(false);
  });

  it("logs and surfaces an error when the graph payload has no nodes", async () => {
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => undefined);
    const infoSpy = vi.spyOn(console, "info").mockImplementation(() => undefined);

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/api/graph")) {
          return new Response(JSON.stringify({ nodes: [], edges: [] }), { status: 200 });
        }
        throw new Error(`Unhandled fetch: ${url}`);
      }),
    );

    const wrapper = mount(App, { global: { plugins: [createPinia()] } });
    await flushUi();

    expect(infoSpy).toHaveBeenCalledWith("Loading route graph");
    expect(errorSpy).toHaveBeenCalledWith("Graph payload contained no nodes", { edgeCount: 0, nodeCount: 0 });
    expect(wrapper.get("[data-testid='graph-error']").text()).toContain("Graph payload contained no nodes");
    expect(wrapper.find("[data-testid='route-graph-svg']").exists()).toBe(false);
  });

  it("logs and surfaces an error when graph edges reference missing nodes", async () => {
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => undefined);

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/api/graph")) {
          return new Response(
            JSON.stringify({
              nodes: [{ id: "A", label: "A", x: 80, y: 90 }],
              edges: [{ id: "A-B", source: "A", target: "B", cost: 4, blocked: false }],
            }),
            { status: 200 },
          );
        }
        throw new Error(`Unhandled fetch: ${url}`);
      }),
    );

    const wrapper = mount(App, { global: { plugins: [createPinia()] } });
    await flushUi();

    expect(errorSpy).toHaveBeenCalledWith("Graph payload references unknown nodes", {
      missingEndpoints: [{ edgeId: "A-B", missing: ["B"] }],
    });
    expect(wrapper.get("[data-testid='graph-error']").text()).toContain("Graph payload references unknown nodes");
    expect(wrapper.find("[data-testid='graph-node-A']").exists()).toBe(false);
  });

  it("asks for a trace explanation from the middle pane and renders fallback state", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith("/api/graph")) {
          return new Response(JSON.stringify(graphResponse), { status: 200 });
        }
        if (url.endsWith("/api/plan") && init?.method === "POST") {
          return new Response(
            JSON.stringify({
              run_id: "run-1",
              trace_id: "trace-1",
              status: "SUCCESS",
              route: ["A", "B"],
              total_cost: 4,
              summary: "Planned route A -> B with total cost 4.",
              candidates: [],
            }),
            { status: 200 },
          );
        }
        if (url.endsWith("/api/traces/trace-1") && (!init || !init.method || init.method === "GET")) {
          return new Response(
            JSON.stringify({
              trace_id: "trace-1",
              run_id: "run-1",
              steps: [
                {
                  step_index: 0,
                  step_type: "planner",
                  name: "planner.mode",
                  summary: "Planner mode: anthropic_with_fallback",
                  payload: { planner_mode: "anthropic_with_fallback" },
                  highlights: {},
                  latency_ms: null,
                },
                {
                  step_index: 1,
                  step_type: "tool",
                  name: "planner.verify_solution",
                  summary: "Route satisfies the requested visits.",
                  payload: { verified: true },
                  highlights: {},
                  latency_ms: null,
                },
              ],
            }),
            { status: 200 },
          );
        }
        if (url.endsWith("/api/traces/trace-1/explain") && init?.method === "POST") {
          return new Response(
            JSON.stringify({
              trace_id: "trace-1",
              planner_mode: "anthropic_with_fallback",
              used_fallback: true,
              answer: "Anthropic explanation failed; showing fallback explanation grounded in trace data.",
              llm_query: {
                system_prompt: "You explain route-planning decisions using only the provided task prompt, final result, and stored trace.",
                user_prompt: "Candidate summary from trace:\\n{\"candidates\":[{\"route\":[\"A\",\"B\"],\"total_cost\":4}]}",
              },
              error: null,
            }),
            { status: 200 },
          );
        }
        throw new Error(`Unhandled fetch: ${url}`);
      }),
    );

    const wrapper = mount(App, { global: { plugins: [createPinia()] } });
    await flushUi();

    expect(wrapper.get("[data-testid='trace-explain-query-link']").text()).toContain("see query");
    await wrapper.get("[data-testid='trace-explain-query-link']").trigger("click");
    await flushUi();
    expect(document.body.querySelector("[data-testid='trace-raw-json']")?.textContent).toContain("{}");
    (document.body.querySelector("[data-testid='trace-raw-close']") as HTMLButtonElement | null)?.click();
    await flushUi();

    await wrapper.get("[data-testid='planner-query']").setValue("Start at A and visit B");
    await wrapper.get("[data-testid='run-planner']").trigger("click");
    await flushUi();

    expect(wrapper.get("[data-testid='trace-explain-card']").text()).toContain("Ask About This Trace");

    await wrapper.get("[data-testid='trace-question']").setValue("Why did you choose A-B instead of A-C?");
    await wrapper.get("[data-testid='trace-explain-submit']").trigger("click");
    await flushUi();

    expect(wrapper.get("[data-testid='trace-explain-answer']").text()).toContain("fallback explanation");
    expect(wrapper.get("[data-testid='trace-explain-fallback']").text()).toContain("Anthropic explanation failed");
    expect(wrapper.get("[data-testid='trace-explain-query-link']").text()).toContain("see query");

    await wrapper.get("[data-testid='trace-explain-query-link']").trigger("click");
    await flushUi();

    expect(document.body.querySelector("[data-testid='trace-raw-json']")?.textContent).toContain("\"system_prompt\":");
    expect(document.body.querySelector("[data-testid='trace-raw-json']")?.textContent).toContain("\"user_prompt\":");
    expect(document.body.querySelector("[data-testid='trace-raw-json']")?.textContent).toContain("Candidate summary from trace");
  });
});
