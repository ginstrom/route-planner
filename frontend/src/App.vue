<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { storeToRefs } from "pinia";

import { useGraphStore } from "./stores/graph";
import { useExplanationStore } from "./stores/explanation";
import { useRunStore } from "./stores/run";
import { useTraceStore } from "./stores/trace";
import type { TraceStep } from "./types";

const graphStore = useGraphStore();
const explanationStore = useExplanationStore();
const runStore = useRunStore();
const traceStore = useTraceStore();

const { nodes, edges, loading: graphLoading, error: graphError } = storeToRefs(graphStore);
const {
  answer: traceExplanationAnswer,
  error: traceExplanationError,
  lastQuery: traceExplanationLastQuery,
  loading: traceExplanationLoading,
  usedFallback: traceExplanationUsedFallback,
} = storeToRefs(explanationStore);
const { latestPlan, running, error } = storeToRefs(runStore);
const { trace, selectedStepIndex } = storeToRefs(traceStore);

const plannerQuery = ref("Start at A and visit C and E");
const selectedEdgeId = ref<string | null>(null);
const rawModalTitle = ref("Raw Trace");
const rawModalJson = ref("");
const traceQuestion = ref("");

const routeEdges = computed(() => {
  const route = latestPlan.value?.route ?? [];
  const active = new Set<string>();
  for (let index = 0; index < route.length - 1; index += 1) {
    active.add([route[index], route[index + 1]].sort().join("-"));
  }
  return active;
});

const graphBounds = computed(() => {
  const width = 520;
  const height = 360;
  return { width, height };
});

const summaryRoute = computed(() => (latestPlan.value?.route.length ? latestPlan.value.route.join(" -> ") : "No route yet"));
const plannerModeStep = computed(() => trace.value?.steps.find((step) => step.name === "planner.mode") ?? null);
const fallbackStep = computed(() => trace.value?.steps.find((step) => step.name === "planner.fallback") ?? null);
const llmErrorStep = computed(() => trace.value?.steps.find((step) => step.name === "planner.llm_error") ?? null);
const graphStateMessage = computed(() => {
  if (graphLoading.value) {
    return "Loading graph from backend...";
  }
  if (graphError.value) {
    return graphError.value;
  }
  return "No graph loaded yet.";
});
const plannerModeLabel = computed(() => {
  const value = plannerModeStep.value?.payload?.planner_mode;
  return typeof value === "string" ? value : "local";
});
const canExplainTrace = computed(() => Boolean(trace.value?.trace_id) && traceQuestion.value.trim().length > 0 && !traceExplanationLoading.value);

function edgeKey(source: string, target: string) {
  return [source, target].sort().join("-");
}

function hasTraceData(value: Record<string, unknown>) {
  return Object.keys(value).length > 0;
}

function formatTraceData(value: Record<string, unknown>) {
  return JSON.stringify(value, null, 2);
}

function openJsonModal(title: string, payload: unknown) {
  rawModalTitle.value = title;
  rawModalJson.value = JSON.stringify(payload, null, 2);
}

