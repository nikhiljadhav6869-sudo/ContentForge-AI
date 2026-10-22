import { create } from "zustand";
import { persist } from "zustand/middleware";
type UI = {
  runId: string | null;
  workspaceId: string | null;
  bindWorkspace: (id: string) => void;
  resetWorkspace: () => void;
  setRunId: (id: string | null) => void;
  collapsed: boolean;
  toggleSidebar: () => void;
};
export const useUI = create<UI>()(
  persist(
    (set) => ({
      runId: null,
      workspaceId: null,
      bindWorkspace: (workspaceId) =>
        set((state) =>
          state.workspaceId === workspaceId ? {} : { workspaceId, runId: null },
        ),
      resetWorkspace: () => set({ workspaceId: null, runId: null }),
      setRunId: (runId) => set({ runId }),
      collapsed: false,
      toggleSidebar: () => set((s) => ({ collapsed: !s.collapsed })),
    }),
    { name: "contentforge-ui" },
  ),
);
