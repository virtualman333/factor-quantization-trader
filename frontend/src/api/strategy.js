import api from '@/utils/api'

export function getStrategies(params) { return api.get('/strategy/configs/', { params }) }
export function getStrategy(id) { return api.get(`/strategy/configs/${id}/`) }
export function createStrategy(data) { return api.post('/strategy/configs/', data) }
export function updateStrategy(id, data) { return api.put(`/strategy/configs/${id}/`, data) }
export function deleteStrategy(id) { return api.delete(`/strategy/configs/${id}/`) }
export function activateStrategy(id) { return api.post(`/strategy/configs/${id}/activate/`) }
export function pauseStrategy(id) { return api.post(`/strategy/configs/${id}/pause/`) }
export function runSignals(id) { return api.post(`/strategy/configs/${id}/run_signals/`) }
export function executeSignals(id) { return api.post(`/strategy/configs/${id}/execute_signals/`) }
export function runBacktest(id, data) { return api.post(`/strategy/configs/${id}/backtest/`, data) }

export function getFactors(params) { return api.get('/strategy/factors/', { params }) }
export function calculateFactor(data) { return api.post('/strategy/factors/calculate/', data) }

export function getSignals(params) { return api.get('/strategy/signals/', { params }) }
export function executeSignal(id) { return api.post(`/strategy/signals/${id}/execute/`) }

export function getBacktests(params) { return api.get('/strategy/backtests/', { params }) }

export function getInstruments(instType) { return api.get('/strategy/configs/instruments/', { params: { inst_type: instType } }) }

