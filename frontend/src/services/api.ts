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
  provider?: string
  param_size?: string
  score_total?: number
  score_quality?: number
  score_speed?: number
  score_fit?: number
  score_context?: number
  fit_level?: string
  estimated_tps?: number
  quantization?: string
  memory_required_gb?: number
  vram_required_gb?: number
  run_mode?: string
  use_case?: string
  max_context?: number
  is_moe?: boolean
  available?: boolean
  source?: string
  supports_multimodal?: boolean
  supports_file_upload?: boolean
  supported_upload_types?: string[]
  capability_source?: string
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

export type ChatAttachmentInfo = {
  id: string
  session_id: string
  message_id?: string | null
  file_name: string
  file_ext: string
  mime_type: string
  file_size: number
  attachment_type: string
  storage_path: string
  extracted_text_preview: string
  ocr_status: string
  status: string
  created_at?: string | null
}

export type SessionMessage = {
  id: string
  session_id: string
  role: 'user' | 'assistant'
  content: string
  content_type: string
  model_name: string
  prompt_tokens: number
  completion_tokens: number
  status: string
  attachments: ChatAttachmentInfo[]
}

export type SessionDetail = {
  session: SessionInfo
  messages: SessionMessage[]
}

export type KnowledgeBaseInfo = {
  id: string
  name: string
  description: string
  path: string
  status: string
  file_count: number
  chunk_count: number
  created_at?: string | null
  updated_at?: string | null
}

export type KnowledgeBaseStats = {
  kb_id: string
  total_size_bytes: number
  file_count: number
  chunk_count: number
  token_count: number
}

export type KnowledgeBaseChunk = {
  id: string
  document_id: string
  kb_id: string
  chunk_index: number
  content: string
  content_hash: string
  page_no?: number | null
  sheet_name?: string
  slide_no?: number | null
  heading_path?: string
  token_count: number
  vector_ref: string
  created_at?: string | null
  file_name?: string
}

export type KnowledgeBaseChunkPage = {
  items: KnowledgeBaseChunk[]
  total: number
  offset: number
  limit: number
}

export type ExportResult = {
  export_id: string
  file_name: string
  file_path: string
}

