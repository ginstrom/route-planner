import { defineStore } from "pinia";

import { apiPost } from "../api";
import type { PlanResponse } from "../types";


export const useRunStore = defineStore("run", {
  state: () => ({
    latestPlan: null as PlanResponse | null,
    running: false,
    error: "" as string,
  }),
  actions: {
    reset() {
      this.latestPlan = null;
      this.running = false;
      this.error = "";
    },
    async runPlanner(query: string) {
      this.running = true;
      this.error = "";
      try {
        this.latestPlan = await apiPost<PlanResponse>("/api/plan", { query });
        return this.latestPlan;
      } catch (error) {
        this.error = error instanceof Error ? error.message : "Planner request failed";
        throw error;
      } finally {
        this.running = false;
      }
    },
  },
});
