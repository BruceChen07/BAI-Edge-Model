export type ApiResponse<T> = {
  code: number
  message: string
  data: T
}

export type ModelInfo = {
  name: string
  size: number
  modified_at: string
  digest: string
}

export type SessionInfo = {
  id: string
  title: string
  mode: string
  language: string
  rag_enabled: boolean
  agent_enabled: boolean
  last_message_at?: string | null
}

export type KnowledgeBaseInfo = {
  id: string
  name: string
  description: string
  path: string
  status: string
  file_count: number
  chunk_count: number
}

export type ChatPayload = {
  session_id: string
  query: string
  model_name?: string
  language?: string
  rag_enabled?: boolean
  agent_enabled?: boolean
  knowledge_base_ids?: string[]
  top_k?: number
  score_threshold?: number
  include_memory?: boolean
}

export type ChatResponse = {
  answer: string
  citations: Array<Record<string, unknown>>
  model_used: string
}

export type ResourceSnapshot = {
  cpu: {
    cpu_percent: number | null
    cpu_cores_physical: number | null
    cpu_cores_logical: number | null
  }
  memory: {
    total_gb: number | null
    available_gb: number | null
    used_gb: number | null
    percent: number | null
    swap_total_gb: number | null
    swap_used_gb: number | null
  }
  gpu: {
    available: boolean
    gpus?: Array<{
      name: string
      memory_total_mb: number
      memory_used_mb: number
      memory_free_mb: number
      utilization_percent: number
    }>
    error?: string
  }
}

export type ModelFeasibility = {
  feasible: boolean
  warnings: string[]
  current_resources: ResourceSnapshot
  model_requirement: {
    ollama_name: string
    param_size: string
    display_name: string
    ram_gb: number
    vram_gb: number | null
    cpu_cores: number
    approx_size_gb: number
    description: string
    modelscope_name: string | null
  } | null
  recommendation: {
    suggested_model: string
    suggested_display_name: string
    suggested_ollama_name: string
    suggested_modelscope_name: string | null
    ram_required_gb: number
    vram_required_gb: number | null
    approx_size_gb: number
    description: string
    reason: string
  } | null
  param_size: string
}

export type ModelRecommendation = {
  ollama_name: string
  param_size: string
  display_name: string
  ram_gb: number
  vram_gb: number | null
  cpu_cores: number
  approx_size_gb: number
  description: string
  tags: string[]
  modelscope_name: string | null
  feasible: boolean
  warnings: string[]
}

export type CatalogItem = {
  ollama_name: string
  param_size: string
  display_name: string
  ram_gb: number
  vram_gb: number | null
  cpu_cores: number
  approx_size_gb: number
  description: string
  tags: string[]
  modelscope_name: string | null
  feasible: boolean
}

export type PullResult = {
  action?: string
  model: string
  display_name?: string
  status?: string
  error?: string
  elapsed_seconds?: number
}

export type TimeoutInfo = {
  model_name: string
  param_size: string
  timeout: {
    connect: number
    read: number
    write: number
    pool: number
  }
  user_override: boolean
}

const API_BASE = 'http://127.0.0.1:8000/api/v1'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const isFormData = init?.body instanceof FormData
  const response = await fetch(`${API_BASE}${path}`, {
    headers: isFormData
      ? init?.headers
      : {
          'Content-Type': 'application/json',
          ...(init?.headers ?? {}),
        },
    ...init,
  })

  if (!response.ok) {
    let detail = `Request failed: ${response.status}`
    try {
      const errorPayload = (await response.json()) as { detail?: string }
      if (errorPayload.detail) {
        detail = errorPayload.detail
      }
    } catch {
      // Ignore JSON parsing failures for non-JSON error responses.
    }
    throw new Error(detail)
  }

  const payload = (await response.json()) as ApiResponse<T>
  return payload.data
}

export const api = {
  getSystemInfo: () => request<Record<string, unknown>>('/system/info'),
  getSettings: () => request<Record<string, unknown>>('/settings'),
  getLanguages: () => request<Array<{ code: string; label: string }>>('/languages'),
  getModels: () => request<ModelInfo[]>('/models'),
  listKnowledgeBases: () => request<KnowledgeBaseInfo[]>('/knowledge-bases'),
  listSessions: () => request<SessionInfo[]>('/sessions'),
  listTasks: () => request<Array<Record<string, unknown>>>('/tasks'),
  listMemories: () => request<Array<Record<string, unknown>>>('/memories'),
  createKnowledgeBase: (payload: { name: string; description?: string }) =>
    request<KnowledgeBaseInfo>('/knowledge-bases', {
      method: 'POST',
      body: JSON.stringify({
        name: payload.name,
        description: payload.description ?? '',
      }),
    }),
  uploadKnowledgeBaseFile: (payload: {
    kbId: string
    file: File
    enableOcr?: boolean
  }) => {
    const formData = new FormData()
    formData.append('file', payload.file)
    return request<Record<string, unknown>>(
      `/knowledge-bases/${payload.kbId}/files/upload?enable_ocr=${payload.enableOcr ?? true}`,
      {
        method: 'POST',
        body: formData,
      },
    )
  },
  createSession: (payload: Partial<SessionInfo> & { title: string }) =>
    request<SessionInfo>('/sessions', {
      method: 'POST',
      body: JSON.stringify({
        title: payload.title,
        mode: payload.mode ?? 'chat',
        language: payload.language ?? 'zh-CN',
        rag_enabled: payload.rag_enabled ?? true,
        agent_enabled: payload.agent_enabled ?? false,
      }),
    }),
  chat: (payload: ChatPayload) =>
    request<ChatResponse>('/chat/completions', {
      method: 'POST',
      body: JSON.stringify({
        language: 'zh-CN',
        rag_enabled: true,
        agent_enabled: false,
        top_k: 5,
        score_threshold: 0.1,
        include_memory: true,
        knowledge_base_ids: [],
        ...payload,
      }),
    }),
  getResources: () =>
    request<{ snapshot: ResourceSnapshot; feasibility?: ModelFeasibility; recommendations: ModelRecommendation[] }>('/system/resources'),
  checkModelResources: (modelName: string) =>
    request<{ snapshot: ResourceSnapshot; feasibility: ModelFeasibility; recommendations: ModelRecommendation[] }>(
      `/system/resources/check?model_name=${encodeURIComponent(modelName)}`,
    ),
  getModelRecommendations: () =>
    request<ModelRecommendation[]>('/system/models/recommendations'),
  getTimeoutInfo: (modelName: string) =>
    request<TimeoutInfo>(`/system/timeout-info?model_name=${encodeURIComponent(modelName)}`),
  setTimeoutOverride: (readTimeoutSeconds: number | null) =>
    request<{ user_timeout_override_seconds: number | null; message: string }>(
      '/system/timeout-override',
      {
        method: 'PUT',
        body: JSON.stringify({ read_timeout_seconds: readTimeoutSeconds }),
      },
    ),
  getModelCatalog: () =>
    request<CatalogItem[]>('/system/models/catalog'),
  pullModel: (modelName: string) =>
    request<PullResult>('/system/models/pull', {
      method: 'POST',
      body: JSON.stringify({ model_name: modelName }),
    }),
}