export type ChatPayload = {
  session_id: string
  query: string
  model_name?: string
  language?: string
  rag_enabled?: boolean
  agent_enabled?: boolean
  knowledge_base_ids?: string[]
  attachment_ids?: string[]
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

// Model catalog (Phase 2) types
export type CatalogEntry = {
  id: string
  model_name: string
  provider: string
  param_size: string
  version: string
  score_total: number
  score_quality: number
  score_speed: number
  score_fit: number
  score_context: number
  fit_level: string
  estimated_tps: number
  quantization: string
  memory_required_gb: number
  vram_required_gb: number
  run_mode: string
  use_case: string
  max_context: number
  is_moe: boolean
  available: boolean
  description: string
  tags: string[]
  source: string
  last_synced_at: string
  created_at: string
  updated_at: string
}

export type CatalogListParams = {
  provider?: string
  param_size?: string
  fit_level?: string
  use_case?: string
  run_mode?: string
  min_score?: number
  sort_by?: string
  sort_dir?: string
  offset?: number
  limit?: number
}

export type CatalogListResponse = {
  total: number
  items: CatalogEntry[]
}

export type PullResult = {
  action?: string
  model: string
  display_name?: string
  status?: string
  error?: string
  elapsed_seconds?: number
}

export type DownloadSource = {
  name: string
  url: string
  priority: number
  enabled: boolean
  timeout_seconds: number
}

export type DownloadPlan = {
  model_name: string
  sources: DownloadSource[]
}

export type DownloadJob = {
  id: string
  model_name: string
  source_name: string
  source_url: string
  total_bytes: number
  downloaded_bytes: number
  chunk_size: number
  status: string
  error_message: string
  retry_count: number
  max_retries: number
  priority: number
  output_path: string
  started_at: string
  completed_at: string
  last_progress_at: string
  created_at: string
  updated_at: string
}

export type DownloadJobListResponse = {
  total: number
  items: DownloadJob[]
}

export type DownloadPullResponse = {
  model_name: string
  status: string
  source?: string
  job_id?: string
  error?: string
  elapsed_seconds?: number
}

export type DownloadProgressEvent = {
  job_id: string
  model_name: string
  status: string
  downloaded_bytes: number
  total_bytes: number
  percent: number
  speed_mbps: number
  eta_seconds: number
  source_name: string
  error: string
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

export const API_BASE = 'http://127.0.0.1:8000/api/v1'

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
  deleteKnowledgeBase: (kbId: string) =>
    request<{ deleted: boolean; kb_id: string }>(`/knowledge-bases/${kbId}`, {
      method: 'DELETE',
    }),
  updateKnowledgeBase: (payload: {
    id: string
    name: string
    description?: string
  }) =>
    request<KnowledgeBaseInfo>(`/knowledge-bases/${payload.id}`, {
      method: 'PUT',
      body: JSON.stringify({
        name: payload.name,
        description: payload.description ?? '',
        status: 'ready',
      }),
    }),
  listKnowledgeBaseFiles: (kbId: string) =>
    request<Array<Record<string, unknown>>>(`/knowledge-bases/${kbId}/files`),
  deleteKnowledgeBaseFile: (kbId: string, fileId: string) =>
    request<{ deleted: boolean }>(
      `/knowledge-bases/${kbId}/files/${fileId}`,
      { method: 'DELETE' },
    ),
  getKnowledgeBaseStats: (kbId: string) =>
    request<KnowledgeBaseStats>(`/knowledge-bases/${kbId}/stats`),
  listKnowledgeBaseChunks: (payload: {
    kbId: string
    documentId?: string
    offset?: number
    limit?: number
  }) => {
    const params = new URLSearchParams()
    if (payload.documentId) {
      params.set('document_id', payload.documentId)
    }
    params.set('offset', String(payload.offset ?? 0))
    params.set('limit', String(payload.limit ?? 50))
    return request<KnowledgeBaseChunkPage>(
      `/knowledge-bases/${payload.kbId}/chunks?${params.toString()}`,
    )
  },
  reindexKnowledgeBase: (kbId: string) =>
    request<Record<string, unknown>>(`/knowledge-bases/${kbId}/reindex`, {
      method: 'POST',
    }),
  createMarkdownExport: (payload: { source_type: string; source_id: string; title: string }) =>
    request<ExportResult>('/exports/markdown', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  createDocxExport: (payload: { source_type: string; source_id: string; title: string }) =>
    request<ExportResult>('/exports/docx', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  createXlsxExport: (payload: { source_type: string; source_id: string; title: string }) =>
    request<ExportResult>('/exports/xlsx', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  listSessions: () => request<SessionInfo[]>('/sessions'),
  getSession: (sessionId: string) =>
    request<SessionDetail>(`/sessions/${encodeURIComponent(sessionId)}`),
  listTasks: () => request<Array<Record<string, unknown>>>('/tasks'),
  getTask: (taskId: string) => request<Record<string, unknown>>(`/tasks/${taskId}`),
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
    modelName?: string
  }) => {
    const formData = new FormData()
    formData.append('file', payload.file)
    const params = new URLSearchParams()
    params.set('enable_ocr', String(payload.enableOcr ?? true))
    if (payload.modelName) {
      params.set('model_name', payload.modelName)
    }
    return request<Record<string, unknown>>(
      `/knowledge-bases/${payload.kbId}/files/upload?${params.toString()}`,
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
  uploadChatAttachment: (payload: {
    sessionId: string
    file: File
    enableOcr?: boolean
    modelName?: string
  }) => {
    const formData = new FormData()
    formData.append('file', payload.file)
    const params = new URLSearchParams()
    params.set('enable_ocr', String(payload.enableOcr ?? true))
    if (payload.modelName) {
      params.set('model_name', payload.modelName)
    }
    return request<ChatAttachmentInfo>(
      `/sessions/${encodeURIComponent(payload.sessionId)}/attachments?${params.toString()}`,
      {
        method: 'POST',
        body: formData,
      },
    )
  },
  deleteChatAttachment: (attachmentId: string) =>
    request<{ deleted: boolean; attachment_id: string }>(
      `/chat/attachments/${encodeURIComponent(attachmentId)}`,
      {
        method: 'DELETE',
      },
    ),
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
  catalogList: (params: CatalogListParams = {}) => {
    const searchParams = new URLSearchParams()
    if (params.provider) searchParams.set('provider', params.provider)
    if (params.param_size) searchParams.set('param_size', params.param_size)
    if (params.fit_level) searchParams.set('fit_level', params.fit_level)
    if (params.use_case) searchParams.set('use_case', params.use_case)
    if (params.run_mode) searchParams.set('run_mode', params.run_mode)
    if (params.min_score !== undefined) searchParams.set('min_score', String(params.min_score))
    if (params.sort_by) searchParams.set('sort_by', params.sort_by)
    if (params.sort_dir) searchParams.set('sort_dir', params.sort_dir)
    if (params.offset !== undefined) searchParams.set('offset', String(params.offset))
    if (params.limit !== undefined) searchParams.set('limit', String(params.limit))
    const qs = searchParams.toString()
    return request<CatalogListResponse>(`/catalog${qs ? '?' + qs : ''}`)
  },
  catalogSearch: (q: string) =>
    request<CatalogListResponse>(`/catalog/search?q=${encodeURIComponent(q)}`),
  catalogDetail: (modelName: string) =>
    request<CatalogEntry>(`/catalog/${encodeURIComponent(modelName)}`),
  catalogSync: (source: string = 'curated') =>
    request<{ message: string; source: string; count_before: number; hint: string }>(
      '/catalog/sync',
      { method: 'POST', body: JSON.stringify({ source }) },
    ),
  getDownloadPlan: (modelName: string, source: string = 'auto') =>
    request<DownloadPlan>(`/download/plan/${encodeURIComponent(modelName)}?source=${encodeURIComponent(source)}`),
  pullModelMultiSource: (payload: {
    model_name: string
    source?: string
    download_url?: string
    chunk_size?: number
  }) =>
    request<DownloadPullResponse>('/download/pull', {
      method: 'POST',
      body: JSON.stringify({
        source: 'auto',
        chunk_size: 1048576,
        ...payload,
      }),
    }),
  listDownloadJobs: (status?: string) =>
    request<DownloadJobListResponse>(`/download/jobs${status ? `?status=${encodeURIComponent(status)}` : ''}`),
  getDownloadJob: (jobId: string) =>
    request<DownloadJob>(`/download/jobs/${encodeURIComponent(jobId)}`),
  pauseDownloadJob: (jobId: string) =>
    request<{ message: string; job_id: string }>(`/download/jobs/${encodeURIComponent(jobId)}/pause`, {
      method: 'POST',
    }),
  pullModel: (modelName: string) =>
    request<PullResult>('/system/models/pull', {
      method: 'POST',
      body: JSON.stringify({ model_name: modelName }),
    }),
}
