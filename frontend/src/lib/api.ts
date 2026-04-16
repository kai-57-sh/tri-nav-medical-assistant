import type { TriageRequest, TriageResponse } from './types';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

// LangChain API 响应类型
interface LangChainAPIResponse {
  output?: {
    session_id?: string;
    text?: string;
    turn_count?: number;
    clarify_questions?: string[];
    triage_level?: string;
    triage_source?: string;
    triage_reason?: string;
    recommended_departments?: string[];
    possible_causes?: string[];
    self_care_tips?: string[];
    red_flags?: string[];
    navigation?: any;  // 权威字段：后端返回 navigation
    weather_alert?: any;
    visual_findings?: any;
    evidence_selected?: any;  // 权威字段：后端返回 evidence_selected
    final_response?: string;
    response?: string;
    status?: string;
    error_message?: string;
    disclaimer?: string;
  };
  metadata?: {
    run_id?: string;
  };
}

// 将 LangChain 响应转换为前端格式
function transformResponse(apiResponse: LangChainAPIResponse): TriageResponse {
  // 统一使用 output 字段作为解析入口
  const output = apiResponse.output ?? (apiResponse as any);
  const hasError = output.error_message && output.error_message.length > 0;

  return {
    status: hasError ? 'error' : (output.status === 'need_more_info' ? 'need_more_info' : 'final'),
    session_id: output.session_id || '',
    triage_level: output.triage_level as any,
    triage_reason: output.triage_reason || '',
    triage_source: output.triage_source,
    recommended_departments: output.recommended_departments || [],
    possible_causes: output.possible_causes || [],
    self_care_tips: output.self_care_tips || [],
    red_flags: output.red_flags || [],
    clarify_questions: output.clarify_questions || [],
    // 权威字段：仅使用 output.navigation，移除向后兼容
    navigation: output.navigation,
    // 权威字段：仅使用 output.evidence_selected，移除向后兼容
    evidence: output.evidence_selected ?? [],
    weather_alert: output.weather_alert,
    visual_findings: output.visual_findings,
    response: output.response || output.final_response || '抱歉，无法获取响应。',
    disclaimer: output.disclaimer,  // 独立字段，不从 response 拼接
    turn_count: output.turn_count || 1,
    error_message: output.error_message,
  };
}

// API 客户端类
export class TriageAPIClient {
  private baseURL: string;

  constructor(baseURL: string = API_BASE) {
    this.baseURL = baseURL;
  }

  // 健康检查
  async healthCheck(): Promise<{ status: string }> {
    const response = await fetch(`${this.baseURL}/health`);
    if (!response.ok) {
      throw new Error('Health check failed');
    }
    return response.json();
  }

  // 发送分诊请求
  async sendTriageMessage(request: TriageRequest): Promise<TriageResponse> {
    const response = await fetch(`${this.baseURL}/assistant/invoke`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ input: request }),
    });

    if (!response.ok) {
      throw new Error(`API error: ${response.status} ${response.statusText}`);
    }

    const apiResponse: LangChainAPIResponse = await response.json();
    return transformResponse(apiResponse);
  }

  // 流式分诊请求 (SSE)
  async streamTriageMessage(
    request: TriageRequest,
    onChunk: (chunk: string) => void,
    onUpdate: (update: any) => void,
    onComplete: (response: TriageResponse) => void,
    onError: (error: Error) => void
  ): Promise<void> {
    try {
      const response = await fetch(`${this.baseURL}/assistant/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ input: request }),
      });

      if (!response.ok) {
        throw new Error(`Stream error: ${response.status} ${response.statusText}`);
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error('No response body');
      }

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            if (data === '[DONE]') {
              continue;
            }

            try {
              const parsed = JSON.parse(data);
              if (parsed.type === 'token') {
                onChunk(parsed.content || '');
              } else if (parsed.type === 'update') {
                onUpdate(parsed.data);
              } else if (parsed.type === 'final') {
                onComplete(transformResponse(parsed.data));
              }
            } catch (e) {
              console.error('Failed to parse SSE data:', e);
            }
          }
        }
      }
    } catch (error) {
      onError(error as Error);
    }
  }
}

// 默认 API 客户端实例
export const apiClient = new TriageAPIClient();
