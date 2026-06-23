export type Locale = 'zh-CN' | 'en-US'

type MessageBundle = {
  title: string
  subtitle: string
  navigation: {
    home: string
    admin: string
    catalog: string
    downloads: string
    knowledgeBases: string
    markdownStudio: string
  }
  panels: {
    system: string
    chat: string
    models: string
    knowledgeBases: string
    sessions: string
    tasks: string
    memories: string
  }
  chat: {
    modelLabel: string
    kbLabel: string
    themeLabel: string
    themeLight: string
    themeDark: string
    themeEyeCare: string
    inputPlaceholder: string
    newSession: string
    send: string
    citations: string
    activeModel: string
    createKnowledgeBase: string
    createKnowledgeBaseTitle: string
    knowledgeBaseName: string
    knowledgeBaseDescription: string
    uploadFiles: string
    uploadHint: string
    submitKnowledgeBase: string
    citationScore: string
    citationMatchedTerms: string
    citationSource: string
    citationSection: string
    citationChunk: string
    citationPage: string
    citationSheet: string
    citationSlide: string
    citationQuote: string
  }
  kbManagement: {
    pageTitle: string
    searchPlaceholder: string
    create: string
    infoTab: string
    filesTab: string
    chunksTab: string
    reindex: string
    reindexing: string
    exportMarkdown: string
    exportDocx: string
    exportXlsx: string
    rename: string
    save: string
    deleteKb: string
    deleteFile: string
    deleteKbConfirm: string
    deleteKbDesc: string
    deleteFileConfirm: string
    uploaded: string
    deleted: string
    renamed: string
    reindexStarted: string
    createdAt: string
    updatedAt: string
    storagePath: string
    storageSize: string
    tokenCount: string
    chunkPreview: string
    chunkIndex: string
    fileName: string
    filterAllFiles: string
    parseStatus: string
    ocrStatus: string
    statusReady: string
    statusOther: string
  }
  status: {
    loading: string
    empty: string
    thinking: string
  }
  catalog: {
    pageTitle: string
    searchPlaceholder: string
    providerPlaceholder: string
    fitPlaceholder: string
    minScore: string
    refresh: string
    syncLocal: string
    syncCatalog: string
    syncFailed: string
    modelsInCatalog: string
    localDetected: string
    catalogDetected: string
    showing: string
    localOnlyHint: string
    model: string
    provider: string
    size: string
    score: string
    tps: string
    mode: string
    memory: string
    context: string
    source: string
    scores: string
    total: string
    quality: string
    speed: string
    fit: string
    contextScore: string
    description: string
    tags: string
    paramSize: string
    runMode: string
    quantization: string
    memoryRequired: string
    vramRequired: string
    estTps: string
    maxContext: string
    useCase: string
    moe: string
    available: string
    installed: string
    notInstalled: string
    yes: string
    no: string
    notAvailable: string
  }
  downloads: {
    navTitle: string
    pageTitle: string
    modelPlaceholder: string
    startDownload: string
    refreshJobs: string
    downloadStarted: string
    downloadStartFailed: string
    downloadPaused: string
    pauseFailed: string
    resolvedPlan: string
    liveProgress: string
    noActiveProgress: string
    latestJob: string
    noJobsYet: string
    downloadJobs: string
    model: string
    source: string
    status: string
    progress: string
    action: string
    pause: string
    output: string
    retries: string
    speed: string
    eta: string
    auto: string
    ollama: string
    huggingFace: string
    modelScope: string
    na: string
  }
}

