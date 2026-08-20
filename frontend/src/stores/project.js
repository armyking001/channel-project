import { create } from 'zustand'

export const useProjectStore = create((set) => ({
  refreshTrigger: 0,
  triggerRefresh: () => set((s) => ({ refreshTrigger: s.refreshTrigger + 1 })),
}))
