import api from './index'

export const analyzeProject = (projectId, analyzeTypes = ['reliability', 'sales_activity'], top_k = 5, modelId = null) =>
  api.post('/agents/analyze', {
    project_id: projectId,
    analyze_types: analyzeTypes,
    top_k,
    model_id: modelId,
  })

export const queryAgent = (projectId, question, top_k = 5, modelId = null) =>
  api.post('/agents/query', {
    project_id: projectId,
    question,
    top_k,
    model_id: modelId,
  })