export const messages: Record<Locale, MessageBundle> = {
  'zh-CN': {
    title: '端侧本地大模型 RAG + Agent 服务',
    subtitle: 'BAI端侧大模型',
    navigation: {
      home: '首页',
      admin: '管理后台',
      catalog: '模型目录',
      downloads: '下载中心',
      knowledgeBases: '知识库管理',
      markdownStudio: 'Markdown 工作室',
    },
    panels: {
      system: '系统信息',
      chat: '对话',
      models: '本地模型',
      knowledgeBases: '知识库',
      sessions: '会话',
      tasks: '任务',
      memories: '记忆',
    },
    chat: {
      modelLabel: '选择模型',
      kbLabel: '关联知识库',
      themeLabel: '主题',
      themeLight: '亮色',
      themeDark: '暗色',
      themeEyeCare: '护眼',
      inputPlaceholder: '输入你的问题，直接和本地大模型对话...',
      newSession: '新建会话',
      send: '发送',
      citations: '引用片段',
      activeModel: '当前模型',
      createKnowledgeBase: '创建知识库',
      createKnowledgeBaseTitle: '创建知识库并导入文件',
      knowledgeBaseName: '知识库名称',
      knowledgeBaseDescription: '知识库描述',
      uploadFiles: '导入文件',
      uploadHint: '支持 PDF、扫描版 PDF、DOC、DOCX。扫描版 PDF 会启用 OCR 识别。',
      submitKnowledgeBase: '创建并导入',
      citationScore: '相关度',
      citationMatchedTerms: '命中词',
      citationSource: '出处定位',
      citationSection: '章节',
      citationChunk: '分块',
      citationPage: '页码',
      citationSheet: '工作表',
      citationSlide: '幻灯片',
      citationQuote: '引用内容',
    },
    kbManagement: {
      pageTitle: '知识库管理',
      searchPlaceholder: '按知识库名称搜索',
      create: '创建知识库',
      infoTab: '概览',
      filesTab: '文件',
      chunksTab: '分块',
      reindex: '重建索引',
      reindexing: '重建中',
      exportMarkdown: '导出 Markdown',
      exportDocx: '导出 DOCX',
      exportXlsx: '导出 XLSX',
      rename: '重命名',
      save: '保存',
      deleteKb: '删除知识库',
      deleteFile: '删除文件',
      deleteKbConfirm: '确认删除该知识库？',
      deleteKbDesc: '该操作会永久删除该知识库下的全部文件与分块。',
      deleteFileConfirm: '确认删除该文件？',
      uploaded: '文件上传成功',
      deleted: '删除成功',
      renamed: '知识库已更新',
      reindexStarted: '已开始重建索引',
      createdAt: '创建时间',
      updatedAt: '更新时间',
      storagePath: '存储路径',
      storageSize: '占用空间',
      tokenCount: 'Token 总量',
      chunkPreview: '内容预览',
      chunkIndex: '分块序号',
      fileName: '文件名',
      filterAllFiles: '全部文件',
      parseStatus: '解析状态',
      ocrStatus: 'OCR 状态',
      statusReady: '就绪',
      statusOther: '处理中',
    },
    status: {
      loading: '加载中...',
      empty: '暂无数据',
      thinking: '模型生成中...',
    },
    catalog: {
      pageTitle: '模型目录',
      searchPlaceholder: '搜索模型...',
      providerPlaceholder: '厂商',
      fitPlaceholder: '适配等级',
      minScore: '最低分数',
      refresh: '刷新',
      syncLocal: '同步本地',
      syncCatalog: '同步目录',
      syncFailed: '同步失败',
      modelsInCatalog: '个模型',
      localDetected: '本地模型',
      catalogDetected: '目录模型',
      showing: '当前展示',
      localOnlyHint: '本地多出 {n} 个，建议点“同步本地”',
      model: '模型',
      provider: '厂商',
      size: '参数',
      score: '评分',
      tps: 'TPS',
      mode: '运行模式',
      memory: '内存',
      context: '上下文',
      source: '来源',
      scores: '评分明细',
      total: '总分',
      quality: '质量',
      speed: '速度',
      fit: '适配',
      contextScore: '上下文',
      description: '描述',
      tags: '标签',
      paramSize: '参数规模',
      runMode: '运行模式',
      quantization: '量化',
      memoryRequired: '所需内存',
      vramRequired: '所需显存',
      estTps: '预计 TPS',
      maxContext: '最大上下文',
      useCase: '适用场景',
      moe: 'MoE',
      available: '可用状态',
      installed: '已安装',
      notInstalled: '未安装',
      yes: '是',
      no: '否',
      notAvailable: '无',
    },
    downloads: {
      navTitle: '下载中心',
      pageTitle: '下载中心',
      modelPlaceholder: '模型名称，例如 qwen3:8b',
      startDownload: '开始下载',
      refreshJobs: '刷新任务',
      downloadStarted: '已开始下载，来源',
      downloadStartFailed: '启动下载失败',
      downloadPaused: '下载已暂停',
      pauseFailed: '暂停失败',
      resolvedPlan: '已解析下载计划',
      liveProgress: '实时进度',
      noActiveProgress: '当前没有活动中的进度流',
      latestJob: '最近任务',
      noJobsYet: '暂无下载任务',
      downloadJobs: '下载任务',
      model: '模型',
      source: '来源',
      status: '状态',
      progress: '进度',
      action: '操作',
      pause: '暂停',
      output: '输出路径',
      retries: '重试次数',
      speed: '速度',
      eta: '剩余时间',
      auto: '自动',
      ollama: 'Ollama',
      huggingFace: 'HuggingFace',
      modelScope: 'ModelScope',
      na: '无',
    },
  },
  'en-US': {
    title: 'Edge Local LLM RAG + Agent Service',
    subtitle: 'BAI Edge Model',
    navigation: {
      home: 'Home',
      admin: 'Admin',
      catalog: 'Catalog',
      downloads: 'Downloads',
      knowledgeBases: 'Knowledge Bases',
      markdownStudio: 'Markdown Studio',
    },
    panels: {
      system: 'System Info',
      chat: 'Conversation',
      models: 'Local Models',
      knowledgeBases: 'Knowledge Bases',
      sessions: 'Sessions',
      tasks: 'Tasks',
      memories: 'Memories',
    },
    chat: {
      modelLabel: 'Model',
      kbLabel: 'Knowledge Bases',
      themeLabel: 'Theme',
      themeLight: 'Light',
      themeDark: 'Dark',
      themeEyeCare: 'Eye Care',
      inputPlaceholder: 'Type your question and chat with a local model...',
      newSession: 'New Session',
      send: 'Send',
      citations: 'Citations',
      activeModel: 'Active Model',
      createKnowledgeBase: 'Create Knowledge Base',
      createKnowledgeBaseTitle: 'Create Knowledge Base And Import Files',
      knowledgeBaseName: 'Knowledge Base Name',
      knowledgeBaseDescription: 'Knowledge Base Description',
      uploadFiles: 'Import Files',
      uploadHint: 'Supports PDF, scanned PDF, DOC, and DOCX. OCR will be enabled for scanned PDFs.',
      submitKnowledgeBase: 'Create And Import',
      citationScore: 'Score',
      citationMatchedTerms: 'Matched Terms',
      citationSource: 'Source',
      citationSection: 'Section',
      citationChunk: 'Chunk',
      citationPage: 'Page',
      citationSheet: 'Sheet',
      citationSlide: 'Slide',
      citationQuote: 'Quote',
    },
    kbManagement: {
      pageTitle: 'Knowledge Base Management',
      searchPlaceholder: 'Search by knowledge base name',
      create: 'Create Knowledge Base',
      infoTab: 'Info',
      filesTab: 'Files',
      chunksTab: 'Chunks',
      reindex: 'Reindex',
      reindexing: 'Reindexing',
      exportMarkdown: 'Export Markdown',
      exportDocx: 'Export DOCX',
      exportXlsx: 'Export XLSX',
      rename: 'Rename',
      save: 'Save',
      deleteKb: 'Delete KB',
      deleteFile: 'Delete File',
      deleteKbConfirm: 'Delete this knowledge base?',
      deleteKbDesc: 'All files and chunks under this knowledge base will be removed permanently.',
      deleteFileConfirm: 'Delete this file?',
      uploaded: 'File uploaded successfully',
      deleted: 'Deleted successfully',
      renamed: 'Knowledge base updated',
      reindexStarted: 'Reindex started',
      createdAt: 'Created At',
      updatedAt: 'Updated At',
      storagePath: 'Storage Path',
      storageSize: 'Storage Size',
      tokenCount: 'Total Tokens',
      chunkPreview: 'Preview',
      chunkIndex: 'Chunk',
      fileName: 'File Name',
      filterAllFiles: 'All Files',
      parseStatus: 'Parse',
      ocrStatus: 'OCR',
      statusReady: 'Ready',
      statusOther: 'Processing',
    },
    status: {
      loading: 'Loading...',
      empty: 'No data',
      thinking: 'Generating...',
    },
    catalog: {
      pageTitle: 'Model Catalog',
      searchPlaceholder: 'Search models...',
      providerPlaceholder: 'Provider',
      fitPlaceholder: 'Fit Level',
      minScore: 'Min Score',
      refresh: 'Refresh',
      syncLocal: 'Sync Local',
      syncCatalog: 'Sync Catalog',
      syncFailed: 'Sync failed',
      modelsInCatalog: 'models in catalog',
      localDetected: 'Local',
      catalogDetected: 'Catalog',
      showing: 'Showing',
      localOnlyHint: '{n} local model(s) missing in catalog, click "Sync Local"',
      model: 'Model',
      provider: 'Provider',
      size: 'Size',
      score: 'Score',
      tps: 'TPS',
      mode: 'Mode',
      memory: 'Memory',
      context: 'Context',
      source: 'Source',
      scores: 'Scores',
      total: 'Total',
      quality: 'Quality',
      speed: 'Speed',
      fit: 'Fit',
      contextScore: 'Context',
      description: 'Description',
      tags: 'Tags',
      paramSize: 'Param Size',
      runMode: 'Run Mode',
      quantization: 'Quantization',
      memoryRequired: 'Memory Required',
      vramRequired: 'VRAM Required',
      estTps: 'Est. TPS',
      maxContext: 'Max Context',
      useCase: 'Use Case',
      moe: 'MoE',
      available: 'Available',
      installed: 'Installed',
      notInstalled: 'Not Installed',
      yes: 'Yes',
      no: 'No',
      notAvailable: 'N/A',
    },
    downloads: {
      navTitle: 'Downloads',
      pageTitle: 'Download Center',
      modelPlaceholder: 'Model name, e.g. qwen3:8b',
      startDownload: 'Start Download',
      refreshJobs: 'Refresh Jobs',
      downloadStarted: 'Download started via',
      downloadStartFailed: 'Failed to start download',
      downloadPaused: 'Download paused',
      pauseFailed: 'Failed to pause',
      resolvedPlan: 'Resolved plan for',
      liveProgress: 'Live Progress',
      noActiveProgress: 'No active progress stream',
      latestJob: 'Latest Job',
      noJobsYet: 'No jobs yet',
      downloadJobs: 'Download Jobs',
      model: 'Model',
      source: 'Source',
      status: 'Status',
      progress: 'Progress',
      action: 'Action',
      pause: 'Pause',
      output: 'Output',
      retries: 'Retries',
      speed: 'Speed',
      eta: 'ETA',
      auto: 'Auto',
      ollama: 'Ollama',
      huggingFace: 'HuggingFace',
      modelScope: 'ModelScope',
      na: 'N/A',
    },
  },
}
