import api from '@/utils/api'

export function getStrategyRanking(params) { return api.get('/strategy/dashboard/strategy_ranking/', { params }) }
export function getFactorHeatmap(params) { return api.get('/strategy/dashboard/factor_heatmap/', { params }) }
export function getMarketOverview(params) { return api.get('/strategy/dashboard/market_overview/', { params }) }
export function getNetValueCurve(params) { return api.get('/strategy/dashboard/net_value/', { params }) }
