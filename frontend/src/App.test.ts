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

    expect(wrapper.get("[data-testid='start-node']").html()).toContain("A");
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
                  payload: {},
                  highlights: {},
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
    expect(wrapper.text()).toContain("Latency: 12 ms");

    await wrapper.get("[data-testid='trace-step-0']").trigger("click");
    await flushUi();

    expect(wrapper.text()).not.toContain("Latency: 12 ms");
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
});
