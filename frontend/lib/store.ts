import { create } from "zustand";
import { persist } from "zustand/middleware";
type UI = {
  runId: string | null;
  setRunId: (id: string) => void;
  collapsed: boolean;
  toggleSidebar: () => void;
};
export const useUI = create<UI>()(
  persist(
    (set) => ({
      runId: null,
      setRunId: (runId) => set({ runId }),
      collapsed: false,
      toggleSidebar: () => set((s) => ({ collapsed: !s.collapsed })),
    }),
    { name: "contentforge-ui" },
  ),
);
