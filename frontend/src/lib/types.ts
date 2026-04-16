// Triage API 类型定义

export type TriageLevel = 'EMERGENCY' | 'URGENT' | 'ROUTINE' | 'SELF_CARE';

export type TriageStatus = 'final' | 'need_more_info' | 'error';

export type RouteMode = 'driving' | 'transit' | 'walking';

// 医院信息
export interface Hospital {
  rank: number;
  name: string;
  is_3a: boolean;
  address: string;
  distance_m: number;
  location: {
    lat: number;
    lng: number;
  };
  phone: string;
  reason: string;
}

// 导航结果
export interface NavigationResult {
  radius_km?: number;
  hospitals: Hospital[];
  route_plan?: {
    to_hospital_rank: number;
    mode: RouteMode;
    eta_min: number;
    summary: string;
  };
}

// 证据
export interface Evidence {
  pmid?: string;
  title?: string;
  year?: string;
  source?: string;
  type?: string;
  note?: string;
  source_type?: string;
  source_description?: string;
  content?: string;
  confidence?: number;
}

// 天气预警（新结构，完全迁移）
export interface WeatherAlert {
  condition?: string;      // 天气状况（如"小雨"、"多云"）
  temp_c?: number;         // 摄氏温度
  humidity?: number;       // 湿度百分比（0-100）
  wind_speed_kmh?: number; // 风速 km/h
  tip?: string;            // 出行建议
}

// 视觉发现
export interface VisualFindings {
  type?: string;
  summary?: string;
  features?: string[];
  confidence?: number;
  observations?: string[];
}

// 请求
export interface TriageRequest {
  session_id: string;
  text: string;
  image_base64?: string;
  gps_lat?: number;
  gps_lng?: number;
}

// 响应
export interface TriageResponse {
  status: TriageStatus;
  session_id: string;
  triage_level?: TriageLevel;
  triage_reason?: string;
  triage_source?: string;
  recommended_departments: string[];
  possible_causes: string[];
  self_care_tips: string[];
  red_flags: string[];
  clarify_questions: string[];
  navigation?: NavigationResult;
  evidence?: Evidence[];
  weather_alert?: WeatherAlert;
  visual_findings?: VisualFindings;
  response: string;
  disclaimer?: string;
  turn_count: number;
  error_message?: string;
}

// 消息
export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  image?: string;
  triageData?: TriageResponse;
}
