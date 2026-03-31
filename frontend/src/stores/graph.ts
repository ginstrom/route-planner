import { defineStore } from "pinia";

import { apiGet, apiPatch, apiPost } from "../api";
import type { EdgeRecord, GraphPayload } from "../types";

function summarizeGraph(graph: GraphPayload) {
  return {
    nodeCount: graph.nodes.length,
    edgeCount: graph.edges.length,
  };
}

function validateGraph(graph: GraphPayload): string | null {
  if (graph.nodes.length === 0) {
    console.error("Graph payload contained no nodes", summarizeGraph(graph));
    return "Graph payload contained no nodes";
  }

  const nodeIds = new Set(graph.nodes.map((node) => node.id));
  const invalidCoordinates = graph.nodes
    .filter((node) => !Number.isFinite(node.x) || !Number.isFinite(node.y))
    .map((node) => node.id);
  if (invalidCoordinates.length > 0) {
    console.error("Graph payload contains invalid node coordinates", { invalidCoordinates });
    return "Graph payload contains invalid node coordinates";
  }

  const missingEndpoints = graph.edges
    .map((edge) => ({
      edgeId: edge.id,
      missing: [edge.source, edge.target].filter((nodeId) => !nodeIds.has(nodeId)),
    }))
    .filter((entry) => entry.missing.length > 0);
  if (missingEndpoints.length > 0) {
    console.error("Graph payload references unknown nodes", { missingEndpoints });
    return "Graph payload references unknown nodes";
  }

  return null;
}

export const useGraphStore = defineStore("graph", {
  state: () => ({
    nodes: [] as GraphPayload["nodes"],
    edges: [] as GraphPayload["edges"],
    loading: false,
    error: "" as string,
  }),
  actions: {
    applyGraph(graph: GraphPayload) {
      const validationError = validateGraph(graph);
      if (validationError) {
        this.nodes = [];
        this.edges = [];
        this.error = validationError;
        return false;
      }
      this.nodes = graph.nodes;
      this.edges = graph.edges;
      this.error = "";
      return true;
    },
    async loadGraph() {
      this.loading = true;
      this.error = "";
      console.info("Loading route graph");
      try {
        const graph = await apiGet<GraphPayload>("/api/graph");
        console.info("Loaded route graph", summarizeGraph(graph));
        this.applyGraph(graph);
      } catch (error) {
        this.nodes = [];
        this.edges = [];
        this.error = error instanceof Error ? error.message : "Graph request failed";
        console.error("Route graph request failed", error);
      } finally {
        this.loading = false;
      }
    },
    async patchEdge(edgeId: string, patch: Partial<Pick<EdgeRecord, "cost" | "blocked">>) {
      const updated = await apiPatch<EdgeRecord>(`/api/graph/edges/${edgeId}`, patch);
      this.edges = this.edges.map((edge) => (edge.id === edgeId ? updated : edge));
      this.error = "";
    },
    async resetGraph() {
      const graph = await apiPost<GraphPayload>("/api/graph/reset", {});
      this.applyGraph(graph);
    },
    async loadScenario(scenarioId: string) {
      const graph = await apiPost<GraphPayload>("/api/graph/load-scenario", { scenario_id: scenarioId });
      this.applyGraph(graph);
    },
  },
});
