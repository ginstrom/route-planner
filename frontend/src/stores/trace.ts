import { defineStore } from "pinia";

import { apiGet } from "../api";
import type { TracePayload } from "../types";


export const useTraceStore = defineStore("trace", {
  state: () => ({
    trace: null as TracePayload | null,
    selectedStepIndex: null as number | null,
  }),
  getters: {
    selectedStep(state) {
      return state.selectedStepIndex === null ? null : (state.trace?.steps[state.selectedStepIndex] ?? null);
    },
  },
  actions: {
    reset() {
      this.trace = null;
      this.selectedStepIndex = null;
    },
    async loadTrace(traceId: string) {
      this.trace = await apiGet<TracePayload>(`/api/traces/${traceId}`);
      this.selectedStepIndex = null;
    },
    selectStep(index: number) {
      this.selectedStepIndex = this.selectedStepIndex === index ? null : index;
    },
  },
});
