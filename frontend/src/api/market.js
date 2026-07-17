import api from '@/utils/api'

export function getInstruments(params) { return api.get('/market/instruments/', { params }) }
export function syncInstruments(data) { return api.post('/market/instruments/sync/', data) }

export function getKlines(params) { return api.get('/market/klines/', { params }) }
export function fetchKlines(data) { return api.post('/market/klines/fetch/', data) }

export function getTickers(params) { return api.get('/market/tickers/', { params }) }
export function refreshTicker(data) { return api.post('/market/tickers/refresh/', data) }

export function getFundingRates(params) { return api.get('/market/funding-rates/', { params }) }
