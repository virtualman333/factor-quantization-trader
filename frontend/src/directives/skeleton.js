/**
 * v-skeleton 指令：给加载中的容器显示骨架屏
 * 用法: <div v-skeleton="loading" height="200px">内容</div>
 */
const DEFAULT_HEIGHT = '120px'

const skeletonEl = (el) => {
  let wrap = el._skeleton
  if (wrap) return wrap
  wrap = document.createElement('div')
  wrap.className = 'skeleton-wrap'
  wrap.style.cssText = `
    position: absolute; inset: 0; overflow: hidden;
    background: #f5f7fa; border-radius: 4px; z-index: 9;
  `
  wrap.innerHTML = `
    <div class="skeleton-block" style="
      width: 100%; height: 100%; background: linear-gradient(90deg, #f5f7fa 25%, #e8eaed 37%, #f5f7fa 63%);
      background-size: 400% 100%; animation: skeleton-loading 1.4s ease infinite;
    "></div>
  `
  const style = document.createElement('style')
  style.textContent = `
    @keyframes skeleton-loading {
      0% { background-position: 100% 50%; }
      100% { background-position: 0 50%; }
    }
  `
  el._skeletonStyle = style
  document.head.appendChild(style)
  el._skeleton = wrap
  return wrap
}

export default {
  mounted(el, binding) {
    el.style.position = el.style.position || 'relative'
    const val = binding.value
    if (val) el.appendChild(skeletonEl(el))
  },
  updated(el, binding) {
    const val = binding.value
    if (val && !el._skeleton) {
      el.appendChild(skeletonEl(el))
    } else if (!val && el._skeleton) {
      el._skeleton.remove()
      el._skeleton = null
    }
  },
  unmounted(el) {
    el._skeleton?.remove?.()
    el._skeleton = null
  },
}
