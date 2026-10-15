import { create } from 'zustand'
import { testStorageZoneConnection } from '../api'

/**
 * 全局存储区域可达性状态
 *
 * - key: zoneId → 'pending' | 'ok' | 'unreachable' | 'testing'
 * - 同时维护 lastChecked 时间戳
 *
 * 约定：
 * - 主界面（StorageZones）在挂载和刷新时调用 testAll(zones)
 * - 任何位置订阅 useStorageZoneReachability(z.id) 即可拿当前状态
 * - 主动刷新后所有依赖它的视图自动更新
 */

export const useStorageZoneReachability = create((set, get) => ({
  // zoneId -> { state: 'ok'|'unreachable'|'pending'|'testing', message?: string, checkedAt?: number }
  status: {},
  // 测试中集合（避免重复触发）
  testingIds: new Set(),

  /**
   * 批量测试所有 zone 的可达性
   * @param {Array<{id:number}>} zones
   */
  async testAll(zones) {
    if (!Array.isArray(zones) || zones.length === 0) return
    const prev = get().status
    // 标记为 testing
    const next = { ...prev }
    for (const z of zones) {
      next[z.id] = { state: 'testing', message: '测试中...', checkedAt: Date.now() }
    }
    set({ status: next })

    // 并发上限 4，避免瞬时打爆后端
    const concurrency = 4
    for (let i = 0; i < zones.length; i += concurrency) {
      const batch = zones.slice(i, i + concurrency)
      await Promise.all(batch.map(z => get().testOne(z.id)))
    }
  },

  /**
   * 测试单个 zone，更新自身状态
   */
  async testOne(zoneId) {
    const prev = get().status
    const cur = prev[zoneId]
    if (cur && cur.state === 'testing') {
      // 如果是并发触发，已在 testing，跳过
    }
    set({
      status: { ...get().status, [zoneId]: { state: 'testing', checkedAt: Date.now() } },
    })
    try {
      const r = await testStorageZoneConnection(zoneId)
      const ok = !!r.data.ok
      set({
        status: {
          ...get().status,
          [zoneId]: {
            state: ok ? 'ok' : 'unreachable',
            message: r.data.message || (ok ? 'OK' : '连接失败'),
            checkedAt: Date.now(),
          },
        },
      })
    } catch (e) {
      const msg = e?.response?.data?.detail || e?.message || '请求失败'
      set({
        status: {
          ...get().status,
          [zoneId]: {
            state: 'unreachable',
            message: msg,
            checkedAt: Date.now(),
          },
        },
      })
    }
  },

  /**
   * 重置某 zone（删除/编辑后调用，重新探测）
   */
  reset(zoneId) {
    const next = { ...get().status }
    delete next[zoneId]
    set({ status: next })
  },
}))

/**
 * 派生辅助：取单个 zone 的当前状态（不订阅，只快照）
 */
export const getZoneStatus = (zoneId) => {
  const all = useStorageZoneReachability.getState().status
  return all[zoneId] || { state: 'pending' }
}