function highlightJson(json: string): string {
  return json
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(
      /("(\\u[\da-fA-F]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?)/g,
      (match) => {
        let cls = "json-number";
        if (/^"/.test(match)) {
          cls = /:$/.test(match) ? "json-key" : "json-string";
        } else if (/true|false/.test(match)) {
          cls = "json-boolean";
        } else if (/null/.test(match)) {
          cls = "json-null";
        }
        return `<span class="${cls}">${match}</span>`;
      },
    );
}

function clearDerivedRouteState() {
  runStore.reset();
  traceStore.reset();
  explanationStore.reset();
  traceQuestion.value = "";
}

async function loadGraph() {
  await graphStore.loadGraph();
}

async function runPlanner() {
  explanationStore.reset();
  traceQuestion.value = "";
  const result = await runStore.runPlanner(plannerQuery.value);
  await traceStore.loadTrace(result.trace_id);
}

async function resetGraph() {
  await graphStore.resetGraph();
  clearDerivedRouteState();
}

async function updateEdgeCost(edgeId: string, nextValue: string) {
  const parsed = Number(nextValue);
  if (!Number.isNaN(parsed) && parsed > 0) {
    await graphStore.patchEdge(edgeId, { cost: parsed });
  }
}

async function toggleEdgeBlocked(edgeId: string, blocked: boolean) {
  await graphStore.patchEdge(edgeId, { blocked });
}

async function explainTrace() {
  if (!trace.value?.trace_id || !traceQuestion.value.trim()) {
    return;
  }
  await explanationStore.askTraceQuestion(trace.value.trace_id, traceQuestion.value.trim(), plannerQuery.value);
}

function openRawTrace(step: TraceStep) {
  openJsonModal("Raw Trace", step);
}

function openRawTraceAll() {
  if (!trace.value) {
    return;
  }
  openJsonModal("Raw Trace", trace.value);
}

function openTraceExplainQuery() {
  openJsonModal("Trace Explanation Query", traceExplanationLastQuery.value);
}

function closeRawTrace() {
  rawModalJson.value = "";
}

onMounted(() => {
  void loadGraph();
});
</script>

<template>
  <div class="shell">
    <aside class="panel controls-panel">
      <p class="eyebrow">Planner Input</p>
      <h1>Graph Controls</h1>

      <label class="field">
        <span>Planner Query</span>
        <textarea v-model="plannerQuery" data-testid="planner-query" rows="4" />
      </label>

      <div class="button-row">
        <button data-testid="run-planner" :disabled="running" type="button" @click="runPlanner">
          {{ running ? "Planning..." : "Run Planner" }}
        </button>
        <button class="ghost-button" type="button" @click="resetGraph">Reset Graph</button>
      </div>

      <div class="edge-table">
        <div class="edge-header">
          <span>Edge</span>
          <span>Cost</span>
          <span>Blocked</span>
        </div>
        <div
          v-for="edge in edges"
          :key="edge.id"
          :data-testid="`edge-row-${edge.id}`"
          class="edge-row"
          :class="{ selected: selectedEdgeId === edge.id }"
          @click="selectedEdgeId = edge.id"
        >
          <span>{{ edge.id }}</span>
          <input :value="edge.cost" type="number" min="1" @change="updateEdgeCost(edge.id, ($event.target as HTMLInputElement).value)" />
          <input :checked="edge.blocked" type="checkbox" @change="toggleEdgeBlocked(edge.id, ($event.target as HTMLInputElement).checked)" />
        </div>
      </div>
    </aside>

    <main class="panel panel-graph">
      <p class="eyebrow">Network View</p>
      <h2>Route Graph</h2>
      <div v-if="graphLoading || graphError || nodes.length === 0" class="graph-state" :class="{ error: Boolean(graphError) }">
        <p :data-testid="graphError ? 'graph-error' : 'graph-status'">{{ graphStateMessage }}</p>
      </div>
      <svg v-else data-testid="route-graph-svg" :viewBox="`0 0 ${graphBounds.width} ${graphBounds.height}`" class="graph-svg">
        <g v-for="edge in edges" :key="edge.id">
          <line
            :x1="nodes.find((node) => node.id === edge.source)?.x ?? 0"
            :y1="nodes.find((node) => node.id === edge.source)?.y ?? 0"
            :x2="nodes.find((node) => node.id === edge.target)?.x ?? 0"
            :y2="nodes.find((node) => node.id === edge.target)?.y ?? 0"
            :data-testid="routeEdges.has(edgeKey(edge.source, edge.target)) ? 'graph-edge-active' : 'graph-edge'"
            class="edge-line"
            :class="{ blocked: edge.blocked, active: routeEdges.has(edgeKey(edge.source, edge.target)) }"
          />
          <text
            :x="((nodes.find((node) => node.id === edge.source)?.x ?? 0) + (nodes.find((node) => node.id === edge.target)?.x ?? 0)) / 2"
            :y="((nodes.find((node) => node.id === edge.source)?.y ?? 0) + (nodes.find((node) => node.id === edge.target)?.y ?? 0)) / 2 - 8"
            class="edge-label"
          >
            {{ edge.cost }}
          </text>
        </g>

        <g v-for="node in nodes" :key="node.id">
          <circle :cx="node.x" :cy="node.y" r="24" class="node-circle" />
          <text :x="node.x" :y="node.y + 6" :data-testid="`graph-node-${node.id}`" class="node-label">
            {{ node.id }}
          </text>
        </g>
      </svg>

      <section data-testid="trace-explain-card" class="trace-explain-card">
        <div class="trace-explain-header">
          <div>
            <p class="eyebrow">Trace Query</p>
            <h3>Ask About This Trace</h3>
          </div>
          <span v-if="traceExplanationUsedFallback" data-testid="trace-explain-fallback" class="summary-flag warning">
            Anthropic explanation failed; fallback used
          </span>
        </div>

        <label class="field">
          <span>Question</span>
          <textarea
            v-model="traceQuestion"
            data-testid="trace-question"
            rows="3"
            placeholder="Why did you choose A-B-C instead of A-C?"
          />
        </label>

        <div class="button-row">
          <button
            data-testid="trace-explain-submit"
            :disabled="!canExplainTrace"
            type="button"
            @click="explainTrace"
          >
            {{ traceExplanationLoading ? "Explaining..." : "Explain Route Choice" }}
          </button>
        </div>

        <div class="trace-query-actions">
          <button
            data-testid="trace-explain-query-link"
            class="trace-raw-link"
            type="button"
            @click.stop="openTraceExplainQuery"
          >
            (see query)
          </button>
        </div>

        <p v-if="!trace?.trace_id" class="graph-helper">Run the planner to ask questions about the completed trace.</p>
        <p v-if="traceExplanationError" class="error">{{ traceExplanationError }}</p>
        <p v-if="traceExplanationAnswer" data-testid="trace-explain-answer" class="trace-explain-answer">{{ traceExplanationAnswer }}</p>
      </section>
    </main>

    <section class="panel trace-panel">
      <p class="eyebrow">Trace Surface</p>
      <h2>Explainability</h2>

      <div class="summary-card">
        <p class="summary-label">Status</p>
        <strong>{{ latestPlan?.status ?? "IDLE" }}</strong>
        <div class="summary-flags">
          <span class="summary-flag" data-testid="planner-mode-flag">Mode: {{ plannerModeLabel }}</span>
          <span v-if="fallbackStep" class="summary-flag warning" data-testid="planner-fallback-flag">Fallback Active</span>
          <span v-if="llmErrorStep" class="summary-flag error-flag" data-testid="planner-error-flag">LLM Error</span>
        </div>
        <p data-testid="summary-route" class="summary-route">{{ summaryRoute }}</p>
        <p>{{ latestPlan?.summary ?? "Run the planner to get a trace-grounded explanation." }}</p>
        <p v-if="fallbackStep" class="warning-text">{{ fallbackStep.summary }}</p>
        <p v-if="llmErrorStep" class="error">{{ llmErrorStep.summary }}</p>
        <p v-if="error" class="error">{{ error }}</p>
      </div>

      <div class="trace-list">
        <div class="trace-section-header">
          <h3>Trace</h3>
          <button
            v-if="trace"
            data-testid="trace-raw-all"
            class="trace-inline-link"
            type="button"
            @click="openRawTraceAll"
          >
            (raw)
          </button>
        </div>
        <div
          v-for="step in trace?.steps ?? []"
          :key="step.step_index"
          class="trace-step-card"
          :class="{ selected: selectedStepIndex === step.step_index }"
        >
          <button
            :data-testid="`trace-step-${step.step_index}`"
            class="trace-step"
            :aria-expanded="selectedStepIndex === step.step_index"
            type="button"
            @click="traceStore.selectStep(step.step_index)"
          >
            <span class="trace-step-copy">
              <strong>{{ step.name }}</strong>
              <span>{{ step.summary }}</span>
            </span>
            <span class="trace-step-actions">
              <span class="trace-step-toggle">{{ selectedStepIndex === step.step_index ? "Hide" : "Show" }}</span>
              <button
                :data-testid="`trace-raw-${step.step_index}`"
                class="trace-raw-link"
                type="button"
                @click.stop="openRawTrace(step)"
              >
                raw
              </button>
            </span>
          </button>

          <div v-if="selectedStepIndex === step.step_index" class="trace-step-details">
            <p>{{ step.summary }}</p>
            <div v-if="hasTraceData(step.payload)" class="trace-step-block">
              <strong>Payload</strong>
              <pre>{{ formatTraceData(step.payload) }}</pre>
            </div>
            <div v-if="hasTraceData(step.highlights)" class="trace-step-block">
              <strong>Highlights</strong>
              <pre>{{ formatTraceData(step.highlights) }}</pre>
            </div>
            <p v-if="step.latency_ms !== null"><strong>Latency:</strong> {{ step.latency_ms }} ms</p>
          </div>
        </div>
      </div>

      <div class="candidate-list">
        <h3>Candidates</h3>
        <div
          v-for="(candidate, index) in latestPlan?.candidates ?? []"
          :key="`${candidate.route.join('-')}-${index}`"
          :data-testid="`candidate-${index}`"
          class="candidate-card"
        >
          <strong>{{ candidate.route.length ? candidate.route.join(" -> ") : "Rejected" }}</strong>
          <span>Cost: {{ candidate.total_cost ?? "n/a" }}</span>
          <span v-if="candidate.rejection_reason">{{ candidate.rejection_reason }}</span>
        </div>
      </div>

    </section>
  </div>

  <Teleport to="body">
    <div v-if="rawModalJson" data-testid="trace-raw-modal" class="trace-raw-modal-backdrop" @click.self="closeRawTrace">
      <div class="trace-raw-modal">
        <div class="trace-raw-modal-header">
          <strong>{{ rawModalTitle }}</strong>
          <button data-testid="trace-raw-close" class="trace-raw-close" type="button" @click="closeRawTrace">Close</button>
        </div>
        <!-- eslint-disable-next-line vue/no-v-html -->
        <pre data-testid="trace-raw-json" class="json-viewer" v-html="highlightJson(rawModalJson)" />
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
:global(body) {
  margin: 0;
  font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
  background:
    radial-gradient(circle at top left, rgba(255, 180, 80, 0.28), transparent 28%),
    linear-gradient(135deg, #f3efe4, #dfe7ea 48%, #b5c7cb);
  color: #142126;
}

:global(button),
:global(select),
:global(input),
:global(textarea) {
  font: inherit;
}

.shell {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 340px 1fr 380px;
  gap: 1rem;
  padding: 1rem;
  box-sizing: border-box;
}

.panel {
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid rgba(20, 33, 38, 0.12);
  border-radius: 24px;
  padding: 1.5rem;
  backdrop-filter: blur(14px);
  box-shadow: 0 24px 60px rgba(20, 33, 38, 0.12);
}

.eyebrow {
  margin: 0 0 0.5rem;
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #8a4b15;
}

h1,
h2,
h3 {
  margin: 0 0 0.75rem;
  font-family: "Space Grotesk", "IBM Plex Sans", sans-serif;
}

.controls-panel,
.trace-panel,
.panel-graph {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.field select,
.field textarea,
.field input,
.scenario-row select {
  border: 1px solid rgba(20, 33, 38, 0.16);
  border-radius: 14px;
  padding: 0.7rem 0.85rem;
  background: rgba(255, 255, 255, 0.9);
}

.button-row,
.scenario-row {
  display: flex;
  gap: 0.6rem;
}

button {
  border: none;
  border-radius: 999px;
  padding: 0.8rem 1rem;
  background: #163f52;
  color: white;
  cursor: pointer;
}

.ghost-button {
  background: rgba(22, 63, 82, 0.1);
  color: #163f52;
}

.visit-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.visit-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.35rem 0.6rem;
  border-radius: 999px;
  background: rgba(22, 63, 82, 0.08);
}

.edge-table {
  display: grid;
  gap: 0.55rem;
}

.edge-header,
.edge-row {
  display: grid;
  grid-template-columns: 1fr 82px 70px;
  gap: 0.5rem;
  align-items: center;
}

.edge-row {
  padding: 0.55rem;
  border-radius: 16px;
  background: rgba(243, 239, 228, 0.8);
}

.edge-row.selected {
  outline: 2px solid rgba(138, 75, 21, 0.4);
}

.graph-svg {
  width: 100%;
  min-height: 520px;
  border-radius: 20px;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.7), rgba(219, 234, 237, 0.9));
}

