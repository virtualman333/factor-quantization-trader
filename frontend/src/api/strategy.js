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
export function getBacktestTasks() { return api.get('/strategy/configs/backtest_tasks/') }
export function runMonteCarlo(id, data) { return api.post(`/strategy/configs/${id}/monte_carlo/`, data) }
export function runWalkForward(id, data) { return api.post(`/strategy/configs/${id}/walk_forward/`, data) }
export function exportBacktestReport(id) { return api.get(`/strategy/configs/${id}/export_report/`, { responseType: 'blob' }) }
export function optimizeParams(id, data) { return api.post(`/strategy/configs/${id}/optimize_params/`, data) }
export function optimizeWeights(id, data) { return api.post(`/strategy/configs/${id}/optimize_weights/`, data) }
export function compareStrategies(data) { return api.post('/strategy/configs/compare/', data) }

export function getPortfolios(params) { return api.get('/strategy/portfolios/', { params }) }
export function createPortfolio(data) { return api.post('/strategy/portfolios/', data) }
export function updatePortfolio(id, data) { return api.put(`/strategy/portfolios/${id}/`, data) }
export function deletePortfolio(id) { return api.delete(`/strategy/portfolios/${id}/`) }
export function runPortfolioBacktest(id, data) { return api.post(`/strategy/portfolios/${id}/backtest/`, data) }

export function getFactors(params) { return api.get('/strategy/factors/', { params }) }
export function createFactor(data) { return api.post('/strategy/factors/', data) }
export function updateFactor(id, data) { return api.put(`/strategy/factors/${id}/`, data) }
export function calculateFactor(data) { return api.post('/strategy/factors/calculate/', data) }

export function getSignals(params) { return api.get('/strategy/signals/', { params }) }
export function executeSignal(id) { return api.post(`/strategy/signals/${id}/execute/`) }

export function getBacktests(params) { return api.get('/strategy/backtests/', { params }) }

export function getInstruments(instType) { return api.get('/strategy/configs/instruments/', { params: { inst_type: instType } }) }

