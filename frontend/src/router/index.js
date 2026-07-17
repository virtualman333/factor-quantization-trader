import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    component: () => import('@/layout/MainLayout.vue'),
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/dashboard/Index.vue'),
        meta: { title: '仪表盘', icon: 'Odometer' },
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
        meta: { title: 'K线数据', icon: 'TrendCharts' },
      },
      {
        path: 'market/tickers',
        name: 'Tickers',
        component: () => import('@/views/market/Tickers.vue'),
        meta: { title: '实时行情', icon: 'DataLine' },
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
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
