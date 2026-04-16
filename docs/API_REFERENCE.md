# TriNav API 参考文档

> 医疗分诊与医院导航助手 - RESTful API 规范

版本: 1.0.0
基础路径: `http://localhost:8000`
协议: HTTP/HTTPS
数据格式: JSON

---

## 目录

1. [概述](#1-概述)
2. [认证](#2-认证)
3. [通用规范](#3-通用规范)
4. [API 端点](#4-api-端点)
5. [数据模型](#5-数据模型)
6. [错误码](#6-错误码)
7. [速率限制](#7-速率限制)
8. [示例代码](#8-示例代码)

---

## 1. 概述

TriNav API 提供医疗分诊和医院导航服务的 RESTful 接口。对外仍保持 `POST /assistant/invoke` 兼容包装，但服务内部默认执行路径已经切换到 v3 runtime；旧 LangGraph/LangServe 路径仅保留为 fallback 和 shadow compare。支持文本描述、图片上传和 GPS 定位等多种输入方式。

### 1.1 核心功能

- **症状分析**: 从用户描述中提取结构化症状信息
- **智能分诊**: 判断就诊 urgency（急诊/紧急/常规/自我护理）
- **医院导航**: 推荐附近医院并提供详细路线规划
- **证据检索**: 从 NCBI/PubMed 获取医学文献证据
- **图像识别**: 分析皮疹、伤口等视觉症状

### 1.2 端点列表

| 端点 | 方法 | 描述 | 认证 |
|:-----|:-----|:-----|:-----|
| `/assistant/invoke` | POST | 执行分诊评估 | 否 |
| `/assistant/v3/invoke` | POST | v3 协议适配入口（JSON） | 否 |
| `/assistant/v3/stream` | POST | v3 协议适配入口（SSE） | 否 |
| `/assistant/v3/shadow/compare` | POST | v1/v3 影子比对（灰度验证） | 否 |
| `/assistant/v3/runtime/doctor` | GET | v3 运行态诊断 | 否 |
| `/health` | GET | 健康检查 | 否 |
| `/` | GET | API 信息 | 否 |
| `/docs` | GET | Swagger UI 文档 | 否 |
| `/redoc` | GET | ReDoc 文档 | 否 |

---

## 2. 认证

当前版本不需要 API Key 认证。生产环境建议添加认证层：

```python
# 建议的认证方式
Authorization: Bearer YOUR_API_KEY

# 或使用查询参数
?api_key=YOUR_API_KEY
```

---

## 3. 通用规范

### 3.1 请求头

```http
Content-Type: application/json
Accept: application/json
```

### 3.2 响应头

> **注意**: 当前版本 (v1.0.0) 返回以下响应头：

```http
Content-Type: application/json
```

**计划中的响应头** (v1.1):
```http
X-Request-ID: uuid        # 请求追踪 ID
X-Response-Time: ms       # 响应时间（毫秒）
```

### 3.3 数据类型

| 类型 | 说明 | 示例 |
|:-----|:-----|:-----|
| `string` | 字符串 | `"手臂红疹"` |
| `number` | 浮点数 | `39.9042` |
| `integer` | 整数 | `1200` |
| `boolean` | 布尔值 | `true` / `false` |
| `array` | 数组 | `["皮肤科", "急诊"]` |
| `object` | 对象 | `{...}` |
| `null` | 空值 | `null` |

### 3.4 分级说明

| 分诊等级 | 描述 | 建议行动 |
|:---------|:-----|:---------|
| `EMERGENCY` | 急诊 | 立即前往急诊或呼叫 120 |
| `URGENT` | 紧急 | 尽快就医（24 小时内） |
| `ROUTINE` | 常规 | 预约门诊 |
| `SELF_CARE` | 自我护理 | 家庭护理 + 观察 |

### 3.5 v3/v4 执行路径与灰度开关

当前版本中，`/assistant/invoke` 仍是对外公开的兼容入口，请求会落入 v3 runtime 默认执行路径；`/assistant/v3/*` 为显式的 v3 协议适配入口。旧 LangGraph 路径不再是默认执行路径，仅用于 fallback/shadow。

典型执行路径：

1. `POST /assistant/invoke` 接收兼容请求包装，或直接调用 `POST /assistant/v3/invoke` / `POST /assistant/v3/stream`
2. 服务写入 `metadata.runtime_mode=v3`
3. 进入 v3 runtime 执行任务协调、内建插件和能力编排
4. 若启用 fallback/shadow，则旧 LangGraph 路径只参与兜底或比对
5. 若启用 canary，则结合 shadow 指标执行放量门禁

推荐环境变量示例：

```ini
V2_RUNTIME_ENABLED=false
V2_SHADOW_COMPARE_ENABLED=false
V3_RUNTIME_ENABLED=true
V3_SHADOW_COMPARE_ENABLED=false
V3_LEGACY_FALLBACK_ENABLED=true
V3_TASK_COORDINATOR_ENABLED=true
V3_BUILTIN_PLUGINS_ENABLED=true
V3_PLUGIN_TRACE_ENABLED=true
V3_PLUGIN_MEDICAL_FOOTER_ENABLED=true
V4_CANARY_ENABLED=false
V4_GATE_MAX_RED_FLAG_MISS_RATE=0.01
V4_GATE_MAX_P95_MS=6000
```

---

## 4. API 端点

### 4.1 分诊评估

**端点**: `POST /assistant/invoke`

**描述**: 执行医疗分诊评估，返回兼容包装下的分诊结果、运行追踪信息和稳定的公开字段集合。该端点对外保持兼容包装，内部默认走 v3 runtime。

**兼容请求包装**：请求体必须包含 `input` 对象，实际参数放在 `input` 内。这一公开 envelope 保持不变，用于兼容既有客户端。

#### 4.1.1 请求参数

| 字段 | 类型 | 必需 | 说明 | 约束 |
|:-----|:------|:-----|:-----|:-----|
| `session_id` | string | ❌ | 会话唯一标识（建议传入） | UUID 格式，缺省将自动生成 |
| `text` | string | ✅ | 症状描述 | 1-2000 字符 |
| `image_base64` | string | ❌ | 图片数据（Base64） | 最大 5MB |
| `gps_lat` | number | ❌ | 纬度 | -90 到 90 |
| `gps_lng` | number | ❌ | 经度 | -180 到 180 |

**注意**: 公开接口仅支持 `gps_lat` / `gps_lng`。未定义的别名字段会被忽略，因此客户端不应再发送 `lat` / `lng`。

#### 4.1.2 请求示例

**纯文本分诊:**

```bash
curl -X POST http://localhost:8000/assistant/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "session_id": "550e8400-e29b-41d4-a716-446655440000",
      "text": "手臂出现红疹，有点痒，持续2天"
    }
  }'
```

**带图片分诊:**

```bash
# 先将图片转换为 base64
image_base64=$(base64 -i rash_photo.jpg)

curl -X POST http://localhost:8000/assistant/invoke \
  -H "Content-Type: application/json" \
  -d "{
    \"input\": {
      \"session_id\": \"550e8400-e29b-41d4-a716-446655440001\",
      \"text\": \"手臂出现这种红疹，很痒，持续3天\",
      \"image_base64\": \"$image_base64\"
    }
  }"
```

**带导航分诊:**

```bash
curl -X POST http://localhost:8000/assistant/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "session_id": "550e8400-e29b-41d4-a716-446655440002",
      "text": "头痛厉害，有点发烧",
      "gps_lat": 39.9042,
      "gps_lng": 116.4074
    }
  }'
```

> **注意**：导航能力基于高德地图，主要覆盖中国境内；海外坐标可能返回空的医院推荐结果。公开 compat 响应当前不会额外展开 `navigation` 对象。

#### 4.1.3 响应参数

**兼容响应包装**：顶层包含 `output` 与 `metadata`。

| 顶层字段 | 类型 | 说明 |
|:-----|:------|:-----|
| `output` | object | 主要响应数据 |
| `metadata` | object | 兼容层元数据；当前固定返回 `{"runtime_mode": "v3"}` |

**output 字段说明：**

| 字段 | 类型 | 说明 |
|:-----|:------|:-----|
| `status` | string | 处理状态：`final` / `need_more_info` / `error` |
| `session_id` | string | 会话 ID |
| `trace_id` | string | 请求追踪 ID |
| `response` | string | 自然语言响应 |
| `safety` | object | 输出安全结果，包含 `risk_level` 与 `matched_rules` |
| `runtime_events` | object[] | 运行时事件列表 |
| `provenance` | object | 结果来源与能力版本信息 |
| `trace` | object | 执行路径、request_id 等追踪信息 |
| `triage_level` | string | 分诊等级（可选） |
| `recommended_departments` | string[] | 推荐科室列表（可选） |
| `possible_causes` | string[] | 可能原因（含限定词，可选） |
| `red_flags` | string[] | 警示信号（可选） |
| `disclaimer` | string | 免责声明（可选） |
| `error_message` | string | 错误信息（仅 `status=error` 时出现） |

#### 4.1.4 响应示例

**成功响应 (ROUTINE):**

```json
{
  "output": {
    "status": "final",
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "trace_id": "trace-routine-1",
    "response": "根据您描述的手臂红疹症状，建议预约皮肤科门诊进一步评估。",
    "safety": {
      "risk_level": "low",
      "matched_rules": []
    },
    "runtime_events": [
      {
        "event_type": "runtime_finished",
        "request_id": "req-routine-1",
        "session_id": "550e8400-e29b-41d4-a716-446655440000",
        "data": {
          "path": "v3_task_coordinator",
          "success": true
        }
      }
    ],
    "provenance": {
      "source": "v3_medical_pipeline",
      "capability_version": "v3"
    },
    "trace": {
      "request_id": "req-routine-1",
      "path": "v3_task_coordinator"
    },
    "triage_level": "ROUTINE",
    "recommended_departments": ["皮肤科"],
    "possible_causes": [
      "过敏相关皮疹（疑似）",
      "接触性皮炎（疑似）"
    ],
    "red_flags": [
      "如果出现呼吸困难/脸唇肿胀/全身迅速扩散，请立刻急诊"
    ],
    "disclaimer": "本建议仅供参考，不替代专业医疗诊断。"
  },
  "metadata": {
    "runtime_mode": "v3"
  }
}
```

**需要更多信息:**

```json
{
  "output": {
    "status": "need_more_info",
    "session_id": "550e8400-e29b-41d4-a716-446655440002",
    "trace_id": "trace-more-info-1",
    "response": "为了更准确地判断您的状况，需要补充更多信息，请描述疼痛部位、持续时间以及是否伴随发热或呕吐。",
    "safety": {
      "risk_level": "low",
      "matched_rules": []
    },
    "runtime_events": [
      {
        "event_type": "runtime_finished",
        "request_id": "req-more-info-1",
        "session_id": "550e8400-e29b-41d4-a716-446655440002",
        "data": {
          "path": "v3_task_coordinator",
          "success": true
        }
      }
    ],
    "provenance": {
      "source": "v3_medical_pipeline",
      "capability_version": "v3"
    },
    "trace": {
      "request_id": "req-more-info-1",
      "path": "v3_task_coordinator"
    },
    "disclaimer": "本建议仅供参考，不替代专业医疗诊断。"
  },
  "metadata": {
    "runtime_mode": "v3"
  }
}
```

**带定位输入的响应:**

```json
{
  "output": {
    "status": "final",
    "session_id": "550e8400-e29b-41d4-a716-446655440003",
    "trace_id": "trace-location-1",
    "response": "结合您提供的位置与症状，建议尽快前往线下医院评估。",
    "safety": {
      "risk_level": "low",
      "matched_rules": []
    },
    "runtime_events": [
      {
        "event_type": "runtime_finished",
        "request_id": "req-location-1",
        "session_id": "550e8400-e29b-41d4-a716-446655440003",
        "data": {
          "path": "v3_task_coordinator",
          "success": true
        }
      }
    ],
    "provenance": {
      "source": "v3_medical_pipeline",
      "capability_version": "v3"
    },
    "trace": {
      "request_id": "req-location-1",
      "path": "v3_task_coordinator"
    },
    "triage_level": "URGENT",
    "recommended_departments": ["神经内科", "发热门诊"],
    "possible_causes": ["急性感染相关不适（疑似）"],
    "red_flags": ["若出现意识改变或持续高热，请立即急诊。"],
    "disclaimer": "本建议仅供参考，不替代专业医疗诊断。"
  },
  "metadata": {
    "runtime_mode": "v3"
  }
}
```

**错误响应:**

```json
{
  "output": {
    "status": "error",
    "session_id": "550e8400-e29b-41d4-a716-446655440004",
    "trace_id": "trace-error-1",
    "response": "",
    "safety": {
      "risk_level": "low",
      "matched_rules": []
    },
    "runtime_events": [],
    "provenance": {
      "source": "assistant_v2"
    },
    "trace": {
      "request_id": "req-error-1",
      "error_stage": "task_orchestration"
    },
    "error_message": "assistant_v3_task_runtime_failed"
  },
  "metadata": {
    "runtime_mode": "v3"
  }
}
```

---

### 4.2 健康检查

**端点**: `GET /health`

**描述**: 检查服务健康状态。

#### 4.2.1 请求示例

```bash
curl http://localhost:8000/health
```

#### 4.2.2 响应参数

| 字段 | 类型 | 说明 |
|:-----|:------|:-----|
| `status` | string | 整体状态：`healthy` / `degraded` |
| `redis` | string | Redis 状态：`healthy` / `unhealthy` |

#### 4.2.3 响应示例

**健康状态:**

```json
{
  "status": "healthy",
  "redis": "healthy"
}
```

**降级状态:**

```json
{
  "status": "degraded",
  "redis": "unhealthy"
}
```

---

### 4.3 API 信息

**端点**: `GET /`

**描述**: 获取 API 基本信息。

#### 4.3.1 请求示例

```bash
curl http://localhost:8000/
```

#### 4.3.2 响应示例

```json
{
  "name": "TriNav Medical Triage Assistant",
  "version": "1.0.0",
  "endpoints": {
    "invoke": "POST /assistant/invoke",
    "health": "GET /health",
    "docs": "GET /docs"
  },
  "documentation": "https://github.com/your-org/TriNav"
}
```

---

## 5. 数据模型

### 5.1 NavigationResult（导航结果）

```typescript
{
  radius_km: number,        // 搜索半径（公里）
  hospitals: [{
    rank: number,           // 推荐排序（1-3）
    name: string,           // 医院名称
    is_3a: boolean,         // 是否三甲医院
    address: string,        // 地址
    distance_m: number,     // 距离（米）
    location: {
      lat: number,          // 纬度
      lng: number           // 经度
    },
    phone: string,          // 电话
    reason: string          // 推荐理由
  }],
  route_plan?: {
    to_hospital_rank: number,   // 目标医院排序
    mode: string,               // 出行方式：driving/transit/walking
    distance_km: number,        // 距离（公里）
    eta_min: number,            // 预计时间（分钟）
    summary: string             // 路线描述
  }                            // 可能为空（路线获取失败）
}
```

### 5.2 WeatherAlert（天气预警）

```typescript
{
  condition: string,       // 天气状况
  temp_c: number,          // 温度（摄氏度）
  humidity: number,        // 湿度（%）
  wind_speed_kmh: number,  // 风速（km/h）
  tip: string              // 出行建议
}
```

### 5.3 VisualFindings（视觉发现）

```typescript
{
  type: string,            // 类型：rash/wound/unknown
  summary: string,         // 摘要描述
  features: string[],      // 特征列表
  confidence: number       // 置信度（0.0-1.0）
}
```

### 5.4 Evidence（医学证据）

```typescript
[{
  pmid: string,            // PubMed ID
  title: string,           // 标题
  year: string,            // 出版年份
  source: string,          // 期刊来源
  type: string,            // 类型（Guideline/Review 等）
  note?: string            // 相关性说明（可选）
}]
```

---

## 6. 错误码

### 6.1 HTTP 状态码

| 状态码 | 说明 | 示例场景 |
|:------|:-----|:---------|
| 200 | 请求正常处理，或 `/assistant/invoke` 返回结构化业务错误 | 成功响应；公开 compat 路由上的 `output.status=error` |
| 422 | 请求参数校验失败 | 缺少 `input` 包装、字段类型错误 |
| 503 | 运行时结构化失败 | `/assistant/v3/invoke` 主执行路径与 fallback 均失败 |
| 500 | 未捕获的服务器异常 | 中间件、部署或未包装异常 |

> **说明**：`POST /assistant/invoke` 是公开 compat 路由。即使 runtime 返回结构化失败，它通常仍返回 HTTP 200，并通过 `output.status=error` 与 `output.error_message` 让客户端判定业务失败。

### 6.2 业务错误码

| 错误信息 | 原因 | 解决方案 |
|:---------|:-----|:---------|
| `输入验证失败: session_id 格式无效，应为UUID` | session_id 格式错误 | 使用有效 UUID |
| `输入验证失败: 文本长度超过限制...` | 文本过长 | 控制在 2000 字符内 |
| `输入验证失败: 图片格式无效，应为base64编码` | 图片编码非法 | 使用 base64 编码图片 |
| `输入验证失败: 图片大小超过限制...` | 图片过大 | 图片大小不超过 5MB |
| `输入验证失败: 纬度无效...` / `经度无效...` | GPS 坐标超出范围 | 检查纬度 -90~90，经度 -180~180 |
| `系统暂时繁忙，请稍后重试` | 服务内部错误 | 稍后重试 |

### 6.3 错误响应格式

```json
{
  "output": {
    "status": "error",
    "error_message": "错误描述"
  },
  "metadata": {
    "runtime_mode": "v3"
  }
}
```

---

## 7. 速率限制

### 7.1 服务端限制

> **注意**: 当前版本 (v1.0.0) **未实现服务端速率限制**。
> 建议客户端自行控制请求频率，避免对服务造成压力。

### 7.2 建议的客户端限制

| 资源 | 建议限制 | 说明 |
|:-----|:---------|:-----|
| 请求总数 | 60 请求/分钟 | 基于 LLM API 响应时间 (~1秒/请求) |
| 单用户请求 | 10 请求/分钟 | 避免单个用户占用过多资源 |

### 7.3 后续版本计划

以下功能计划在 v1.1 实现：

- ✅ 服务端速率限制（基于 IP 和 API Key）
- ✅ `X-RateLimit-*` 响应头
- ✅ `429 Too Many Requests` 状态码
- ✅ `retry_after` 字段

---

## 8. 示例代码

### 8.1 Python 客户端

```python
import requests
import uuid
from typing import Optional, Dict, List


class TriNavClient:
    """TriNav API 客户端"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.endpoint = f"{base_url}/assistant/invoke"

    def health_check(self) -> bool:
        """检查服务健康状态"""
        try:
            response = requests.get(f"{self.base_url}/health")
            data = response.json()
            return data.get("status") == "healthy"
        except:
            return False

    def triage(
        self,
        text: str,
        session_id: Optional[str] = None,
        image_path: Optional[str] = None,
        gps_lat: Optional[float] = None,
        gps_lng: Optional[float] = None
    ) -> Dict:
        """
        发起分诊请求

        Args:
            text: 症状描述（必需）
            session_id: 会话ID（默认生成新UUID）
            image_path: 图片路径（可选）
            gps_lat: 纬度（可选）
            gps_lng: 经度（可选）

        Returns:
            分诊结果字典
        """
        import base64

        if session_id is None:
            session_id = str(uuid.uuid4())

        payload = {
            "session_id": session_id,
            "text": text
        }

        # 添加可选参数
        if image_path:
            with open(image_path, "rb") as f:
                payload["image_base64"] = base64.b64encode(f.read()).decode()

        if gps_lat is not None:
            payload["gps_lat"] = gps_lat

        if gps_lng is not None:
            payload["gps_lng"] = gps_lng

        response = requests.post(
            self.endpoint,
            json={"input": payload},
            timeout=30
        )
        response.raise_for_status()
        data = response.json()
        return data.get("output", data)


# 使用示例
if __name__ == "__main__":
    client = TriNavClient()

    # 检查服务状态
    if not client.health_check():
        print("服务不可用")
        exit(1)

    # 纯文本分诊
    result = client.triage(text="手臂红疹，有点痒")
    print(f"分诊等级: {result['triage_level']}")
    print(f"推荐科室: {result['recommended_departments']}")

    # 带定位输入的分诊
    result = client.triage(
        text="头痛发烧",
        gps_lat=39.9042,
        gps_lng=116.4074
    )

    print(f"自然语言答复: {result['response']}")
    print(f"执行路径: {result['trace']['path']}")
```

### 8.2 JavaScript 客户端

```javascript
class TriNavClient {
  constructor(baseUrl = 'http://localhost:8000') {
    this.baseUrl = baseUrl;
    this.endpoint = `${baseUrl}/assistant/invoke`;
  }

  async healthCheck() {
    try {
      const response = await fetch(`${this.baseUrl}/health`);
      const data = await response.json();
      return data.status === 'healthy';
    } catch (error) {
      return false;
    }
  }

  async triage({
    text,
    sessionId = crypto.randomUUID(),
    imageBase64 = null,
    gpsLat = null,
    gpsLng = null
  }) {
    const payload = {
      session_id: sessionId,
      text: text
    };

    if (imageBase64) {
      payload.image_base64 = imageBase64;
    }

    if (gpsLat !== null) {
      payload.gps_lat = gpsLat;
    }

    if (gpsLng !== null) {
      payload.gps_lng = gpsLng;
    }

    const response = await fetch(this.endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ input: payload })
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const data = await response.json();
    return data.output ?? data;
  }
}

// 使用示例
(async () => {
  const client = new TriNavClient();

  // 健康检查
  const isHealthy = await client.healthCheck();
  if (!isHealthy) {
    console.error('服务不可用');
    return;
  }

  // 纯文本分诊
  const result = await client.triage({
    text: '手臂红疹，有点痒'
  });

  console.log('分诊等级:', result.triage_level);
  console.log('推荐科室:', result.recommended_departments);

  // 带定位输入的分诊
  const navResult = await client.triage({
    text: '头痛发烧',
    gpsLat: 39.9042,
    gpsLng: 116.4074
  });

  console.log('自然语言答复:', navResult.response);
  console.log('执行路径:', navResult.trace.path);
})();
```

### 8.3 cURL 示例

```bash
#!/bin/bash

# 基础URL
BASE_URL="http://localhost:8000"

# 健康检查
echo "=== 健康检查 ==="
curl -s $BASE_URL/health | jq

# 纯文本分诊
echo -e "\n=== 纯文本分诊 ==="
curl -s -X POST $BASE_URL/assistant/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "session_id": "'$(uuidgen)'"',
      "text": "手臂红疹，有点痒，持续2天"
    }
  }' | jq

# 带导航分诊
echo -e "\n=== 带导航分诊 ==="
curl -s -X POST $BASE_URL/assistant/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "session_id": "'$(uuidgen)'"',
      "text": "头痛发烧",
      "gps_lat": 39.9042,
      "gps_lng": 116.4074
    }
  }' | jq

# 带图片分诊
echo -e "\n=== 带图片分诊 ==="
IMAGE_BASE64=$(base64 -i rash_photo.jpg)
curl -s -X POST $BASE_URL/assistant/invoke \
  -H "Content-Type: application/json" \
  -d "{
    \"input\": {
      \"session_id\": \"$(uuidgen)\",
      \"text\": \"手臂这种皮疹，很痒\",
      \"image_base64\": \"$IMAGE_BASE64\"
    }
  }" | jq
```

---

## 附录

### A. 状态码速查表

| HTTP 状态 | `status` 字段 | 说明 |
|:----------|:-------------|:-----|
| 200 | `final` | 分诊完成 |
| 200 | `need_more_info` | 需要更多信息 |
| 200 | `error` | 公开 `/assistant/invoke` 的结构化业务失败 |
| 422 | - | 请求参数校验失败 |
| 503 | `error` | `/assistant/v3/invoke` 等显式 runtime 路由失败 |
| 500 | - | 未捕获的服务器内部错误 |

### B. triage_level 枚举值

```typescript
type TriageLevel =
  | "EMERGENCY"  // 急诊 - 立即就医
  | "URGENT"     // 紧急 - 尽快就医
  | "ROUTINE"    // 常规 - 预约门诊
  | "SELF_CARE"; // 自我护理 - 居家观察
```

### C. triage_source 枚举值

```typescript
type TriageSource =
  | "rule_engine"  // 规则引擎判断（红旗规则）
  | "llm"          // LLM判断
  | "merged";      // 合并判断
```

### D. 支持的图片格式

| 格式 | MIME 类型 | 最大大小 |
|:-----|:----------|:---------|
| JPEG | image/jpeg | 5MB |
| PNG | image/png | 5MB |

### E. GPS 坐标格式

```typescript
{
  gps_lat: number,  // 纬度: -90 ~ 90
  gps_lng: number   // 经度: -180 ~ 180
}
```

### F. 性能指标参考

| 分诊等级 | 目标响应时间 (p95) |
|:---------|:------------------|
| EMERGENCY | ≤5 秒 |
| URGENT | ≤10 秒 |
| ROUTINE | ≤15 秒 |
| SELF_CARE | ≤15 秒 |

---

**文档版本**: 1.0.0
**最后更新**: 2026-01-12
**维护者**: TriNav 开发团队

---

## 📄 免责声明

**TriNav 是一个辅助工具，不替代专业医疗建议。紧急情况请立即呼叫急救（120）或前往急诊。**
