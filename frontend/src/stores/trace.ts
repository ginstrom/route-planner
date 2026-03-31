import { defineStore } from "pinia";

import { apiGet } from "../api";
import type { TracePayload } from "../types";


export const useTraceStore = defineStore("trace", {
  state: () => ({
    trace: null as TracePayload | null,
    selectedStepIndex: 0,
  }),
  getters: {
    selectedStep(state) {
      return state.trace?.steps[state.selectedStepIndex] ?? null;
    },
  },
  actions: {
    async loadTrace(traceId: string) {
      this.trace = await apiGet<TracePayload>(`/api/traces/${traceId}`);
      this.selectedStepIndex = 0;
    },
    selectStep(index: number) {
      this.selectedStepIndex = index;
    },
  },
});
