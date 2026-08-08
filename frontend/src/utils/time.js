/**
 * 时间工具：统一按北京时间（东八区，Asia/Shanghai）格式化，
 * 不依赖浏览器本地时区，避免不同用户看到不同时间。
 */
const BEIJING_TZ = 'Asia/Shanghai'

const intlDateTime = new Intl.DateTimeFormat('zh-CN', {
  timeZone: BEIJING_TZ,
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hour12: false,
})

const intlDate = new Intl.DateTimeFormat('zh-CN', {
  timeZone: BEIJING_TZ,
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
})

/**
 * 解析任意时间值为 Date 对象。
 * 兼容：ISO 字符串 / 数字时间戳 / Date 实例
 */
export function parseTime(value) {
  if (value === null || value === undefined || value === '') return null
  if (value instanceof Date) return isNaN(value.getTime()) ? null : value
  if (typeof value === 'number') {
    const d = new Date(value < 1e12 ? value * 1000 : value)
    return isNaN(d.getTime()) ? null : d
  }
  const d = new Date(value)
  return isNaN(d.getTime()) ? null : d
}

/** 格式化：YYYY-MM-DD HH:mm:ss（北京时间） */
export function formatDateTime(value) {
  const d = parseTime(value)
  if (!d) return '--'
  const parts = intlDateTime.formatToParts(d)
  const map = {}
  parts.forEach((p) => { map[p.type] = p.value })
  return `${map.year}-${map.month}-${map.day} ${map.hour}:${map.minute}:${map.second}`
}

/** 格式化：YYYY-MM-DD（北京时间） */
export function formatDate(value) {
  const d = parseTime(value)
  if (!d) return '--'
  const parts = intlDate.formatToParts(d)
  const map = {}
  parts.forEach((p) => { map[p.type] = p.value })
  return `${map.year}-${map.month}-${map.day}`
}

/** 格式化：MM-DD HH:mm（北京时间，紧凑） */
export function formatShort(value) {
  const d = parseTime(value)
  if (!d) return '--'
  const parts = intlDateTime.formatToParts(d)
  const map = {}
  parts.forEach((p) => { map[p.type] = p.value })
  return `${map.month}-${map.day} ${map.hour}:${map.minute}`
}

/** 当前北京时间字符串 YYYY-MM-DD HH:mm:ss */
export function nowBeijing() {
  return formatDateTime(new Date())
}
