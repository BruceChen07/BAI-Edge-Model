export type Locale = 'zh-CN' | 'en-US'

type MessageBundle = {
  title: string
  subtitle: string
  navigation: {
    home: string
    admin: string
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
  }
  status: {
    loading: string
    empty: string
    thinking: string
  }
}

export const messages: Record<Locale, MessageBundle> = {
  'zh-CN': {
    title: '端侧本地大模型 RAG + Agent 服务',
    subtitle: 'BAI端侧大模型',
    navigation: {
      home: '首页',
      admin: '管理配置',
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
    },
    status: {
      loading: '加载中...',
      empty: '暂无数据',
      thinking: '模型生成中...',
    },
  },
  'en-US': {
    title: 'Edge Local LLM RAG + Agent Service',
    subtitle: 'BAI Edge Model',
    navigation: {
      home: 'Home',
      admin: 'Admin',
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
    },
    status: {
      loading: 'Loading...',
      empty: 'No data',
      thinking: 'Generating...',
    },
  },
}