.graph-state {
  min-height: 520px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 20px;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.7), rgba(219, 234, 237, 0.9));
  color: #173746;
  text-align: center;
  padding: 1.5rem;
  box-sizing: border-box;
}

.graph-state.error {
  color: #9a3125;
}

.graph-helper {
  margin: 0;
  color: #4f6470;
}

.edge-line {
  stroke: #142126;
  stroke-width: 6;
  stroke-linecap: round;
}

.edge-line.active {
  stroke: #22915d;
}

.edge-line.blocked {
  stroke-dasharray: 12 10;
  stroke: #b03f2f;
}

.edge-line.blocked.active {
  stroke: #22915d;
}

.edge-label {
  font-size: 14px;
  fill: #173746;
  font-weight: 700;
  text-anchor: middle;
}

.node-circle {
  fill: #173746;
}

.node-label {
  fill: #f9f4ea;
  font-weight: 700;
  text-anchor: middle;
}

.summary-card,
.trace-list,
.candidate-list,
.trace-explain-card {
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
}

.trace-explain-card {
  padding: 1rem 1.1rem;
  border-radius: 20px;
  background: rgba(243, 239, 228, 0.72);
  border: 1px solid rgba(20, 33, 38, 0.08);
}

.trace-explain-header {
  display: flex;
  justify-content: space-between;
  gap: 0.75rem;
  align-items: flex-start;
}

