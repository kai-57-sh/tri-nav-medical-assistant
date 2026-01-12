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

TriNav API 提供医疗分诊和医院导航服务的 RESTful 接口。基于 LangServe 构建，支持文本描述、图片上传和 GPS 定位等多种输入方式。

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

```http
Content-Type: application/json
X-Request-ID: uuid
X-Response-Time: ms
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

---

## 4. API 端点

### 4.1 分诊评估

**端点**: `POST /assistant/invoke`

**描述**: 执行医疗分诊评估，返回分诊等级、推荐科室、医院导航等信息。

#### 4.1.1 请求参数

| 字段 | 类型 | 必需 | 说明 | 约束 |
|:-----|:------|:-----|:-----|:-----|
| `session_id` | string | ✅ | 会话唯一标识 | UUID 格式 |
| `text` | string | ✅ | 症状描述 | 1-2000 字符 |
| `image_base64` | string | ❌ | 图片数据（Base64） | 最大 5MB |
| `gps_lat` | number | ❌ | 纬度 | -90 到 90 |
| `gps_lng` | number | ❌ | 经度 | -180 到 180 |

#### 4.1.2 请求示例

**纯文本分诊:**

```bash
curl -X POST http://localhost:8000/assistant/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "text": "手臂出现红疹，有点痒，持续2天"
  }'
```

**带图片分诊:**

```bash
# 先将图片转换为 base64
image_base64=$(base64 -i rash_photo.jpg)

curl -X POST http://localhost:8000/assistant/invoke \
  -H "Content-Type: application/json" \
  -d "{
    \"session_id\": \"550e8400-e29b-41d4-a716-446655440001\",
    \"text\": \"手臂出现这种红疹，很痒，持续3天\",
    \"image_base64\": \"$image_base64\"
  }"
```

**带导航分诊:**

```bash
curl -X POST http://localhost:8000/assistant/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "550e8400-e29b-41d4-a716-446655440002",
    "text": "头痛厉害，有点发烧",
    "gps_lat": 39.9042,
    "gps_lng": 116.4074
  }'
