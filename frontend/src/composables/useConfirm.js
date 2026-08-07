/**
 * 操作确认 Hook：统一封装危险操作确认弹窗
 * 用法:
 *   const { confirmDelete } = useConfirm()
 *   confirmDelete('删除策略', async () => { await deleteStrategy(id) })
 */
import { ElMessageBox } from 'element-plus'

export function useConfirm() {
  /**
   * 通用确认
   * @param {String} message 提示内容
   * @param {String} title 标题
   * @param {Object} options 额外配置
   * @returns {Promise<Boolean>}
   */
  async function confirm(message, title = '确认操作', options = {}) {
    try {
      await ElMessageBox.confirm(message, title, {
        confirmButtonText: options.confirmText || '确认',
        cancelButtonText: '取消',
        type: options.type || 'warning',
        ...options,
      })
      return true
    } catch {
      return false
    }
  }

  /**
   * 危险操作确认（删除/撤单/切实盘等）
   * @param {String} message
   * @param {Function} action 确认后执行的操作
   */
  async function confirmDanger(message, action, options = {}) {
    const ok = await confirm(message, options.title || '危险操作', {
      type: 'warning',
      confirmButtonText: options.confirmText || '确认执行',
    })
    if (!ok) return false
    try {
      await action()
      return true
    } catch (e) {
      return false
    }
  }

  /**
   * 删除确认（红色按钮）
   * @param {String} name 要删除的对象名称
   * @param {Function} action
   */
  async function confirmDelete(name, action) {
    return confirmDanger(
      `此操作将永久删除「${name}」，是否继续？`,
      action,
      { title: '删除确认', confirmText: '删除' }
    )
  }

  return { confirm, confirmDanger, confirmDelete }
}