.trace-explain-answer {
  margin: 0;
  line-height: 1.5;
}

.summary-flags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.summary-flag {
  display: inline-flex;
  align-items: center;
  padding: 0.3rem 0.7rem;
  border-radius: 999px;
  background: rgba(22, 63, 82, 0.1);
  color: #163f52;
  font-size: 0.85rem;
  font-weight: 700;
}

.summary-flag.warning {
  background: rgba(219, 109, 40, 0.16);
  color: #9b4918;
}

.summary-flag.error-flag {
  background: rgba(176, 63, 47, 0.15);
  color: #9a3125;
}

.summary-route {
  font-weight: 700;
}

.trace-step-card,
.candidate-card {
  border-radius: 18px;
  background: rgba(243, 239, 228, 0.85);
}

.trace-query-actions {
  display: flex;
  justify-content: flex-start;
}

.trace-section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
}

.trace-step,
.candidate-card {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  padding: 0.8rem;
  text-align: left;
}

.trace-step {
  width: 100%;
  align-items: stretch;
  background: transparent;
  border-radius: 18px;
  color: inherit;
}

.trace-step-copy {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.trace-step-toggle {
  font-size: 0.85rem;
  font-weight: 700;
  color: #8a4b15;
}

.trace-step-actions {
  margin-top: 0.45rem;
  display: inline-flex;
  align-items: center;
  gap: 0.6rem;
}

.trace-raw-link,
.trace-raw-close,
.trace-inline-link {
  padding: 0;
  border: none;
  background: transparent;
  color: #8a4b15;
  font-size: 0.85rem;
  font-weight: 700;
  text-decoration: underline;
  border-radius: 0;
}

.trace-step-card.selected {
  outline: 2px solid rgba(22, 63, 82, 0.35);
}

.trace-step-details {
  display: grid;
  gap: 0.65rem;
  padding: 0 0.8rem 0.8rem;
  color: #173746;
}

.trace-step-details p {
  margin: 0;
}

.trace-step-block {
  display: grid;
  gap: 0.35rem;
}

.trace-step-block pre {
  margin: 0;
  padding: 0.75rem;
  border-radius: 14px;
  background: rgba(20, 33, 38, 0.06);
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-word;
}

:global(.trace-raw-modal-backdrop) {
  position: fixed;
  inset: 0;
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1.5rem;
  background: rgba(20, 33, 38, 0.55);
}

:global(.trace-raw-modal) {
  width: min(760px, 90vw);
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding: 1rem;
  border-radius: 20px;
  background: #f9f4ea;
  box-shadow: 0 24px 60px rgba(20, 33, 38, 0.2);
}

:global(.trace-raw-modal-header) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  flex-shrink: 0;
}

:global(.trace-raw-modal-header button) {
  padding: 0;
  border: none;
  background: transparent;
  color: #8a4b15;
  font-size: 0.85rem;
  font-weight: 700;
  text-decoration: underline;
  border-radius: 0;
  cursor: pointer;
}

:global(.json-viewer) {
  margin: 0;
  padding: 1rem;
  border-radius: 14px;
  background: #1e2d33;
  color: #cdd8dc;
  overflow: auto;
  max-height: calc(80vh - 5rem);
  white-space: pre-wrap;
  word-break: break-all;
  font-family: "IBM Plex Mono", "Fira Code", "Cascadia Code", monospace;
  font-size: 0.85rem;
  line-height: 1.5;
}

:global(.json-key) { color: #7ecfdb; }
:global(.json-string) { color: #a8d9a0; }
:global(.json-number) { color: #f0a97e; }
:global(.json-boolean) { color: #c79eec; }
:global(.json-null) { color: #e87a7a; }

.error {
  color: #b03f2f;
}

.warning-text {
  color: #9b4918;
}

@media (max-width: 1120px) {
  .shell {
    grid-template-columns: 1fr;
  }
}
</style>
