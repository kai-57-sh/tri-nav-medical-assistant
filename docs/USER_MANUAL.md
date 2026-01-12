# TriNav 用户使用手册

> 医疗分诊与医院导航助手 - 完整用户指南

**版本**: 1.1.0
**更新日期**: 2026-01-12
**项目状态**: ✅ 生产就绪

---

## 📋 目录

1. [系统概述](#1-系统概述)
2. [快速开始](#2-快速开始)
3. [安装与配置](#3-安装与配置)
4. [API 接口说明](#4-api-接口说明)
5. [使用场景与示例](#5-使用场景与示例)
6. [工作流程详解](#6-工作流程详解)
7. [数据模型](#7-数据模型)
8. [安全与合规](#8-安全与合规)
9. [故障排除](#9-故障排除)
10. [开发指南](#10-开发指南)
11. [部署指南](#11-部署指南)
12. [性能优化](#12-性能优化)
13. [监控与运维](#13-监控与运维)
14. [附录](#14-附录)

---

## 1. 系统概述

### 1.1 什么是 TriNav？

**TriNav** (Triage + Navigation) 是一个基于 LangChain 和 LangGraph 的智能医疗分诊与医院导航助手系统。它通过 **18 节点的 LangGraph 工作流** 实现：

```
┌─────────────────────────────────────────────────────────────────────┐
│                         TriNav 核心功能                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  🏥 症状分析      → 提取结构化临床信息（部位、症状、持续时间）       │
│  🚨 智能分诊      → 判断就诊 urgency（急诊/紧急/常规/自我护理）      │
│  🗺️ 医院导航      → 推荐附近医院并提供详细路线规划                   │
│  📚 证据检索      → 从 NCBI/PubMed 获取医学文献证据                 │
│  🖼️ 图像识别      → 分析皮疹、伤口等视觉症状（Qwen VL）             │
│  💬 多轮对话      → 支持最多 2 轮澄清对话获取更多信息                 │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 技术架构

```
┌───────────────────────────────────────────────────────────────────────┐
│                         TriNav 系统架构                               │
├───────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────┐     ┌──────────────────────────────────────┐   │
│  │   输入层        │     │         LangGraph 18节点工作流        │   │
│  ├─────────────────┤     │                                      │   │
│  │ • 文本描述      │ ──→ │  输入验证 → 会话加载 → 图像处理       │   │
│  │ • 图片上传      │     │  → 临床提取 → 红旗检测 → 分诊分类     │   │
│  │ • GPS 定位      │     │  → 证据检索 → 导航推荐 → 推理验证     │   │
│  └─────────────────┘     │  → 响应生成                           │   │
│                          └──────────────────────────────────────┘   │
│                                        │                             │
│  ┌─────────────────────────────────────┼─────────────────────────┐ │
│  │         服务层                       │                         │ │
│  ├─────────────────────────────────────┼─────────────────────────┤ │
│  │ • LLM 服务    │ ←→ Qwen API          │                         │ │
│  │ • Redis 服务  │ ←→ 会话存储          │                         │ │
│  │ • 高德地图    │ ←→ 医院导航          │                         │ │
│  │ • NCBI 服务   │ ←→ 文献检索          │                         │ │
│  │ • 天气服务    │ ←→ Open-Meteo        │                         │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │   输出层                                                         │ │
│  ├─────────────────────────────────────────────────────────────────┤ │
│  │ • 分诊等级 (EMERGENCY/URGENT/ROUTINE/SELF_CARE)                 │ │
│  │ • 推荐科室 (皮肤科、急诊、发热门诊等)                            │ │
│  │ • 医院列表 (3 家医院，优先三甲)                                  │ │
│  │ • 导航路线 (距离、预计时间、天气提醒)                            │ │
│  │ • 医学证据 (PubMed 文献引用)                                    │ │
│  │ • 自我护理建议                                                  │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                                                                         │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.3 分诊等级说明

| 等级 | 图标 | 含义 | 建议行动 | 典型场景 | 响应时间 |
|:----:|:----:|------|----------|----------|----------|
| **EMERGENCY** | 🚨 | 急诊 | 立即前往急诊或呼叫 120 | 胸痛、呼吸困难、严重出血 | ≤5 秒 |
| **URGENT** | ⚠️ | 紧急 | 尽快就医（24 小时内） | 高热、剧烈腹痛 | ≤10 秒 |
| **ROUTINE** | 🏥 | 常规 | 预约门诊 | 皮疹、轻微咳嗽 | ≤15 秒 |
| **SELF_CARE** | 🏠 | 自我护理 | 家庭护理 + 观察 | 轻微擦伤、普通感冒 | ≤15 秒 |

### 1.4 项目状态

```
✅ 生产就绪

已完成：
  ✓ 7 个 Pydantic 数据模型
  ✓ 5 个服务层模块（Redis、LLM、高德、NCBI、天气）
  ✓ 18 个 LangGraph 工作流节点
  ✓ 15 条版本化红旗规则
  ✓ 测试套件（单元测试 + 集成测试）
  ✓ LangServe API 服务器
  ✓ 安全验证机制
  ✓ 优雅降级处理
  ✓ 可观测性和监控
```

---

## 2. 快速开始

### 2.1 最小化运行示例（5 分钟）

```bash
# 1. 克隆项目
cd /AII-wuqi/AII_home/fq_775/TriNav

# 2. 创建虚拟环境
python3.11 -m venv .venv
source .venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 4. 配置环境变量（最小配置）
cat > .env << EOF
QWEN_API_KEY=sk-xxxxx  # 替换为你的 API Key
REDIS_URL=redis://localhost:6379
AMAP_API_KEY=your_amap_key_here  # 可选，导航功能需要
TRINAV_LOG_FILE=logs/trinav.log  # 可选，日志文件路径
EOF

# 5. 启动 Redis
docker run -d -p 6379:6379 redis:7-alpine

# 6. 启动服务
python -m src.server

# 服务将在 http://localhost:8000 启动
```

### 2.2 第一个 API 调用

```bash
curl -X POST http://localhost:8000/assistant/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "text": "手臂出现红疹，有点痒，持续2天"
  }'
```

**预期响应：**

```json
{
  "status": "final",
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
  "response": "根据您描述的手臂红疹症状...",
  "disclaimer": "本建议仅供参考，不替代专业医疗诊断"
}
```

### 2.3 验证安装

```bash
# 健康检查
curl http://localhost:8000/health

# 查看服务信息
curl http://localhost:8000/

# 访问 API 文档
# 浏览器打开: http://localhost:8000/docs
```

---

## 3. 安装与配置

### 3.1 系统要求

| 组件 | 最低要求 | 推荐配置 | 说明 |
|:-----|:---------|:---------|------|
| **Python** | 3.11+ | 3.11+ | LangChain 需要 3.9+ |
| **Redis** | 5.0+ | 7.0+ | 会话存储 |
| **内存** | 2GB | 4GB+ | 取决于并发量 |
| **CPU** | 2 核 | 4 核+ | 多节点并发处理 |
| **磁盘** | 1GB | 5GB+ | 日志和缓存 |

### 3.2 环境变量配置

创建 `.env` 文件：

```bash
# ============================================================================
# TriNav 环境配置文件
# ============================================================================

# ---------------------------------------------------------------------------
# 必需配置
# ---------------------------------------------------------------------------
# Qwen API Key（阿里云通义千问）
# 获取地址: https://bailian.console.aliyun.com/
QWEN_API_KEY=sk-xxxxx
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# ---------------------------------------------------------------------------
# 可选配置
# ---------------------------------------------------------------------------

# Redis 配置
REDIS_URL=redis://localhost:6379
REDIS_SESSION_TTL=3600           # 会话过期时间（秒），默认 60 分钟
REDIS_MAX_CONNECTIONS=20          # 连接池大小

# 高德地图 API Key（导航功能必需）
# 获取地址: https://lbs.amap.com/
AMAP_API_KEY=your_amap_api_key_here
AMAP_SEARCH_RADIUS=10000          # 搜索半径（米），默认 10 公里

# NCBI/PubMed（无需 API Key）
NCBI_BASE_URL=https://eutils.ncbi.nlm.nih.gov/entrez/eutils
NCBI_API_DELAY=0.5                # API 请求间隔（秒）

# 天气服务
WEATHER_API_URL=https://api.open-meteo.com/v1/forecast

# ---------------------------------------------------------------------------
# 观察性配置（可选）
# ---------------------------------------------------------------------------

# LangSmith 追踪
LANGCHAIN_TRACING_V2=false
LANGCHAIN_API_KEY=your_langsmith_key_here
LANGCHAIN_PROJECT=trinav-dev

# OpenTelemetry 追踪
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317

# ---------------------------------------------------------------------------
# 服务器配置
# ---------------------------------------------------------------------------
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
SERVER_DEBUG=false                # 开发模式热重载
LOG_LEVEL=INFO                    # DEBUG, INFO, WARNING, ERROR
TRINAV_LOG_FILE=logs/trinav.log   # 可选，日志文件路径
```

### 3.3 API Key 获取指南

#### Qwen API Key（必需）

1. 访问 [阿里云百炼平台](https://bailian.console.aliyun.com/)
2. 开通「通义千问」服务
3. 在「API-KEY 管理」中创建新的 API Key
4. 复制 Key 到 `.env` 文件的 `QWEN_API_KEY`

#### 高德地图 API Key（可选，导航功能需要）

1. 访问 [高德开放平台](https://lbs.amap.com/)
2. 注册/登录账号
3. 进入「控制台」→「应用管理」→「创建应用」
4. 添加 Key，选择「Web服务」类型
5. 复制 Key 到 `.env` 文件的 `AMAP_API_KEY`

### 3.4 Docker 环境安装

**使用 Docker Compose（示例，需自行保存为 docker-compose.yml）：**

> 说明：仓库不内置 docker-compose.yml，可按需参考下方示例创建。

```yaml
# docker-compose.yml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    container_name: trinav-redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes
    restart: unless-stopped

volumes:
  redis_data:
```

```bash
# 启动 Redis
redis-server
# or: docker run --name trinav-redis -p 6379:6379 redis:7-alpine

# 验证运行
docker ps | grep redis
redis-cli ping  # 应返回 PONG
```

### 3.5 生产环境部署

详见 [11. 部署指南](#11-部署指南)

---

## 4. API 接口说明

### 4.1 核心接口：分诊评估

**端点：** `POST /assistant/invoke`

**请求头：**
```http
Content-Type: application/json
```

**请求参数：**

| 字段 | 类型 | 必需 | 说明 | 约束 |
|:-----|:------|:-----|:------|------|
| `session_id` | string | ✅ | 会话唯一标识 | UUID 格式 |
| `text` | string | ✅ | 症状描述 | 1-2000 字符 |
| `image_base64` | string | ❌ | 图片数据 | Base64 编码，最大 5MB |
| `gps_lat` | float | ❌ | 纬度 | -90 到 90 |
| `gps_lng` | float | ❌ | 经度 | -180 到 180 |

**响应字段：**

| 字段 | 类型 | 说明 |
|:-----|:------|:------|
| `status` | string | `final`（完成）, `need_more_info`（需澄清）, `error`（错误） |
| `triage_level` | string | `EMERGENCY`, `URGENT`, `ROUTINE`, `SELF_CARE` |
| `triage_reason` | string | 分诊原因说明 |
| `triage_source` | string | `rule_engine`（规则）, `llm`（模型）, `merged`（合并） |
| `recommended_departments` | string[] | 推荐科室列表 |
| `possible_causes` | string[] | 可能原因（含"疑似"/"可能"限定词） |
| `self_care_tips` | string[] | 自我护理建议 |
| `red_flags` | string[] | 警示信号 |
| `clarify_questions` | string[] | 澄清问题（需更多信息时） |
| `navigation` | object | 导航信息（提供 GPS 时） |
| `evidence` | object[] | NCBI 医学证据 |
| `weather_alert` | object | 天气预警 |
| `disclaimer` | string | 免责声明 |
| `error_message` | string | 错误信息（仅错误时） |

### 4.2 健康检查接口

**端点：** `GET /health`

**响应：**
```json
{
  "status": "healthy",
  "redis": "healthy"
}
```

### 4.3 交互式 API 文档

启动服务后访问：
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### 4.4 错误码参考

| HTTP 状态码 | 错误类型 | 说明 | 处理建议 |
|:-----------|:---------|:-----|:---------|
| 200 | 成功 | 请求正常处理 | - |
| 400 | 参数错误 | 请求参数不合法 | 检查请求格式 |
| 500 | 服务器错误 | 内部处理错误 | 稍后重试 |

---

## 5. 使用场景与示例

### 5.1 场景一：纯文本分诊 (US1)

**用户场景：** 用户描述症状，获取分诊建议

```bash
curl -X POST http://localhost:8000/assistant/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "text": "胸口有点闷，持续半天了，伴有轻微呼吸困难"
  }'
```

**响应示例：**
```json
{
  "status": "final",
  "triage_level": "EMERGENCY",
  "triage_reason": "胸闷伴呼吸困难，触发红旗规则 RF_CHEST_TIGHTNESS_PLUS_DIFFICULTY",
  "triage_source": "rule_engine",
  "recommended_departments": ["急诊"],
  "possible_causes": [],
  "self_care_tips": [],
  "red_flags": [
    "胸闷伴呼吸困难，建议立即急诊/呼叫急救"
  ],
  "response": "检测到您的症状存在紧急情况。请立即前往急诊或呼叫急救车。"
}
```

### 5.2 场景二：带图片的分诊 (US2)

**用户场景：** 用户上传皮疹图片，结合文字描述

```python
import base64
import requests

# 读取图片并编码为 base64
with open("rash_photo.jpg", "rb") as f:
    image_base64 = base64.b64encode(f.read()).decode()

response = requests.post(
    "http://localhost:8000/assistant/invoke",
    json={
        "session_id": "550e8400-e29b-41d4-a716-446655440001",
        "text": "手臂出现这种红疹，很痒，持续3天了",
        "image_base64": image_base64
    }
)
result = response.json()
print(f"分诊等级: {result['triage_level']}")
print(f"推荐科室: {result['recommended_departments']}")
print(f"视觉发现: {result.get('visual_findings', 'N/A')}")
```

**响应示例：**
```json
{
  "status": "final",
  "triage_level": "ROUTINE",
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
  "visual_findings": {
    "type": "rash",
    "summary": "手臂红斑伴丘疹",
    "features": ["红斑", "丘疹", "局部肿胀"],
    "confidence": 0.85
  }
}
```

### 5.3 场景三：带导航的分诊 (US3)

**用户场景：** 提供位置信息，获取医院推荐和导航

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

**响应示例：**
```json
{
  "status": "final",
  "triage_level": "URGENT",
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
        "distance_m": 3500,
        "reason": "三甲综合医院，口碑较好"
      },
      {
        "rank": 3,
        "name": "朝阳医院",
        "is_3a": false,
        "distance_m": 900,
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
    "tip": "下雨路滑，出行请注意安全，建议携带雨具"
  }
}
```

### 5.4 场景四：多轮澄清对话 (US4)

**用户场景：** 系统需要更多信息才能做出判断

**第一次请求：**
```bash
curl -X POST http://localhost:8000/assistant/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "550e8400-e29b-41d4-a716-446655440003",
    "text": "肚子不舒服"
  }'
```

**响应：**
```json
{
  "status": "need_more_info",
  "clarify_questions": [
    "疼痛的具体部位在哪里？（如上腹部、下腹部、左/右侧）",
    "疼痛持续多长时间了？",
    "是否伴有其他症状？（如发热、呕吐、腹泻、便血）"
  ],
  "response": "为了更准确地判断您的状况，需要了解一些额外信息。请回答以下问题...",
  "turn_count": 1
}
```

**第二次请求（澄清后）：**
```bash
curl -X POST http://localhost:8000/assistant/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "550e8400-e29b-41d4-a716-446655440003",
    "text": "右下腹痛，持续4小时，伴有轻微恶心，没有发烧"
  }'
```

**响应：**
```json
{
  "status": "final",
  "triage_level": "URGENT",
  "recommended_departments": ["急诊", "普外科"],
  "possible_causes": [
    "急性阑尾炎（疑似）"
  ],
  "response": "根据您的描述，右下腹痛持续4小时伴有恶心，建议尽快就医排查。",
  "turn_count": 2
}
```

### 5.5 完整客户端示例

```python
import base64
import requests
import uuid
from typing import Optional, Dict, List


class TriNavClient:
    """TriNav API 客户端封装"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.endpoint = f"{base_url}/assistant/invoke"

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

    def print_result(self, result: Dict):
        """格式化打印结果"""
        print(f"\n{'='*60}")
        print(f"分诊等级: {result.get('triage_level', 'N/A')}")
        print(f"分诊原因: {result.get('triage_reason', 'N/A')}")
        print(f"推荐科室: {', '.join(result.get('recommended_departments', []))}")

        if result.get('possible_causes'):
            print(f"\n可能原因:")
            for cause in result['possible_causes']:
                print(f"  • {cause}")

        if result.get('self_care_tips'):
            print(f"\n自我护理建议:")
            for tip in result['self_care_tips']:
                print(f"  • {tip}")

        if result.get('red_flags'):
            print(f"\n⚠️ 警示信号:")
            for flag in result['red_flags']:
                print(f"  • {flag}")

        if result.get('navigation'):
            nav = result['navigation']
            print(f"\n🗺️ 推荐医院:")
            for hospital in nav.get('hospitals', [])[:3]:
                print(f"  {hospital['rank']}. {hospital['name']}")
                print(f"     {hospital['address']}")
                print(f"     距离: {hospital['distance_m']}米 | 三甲: {'是' if hospital['is_3a'] else '否'}")

        if result.get('clarify_questions'):
            print(f"\n❓ 需要澄清的问题:")
            for i, q in enumerate(result['clarify_questions'], 1):
                print(f"  {i}. {q}")

        print(f"{'='*60}\n")

    def health_check(self) -> bool:
        """检查服务健康状态"""
        try:
            response = requests.get(f"{self.base_url}/health")
            return response.json().get("status") == "healthy"
        except:
            return False


# 使用示例
if __name__ == "__main__":
    client = TriNavClient()

    # 检查服务状态
    if not client.health_check():
        print("服务不可用，请检查服务器是否启动")
        exit(1)

    print("✅ TriNav 服务正常")

    # 示例 1: 文本分诊
    print("\n【示例 1】文本分诊")
    result = client.triage(
        text="手臂红疹，有点痒，持续2天"
    )
    client.print_result(result)

    # 示例 2: 带导航分诊
    print("\n【示例 2】带导航分诊")
    result = client.triage(
        text="头痛发烧",
        gps_lat=39.9042,
        gps_lng=116.4074
    )
    client.print_result(result)

    # 示例 3: 急诊情况
    print("\n【示例 3】急诊情况")
    result = client.triage(
        text="胸口闷，呼吸困难，持续半小时"
    )
    client.print_result(result)
```

---

## 6. 工作流程详解

### 6.1 18 节点工作流概览

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     TriNav 18 节点工作流                                  │
└─────────────────────────────────────────────────────────────────────────┘

  [用户输入]
  session_id, text, image?, gps_lat?, gps_lng?
       │
       ▼
   ┌──────────────┐
   │ 1. 输入验证器 │  ← 验证 UUID 格式、文本长度、GPS 范围
   └──────────────┘
       │
       ▼
   ┌──────────────┐
   │ 2. 会话加载器 │  ← 从 Redis 加载历史会话（或初始化）
   └──────────────┘
       │
       ▼
   ┌──────────────┐
   │ 3. 图像质量门 │  ← 检查图片清晰度、光线、对焦
   └──────────────┘
       │
       ▼
   ┌──────────────┐
   │ 4. 视觉提取器 │  ← Qwen-VL 提取视觉特征（如提供图片）
   └──────────────┘
       │
       ▼
   ┌──────────────┐
   │ 5. 临床提取器 │  ← LLM 提取结构化症状信息
   └──────────────┘
       │
       ▼
   ┌──────────────┐
   │ 6. 红旗检测器 │  ← 规则引擎：15 条红旗规则匹配
   └──────────────┘
       │
       ▼
   ┌──────────────┐
   │ 7. 分诊分类器 │  ← LLM 分诊等级判断（保守策略）
   └──────────────┘
       │
       ▼
   ┌──────────────┐
   │ 8. 分诊合并器 │  ← 合并规则+LLM 结果（规则优先）
   └──────────────┘
       │
       ▼
   ┌──────────────┐
   │ 9. 领域分类器 │  ← 识别病例所属医学专科
   └──────────────┘
       │
       ▼
   ┌─────────────────┐
   │ 10. 澄清生成器   │  ← 信息不足时生成澄清问题（最多2轮）
   └─────────────────┘
       │
       ▼
   ┌─────────────────┐
   │ 11. 证据路由器   │  ← 决策：是否需要 NCBI 证据检索
   └─────────────────┘
       │
       ├─→ [跳过证据] ──────────────────────┐
       │                                    │
       └─→ [检索证据]                        │
            │                               │
            ▼                               │
       ┌──────────────┐                     │
       │12.NCBI查询构建│                     │
       └──────────────┘                     │
            │                               │
            ▼                               │
       ┌──────────────┐                     │
       │13.NCBI检索器  │ ← PubMed 文献检索   │
       └──────────────┘                     │
            │                               │
            └───────────────────────────────┤
                                             ▼
                                      ┌──────────────┐
                                      │14. 医院导航器 │ ← GPS 时搜索附近医院
                                      └──────────────┘
                                             │
                                             ▼
                                      ┌──────────────┐
                                      │15. 天气获取器 │ ← 天气预警
                                      └──────────────┘
                                             │
                                             ▼
                                      ┌──────────────┐
                                      │16. 推理验证器 │ ← 安全检查
                                      └──────────────┘
                                             │
                                             ▼
                                      ┌──────────────┐
                                      │17. 会话保存器 │ ← 保存到 Redis
                                      └──────────────┘
                                             │
                                             ▼
                                      ┌──────────────┐
                                      │18. 最终路由器 │ ← 格式化输出
                                      └──────────────┘
                                             │
                                             ▼
                                        [返回结果]
```

### 6.2 节点详细说明

| 节点 | 功能 | 输入 | 输出 | 处理时间 |
|:-----|:-----|:-----|:-----|:---------|
| 1. input_validator | 验证输入格式 | 原始输入 | 验证通过/失败 | <50ms |
| 2. session_loader | 加载会话状态 | session_id | 历史状态 | 50-100ms |
| 3. image_quality_gate | 检查图片质量 | image_base64 | 质量评分 | 100-200ms |
| 4. vision_extract | 提取视觉特征 | 图片数据 | 视觉发现 | 1-2s |
| 5. clinical_extractor | 提取症状信息 | text + vision | SymptomSchema | 2-3s |
| 6. red_flag_detector | 红旗规则检测 | SymptomSchema | 规则匹配 | <100ms |
| 7. triage_classifier | LLM 分诊分类 | SymptomSchema | 分诊等级 | 2-3s |
| 8. triage_merger | 合并分诊结果 | 规则+LLM | 最终等级 | <50ms |
| 9. domain_classifier | 识别医学专科 | 分诊结果 | 专科分类 | 1-2s |
| 10. clarification_generator | 生成澄清问题 | 症状信息 | 问题列表 | 1-2s |
| 11. evidence_router | 决策证据检索 | 分诊等级 | 是/否 | <50ms |
| 12. ncbi_query_builder | 构建 NCBI 查询 | 症状关键词 | 查询语句 | <100ms |
| 13. ncbi_retriever_tool | 检索医学文献 | NCBI 查询 | 文献列表 | 2-5s |
| 14. navigator | 医院搜索导航 | GPS 坐标 | 医院列表+路线 | 1-2s |
| 15. weather_fetcher | 获取天气信息 | GPS 坐标 | 天气预警 | 500ms |
| 16. reasoning_verifier | 推理安全验证 | 完整响应 | 验证结果 | 1-2s |
| 17. session_saver | 保存会话状态 | 完整状态 | 保存确认 | 50-100ms |
| 18. final_status_router | 最终响应路由 | 完整状态 | JSON 响应 | <100ms |

### 6.3 条件路由逻辑

```
证据路由 (节点 11):
  ├─ 分诊等级 = EMERGENCY → 跳过 NCBI（性能优化）
  ├─ 分诊等级 = SELF_CARE → 跳过 NCBI
  └─ 其他 → 执行 NCBI 检索

导航路由 (节点 14):
  ├─ 提供 GPS → 执行医院搜索
  └─ 未提供 GPS → 跳过导航

澄清路由 (节点 10):
  ├─ 信息不足 → 生成澄清问题
  ├─ 轮次 < 2 → 继续澄清
  └─ 轮次 = 2 → 强制输出结果
```

### 6.4 红旗检测规则（15 条）

| 规则 ID | 触发条件 | 分诊等级 | 优先级 |
|:--------|:---------|:---------|:-------|
| RF_BREATHING_DIFFICULTY | 呼吸困难 | EMERGENCY | 高 |
| RF_CHEST_PAIN | 胸口疼痛/闷/压迫感 | EMERGENCY | 高 |
| RF_CHEST_TIGHTNESS_PLUS_DIFFICULTY | 胸闷+呼吸困难 | EMERGENCY | 高 |
| RF_SEVERE_BLEEDING | 大出血 | EMERGENCY | 高 |
| RF_HIGH_FEVER_WITH_SEVERITY | 高热+严重 | EMERGENCY | 中 |
| RF_HEAD_INJURY | 头部受伤+意识症状 | EMERGENCY | 高 |
| RF_SEVERE_ALLERGIC_REACTION | 严重过敏反应 | EMERGENCY | 高 |
| RF_SUICIDAL_THOUGHTS | 自杀想法 | EMERGENCY | 高 |
| RF_ABDOMINAL_PAIN_SEVERE | 严重腹痛+伴随症状 | EMERGENCY | 中 |
| RF_STROKE_SYMPTOMS | 中风症状 | EMERGENCY | 高 |
| RF_SEIZURE | 抽搐发作 | EMERGENCY | 高 |
| RF_FRACTURE_OR_TRAUMA | 骨折/严重创伤 | EMERGENCY | 高 |
| RF_POISONING | 中毒/误服 | EMERGENCY | 高 |
| RF_PREGNANCY_COMPPLICATIONS | 孕期并发症 | EMERGENCY | 高 |
| RF_HEART_ATTACK_SYMPTOMS | 心梗症状 | EMERGENCY | 高 |

### 6.5 会话状态管理

```
Redis 存储结构:
┌────────────────────────────────────────────────────────────┐
│ Key: session:{session_id}                                  │
│ TTL: 3600 秒 (60 分钟)                                     │
├────────────────────────────────────────────────────────────┤
│ {                                                           │
│   "turn_count": 1,              # 对话轮次                 │
│   "symptom_schema": {           # 症状结构化数据           │
│     "body_part": "手臂",        #   - 部位                 │
│     "symptoms": ["红疹", "痒"], #   - 症状列表             │
│     "duration": "2天",          #   - 持续时间             │
│     "severity": "轻微"          #   - 严重程度             │
│   },                                                    │
│   "clarify_questions": [        # 已问的澄清问题           │
│     "疼痛持续多长时间？"                                │
│   ],                                                    │
│   "last_update": "2026-01-11T12:00:00Z"                   │
│ }                                                           │
└────────────────────────────────────────────────────────────┘
```

---

## 7. 数据模型

### 7.1 SymptomSchema（症状结构化）

```python
{
  "body_part": "手臂",              # 患病部位
  "symptoms": ["红疹", "痒"],       # 症状列表
  "duration": "2天",                # 持续时间
  "severity": "轻微",               # 严重程度: 轻微/中度/严重
  "onset": "逐渐",                  # 起病方式: 突然/逐渐
  "accompanying_symptoms": [],      # 伴随症状

  # 视觉发现（如有图片）
  "visual_findings": {
    "type": "rash",                 # 类型: rash/wound/unknown
    "summary": "手臂红斑伴丘疹",
    "features": ["红斑", "丘疹"],
    "confidence": 0.85
  }
}
```

### 7.2 TriageAssessment（分诊评估）

```python
{
  "triage_level": "ROUTINE",           # 分诊等级
  "triage_reason": "症状轻微",          # 分诊原因
  "triage_source": "llm",              # 来源: rule_engine/llm/merged
  "recommended_departments": ["皮肤科"], # 推荐科室
  "possible_causes": [                 # 可能原因（含限定词）
    "过敏相关皮疹（疑似）",
    "接触性皮炎（疑似）"
  ],
  "self_care_tips": [                  # 自我护理建议
    "避免抓挠患处",
    "保持患处清洁干燥"
  ],
  "red_flags": [                       # 警示信号
    "如果出现呼吸困难，请立刻急诊"
  ],
  "red_flags_hit": []                  # 触发的规则ID列表
}
```

### 7.3 NavigationResult（导航结果）

```python
{
  "radius_km": 10,                     # 搜索半径
  "hospitals": [                       # 推荐医院列表（最多3家）
    {
      "rank": 1,                       # 推荐排序
      "name": "北京协和医院",
      "is_3a": true,                   # 是否三甲
      "address": "北京市东城区帅府园1号",
      "distance_m": 1200,              # 距离（米）
      "location": {"lat": 39.914, "lng": 116.417},
      "phone": "010-69156699",
      "reason": "三甲综合医院，距离较近"
    }
    # ... 共 3 家医院
  ],
  "route_plan": {                      # 路线规划
    "to_hospital_rank": 1,             # 目标医院排序
    "mode": "driving",                 # 出行方式
    "distance_km": 1.2,                # 距离
    "eta_min": 15                      # 预计时间（分钟）
  }
}
```

### 7.4 WeatherAlert（天气预警）

```python
{
  "condition": "小雨",                 # 天气状况
  "temp_c": 8,                         # 温度（摄氏度）
  "humidity": 75,                      # 湿度（%）
  "wind_speed_kmh": 15,                # 风速
  "tip": "下雨路滑，出行请注意安全"    # 出行建议
}
```

---

## 8. 安全与合规

### 8.1 安全原则（宪章）

```
┌─────────────────────────────────────────────────────────────────┐
│                    TriNav 安全宪章                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  原则 I: 安全优先                                               │
│    → 红旗规则覆盖 LLM 判断                                      │
│    → 规则检测失败时升级为 EMERGENCY                             │
│                                                                 │
│  原则 II: 清晰边界                                              │
│    → 不提供诊断性结论                                           │
│    → 不开处方或推荐具体用药                                      │
│    → 不建议延迟就医                                             │
│                                                                 │
│  原则 III: 及时就医                                             │
│    → 所有级别都建议医疗关注                                     │
│    → SELF_CARE 仍建议观察后就医                                 │
│                                                                 │
│  原则 IV: 数据最小化                                            │
│    → Redis 仅存结构化数据                                       │
│    → 60 分钟 TTL 自动清理                                       │
│    → 不存储原始图片                                             │
│                                                                 │
│  原则 V: 降级保护                                               │
│    → 外部服务故障时优雅降级                                     │
│    → 确保核心功能可用                                           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 8.2 禁止内容过滤

系统会自动过滤以下类型内容：

| 禁止类型 | 示例 | 处理方式 |
|:---------|:-----|:---------|
| 诊断性结论 | "这是XX病" | 替换为"疑似XX" |
| 药物剂量 | "每日服用XX mg" | 完全移除 |
| 延迟就医 | "可以先观察几天" | 替换为"建议尽快就医" |
| 替代专业 | "不用去医院" | 完全移除 |

### 8.3 限定词强制

所有可能的病因描述必须包含限定词：

- ✅ 正确：`过敏相关皮疹（疑似）`、`可能是接触性皮炎`
- ❌ 错误：`这是过敏`、`确诊为XX`

### 8.4 双重安全验证

```
第一层：规则引擎（红旗检测）
    ↓
第二层：LLM 推理验证器
    ↓
输出：安全且负责任的响应
```

### 8.5 免责声明

所有响应均包含以下免责声明：

> **本建议仅供参考，不替代专业医疗诊断。如有紧急情况，请立即前往急诊或呼叫急救。**

---

## 9. 故障排除

### 9.1 常见问题速查表

| 问题 | 可能原因 | 解决方案 |
|:-----|:---------|:---------|
| 服务无法启动 | Redis 未运行 | 启动 Redis（`redis-server` 或 `docker run -d -p 6379:6379 redis:7-alpine`） |
| API 调用超时 | LLM 响应慢 | 检查网络，增加超时时间 |
| 导航功能不可用 | 未配置高德 API Key | 添加 `AMAP_API_KEY` |
| 海外坐标无医院 | 高德地图覆盖有限 | 使用国内坐标或接入海外地图服务 |
| 会话不持久 | Redis 连接失败 | 检查 `REDIS_URL` |
| 分诊结果为空 | LLM 配置错误 | 验证 `QWEN_API_KEY` |
| 图片识别失败 | 图片格式不支持 | 使用 JPEG/PNG，<5MB |

### 9.2 日志查看

```bash
# 默认日志路径：logs/trinav.log（可用 TRINAV_LOG_FILE 覆盖）
# 查看服务日志
tail -f logs/trinav.log

# 过滤错误日志
grep ERROR logs/trinav.log

# 按 session_id 过滤
grep "session_id=550e8400" logs/trinav.log
```

### 9.3 健康检查

```bash
# 基础健康检查
curl http://localhost:8000/health

# 预期输出
{
  "status": "healthy",
  "redis": "healthy"
}

# Redis 连接测试
redis-cli -h localhost -p 6379 ping
# 应输出: PONG

# Qwen API 测试
curl -X POST https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions \
  -H "Authorization: Bearer $QWEN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen-turbo","messages":[{"role":"user","content":"test"}]}'
```

### 9.4 性能问题诊断

```bash
# 检查响应时间
curl -w "@curl-format.txt" -X POST http://localhost:8000/assistant/invoke \
  -H "Content-Type: application/json" \
  -d '{"session_id":"test","text":"手臂红疹"}'

# curl-format.txt 内容:
# time_namelookup:  %{time_namelookup}\n
# time_connect:     %{time_connect}\n
# time_appconnect:  %{time_appconnect}\n
# time_pretransfer: %{time_pretransfer}\n
# time_starttransfer: %{time_starttransfer}\n
# time_total:       %{time_total}\n

# 检查 Redis 性能
redis-cli --latency

# 检查系统资源
top -p $(pgrep -f "python -m src.server")
```

### 9.5 错误场景处理

**场景 1：Redis 连接失败**

```bash
# 症状：日志显示 "Redis connection failed"
# 影响：会话无法持久化，系统降级运行
# 解决方案：
1. 检查 Redis 是否运行
2. 验证 REDIS_URL 配置
3. 重启 Redis 服务
```

**场景 2：LLM API 超时**

```bash
# 症状：请求超过 30 秒无响应
# 影响：无法完成分诊
# 解决方案：
1. 检查网络连接
2. 验证 QWEN_API_KEY 有效性
3. 增加超时配置
```

**场景 3：图片处理失败**

```bash
# 症状：带图片请求返回错误
# 影响：仅使用文本分析
# 解决方案：
1. 检查图片大小（<5MB）
2. 验证图片格式（JPEG/PNG）
3. 确认 base64 编码正确
```

---

## 10. 开发指南

### 10.1 本地开发设置

```bash
# 克隆项目
cd /AII-wuqi/AII_home/fq_775/TriNav

# 创建虚拟环境
python3.11 -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 配置开发环境变量
cat > .env << EOF
QWEN_API_KEY=sk-xxxxx
REDIS_URL=redis://localhost:6379
SERVER_DEBUG=true
LOG_LEVEL=DEBUG
TRINAV_LOG_FILE=logs/trinav.log
EOF

# 启动 Redis
redis-server
# or: docker run --name trinav-redis -p 6379:6379 redis:7-alpine

# 启动开发服务器（热重载）
python -m src.server
```

### 10.2 运行测试

```bash
# 运行所有测试
pytest -v

# 运行特定测试
pytest tests/unit/test_nodes/test_red_flag_detector.py -v

# 运行测试并生成覆盖率报告
pytest --cov=src --cov-report=html --cov-report=term

# 查看覆盖率报告
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

### 10.3 代码质量工具

```bash
# 代码格式化
black src/ tests/

# 代码检查
ruff check src/ tests/

# 自动修复
ruff check --fix src/ tests/

# 类型检查
mypy src/

# 安全检查
bandit -r src/
```

### 10.4 添加新的工作流节点

```python
# src/chains/nodes/my_custom_node.py
from .base import safe_node
from ..graph.triage_graph import TriageState
from ...utils.logging_config import get_logger

logger = get_logger(__name__)

@safe_node
async def my_custom_node(state: TriageState) -> TriageState:
    """
    自定义节点逻辑

    Args:
        state: 当前工作流状态

    Returns:
        更新后的状态
    """
    logger.info("执行自定义节点")

    # 你的逻辑
    custom_value = process_something(state)

    # 更新状态
    state["custom_field"] = custom_value

    return state
```

在 `src/chains/graph/triage_graph.py` 中注册：

```python
from ..nodes import my_custom_node

def build_graph() -> StateGraph:
    graph = StateGraph(TriageState)

    # 添加节点
    graph.add_node("my_custom_node", my_custom_node)

    # 添加边
    graph.add_edge("previous_node", "my_custom_node")
    graph.add_edge("my_custom_node", "next_node")

    return graph.compile()
```

### 10.5 修改红旗规则

编辑 `src/config/red_flag_rules.yaml`：

```yaml
- id: RF_MY_NEW_RULE
  priority: high
  version: 1.0.0
  conditions:
    - field: symptoms
      op: contains_any
      value: ["新症状关键词"]
  triage_level: EMERGENCY
  user_message: "这是新的红旗规则消息"
  department: ["急诊"]
```

**⚠️ 警告**：规则修改需要医疗顾问审核！

### 10.6 调试技巧

```python
# 启用调试日志
import logging
logging.basicConfig(level=logging.DEBUG)

# 在节点中打印状态
@safe_node
async def debug_node(state: TriageState) -> TriageState:
    logger.debug(f"当前状态: {state}")
    # 使用 breakpoint() 进入调试器
    # breakpoint()
    return state

# 查看 LangGraph 执行图
from src.chains.graph.triage_graph import build_graph
graph = build_graph()
print(graph.get_graph().print_ascii())
```

---

## 11. 部署指南

### 11.1 Docker 部署

**Dockerfile:**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY src/ src/
COPY .env.example .env

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["python", "-m", "src.server"]
```

**docker-compose.yml（示例，需自行保存）：**

> 说明：仓库不内置 docker-compose.yml，可按需参考下方示例创建。

```yaml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    container_name: trinav-redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 3

  trinav:
    build: .
    container_name: trinav-app
    ports:
      - "8000:8000"
    environment:
      - REDIS_URL=redis://redis:6379
      - QWEN_API_KEY=${QWEN_API_KEY}
      - AMAP_API_KEY=${AMAP_API_KEY}
    depends_on:
      redis:
        condition: service_healthy
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  redis_data:
```

**部署命令（基于上面的 docker-compose.yml 示例）：**

```bash
# 构建并启动
docker-compose up -d

# 查看日志
docker-compose logs -f trinav

# 停止服务
docker-compose down
```

### 11.2 Kubernetes 部署

**deployment.yaml:**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: trinav
spec:
  replicas: 3
  selector:
    matchLabels:
      app: trinav
  template:
    metadata:
      labels:
        app: trinav
    spec:
      containers:
      - name: trinav
        image: your-registry/trinav:1.0.0
        ports:
        - containerPort: 8000
        env:
        - name: REDIS_URL
          value: "redis://redis-service:6379"
        - name: QWEN_API_KEY
          valueFrom:
            secretKeyRef:
              name: trinav-secrets
              key: qwen-api-key
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "2000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5

---
apiVersion: v1
kind: Service
metadata:
  name: trinav-service
spec:
  selector:
    app: trinav
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: LoadBalancer
```

### 11.3 生产环境配置

**环境变量检查清单：**

```bash
# 必需配置
QWEN_API_KEY=sk-xxxxx                    # ✅ 必填
REDIS_URL=redis://localhost:6379         # ✅ 必填

# 可选配置
AMAP_API_KEY=xxxxx                       # 导航功能需要
LANGCHAIN_TRACING_V2=true                # 可观测性
LANGCHAIN_API_KEY=xxxxx                  # LangSmith

# 生产配置
SERVER_DEBUG=false                       # ✅ 生产设为 false
LOG_LEVEL=INFO                           # ✅ 避免 DEBUG
TRINAV_LOG_FILE=logs/trinav.log          # 可选，日志文件路径
```

---

## 12. 性能优化

### 12.1 目标性能指标

| 指标 | 目标值 | 说明 |
|:-----|:-------|:-----|
| EMERGENCY 分诊 | ≤5 秒 (p95) | 跳过 NCBI |
| URGENT 分诊 | ≤10 秒 (p95) | 含 NCBI |
| ROUTINE 分诊 | ≤15 秒 (p95) | 含 NCBI |
| 并发用户 | 100+ | 基线 |
| 月度可用性 | 99.5% | 约 3.6 小时/月 |

### 12.2 性能优化建议

**1. 急诊路径优化**
- EMERGENCY 级别跳过 NCBI 检索
- 规则引擎优先于 LLM

**2. Redis 连接池**
```python
# src/config/settings.py
REDIS_MAX_CONNECTIONS = 20  # 根据并发量调整
```

**3. LLM 缓存**
```python
# 对相似查询进行缓存
cache_key = f"triage:{hash(symptom_text)}"
cached_result = await redis.get(cache_key)
```

**4. 异步处理**
- 所有节点使用 async/await
- 外部 API 调用使用 httpx.AsyncClient

**5. 水平扩展**
- 无状态设计（Redis 分离）
- 可部署多实例

### 12.3 性能监控

```python
# Prometheus 指标
from src.utils.metrics import (
    request_duration,
    triage_decisions,
    external_service_health
)

# 自定义指标
from prometheus_client import Histogram

llm_response_time = Histogram(
    'llm_response_seconds',
    'LLM response time',
    ['model', 'operation']
)
```

---

## 13. 监控与运维

### 13.1 日志结构

```json
{
  "timestamp": "2026-01-11T12:00:00Z",
  "level": "INFO",
  "logger": "src.chains.nodes.clinical_extractor",
  "message": "Symptom extraction completed",
  "context": {
    "session_id": "550e8400-...",
    "correlation_id": "550e8400-...",
    "node": "clinical_extractor",
    "duration_ms": 2450
  }
}
```

### 13.2 Prometheus 指标

```bash
# 暴露指标的端点
curl http://localhost:8000/metrics

# 关键指标
# - trinav_request_count{endpoint, status}
# - trinav_request_duration{endpoint}
# - trinav_triage_decisions{triage_level, source}
# - trinav_external_service_health{service_name}
```

### 13.3 告警规则

**alerting_rules.yml:**

```yaml
groups:
- name: trinav
  rules:
  - alert: HighErrorRate
    expr: rate(trinav_request_count{status="error"}[5m]) > 0.05
    for: 5m
    annotations:
      summary: "High error rate detected"

  - alert: RedisUnhealthy
    expr: trinav_external_service_health{service_name="redis"} == 0
    for: 2m
    annotations:
      summary: "Redis connection failed"
```

---

## 14. 附录

### 14.1 完整 API 示例代码

详见 [5.5 完整客户端示例](#55-完整客户端示例)

### 14.2 错误码参考

| HTTP 状态码 | 错误类型 | 说明 |
|:-----------|:---------|:-----|
| 200 | 成功 | 请求正常处理 |
| 400 | 参数错误 | 请求参数不合法 |
| 500 | 服务器错误 | 内部处理错误 |

### 14.3 支持与反馈

- **GitHub Issues**: [项目地址]
- **文档**: `docs/` 目录
- **技术计划**: `specs/001-medical-triage-nav/`

### 14.4 版本历史

| 版本 | 日期 | 变更 |
|:-----|:-----|:-----|
| 1.0.0 | 2026-01-11 | 初始版本 - 生产就绪 |

---

## 📄 免责声明

**TriNav 是一个辅助工具，不替代专业医疗建议。紧急情况请立即呼叫急救（120）或前往急诊。**

---

**文档版本**: 1.0.0
**最后更新**: 2026-01-11
**维护者**: TriNav 开发团队
