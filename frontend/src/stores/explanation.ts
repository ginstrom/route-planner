import { defineStore } from "pinia";

import { apiPost } from "../api";
import type { TraceExplainResponse } from "../types";


export const useExplanationStore = defineStore("explanation", {
  state: () => ({
    question: "" as string,
    answer: "" as string,
    plannerMode: "" as string,
    error: "" as string,
    lastQuery: {} as Record<string, string>,
    usedFallback: false,
    loading: false,
  }),
  actions: {
    reset() {
      this.question = "";
      this.answer = "";
      this.plannerMode = "";
      this.error = "";
      this.lastQuery = {};
      this.usedFallback = false;
      this.loading = false;
    },
    async askTraceQuestion(traceId: string, question: string, taskPrompt: string) {
      this.loading = true;
      this.error = "";
      this.answer = "";
      this.usedFallback = false;
      this.question = question;
      try {
        const response = await apiPost<TraceExplainResponse>(`/api/traces/${traceId}/explain`, {
          question,
          task_prompt: taskPrompt,
        });
        this.answer = response.answer;
        this.plannerMode = response.planner_mode;
        this.usedFallback = response.used_fallback;
        this.lastQuery = response.llm_query;
        this.error = response.error ?? "";
        return response;
      } catch (error) {
        this.error = error instanceof Error ? error.message : "Trace explanation request failed";
        throw error;
      } finally {
        this.loading = false;
      }
    },
  },
});
