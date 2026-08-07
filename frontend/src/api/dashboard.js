import api from '@/utils/api'

export function getStrategyRanking(params) { return api.get('/strategy/dashboard/strategy_ranking/', { params }) }
export function getFactorHeatmap(params) { return api.get('/strategy/dashboard/factor_heatmap/', { params }) }
export function getMarketOverview(params) { return api.get('/strategy/dashboard/market_overview/', { params }) }
export function getNetValueCurve(params) { return api.get('/strategy/dashboard/net_value/', { params }) }
export function getCorrelationMatrix(params) { return api.get('/strategy/dashboard/correlation/', { params }) }
export function getFactorIC(params) { return api.get('/strategy/dashboard/factor_ic/', { params }) }
export function getMarketState(params) { return api.get('/strategy/dashboard/market_state/', { params }) }
