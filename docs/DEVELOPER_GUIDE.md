# TriNav 开发者指南

> 深入技术架构与开发实践手册

版本: 1.1.0
更新日期: 2026-01-12

---

## 目录

1. [项目架构](#1-项目架构)
2. [核心模块详解](#2-核心模块详解)
3. [LangGraph 工作流](#3-langgraph-工作流)
4. [节点开发指南](#4-节点开发指南)
5. [服务层架构](#5-服务层架构)
6. [数据流与状态管理](#6-数据流与状态管理)
7. [安全机制实现](#7-安全机制实现)
8. [测试策略](#8-测试策略)
9. [性能优化](#9-性能优化)
10. [故障处理](#10-故障处理)

---

## 1. 项目架构

### 1.1 技术栈全景

```
┌─────────────────────────────────────────────────────────────────┐
│                    TriNav 技术栈分层图                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  API Layer (FastAPI + LangServe)                         │ │
│  │  ┌─────────────────────────────────────────────────┐     │ │
│  │  │ src/server.py                                    │     │ │
│  │  │  - FastAPI app                                   │     │ │
│  │  │  - LangServe routes (/assistant/invoke)          │     │ │
│  │  │  - Health check (/health)                        │     │ │
│  │  │  - CORS middleware                               │     │ │
│  │  └─────────────────────────────────────────────────┘     │ │
│  └───────────────────────────────────────────────────────────┘ │
│                              │                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  Workflow Layer (LangGraph 1.0.5+)                       │ │
│  │  ┌─────────────────────────────────────────────────┐     │ │
│  │  │ src/chains/                                     │     │ │
│  │  │  ├─ graph/triage_graph.py   # StateGraph定义    │     │ │
│  │  │  ├─ triage_chain.py          # Chain导出         │     │ │
│  │  │  └─ nodes/                   # 18个节点          │     │ │
│  │  │     ├─ base.py              # @safe_node装饰器  │     │ │
│  │  │     ├─ input_validator.py   # 输入验证          │     │ │
│  │  │     ├─ session_loader.py    # 会话加载          │     │ │
│  │  │     ├─ clinical_extractor.py # 临床提取         │     │ │
│  │  │     ├─ red_flag_detector.py # 红旗检测          │     │ │
│  │  │     ├─ triage_classifier.py # LLM分诊          │     │ │
│  │  │     └─ ...                                       │     │ │
│  │  └─────────────────────────────────────────────────┘     │ │
│  └───────────────────────────────────────────────────────────┘ │
│                              │                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  Service Layer (外部服务集成)                              │ │
│  │  ┌─────────────────────────────────────────────────┐     │ │
│  │  │ src/services/                                   │     │ │
│  │  │  ├─ llm_service.py          # Qwen模型          │     │ │
│  │  │  │   ├─ qwen-plus (提取/分诊/验证)              │     │ │
│  │  │  │   └─ qwen-vl-plus (图像识别)                │     │ │
│  │  │  ├─ redis_service.py        # 会话存储          │     │ │
│  │  │  ├─ amap_service.py         # 高德地图          │     │ │
│  │  │  ├─ ncbi_service.py         # PubMed检索        │     │ │
│  │  │  └─ weather_service_*.py   # 天气服务          │     │ │
│  │  └─────────────────────────────────────────────────┘     │ │
│  └───────────────────────────────────────────────────────────┘ │
│                              │                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  Utility Layer (工具与基础设施)                            │ │
│  │  ┌─────────────────────────────────────────────────┐     │ │
│  │  │ src/utils/                                      │     │ │
│  │  │  ├─ logging_config.py    # 结构化日志           │     │ │
│  │  │  ├─ telemetry.py         # OpenTelemetry        │     │ │
│  │  │  ├─ metrics.py           # Prometheus指标       │     │ │
│  │  │  └─ safety_filters.py    # 安全过滤器           │     │ │
│  │  │                                                 │     │ │
│  │  │ src/config/                                     │     │ │
│  │  │  ├─ settings.py          # Pydantic设置        │     │ │
│  │  │  └─ red_flag_rules.yaml  # 红旗规则定义        │     │ │
│  │  └─────────────────────────────────────────────────┘     │ │
│  └───────────────────────────────────────────────────────────┘ │
│                              │                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  Data Layer (数据模型)                                     │ │
│  │  ┌─────────────────────────────────────────────────┐     │ │
│  │  │ src/models/                                     │     │ │
│  │  │  ├─ symptom_schema.py      # SymptomSchema     │     │ │
│  │  │  ├─ triage_assessment.py   # TriageAssessment  │     │ │
│  │  │  ├─ navigation_result.py   # NavigationResult  │     │ │
│  │  │  ├─ evidence.py             # Evidence          │     │ │
│  │  │  ├─ weather_alert.py        # WeatherAlert      │     │ │
│  │  │  ├─ red_flag_rule.py        # RedFlagRule       │     │ │
│  │  │  └─ session.py              # Session           │     │ │
│  │  └─────────────────────────────────────────────────┘     │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 依赖关系图

```
requirements.txt (生产依赖)
├── langchain>=0.3.0              # LLM框架
├── langgraph>=1.0.5              # 工作流编排
├── langchain-openai>=0.2.0       # Qwen兼容接口
├── fastapi>=0.104.0              # API框架
├── langserve>=0.2.0              # LangChain服务化
├── uvicorn>=0.24.0               # ASGI服务器
├── redis>=5.0.0                  # 缓存/会话
├── pydantic>=2.5.0               # 数据验证
├── pydantic-settings>=2.1.0      # 配置管理
├── httpx>=0.25.0                 # 异步HTTP客户端
├── tenacity>=8.2.0               # 重试机制
└── prometheus-client>=0.19.0     # 指标暴露

requirements-dev.txt (开发依赖)
├── pytest>=7.4.0                 # 测试框架
├── pytest-asyncio>=0.21.0        # 异步测试
├── pytest-cov>=4.1.0             # 覆盖率
├── black>=23.12.0                # 代码格式化
├── ruff>=0.1.0                   # 代码检查
├── mypy>=1.7.0                   # 类型检查
└── bandit>=1.7.0                 # 安全检查
```

### 1.3 目录结构说明

```
TriNav/
├── src/                          # 源代码根目录
│   ├── __init__.py
│   ├── server.py                 # FastAPI应用入口
│   │
│   ├── chains/                   # LangChain/LangGraph层
│   │   ├── __init__.py
│   │   ├── triage_chain.py       # Chain导出（LangServe）
│   │   ├── graph/                # StateGraph定义
│   │   │   ├── __init__.py
│   │   │   └── triage_graph.py   # 18节点工作流
│   │   └── nodes/                # 工作流节点（18个）
│   │       ├── __init__.py
│   │       ├── base.py           # @safe_node装饰器
│   │       ├── input_validator.py
│   │       ├── session_loader.py
│   │       ├── image_quality_gate.py
│   │       ├── vision_extract.py
│   │       ├── clinical_extractor.py
│   │       ├── red_flag_detector.py
│   │       ├── triage_classifier.py
│   │       ├── triage_merger.py
│   │       ├── domain_classifier.py
│   │       ├── clarification_generator.py
│   │       ├── evidence_router.py
│   │       ├── ncbi_query_builder.py
│   │       ├── ncbi_retriever_tool.py
│   │       ├── navigator.py
│   │       ├── weather_fetcher.py
│   │       ├── reasoning_verifier.py
│   │       ├── session_saver.py
│   │       └── final_status_router.py
│   │
│   ├── services/                 # 服务层（外部API集成）
│   │   ├── __init__.py
│   │   ├── llm_service.py        # Qwen模型服务
│   │   ├── redis_service.py      # Redis服务
│   │   ├── amap_service.py       # 高德地图
│   │   ├── ncbi_service.py       # NCBI/PubMed
│   │   └── weather_service_*.py  # 天气服务
│   │
│   ├── models/                   # Pydantic数据模型
│   │   ├── __init__.py
│   │   ├── symptom_schema.py     # 症状结构化
│   │   ├── triage_assessment.py  # 分诊评估
│   │   ├── navigation_result.py  # 导航结果
│   │   ├── evidence.py           # 医学证据
│   │   ├── weather_alert.py      # 天气预警
│   │   ├── red_flag_rule.py      # 红旗规则
│   │   └── session.py            # 会话状态
│   │
│   ├── utils/                    # 工具模块
│   │   ├── __init__.py
│   │   ├── logging_config.py     # 日志配置
│   │   ├── telemetry.py          # OpenTelemetry
│   │   ├── metrics.py            # Prometheus指标
│   │   └── safety_filters.py     # 安全过滤器
│   │
│   └── config/                   # 配置模块
│       ├── __init__.py
│       ├── settings.py           # Pydantic Settings
│       └── red_flag_rules.yaml   # 红旗规则定义
│
├── tests/                        # 测试代码
│   ├── conftest.py               # pytest配置
│   ├── unit/                     # 单元测试
│   │   ├── test_nodes/           # 节点测试
│   │   ├── test_services/        # 服务测试
│   │   └── test_models/          # 模型测试
│   ├── integration/              # 集成测试
│   └── contract/                 # 契约测试
│
├── docs/                         # 文档
│   ├── USER_MANUAL.md            # 用户手册
│   └── DEVELOPER_GUIDE.md        # 开发者指南（本文件）
│
├── frontend/                     # 前端（Vite + React）
│
├── specs/                        # 规格文档
│   └── 001-medical-triage-nav/
│
├── .env.example                  # 环境变量模板
├── AGENTS.md                     # 贡献与协作指南
├── docker-compose.yml            # Docker编排（可选，自行提供）
├── Dockerfile                    # 镜像构建（可选，自行提供）
├── requirements.txt              # 生产依赖
├── requirements-dev.txt          # 开发依赖
├── pyproject.toml               # 项目配置
└── README.md                     # 项目说明
```

---

## 2. 核心模块详解

### 2.1 TriageState（工作流状态）

`TriageState` 是 LangGraph 工作流的核心数据结构，在整个 18 节点工作流中传递和更新：

```python
# src/chains/graph/triage_graph.py
class TriageState(TypedDict):
    """工作流状态定义"""

    # === 输入字段 ===
    session_id: str                      # 会话唯一标识
    text: str                            # 用户症状描述
    image_base64: Optional[str]          # 图片数据（Base64）
    gps_lat: Optional[float]             # GPS纬度
    gps_lng: Optional[float]             # GPS经度

    # === 会话状态 ===
    turn_count: int                      # 对话轮次
    symptom_schema: Optional[Dict]       # 结构化症状
    clarify_questions: List[str]         # 澄清问题列表

    # === 分诊决策 ===
    triage_level: Optional[Literal]      # 分诊等级
    triage_source: Optional[str]         # 来源：rule_engine/llm/merged
    triage_reason: Optional[str]         # 分诊原因
    recommended_departments: List[str]   # 推荐科室
    possible_causes: List[str]           # 可能原因
    self_care_tips: List[str]            # 自我护理建议
    red_flags: List[str]                 # 警示信号

    # === 红旗检测 ===
    rule_triage_level: Optional[str]     # 规则引擎判断
    llm_triage_level: Optional[str]      # LLM判断
    red_flags_hit: List[str]             # 触发的规则ID

    # === 澄清 ===
    need_clarify: bool                   # 是否需要澄清

    # === 图像处理 ===
    image_as_valid: bool                 # 图片是否有效

    # === 证据检索 ===
    should_retrieve_evidence: bool       # 是否检索证据
    ncbi_query: str                      # NCBI查询语句

    # === 外部服务结果 ===
    visual_findings: Optional[Dict]      # 视觉发现
    evidence_selected: Optional[List]    # 选中的证据
    navigation_result: Optional[Dict]    # 导航结果
    weather_alert: Optional[Dict]        # 天气预警
    case_domain: Optional[str]           # 病例领域

    # === 最终输出 ===
    final_response: Optional[str]        # 最终响应文本
    status: Literal                      # 状态：final/need_more_info/error
    error_message: Optional[str]         # 错误信息
```

### 2.2 @safe_node 装饰器

`@safe_node` 是所有工作流节点的核心装饰器，提供统一的错误处理、日志记录和优雅降级：

```python
# src/chains/nodes/base.py
def safe_node(node_name: str, raise_on_error: bool = False):
    """节点装饰器，提供错误处理和日志记录

    功能：
    1. 设置 correlation_id 用于日志追踪
    2. 记录节点进入/退出日志
    3. 捕获并处理异常
    4. 根据配置决定是否抛出异常
    5. 实现优雅降级

    Args:
        node_name: 节点名称（用于日志）
        raise_on_error: 是否抛出异常（默认False）
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(state: Dict[str, Any]) -> Dict[str, Any]:
            # 设置关联ID
            session_id = state.get("session_id")
            set_correlation_id(session_id)

            try:
                # 执行节点函数
                result = await func(state)

                # 合并结果到状态
                return {**state, **result}

            except ValueError as e:
                # 验证错误：记录但不崩溃
                record_error("validation_error", node_name)
                return {**state, "status": "error", "error_message": str(e)}

            except Exception as e:
                # 意外错误：优雅降级
                record_error("node_error", node_name)

                # 如果已有急诊判断，仍返回final
                if state.get("triage_level") == "EMERGENCY":
                    return {**state, "status": "final"}

                return {**state, "status": "error", "error_message": "系统暂时繁忙"}
        return wrapper
    return decorator
```

**使用示例：**

```python
from .base import safe_node

@safe_node("my_custom_node")
async def my_custom_node(state: TriageState) -> TriageState:
    """自定义节点逻辑"""
    # 处理逻辑
    result = process_something(state)

    # 返回更新（会合并到state）
    return {"custom_field": result}
```

### 2.3 LLMService 架构

LLMService 封装了所有 Qwen 模型交互，提供多实例、重试、降级：

```python
# src/services/llm_service.py
class LLMService:
    """LLM服务

    设计原则：
    1. 多模型实例：不同用途使用不同模型
    2. 温度控制：根据任务调整temperature
    3. 重试机制：使用tenacity实现指数退避
    4. 优雅降级：失败时返回安全默认值
    """

    def __init__(self):
        """初始化4个模型实例"""
        # 提取模型：低温度(0.1)，保证一致性
        self._extractor = ChatOpenAI(model="qwen-plus", temperature=0.1)

        # 视觉模型：中温度(0.2)，平衡准确性和创造性
        self._vision = ChatOpenAI(model="qwen-vl-plus", temperature=0.2)

        # 验证模型：零温度(0.0)，严格安全检查
        self._verifier = ChatOpenAI(model="qwen-plus", temperature=0.0)

        # 分诊模型：中温度(0.3)，允许一定创造性
        self._triage = ChatOpenAI(model="qwen-plus", temperature=0.3)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=5)
    )
    async def _invoke_with_retry(self, model, messages) -> str:
        """带重试的LLM调用"""
        response = await model.ainvoke(messages)
        return response.content
```

**模型选择策略：**

| 任务 | 模型 | Temperature | 理由 |
|:-----|:-----|:------------|:-----|
| 症状提取 | qwen-plus | 0.1 | 需要稳定、一致的输出 |
| 视觉识别 | qwen-vl-plus | 0.2 | 需要一定的描述灵活性 |
| 安全验证 | qwen-plus | 0.0 | 需要严格、可重复的判断 |
| 分诊分类 | qwen-plus | 0.3 | 需要平衡准确性和创造性 |
| 科室分类 | qwen-plus | 0.1 | 需要稳定的分类结果 |
| 澄清生成 | qwen-plus | 0.1 | 需要一致的输出格式 |

---

## 3. LangGraph 工作流

### 3.1 StateGraph 构建

```python
# src/chains/graph/triage_graph.py
def build_graph() -> StateGraph:
    """构建LangGraph工作流

    关键概念：
    1. StateGraph: 基于状态的有向图
    2. Node: 处理节点，接收并返回状态
    3. Edge: 连接节点，定义执行流程
    4. Conditional Edge: 条件边，根据状态路由
    """
    # 创建状态图
    graph = StateGraph(TriageState)

    # === 添加所有节点 ===
    graph.add_node("input_validator", input_validator)
    graph.add_node("session_loader", session_load)
    # ... 添加其他16个节点

    # === 定义边（执行流程） ===
    graph.set_entry_point("input_validator")
    graph.add_edge("input_validator", "session_loader")
    # ... 定义其他边

    # === 条件边示例 ===
    graph.add_conditional_edges(
        "evidence_router",
        _should_skip_ncbi,  # 路由函数
        {
            True: "navigator",      # 跳过NCBI
            False: "ncbi_query_builder"  # 执行NCBI
        }
    )

    # 编译并返回
    return graph.compile()
```

### 3.2 条件路由函数

```python
def _should_skip_ncbi(state: TriageState) -> bool:
    """决策：是否跳过NCBI检索

    跳过条件：
    - EMERGENCY级别（性能优化）
    - SELF_CARE级别（不需要证据）
    """
    should_retrieve = state.get("should_retrieve_evidence", False)
    return not should_retrieve


def _needs_clarification(state: TriageState) -> bool:
    """决策：是否需要澄清"""
    return state.get("need_clarify", False)


def _should_skip_navigation(state: TriageState) -> bool:
    """决策：是否跳过导航"""
    triage_level = state.get("triage_level")
    return triage_level in ("SELF_CARE", None)
```

### 3.3 工作流执行流程

```
请求 → input_validator → session_loader → image_quality_gate
     → vision_extract → clinical_extractor → red_flag_detector
     → triage_classifier → triage_merger → domain_classifier
     → clarification_generator
        │
        ├─ need_clarify=True → evidence_router
        └─ need_clarify=False → evidence_router
              │
              ├─ skip_ncbi=True → navigator
              └─ skip_ncbi=False → ncbi_query_builder
                                   → ncbi_retriever_tool
                                   → navigator
                                         → weather_fetcher
                                         → reasoning_verifier
                                         → session_saver
                                         → final_status_router
                                         → END
```

---

## 4. 节点开发指南

### 4.1 节点开发模板

```python
"""自定义节点模板"""
from typing import Dict, Any
from .base import safe_node
from ...utils.logging_config import get_logger
from ...services.llm_service import get_llm_service

logger = get_logger(__name__)

@safe_node("my_custom_node")
async def my_custom_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    自定义节点

    Args:
        state: 当前工作流状态

    Returns:
        状态更新字典（会合并到原状态）
    """
    logger.info("执行自定义节点", extra={
        "session_id": state.get("session_id")
    })

    # 1. 从状态中读取数据
    symptom_schema = state.get("symptom_schema")
    text = state.get("text")

    # 2. 执行业务逻辑
    try:
        result = await process_logic(symptom_schema, text)
    except Exception as e:
        logger.error(f"处理失败: {e}")
        # 返回错误状态
        return {
            "status": "error",
            "error_message": f"处理失败: {str(e)}"
        }

    # 3. 返回更新（只包含需要更新的字段）
    return {
        "custom_field": result,
        # 不要返回整个state，只返回更新部分
    }


async def process_logic(symptom_schema: Dict, text: str) -> Any:
    """实际处理逻辑"""
    # 实现你的逻辑
    pass
```

### 4.2 节点最佳实践

**✅ DO:**

1. **使用 @safe_node 装饰器**
   ```python
   @safe_node("node_name")
   async def my_node(state: TriageState) -> TriageState:
       ...
   ```

2. **只返回更新的字段**
   ```python
   # ✅ 正确
   return {"triage_level": "EMERGENCY"}

   # ❌ 错误：不要返回整个state
   return {**state, "triage_level": "EMERGENCY"}
   ```

3. **使用 logger 记录关键信息**
   ```python
   logger.info("处理完成", extra={
       "session_id": session_id,
       "triage_level": triage_level
   })
   ```

4. **处理外部服务失败**
   ```python
   try:
       result = await external_service.call()
   except Exception as e:
       logger.error(f"外部服务失败: {e}")
       # 返回降级结果
       return {"custom_field": default_value}
   ```

**❌ DON'T:**

1. **不要在节点中阻塞**
   ```python
   # ❌ 错误
   time.sleep(5)  # 不要阻塞

   # ✅ 正确
   await asyncio.sleep(5)
   ```

2. **不要直接修改 state**
   ```python
   # ❌ 错误
   state["custom_field"] = value
   return state

   # ✅ 正确
   return {"custom_field": value}
   ```

3. **不要忽略异常**
   ```python
   # ❌ 错误
   try:
       result = risky_operation()
   except:
       pass  # 忽略所有异常

   # ✅ 正确
   try:
       result = risky_operation()
   except Exception as e:
       logger.error(f"操作失败: {e}")
       return {"error": str(e)}
   ```

### 4.3 节点测试模板

```python
# tests/unit/test_nodes/test_my_custom_node.py
import pytest
from src.chains.nodes.my_custom_node import my_custom_node

@pytest.mark.asyncio
async def test_my_custom_node_success():
    """测试节点正常流程"""
    # 准备输入状态
    state = {
        "session_id": "test-123",
        "text": "手臂红疹",
        "symptom_schema": {
            "body_part": "手臂",
            "symptoms": ["红疹"]
        }
    }

    # 执行节点
    result = await my_custom_node(state)

    # 验证输出
    assert "custom_field" in result
    assert result["custom_field"] is not None
    assert result.get("status") != "error"


@pytest.mark.asyncio
async def test_my_custom_node_error_handling():
    """测试节点错误处理"""
    state = {
        "session_id": "test-123",
        "text": None,  # 无效输入
    }

    result = await my_custom_node(state)

    # 验证错误处理
    assert result.get("status") == "error"
    assert "error_message" in result
```

---

## 5. 服务层架构

### 5.1 RedisService 设计

```python
# src/services/redis_service.py
class RedisService:
    """Redis服务

    用途：
    1. 会话状态存储（60分钟TTL）
    2. 可选：LLM响应缓存
    3. 可选：限流计数器

    数据结构：
    - Key: session:{session_id}
    - Value: JSON序列化的会话状态
    - TTL: 3600秒（60分钟）
    """

    def __init__(self):
        self._client: Optional[redis.Redis] = None
        self._healthy = False

    async def get_session(self, session_id: str) -> Optional[Dict]:
        """获取会话状态"""
        try:
            key = f"session:{session_id}"
            data = await self._client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"获取会话失败: {e}")
            return None

    async def save_session(
        self,
        session_id: str,
        state: Dict,
        ttl: int = 3600
    ) -> bool:
        """保存会话状态"""
        try:
            key = f"session:{session_id}"
            data = json.dumps(state, ensure_ascii=False)
            await self._client.setex(key, ttl, data)
            return True
        except Exception as e:
            logger.error(f"保存会话失败: {e}")
            return False
```

### 5.2 AmapService 设计

```python
# src/services/amap_service.py
class AmapService:
    """高德地图服务

    功能：
    1. 搜索附近医院（POI搜索）
    2. 获取医院详情
    3. 路线规划（驾车/公交/步行）

    API限制：
    - QPS限制：根据高德等级
    - 日调用量：根据高德等级
    """

    async def search_hospitals(
        self,
        lat: float,
        lng: float,
        radius: int = 10000,
        keywords: str = "医院"
    ) -> List[Dict]:
        """搜索附近医院

        Args:
            lat: 纬度
            lng: 经度
            radius: 搜索半径（米）
            keywords: 搜索关键词

        Returns:
            医院列表，按距离排序
        """
        url = "https://restapi.amap.com/v5/place/around"
        params = {
            "key": self.api_key,
            "location": f"{lng},{lat}",
            "radius": radius,
            "keywords": keywords,
            "sort": "distance"
        }

        response = await self._client.get(url, params=params)
        return self._parse_hospitals(response)

    async def get_route(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        mode: str = "driving"
    ) -> Dict:
        """获取路线规划

        Args:
            origin: 起点 (lat, lng)
            destination: 终点 (lat, lng)
            mode: 出行方式

        Returns:
            路线信息（距离、时间、路线描述）
        """
        url = f"https://restapi.amap.com/v3/direction/{mode}"
        params = {
            "key": self.api_key,
            "origin": f"{origin[1]},{origin[0]}",
            "destination": f"{destination[1]},{destination[0]}"
        }

        response = await self._client.get(url, params=params)
        return self._parse_route(response)
```

### 5.3 NCBIService 设计

```python
# src/services/ncbi_service.py
class NCBIService:
    """NCBI E-utilities服务

    功能：
    1. 搜索PubMed文献
    2. 获取文献摘要
    3. 提取相关证据

    API限制：
    - 无需API Key
    - 每秒最多3次请求（官方限制）
    - 需要延迟控制
    """

    def __init__(self):
        self.base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
        self._last_request_time = 0
        self._min_delay = 0.5  # 500ms

    async def search_pubmed(
        self,
        query: str,
        max_results: int = 5
    ) -> List[Dict]:
        """搜索PubMed

        Args:
            query: 搜索查询（支持MeSH术语）
            max_results: 最大结果数

        Returns:
            文献列表（包含PMID、标题、摘要）
        """
        # 速率限制
        await self._rate_limit()

        # Step 1: esearch（获取PMID列表）
        search_url = f"{self.base_url}/esearch.fcgi"
        search_params = {
            "db": "pubmed",
            "term": query,
            "retmax": max_results,
            "retmode": "json"
        }

        search_response = await self._client.get(
            search_url,
            params=search_params
        )
        pmids = search_response.get("esearchresult", {}).get("idlist", [])

        if not pmids:
            return []

        # Step 2: esummary（获取文献详情）
        await self._rate_limit()
        summary_url = f"{self.base_url}/esummary.fcgi"
        summary_params = {
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "json"
        }

        summary_response = await self._client.get(
            summary_url,
            params=summary_params
        )

        return self._parse_summaries(summary_response)

    async def _rate_limit(self):
        """速率限制：确保每秒不超过2次请求"""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_delay:
            await asyncio.sleep(self._min_delay - elapsed)
        self._last_request_time = time.time()
```

---

## 6. 数据流与状态管理

### 6.1 完整数据流

```
┌─────────────────────────────────────────────────────────────┐
│                      数据流全景图                             │
└─────────────────────────────────────────────────────────────┘

用户输入
  │
  ├─ session_id (UUID)
  ├─ text (症状描述)
  ├─ image_base64? (可选图片)
  └─ gps_lat/lng? (可选位置)
      │
      ▼
┌─────────────────────┐
│  FastAPI/LangServe  │
└─────────────────────┘
      │
      ▼
┌───────────────────────────────────────────────────────────┐
│                  LangGraph StateGraph                     │
│                                                           │
│  State 传入各节点 → 节点处理 → State 更新 → 下一节点       │
│                                                           │
│  ┌─────────────────────────────────────────────────┐     │
│  │ 节点示例: clinical_extractor                    │     │
│  │                                                 │     │
│  │ 输入: state = {text, visual_findings}           │     │
│  │   ↓                                             │     │
│  │ 处理: LLMService.extract_symptoms()             │     │
│  │   ↓                                             │     │
│  │ 输出: {symptom_schema: {...}}                   │     │
│  │                                                 │     │
│  │ State 更新: state.symptom_schema = {...}        │     │
│  └─────────────────────────────────────────────────┘     │
│                                                           │
└───────────────────────────────────────────────────────────┘
      │
      ▼
┌───────────────────────────────────────────────────────────┐
│                   状态更新与传递                           │
│                                                           │
│  每个节点返回的字典会合并到 TriageState:                  │
│                                                           │
│  updated_state = {**original_state, **node_result}        │
│                                                           │
│  示例:                                                    │
│  original = {"session_id": "123", "text": "手臂红疹"}     │
│  node_result = {"symptom_schema": {...}}                 │
│  updated = {                                              │
│    "session_id": "123",                                   │
│    "text": "手臂红疹",                                     │
│    "symptom_schema": {...}                                │
│  }                                                        │
│                                                           │
└───────────────────────────────────────────────────────────┘
      │
      ▼
┌───────────────────────────────────────────────────────────┐
│                   外部服务调用                             │
│                                                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  Redis       │  │  Qwen API    │  │  Amap API    │  │
│  │  会话存储     │  │  LLM调用     │  │  医院搜索     │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│                                                           │
│  ┌──────────────┐  ┌──────────────┐                     │
│  │  NCBI API    │  │  Weather API │                     │
│  │  文献检索     │  │  天气查询     │                     │
│  └──────────────┘  └──────────────┘                     │
│                                                           │
└───────────────────────────────────────────────────────────┘
      │
      ▼
┌───────────────────────────────────────────────────────────┐
│                   最终响应组装                             │
│                                                           │
│  {                                                         │
│    "status": "final",                                     │
│    "triage_level": "ROUTINE",                             │
│    "recommended_departments": ["皮肤科"],                  │
│    "navigation": {...},    # 如果提供GPS                  │
│    "evidence": [...],      # NCBI检索结果                 │
│    "response": "根据您描述的症状...",                     │
│    "disclaimer": "本建议仅供参考..."                      │
│  }                                                         │
│                                                           │
└───────────────────────────────────────────────────────────┘
      │
      ▼
   返回用户
```

### 6.2 Redis 会话存储

```python
# Redis Key 结构
Key: session:{session_id}
Value: {
  "turn_count": 1,
  "symptom_schema": {
    "body_part": "手臂",
    "symptoms": ["红疹", "痒"]
  },
  "clarify_questions": [
    "症状持续多久了？"
  ]
}
TTL: 3600 秒 (60分钟)

# 序列化示例
import json

# 保存
await redis.setex(
    f"session:{session_id}",
    3600,
    json.dumps(state, ensure_ascii=False)
)

# 读取
data = await redis.get(f"session:{session_id}")
if data:
    state = json.loads(data)
```

---

## 7. 安全机制实现

### 7.1 红旗规则引擎

```python
# src/chains/nodes/red_flag_detector.py
@safe_node("red_flag_detector")
async def red_flag_detector(state: TriageState) -> TriageState:
    """红旗规则检测

    优先级：规则引擎 > LLM判断
    """
    symptom_schema = state.get("symptom_schema", {})

    # 加载红旗规则
    rules = load_red_flag_rules()

    # 规则匹配
    red_flags_hit = []
    rule_triage_level = None

    for rule in rules:
        if match_rule(symptom_schema, rule):
            red_flags_hit.append(rule["id"])
            # 规则优先：一旦匹配到EMERGENCY，立即返回
            if rule["triage_level"] == "EMERGENCY":
                rule_triage_level = "EMERGENCY"
                break

    return {
        "red_flags_hit": red_flags_hit,
        "rule_triage_level": rule_triage_level or "ROUTINE"
    }


def match_rule(symptom_schema: Dict, rule: Dict) -> bool:
    """匹配单个规则"""
    for condition in rule["conditions"]:
        field = condition["field"]
        op = condition["op"]
        value = condition["value"]

        field_value = symptom_schema.get(field, [])

        if op == "contains_any":
            if any(v in field_value for v in value):
                return True
        elif op == "equals":
            if field_value == value:
                return True

    return False
```

### 7.2 安全过滤器

```python
# src/utils/safety_filters.py
class SafetyFilter:
    """安全过滤器

    功能：
    1. 检测禁止内容
    2. 强制限定词
    3. 过滤延迟就医建议
    """

    PROHIBITED_PATTERNS = [
        (r"确诊|诊断|你得的是|是XX病", "诊断性语言"),
        (r"每次\s*\d+\s*mg|每日\s*\d+片", "药物剂量"),
        (r"不用就医|不用看医生|肯定没事", "延迟就医")
    ]

    QUALIFIER_PATTERNS = [
        "疑似", "可能", "相关", "考虑"
    ]

    def sanitize_response(self, response: str) -> str:
        """清理响应内容"""
        # 1. 检测禁止内容
        for pattern, description in self.PROHIBITED_PATTERNS:
            if re.search(pattern, response):
                logger.warning(f"检测到{description}")
                # 替换或删除
                response = re.sub(pattern, "", response)

        # 2. 确保限定词存在
        if not any(q in response for q in self.QUALIFIER_PATTERNS):
            # 如果没有限定词，添加"疑似"
            response = response.replace("是", "疑似是")

        return response
```

### 7.3 推理验证器

```python
# src/chains/nodes/reasoning_verifier.py
@safe_node("reasoning_verifier")
async def reasoning_verifier(state: TriageState) -> TriageState:
    """推理验证节点（双重安全检查）

    1. 规则引擎检查（已在red_flag_detector完成）
    2. LLM推理验证（本节点）
    """
    llm_service = get_llm_service()

    draft_response = state.get("draft_response", "")

    # LLM安全验证
    verification = await llm_service.verify_safety(draft_response)

    if not verification["is_safe"]:
        logger.warning(f"安全验证失败: {verification['violations']}")

        # 使用清理后的内容
        sanitized = verification["sanitized_content"]
        return {
            "final_response": sanitized,
            "safety_violations": verification["violations"]
        }

    return {
        "final_response": draft_response
    }
```

---

## 8. 测试策略

### 8.1 测试金字塔

```
         /\
        /  \
       / E2E \        ← 端到端测试（少量）
      /--------\
     /  集成测试  \     ← 集成测试（适量）
    /--------------\
   /    单元测试      \   ← 单元测试（大量）
  /------------------\
```

### 8.2 单元测试

```python
# tests/unit/test_nodes/test_clinical_extractor.py
import pytest
from src.chains.nodes.clinical_extractor import clinical_extractor

@pytest.mark.asyncio
@pytest.mark.unit
async def test_clinical_extractor_success():
    """测试临床提取成功场景"""
    state = {
        "session_id": "test-123",
        "text": "手臂红疹，有点痒，持续2天"
    }

    result = await clinical_extractor(state)

    assert "symptom_schema" in result
    assert result["symptom_schema"]["body_part"] == "手臂"
    assert "红疹" in result["symptom_schema"]["symptoms"]


@pytest.mark.asyncio
@pytest.mark.unit
async def test_clinical_extractor_with_visual_findings():
    """测试带视觉发现的临床提取"""
    state = {
        "session_id": "test-123",
        "text": "手臂这样，很痒",
        "visual_findings": {
            "type": "rash",
            "summary": "手臂红斑伴丘疹",
            "features": ["红斑", "丘疹"]
        }
    }

    result = await clinical_extractor(state)

    assert result["symptom_schema"]["body_part"] == "手臂"
    assert "红疹" in result["symptom_schema"]["symptoms"] or "皮疹" in result["symptom_schema"]["symptoms"]


@pytest.mark.asyncio
@pytest.mark.unit
async def test_clinical_extractor_error_handling():
    """测试错误处理"""
    state = {
        "session_id": "test-123",
        "text": None  # 无效输入
    }

    result = await clinical_extractor(state)

    # 应该优雅降级
    assert result.get("status") == "error"
```

### 8.3 集成测试

```python
# tests/integration/test_full_workflow.py
import pytest
from src.chains.triage_chain import invoke_chain

@pytest.mark.asyncio
@pytest.mark.integration
async def test_full_workflow_text_only():
    """测试完整工作流（仅文本）"""
    result = await invoke_chain(
        session_id="integration-test-001",
        text="手臂红疹，有点痒，持续2天"
    )

    assert result["status"] == "final"
    assert result["triage_level"] in ["EMERGENCY", "URGENT", "ROUTINE", "SELF_CARE"]
    assert len(result["recommended_departments"]) > 0
    assert "disclaimer" in result


@pytest.mark.asyncio
@pytest.mark.integration
async def test_full_workflow_with_navigation():
    """测试完整工作流（含导航）"""
    result = await invoke_chain(
        session_id="integration-test-002",
        text="头痛发烧",
        gps_lat=39.9042,
        gps_lng=116.4074
    )

    assert result["status"] == "final"
    assert "navigation" in result
    assert "hospitals" in result["navigation"]
    assert len(result["navigation"]["hospitals"]) == 3
```

### 8.4 Mock 外部服务

```python
# tests/conftest.py
import pytest
from unittest.mock import AsyncMock, patch

@pytest.fixture
def mock_llm_service():
    """Mock LLM服务"""
    with patch("src.services.llm_service.get_llm_service") as mock:
        service = AsyncMock()
        service.extract_symptoms.return_value = {
            "body_part": "手臂",
            "symptoms": ["红疹"],
            "duration": "2天"
        }
        service.classify_triage.return_value = {
            "triage_level": "ROUTINE",
            "recommended_departments": ["皮肤科"]
        }
        mock.return_value = service
        yield service


@pytest.fixture
def mock_redis_service():
    """Mock Redis服务"""
    with patch("src.services.redis_service.get_redis_service") as mock:
        service = AsyncMock()
        service.get_session.return_value = None
        service.save_session.return_value = True
        service.is_healthy = True
        mock.return_value = service
        yield service


# 使用mock
@pytest.mark.asyncio
async def test_with_mock(mock_llm_service):
    """使用mock的测试"""
    result = await mock_llm_service.extract_symptoms("手臂红疹")
    assert result["body_part"] == "手臂"
```

---

## 9. 性能优化

### 9.1 性能优化清单

| 优化项 | 当前实现 | 进一步优化 |
|:------|:--------|:----------|
| **急诊路径** | 跳过NCBI | ✅ 已优化 |
| **Redis连接池** | 默认配置 | 调整连接数 |
| **LLM缓存** | 未实现 | 添加缓存层 |
| **并发处理** | 异步/await | 考虑并行节点 |
| **数据库查询** | N/A | 不适用 |
| **响应压缩** | 未实现 | 添加gzip |

### 9.2 添加LLM缓存

```python
# src/utils/cache.py
from typing import Optional, Dict, Any
import hashlib
import json

class LLMCache:
    """LLM响应缓存

    策略：
    1. 相似查询复用结果
    2. TTL: 24小时
    3. 仅缓存成功的响应
    """

    def __init__(self, redis_client):
        self.redis = redis_client
        self.ttl = 86400  # 24小时

    def _hash_input(self, input_data: Dict) -> str:
        """生成输入hash"""
        normalized = json.dumps(input_data, sort_keys=True)
        return hashlib.sha256(normalized.encode()).hexdigest()

    async def get(self, input_data: Dict) -> Optional[str]:
        """获取缓存"""
        key = f"llm_cache:{self._hash_input(input_data)}"
        cached = await self.redis.get(key)
        return cached.decode() if cached else None

    async def set(self, input_data: Dict, response: str):
        """设置缓存"""
        key = f"llm_cache:{self._hash_input(input_data)}"
        await self.redis.setex(key, self.ttl, response)


# 使用示例
async def extract_symptoms_with_cache(
    text: str,
    cache: LLMCache
) -> Dict:
    # 尝试从缓存获取
    cache_key = {"text": text, "operation": "extract_symptoms"}
    cached = await cache.get(cache_key)

    if cached:
        return json.loads(cached)

    # 缓存未命中，调用LLM
    result = await llm_service.extract_symptoms(text)

    # 保存到缓存
    await cache.set(cache_key, json.dumps(result))

    return result
```

### 9.3 性能监控

```python
# src/utils/performance.py
import time
from functools import wraps
from prometheus_client import Histogram

# 定义指标
node_duration = Histogram(
    'trinav_node_duration_seconds',
    'Node execution duration',
    ['node_name']
)

def timed(node_name: str):
    """节点计时装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start
                node_duration.labels(node_name=node_name).observe(duration)
        return wrapper
    return decorator


# 使用示例
@safe_node("clinical_extractor")
@timed("clinical_extractor")
async def clinical_extractor(state: TriageState) -> TriageState:
    ...
```

---

## 10. 故障处理

### 10.1 故障场景与处理策略

| 故障场景 | 影响 | 处理策略 |
|:--------|:-----|:---------|
| Redis连接失败 | 会话不持久 | 继续处理，降级运行 |
| LLM API超时 | 无法分诊 | 返回错误，建议重试 |
| 高德API失败 | 无导航 | 其他功能正常 |
| NCBI API失败 | 无证据 | 其他功能正常 |
| 图片处理失败 | 仅文本分析 | 继续处理 |
| 节点执行失败 | 优雅降级 | 根据已有状态决定 |

### 10.2 断路器模式

```python
# src/utils/circuit_breaker.py
from enum import Enum
import time

class CircuitState(Enum):
    CLOSED = "closed"       # 正常
    OPEN = "open"           # 熔断
    HALF_OPEN = "half_open" # 半开

class CircuitBreaker:
    """断路器实现

    状态转换：
    CLOSED → OPEN: 失败次数超过阈值
    OPEN → HALF_OPEN: 超过恢复时间
    HALF_OPEN → CLOSED: 尝试成功
    HALF_OPEN → OPEN: 尝试失败
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60
    ):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.last_failure_time = None
        self.state = CircuitState.CLOSED

    def record_failure(self):
        """记录失败"""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN

    def record_success(self):
        """记录成功"""
        self.failure_count = 0
        self.state = CircuitState.CLOSED

    def can_attempt(self) -> bool:
        """判断是否可以尝试"""
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                return True
            return False

        # HALF_OPEN
        return True


# 使用示例
llm_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=30)

async def call_llm_with_breaker(prompt: str) -> str:
    if not llm_breaker.can_attempt():
        raise Exception("LLM service is circuit-broken")

    try:
        result = await llm_service.ainvoke(prompt)
        llm_breaker.record_success()
        return result
    except Exception as e:
        llm_breaker.record_failure()
        raise
```

### 10.3 重试策略

```python
# 使用tenacity的重试策略
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

@retry(
    stop=stop_after_attempt(3),              # 最多重试3次
    wait=wait_exponential(multiplier=1, min=1, max=5),  # 指数退避
    retry=retry_if_exception_type((ConnectionError, TimeoutError))  # 重试条件
)
async def external_api_call() -> Dict:
    """带重试的外部API调用"""
    response = await http_client.get(url)
    return response.json()
```

---

## 附录

### A. 环境变量完整列表

```bash
# === Qwen API ===
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
QWEN_API_KEY=sk-xxxxx

# === Redis ===
REDIS_URL=redis://localhost:6379
REDIS_SESSION_TTL=3600

# === 高德地图 ===
AMAP_API_KEY=xxxxx
AMAP_SEARCH_RADIUS=10000

# === NCBI ===
NCBI_BASE_URL=https://eutils.ncbi.nlm.nih.gov/entrez/eutils
NCBI_API_DELAY=0.5

# === 天气 ===
WEATHER_API_URL=https://api.open-meteo.com/v1/forecast

# === 服务器 ===
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
SERVER_DEBUG=false
LOG_LEVEL=INFO
TRINAV_LOG_FILE=logs/trinav.log

# === 可观测性 ===
LANGCHAIN_TRACING_V2=false
LANGCHAIN_API_KEY=xxxxx
LANGCHAIN_PROJECT=trinav-dev

# === 约束 ===
MAX_TEXT_LENGTH=2000
MAX_CLARIFICATION_ROUNDS=2
MAX_CLARIFICATION_QUESTIONS=3
```

### B. 常用命令

```bash
# 开发
python -m src.server                    # 启动服务
pytest -v                               # 运行测试
black src/ tests/                       # 格式化代码
ruff check src/ tests/                  # 检查代码

# 前端
cd frontend                             # 进入前端目录
npm install                             # 安装依赖
npm run dev                             # 启动前端

# 日志
tail -f logs/trinav.log                 # 追踪日志

# Redis (本地或 Docker)
redis-server                            # 本地启动
# or: docker run --name trinav-redis -p 6379:6379 redis:7-alpine
redis-cli ping                          # 检查连接
redis-cli keys "session:*"              # 查看会话
redis-cli del "session:xxx"             # 删除会话
```

### C. 有用的链接

- [LangChain文档](https://python.langchain.com/)
- [LangGraph文档](https://langchain-ai.github.io/langgraph/)
- [Qwen API文档](https://help.aliyun.com/zh/dashscope/)
- [Pydantic V2文档](https://docs.pydantic.dev/)

---

**文档版本**: 1.1.0
**最后更新**: 2026-01-12
**维护者**: TriNav 开发团队