```

#### 4.1.3 响应参数

| 字段 | 类型 | 说明 |
|:-----|:------|:-----|
| `status` | string | 处理状态：`final` / `need_more_info` / `error` |
| `session_id` | string | 会话 ID |
| `triage_level` | string | 分诊等级 |
| `triage_reason` | string | 分诊原因说明 |
| `triage_source` | string | 来源：`rule_engine` / `llm` / `merged` |
| `recommended_departments` | string[] | 推荐科室列表 |
| `possible_causes` | string[] | 可能原因（含限定词） |
| `self_care_tips` | string[] | 自我护理建议 |
| `red_flags` | string[] | 警示信号 |
| `clarify_questions` | string[] | 澄清问题（需更多信息时） |
| `navigation` | object | 导航信息（提供 GPS 时） |
| `evidence` | object[] | 医学证据（NCBI 检索结果） |
| `weather_alert` | object | 天气预警（提供 GPS 时） |
| `visual_findings` | object | 视觉发现（提供图片时） |
| `response` | string | 自然语言响应 |
| `disclaimer` | string | 免责声明 |
| `turn_count` | integer | 对话轮次 |
| `error_message` | string | 错误信息（仅错误时） |

#### 4.1.4 响应示例

**成功响应 (ROUTINE):**

```json
{
  "status": "final",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "triage_level": "ROUTINE",
  "triage_reason": "症状轻微，无紧急征象",
  "triage_source": "llm",
  "recommended_departments": ["皮肤科"],
  "possible_causes": [
    "过敏相关皮疹（疑似）",
    "接触性皮炎（疑似）"
  ],
  "self_care_tips": [
    "避免抓挠患处",
    "保持患处清洁干燥",
    "记录皮疹变化"
  ],
  "red_flags": [
    "如果出现呼吸困难/脸唇肿胀/全身迅速扩散，请立刻急诊"
  ],
  "clarify_questions": [],
  "response": "根据您描述的手臂红疹症状，建议您前往皮肤科就诊。症状轻微，可以预约常规门诊...",
  "disclaimer": "本建议仅供参考，不替代专业医疗诊断。如有紧急情况，请立即前往急诊或呼叫急救。",
  "turn_count": 1
}
```

**急诊响应 (EMERGENCY):**

```json
{
  "status": "final",
  "session_id": "550e8400-e29b-41d4-a716-446655440001",
  "triage_level": "EMERGENCY",
  "triage_reason": "胸闷伴呼吸困难，触发红旗规则 RF_CHEST_TIGHTNESS_PLUS_DIFFICULTY",
  "triage_source": "rule_engine",
  "recommended_departments": ["急诊"],
  "possible_causes": [],
  "self_care_tips": [],
  "red_flags": [
    "胸闷伴呼吸困难，建议立即急诊/呼叫急救"
  ],
  "response": "检测到您的症状存在紧急情况。请立即前往急诊或呼叫急救车（120）。",
  "disclaimer": "本建议仅供参考，不替代专业医疗诊断。如有紧急情况，请立即前往急诊或呼叫急救。"
}
```

**需要更多信息:**

```json
{
  "status": "need_more_info",
  "session_id": "550e8400-e29b-41d4-a716-446655440002",
  "clarify_questions": [
    "疼痛的具体部位在哪里？（如上腹部、下腹部、左/右侧）",
    "疼痛持续多长时间了？",
    "是否伴有其他症状？（如发热、呕吐、腹泻、便血）"
  ],
  "response": "为了更准确地判断您的状况，需要了解一些额外信息。请回答以下问题...",
  "turn_count": 1
}
```

**带导航的响应:**

```json
{
  "status": "final",
  "session_id": "550e8400-e29b-41d4-a716-446655440003",
  "triage_level": "URGENT",
  "triage_reason": "头痛发热，建议尽快就医",
  "triage_source": "llm",
  "recommended_departments": ["神经内科", "发热门诊"],
  "navigation": {
    "radius_km": 10,
    "hospitals": [
      {
        "rank": 1,
        "name": "北京协和医院",
        "is_3a": true,
        "address": "北京市东城区帅府园1号",
        "distance_m": 1200,
        "location": {"lat": 39.914, "lng": 116.417},
        "phone": "010-69156699",
        "reason": "三甲综合医院，距离较近，急诊/门诊齐全"
      },
      {
        "rank": 2,
        "name": "中日友好医院",
        "is_3a": true,
        "address": "北京市朝阳区樱花园东街",
        "distance_m": 3500,
        "location": {"lat": 39.979, "lng": 116.447},
        "phone": "010-84205566",
        "reason": "三甲综合医院，口碑较好"
      },
      {
        "rank": 3,
        "name": "朝阳医院",
        "is_3a": false,
        "address": "北京市朝阳区工人体育场南路",
        "distance_m": 900,
        "location": {"lat": 39.921, "lng": 116.457},
        "phone": "010-85231000",
        "reason": "距离更近，可作为备选"
      }
    ],
    "route_plan": {
      "to_hospital_rank": 1,
      "mode": "driving",
      "distance_km": 1.2,
      "eta_min": 15,
      "summary": "大约15分钟车程，约1.2公里"
    }
  },
  "weather_alert": {
    "condition": "小雨",
    "temp_c": 8,
    "humidity": 75,
    "wind_speed_kmh": 15,
    "tip": "下雨路滑，出行请注意安全，建议携带雨具"
  }
}
```

**错误响应:**

```json
{
  "status": "error",
  "error_message": "session_id is required"
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
  route_plan: {
    to_hospital_rank: number,   // 目标医院排序
    mode: string,               // 出行方式：driving/transit/walking
    distance_km: number,        // 距离（公里）
    eta_min: number,            // 预计时间（分钟）
    summary: string             // 路线描述
  }
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
  abstract: string,        // 摘要
  relevance: number        // 相关性得分
}]
```

---

## 6. 错误码

### 6.1 HTTP 状态码

| 状态码 | 说明 | 示例场景 |
|:------|:-----|:---------|
| 200 | 成功 | 请求正常处理 |
| 400 | 请求参数错误 | 缺少必需参数、参数格式错误 |
| 500 | 服务器错误 | 内部处理异常 |

### 6.2 业务错误码

| 错误信息 | 原因 | 解决方案 |
|:---------|:-----|:---------|
| `session_id is required` | 缺少 session_id | 提供有效的 UUID 格式 session_id |
| `text is required` | 缺少症状描述 | 提供文本描述 |
| `Invalid GPS coordinates` | GPS 坐标无效 | 检查纬度范围 -90~90，经度范围 -180~180 |
| `Image size exceeds limit` | 图片过大 | 图片大小不超过 5MB |
| `系统暂时繁忙，请稍后重试` | 服务内部错误 | 稍后重试 |

### 6.3 错误响应格式

```json
{
  "status": "error",
  "error_message": "错误描述"
}
```

---

## 7. 速率限制

### 7.1 当前限制

| 资源 | 限制 | 时间窗口 |
|:-----|:-----|:---------|
| 请求总数 | 100 请求/分钟 | 滑动窗口 |
| 单IP请求 | 60 请求/分钟 | 滑动窗口 |

### 7.2 响应头

```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1641234567
```

### 7.3 超限响应

**状态码**: 429 Too Many Requests

```json
{
  "error": "Rate limit exceeded",
  "message": "每分钟最多100次请求",
  "retry_after": 30
}
```

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
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        return response.json()


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

    # 带导航分诊
    result = client.triage(
        text="头痛发烧",
        gps_lat=39.9042,
        gps_lng=116.4074
    )

    if result.get("navigation"):
        print("推荐医院:")
        for hospital in result['navigation']['hospitals']:
            print(f"  {hospital['rank']}. {hospital['name']}")
            print(f"     {hospital['address']}")
            print(f"     距离: {hospital['distance_m']}米")
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
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return await response.json();
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

  // 带导航分诊
  const navResult = await client.triage({
    text: '头痛发烧',
    gpsLat: 39.9042,
    gpsLng: 116.4074
  });

  if (navResult.navigation) {
    console.log('推荐医院:');
    navResult.navigation.hospitals.forEach(hospital => {
      console.log(`  ${hospital.rank}. ${hospital.name}`);
      console.log(`     ${hospital.address}`);
      console.log(`     距离: ${hospital.distance_m}米`);
    });
  }
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
    "session_id": "'$(uuidgen)'"',
    "text": "手臂红疹，有点痒，持续2天"
  }' | jq

# 带导航分诊
echo -e "\n=== 带导航分诊 ==="
curl -s -X POST $BASE_URL/assistant/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "'$(uuidgen)'"',
    "text": "头痛发烧",
    "gps_lat": 39.9042,
    "gps_lng": 116.4074
  }' | jq

# 带图片分诊
echo -e "\n=== 带图片分诊 ==="
IMAGE_BASE64=$(base64 -i rash_photo.jpg)
curl -s -X POST $BASE_URL/assistant/invoke \
  -H "Content-Type: application/json" \
  -d "{
    \"session_id\": \"$(uuidgen)\",
    \"text\": \"手臂这种皮疹，很痒\",
    \"image_base64\": \"$IMAGE_BASE64\"
  }" | jq
```

---

## 附录

### A. 状态码速查表

| HTTP 状态 | `status` 字段 | 说明 |
|:----------|:-------------|:-----|
| 200 | `final` | 分诊完成 |
| 200 | `need_more_info` | 需要更多信息 |
| 200 | `error` | 处理失败 |
| 400 | - | 请求参数错误 |
| 500 | - | 服务器内部错误 |

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
**最后更新**: 2026-01-11
**维护者**: TriNav 开发团队

---

## 📄 免责声明

**TriNav 是一个辅助工具，不替代专业医疗建议。紧急情况请立即呼叫急救（120）或前往急诊。**
