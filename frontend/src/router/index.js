import { createRouter, createWebHistory } from 'vue-router'
import { getToken, getStoredUser } from '@/utils/token.js'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/auth/Login.vue'),
    meta: { title: '登录', requiresAuth: false },
  },
  {
    path: '/',
    component: () => import('@/layout/MainLayout.vue'),
    redirect: '/dashboard',
    meta: { requiresAuth: true },
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/dashboard/Index.vue'),
        meta: { title: '仪表盘', icon: 'Odometer', noCache: true },
      },
      {
        path: 'market/instruments',
        name: 'Instruments',
        component: () => import('@/views/market/Instruments.vue'),
        meta: { title: '交易品种', icon: 'Coin' },
      },
      {
        path: 'market/klines',
        name: 'Klines',
        component: () => import('@/views/market/Klines.vue'),
        meta: { title: 'K线数据', icon: 'TrendCharts', noCache: true },
      },
      {
        path: 'market/tickers',
        name: 'Tickers',
        component: () => import('@/views/market/Tickers.vue'),
        meta: { title: '实时行情', icon: 'DataLine', noCache: true },
      },
      {
        path: 'account/balances',
        name: 'Balances',
        component: () => import('@/views/account/Balances.vue'),
        meta: { title: '账户余额', icon: 'Wallet' },
      },
      {
        path: 'account/positions',
        name: 'Positions',
        component: () => import('@/views/account/Positions.vue'),
        meta: { title: '持仓管理', icon: 'PieChart' },
      },
      {
        path: 'account/netvalue',
        name: 'NetValue',
        component: () => import('@/views/account/NetValue.vue'),
        meta: { title: '净值曲线', icon: 'DataAnalysis' },
      },
      {
        path: 'account/analysis',
        name: 'AccountAnalysis',
        component: () => import('@/views/account/Analysis.vue'),
        meta: { title: '账户分析', icon: 'TrendCharts' },
      },
      {
        path: 'analysis',
        name: 'DataAnalysis',
        component: () => import('@/views/analysis/Index.vue'),
        meta: { title: '数据分析', icon: 'Histogram' },
      },
      {
        path: 'strategy/list',
        name: 'StrategyList',
        component: () => import('@/views/strategy/List.vue'),
        meta: { title: '策略管理', icon: 'SetUp' },
      },
      {
        path: 'strategy/factors',
        name: 'Factors',
        component: () => import('@/views/strategy/Factors.vue'),
        meta: { title: '因子定义', icon: 'Grid' },
      },
      {
        path: 'strategy/signals',
        name: 'Signals',
        component: () => import('@/views/strategy/Signals.vue'),
        meta: { title: '交易信号', icon: 'Bell' },
      },
      {
        path: 'strategy/backtests',
        name: 'Backtests',
        component: () => import('@/views/strategy/Backtests.vue'),
        meta: { title: '回测结果', icon: 'Histogram' },
      },
      {
        path: 'strategy/portfolios',
        name: 'Portfolios',
        component: () => import('@/views/strategy/Portfolios.vue'),
        meta: { title: '策略组合', icon: 'Files' },
      },
      {
        path: 'orders/list',
        name: 'OrderList',
        component: () => import('@/views/orders/List.vue'),
        meta: { title: '订单管理', icon: 'List' },
      },
      {
        path: 'orders/create',
        name: 'OrderCreate',
        component: () => import('@/views/orders/Create.vue'),
        meta: { title: '创建订单', icon: 'Plus' },
      },
      {
        path: 'settings',
        name: 'Settings',
        component: () => import('@/views/settings/Index.vue'),
        meta: { title: '系统设置', icon: 'Setting' },
      },
      {
        path: 'profile',
        name: 'Profile',
        component: () => import('@/views/settings/Profile.vue'),
        meta: { title: '个人中心', icon: 'User' },
      },
      {
        path: 'admin',
        name: 'Admin',
        component: () => import('@/views/settings/Admin.vue'),
        meta: { title: '系统管理', icon: 'Setting', requiresAdmin: true },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 路由守卫：未登录时重定向到 /login，管理员页面检查权限
router.beforeEach((to, from, next) => {
  const token = getToken()
  if (to.path === '/login') {
    if (token) {
      next('/')
    } else {
      next()
    }
    return
  }
  if (to.matched.some((r) => r.meta.requiresAuth !== false) && !token) {
    next({ path: '/login', query: { redirect: to.fullPath } })
    return
  }
  // 管理员页面需要 is_staff 或 is_superuser
  if (to.matched.some((r) => r.meta.requiresAdmin)) {
    const user = getStoredUser()
    if (!user || !(user.is_staff || user.is_superuser)) {
      next('/dashboard')
      return
    }
  }
  next()
})

export default router
