import api from '@/utils/api'

export function getBalances(params) { return api.get('/account/balances/', { params }) }
export function saveBalanceSnapshot() { return api.post('/account/balances/snapshot/') }
export function getLiveBalance() { return api.get('/account/balances/live/') }

export function getPositions(params) { return api.get('/account/positions/', { params }) }
export function savePositionSnapshot(data) { return api.post('/account/positions/snapshot/', data) }
export function getLivePositions(params) { return api.get('/account/positions/live/', { params }) }

export function getNetValues(params) { return api.get('/account/net-value/', { params }) }
export function recordNetValue() { return api.post('/account/net-value/record/') }
