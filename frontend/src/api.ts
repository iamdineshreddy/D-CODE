import axios from 'axios'
const base = ''
export const api = axios.create({ baseURL: base })

export const getOverview = () => api.get('/api/overview').then(r => r.data)
export const getProviders = () => api.get('/api/providers').then(r => r.data)
export const getModels = () => api.get('/api/models').then(r => r.data)
export const refreshAll = () => api.post('/api/providers/refresh-all').then(r => r.data)
export const getTasks = () => api.get('/api/tasks').then(r => r.data)
export const createTask = (p: any) => api.post('/api/tasks', p).then(r => r.data)
export const runTask = (id: string) => api.post(`/api/tasks/${id}/run`).then(r => r.data)
export const runTaskSync = (id: string) => api.post(`/api/tasks/${id}/run-sync`).then(r => r.data)
export const getCheckpoints = (id: string) => api.get(`/api/tasks/${id}/checkpoints`).then(r => r.data)
export const getUsage = () => api.get('/api/usage/summary').then(r => r.data)
export const getBudget = () => api.get('/api/usage/budget').then(r => r.data)
export const optimize = (p: any) => api.post('/api/optimize', p).then(r => r.data)
export const route = (p: any) => api.post('/api/route', p).then(r => r.data)
export const getApprovals = () => api.get('/api/approvals').then(r => r.data)
