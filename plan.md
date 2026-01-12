# TriNav 医院推荐问题修复计划（可执行版）

## 目标
1) 以前端为入口，严格对齐 LangServe 权威契约（`{input}/{output}` 包裹、`disclaimer` 独立字段、`weather_alert` 新结构）。  
2) 用户请求医院但未定位时，明确引导定位，并保证 `session_id` 连续性。  
3) 后端识别“医院推荐”意图并复用上一轮分诊，避免误判为居家观察，同时保持安全链路。  

## 范围
- 前端：`frontend/src/lib/api.ts`、`frontend/src/lib/types.ts`、`frontend/src/components/triage/TriageCard.tsx`、`frontend/src/App.tsx`  
- 后端：`src/chains/graph/triage_graph.py`、`src/chains/nodes/session_loader.py`、`src/chains/nodes/session_saver.py`、`src/chains/nodes/navigator.py`、新增意图检测节点  
- 测试：`tests/` 相关用例或新增用例  

## 计划（按 1/2/3）

### 1) 权威契约对齐（前端字段映射 + 展示）
1.1 明确 LangServe 权威结构  
- 约束：请求必须 `{ "input": { ... } }`，响应必须 `{ "output": { ... } }`。  
- `disclaimer` 独立字段，不应拼接进 `response`。  
- `weather_alert` 使用新结构：`condition/temp_c/humidity/wind_speed_kmh/tip`。  

1.2 修正前端响应转换逻辑  
- 文件：`frontend/src/lib/api.ts`  
- 动作：  
  - 以 `apiResponse.output ?? apiResponse` 作为统一解析入口。  
  - `navigation` 仅以 `output.navigation` 为主，保留 `navigation_result` 为向后兼容。  
  - `disclaimer` 单独读取并渲染，不再依赖 `response` 文本拼接。  

1.3 调整前端类型定义  
- 文件：`frontend/src/lib/types.ts`  
- 动作：  
  - `WeatherAlert` 以新结构为主字段；旧字段仅保留为兼容（若仍需）。  
  - 明确 `disclaimer?: string`。  

1.4 调整 UI 展示逻辑  
- 文件：`frontend/src/components/triage/TriageCard.tsx`  
- 动作：  
  - 优先展示 `weather_alert.condition/temp_c/humidity/wind_speed_kmh/tip`。  
  - 避免空值占位（如 “气温: °C”）。  
  - `disclaimer` 使用独立区域展示。  

1.5 验收  
- 条件：LangServe 响应为 `{output}` 时，UI 正确展示 `response/triage/navigation/weather/disclaimer`，无空字段占位。  

### 2) 前端定位引导（并保证会话连续性）
2.1 增加“医院请求”关键词检测（含负向规则）  
- 文件：`frontend/src/App.tsx`  
- 动作：  
  - 正向关键词：`医院/就医/导航/推荐医院/挂号/急诊`。  
  - 负向关键词：`不去医院/不想去医院/无需就医`，命中则不触发定位引导。  

2.2 无定位时的引导行为  
- 文件：`frontend/src/App.tsx`  
- 动作：  
  - 若命中医院请求且 `gpsLocation` 为空：  
    - 直接插入助手提示：“需要定位才能推荐医院，请先获取位置”。  
    - 不发起后端请求，避免误判路径。  

2.3 维持 `session_id` 连续性  
- 文件：`frontend/src/lib/api.ts` 或 `frontend/src/App.tsx`  
- 动作：  
  - 会话初始化后保存 `session_id` 并在后续请求复用。  
  - 确保“推荐医院”场景仍使用同一 `session_id`，以复用分诊。  

2.4 定位成功后的行为  
- 方案 A：提示“已获取位置，请重新发送医院请求”。  
- 方案 B：保存上一条医院请求，定位完成后自动重发（产品允许时）。  

2.5 验收  
- 无定位时请求医院：明确引导定位，不误触发居家观察。  
- 定位后复发请求：返回医院卡片与路线/天气提示。  

### 3) 后端“医院推荐”意图复用分诊
3.1 新增意图检测节点  
- 文件：新增 `src/chains/nodes/navigation_intent_detector.py`  
- 动作：  
  - 规则：医院关键词 + 短句 + 不含典型症状描述。  
  - 输出：`navigation_only: bool`。  

3.2 扩展 session_saver / session_loader  
- 文件：`src/chains/nodes/session_saver.py`、`src/chains/nodes/session_loader.py`  
- 动作：  
  - 保存并读取：`triage_level/triage_reason/recommended_departments/possible_causes/self_care_tips/red_flags/case_domain`。  
  - 确保复用路径具备完整分诊上下文。  

3.3 更新工作流分支（保留安全链路）  
- 文件：`src/chains/graph/triage_graph.py`  
- 动作：  
  - 在 `session_loader` 后增加意图检测节点。  
  - 若 `navigation_only=True` 且已加载历史分诊：  
    - 跳过 `clinical_extractor/triage_classifier`。  
    - 显式设置 `should_retrieve_evidence=False`。  
    - 直接进入 `navigator -> weather_fetcher -> reasoning_verifier -> final_status_router`。  
  - 若无历史分诊：返回 `need_more_info`，提示补充症状。  

3.4 SELF_CARE 处理策略（需明确决策）  
- 方案 A：仍允许导航，但在 `response` 中明确“无需就医，仅在坚持就医时提供就近医院”。  
- 方案 B：不返回导航，直接提示补充症状或居家护理建议。  

3.5 验收  
- 场景 1：有历史分诊 + GPS + “请给出推荐医院” → `navigation` 非空。  
- 场景 2：无历史分诊 + “请给出推荐医院” → `need_more_info`。  
- 场景 3：历史分诊为 `SELF_CARE` → 与 3.4 选择一致。  

## 测试与回归
- 新增/更新测试：  
  - LangServe `{input}/{output}` 包裹 + `disclaimer` 独立字段。  
  - `navigation_only` 分支复用分诊（含 GPS/无 GPS）。  
  - 前端定位引导逻辑（关键词 + 负向关键词）。  
  - `weather_alert` 新结构展示与空值处理。  

## 输出物
- 完整对齐 LangServe 的前端字段映射与 UI 展示  
- 前端定位引导与会话复用逻辑  
- 后端意图复用分诊与稳定导航输出  
- 对应测试与回归验证  

## 回归验证
1) 首次症状输入 → 正常分诊 + 提示定位  
2) 用户请求推荐医院 → 引导定位 → 返回医院卡片  
3) 第二轮仅说“推荐医院” → 复用上一轮分诊（同 `session_id`）

## 测试覆盖缺口计划（按文件）
说明：
- 覆盖数据来源：/tmp/coverage.json（由 `pytest --cov=src --cov-report=html` 生成）
- 当前未启用分支覆盖（未使用 `--cov-branch`），因此“缺失分支”统一为 n/a；如需分支覆盖请重新生成报告

### src/chains/graph/triage_graph.py
- 缺失行：107-108, 113, 256
- 缺失分支：n/a（未启用分支覆盖）
- 用例建议：
  - triage_level 为 `SELF_CARE` 或 `None` 时 `_should_skip_navigation` 返回 True
  - status="error" 时 `_has_error` 返回 True
  - `get_graph_mermaid()` 返回包含 `graph TD` 与关键节点名的字符串

### src/chains/nodes/base.py
- 缺失行：60, 78, 83
- 缺失分支：n/a（未启用分支覆盖）
- 用例建议：
  - `raise_on_error=True` 且被包裹函数抛 ValueError 时继续抛出
  - `raise_on_error=True` 且抛 Exception 时继续抛出
  - `triage_level="EMERGENCY"` 且异常触发时返回 `status="final"` 且 `error_message=None`

### src/chains/nodes/clarification_generator.py
- 缺失行：49
- 缺失分支：n/a（未启用分支覆盖）
- 用例建议：
  - `symptom_schema=None` 且非紧急时返回默认问题并设置 `need_clarify=True`

### src/chains/nodes/clinical_extractor.py
- 缺失行：27
- 缺失分支：n/a（未启用分支覆盖）
- 用例建议：
  - `text` 与 `visual_findings` 皆为空时触发 ValueError（safe_node 返回 error 状态）

### src/chains/nodes/domain_classifier.py
- 缺失行：69, 71, 75
- 缺失分支：n/a（未启用分支覆盖）
- 用例建议：
  - `llm_service.classify_domain` 抛异常时返回 `case_domain=None`

### src/chains/nodes/image_quality_gate.py
- 缺失行：53, 80, 84, 87, 91, 105-107
- 缺失分支：n/a（未启用分支覆盖）
- 用例建议：
  - 包含 data URL 前缀的 base64 输入触发前缀剥离分支
  - 图像尺寸过小/过大触发维度告警分支
  - `Image.open` 抛异常时走通用异常分支

### src/chains/nodes/input_validator.py
- 缺失行：43-44, 49-50, 62, 68, 72, 78
- 缺失分支：n/a（未启用分支覆盖）
- 用例建议：
  - `session_id` 为空时生成新 UUID
  - 非法 UUID 触发格式校验异常
  - 纯空白文本触发 “文本内容不能为空”
  - data URL 前缀/非法 base64/超限尺寸各触发对应异常

### src/chains/nodes/navigator.py
- 缺失行：89, 93
- 缺失分支：n/a（未启用分支覆盖）
- 用例建议：
  - `amap_service.search_hospitals` 返回空列表时返回 `navigation_result=None`

### src/chains/nodes/ncbi_query_builder.py
- 缺失行：92
- 缺失分支：n/a（未启用分支覆盖）
- 用例建议：
  - `symptoms=[""]` 且 `body_part=""` 时 `query_terms` 为空并返回空字符串

### src/chains/nodes/reasoning_verifier.py
- 缺失行：47
- 缺失分支：n/a（未启用分支覆盖）
- 用例建议：
  - 触发违规且 `verify_safety` 返回 `is_safe=True` 时使用 `sanitized_content`

### src/chains/nodes/red_flag_detector.py
- 缺失行：23-25, 50, 65-68, 70-71, 100-101
- 缺失分支：n/a（未启用分支覆盖）
- 用例建议：
  - 规则文件读取失败时 `_load_red_flag_rules` 返回空列表
  - `_matches_rule` 遇到缺失字段返回 False
  - `contains_all` 在 list 与 str 两条路径都覆盖失败分支
  - `rules` 为空时返回空结果并记录告警

### src/chains/nodes/response_composer.py
- 缺失行：39
- 缺失分支：n/a（未启用分支覆盖）
- 用例建议：
  - `triage_level="URGENT"` 时包含“⏰ 尽快就医”

### src/chains/nodes/session_saver.py
- 缺失行：26-27
- 缺失分支：n/a（未启用分支覆盖）
- 用例建议：
  - `session_id` 缺失时跳过保存并返回空字典

### src/chains/nodes/weather_fetcher.py
- 缺失行：54, 58, 75, 79
- 缺失分支：n/a（未启用分支覆盖）
- 用例建议：
  - Redis 命中缓存时直接返回缓存天气数据
  - 天气服务返回 None 时返回 `weather_alert=None`

### src/config/settings.py
- 缺失行：68, 77
- 缺失分支：n/a（未启用分支覆盖）
- 用例建议：
  - `QWEN_API_KEY` 为空或以 `your_` 开头触发校验异常
  - `log_level` 非法值触发校验异常

### src/models/__init__.py
- 缺失行：2-8, 10
- 缺失分支：n/a（未启用分支覆盖）
- 用例建议：
  - 直接 `import src.models` 或从包内导入任一模型以覆盖 `__all__`

### src/models/evidence.py
- 缺失行：2-3, 6, 10, 13-16, 23, 25-26
- 缺失分支：n/a（未启用分支覆盖）
- 用例建议：
  - 构造合法 Evidence（year=4位数字）
  - year 非 4 位、type 非枚举值、title 超长分别触发校验错误

### src/models/navigation_result.py
- 缺失行：2-3, 6, 9-10, 14-15, 22-23, 33, 36-43, 50-51, 65, 69, 77, 84-86, 88-90, 92-94, 96-99, 102, 107-108
- 缺失分支：n/a（未启用分支覆盖）
- 用例建议：
  - hospitals 数量≠3 时触发 `exactly_three_hospitals`
  - rank 序列非 1/2/3 时触发 `ranked_correctly`
  - route_plan 字段非法（mode/eta/summary）触发校验

### src/models/red_flag_rule.py
- 缺失行：2-3, 6, 9, 13, 17, 20, 24, 29, 33, 36, 43, 47, 53, 59-61, 63-65, 67-68
- 缺失分支：n/a（未启用分支覆盖）
- 用例建议：
  - `id` 不以 `RF_` 开头触发校验异常
  - `conditions` 为空或 `op` 非允许值触发校验

### src/models/session.py
- 缺失行：2-4, 7, 11, 14, 20, 26, 30, 34, 39, 46, 50, 55-57, 59-61, 63-64
- 缺失分支：n/a（未启用分支覆盖）
- 用例建议：
  - `turn_count>2` 触发校验异常
  - `triage_level`/`case_domain` 不匹配正则触发校验

### src/models/symptom_schema.py
- 缺失行：2-3, 6, 9, 14, 20, 24, 31-32, 42, 46, 52, 60, 65, 70, 74, 81, 86-87
- 缺失分支：n/a（未启用分支覆盖）
- 用例建议：
  - `VisualFindings.type` 非法值触发校验异常
  - `severity`/`onset` 非允许值触发校验

### src/models/triage_assessment.py
- 缺失行：2-3, 6, 10, 14, 20, 26, 34, 41-43, 45-48, 51, 58-60, 62-66, 69, 77, 82-83
- 缺失分支：n/a（未启用分支覆盖）
- 用例建议：
  - `possible_causes` 不含“疑似/可能/相关”触发校验
  - `self_care_tips` 含用药/剂量词触发校验

### src/models/weather_alert.py
- 缺失行：2, 5, 8, 14, 18, 24, 29, 36-37
- 缺失分支：n/a（未启用分支覆盖）
- 用例建议：
  - `humidity` 越界或 `tip` 为空触发校验异常

### src/server.py
- 缺失行：6, 8-11, 13-16, 19-20, 23-24, 26, 29-30, 33-37, 39-43, 46-52, 54, 56, 60, 68, 78, 87-88, 90, 92-93, 95, 101-102, 104, 116, 118, 127-128
- 缺失分支：n/a（未启用分支覆盖）
- 用例建议：
  - `/health` 在 Redis healthy/unhealthy 下返回 `status` 与 `redis` 字段正确
  - `/` 根路由返回 endpoints 与 version 字段
  - lifespan 中 Redis/LLM 初始化异常时指标与日志路径覆盖

### src/services/amap_service.py
- 缺失行：46-47, 64-66, 68-72, 74-78, 80-84, 117-118, 169, 174, 199-201, 243-244, 249, 289, 301-303, 313-315, 320
- 缺失分支：n/a（未启用分支覆盖）
- 用例建议：
  - API key 为空时 `_make_request` 返回 None
  - API status!=1 或 timeout/HTTPError/Exception 时返回 None 并标记不健康
  - `search_hospitals` 结果缺失 `pois` 时返回空列表
  - `_parse_hospital` 缺少 name/非法 location 或 ValueError 路径
  - `_generate_ranking_reason` 覆盖距离<5km 与 “综合/总医院” 关键词
  - `get_route` 无 paths 返回 None，长时长走小时文案分支，解析异常返回 None
  - `is_healthy` 在无 key 时为 False

### src/services/llm_service.py
- 缺失行：74-77, 107-110, 156, 175-176, 178, 187-189, 260-261, 263, 272-274, 334-335, 337, 343-344, 346, 419-420, 422, 429-431, 485-486, 488-490, 546-548, 550-552, 557
- 缺失分支：n/a（未启用分支覆盖）
- 用例建议：
  - `ChatOpenAI` 构造抛异常触发 `_setup_models` 失败路径
  - `ainvoke` 抛异常触发 `_invoke_with_retry` 错误路径
  - `extract_symptoms/verify_safety/extract_visual_features/generate_clarification_questions` JSON 解析失败回退
  - `classify_triage` JSON 解析失败回退与异常抛出路径
  - `classify_domain` 返回非法值或抛异常时回退为 `other`
  - `is_healthy` 属性返回值覆盖

### src/services/ncbi_service.py
- 缺失行：65-69, 71-75, 77-81, 125-127, 142, 153-154, 162, 173-175, 194, 205, 207-209, 222-224, 251, 263, 272, 292, 298, 322
- 缺失分支：n/a（未启用分支覆盖）
- 用例建议：
  - `_make_request` 的 timeout/HTTPError/Exception 路径
  - `search_pubmed` 返回结构缺失 `esearchresult` 时返回空列表
  - `fetch_article_details` 空 pmid_list 或 result 缺失时返回空列表
  - `_parse_article` 无 title 返回 None；authors fallback 路径需补测（当前 `authists` 拼写错误会抛异常）
  - `_classify_article_type` 覆盖 SystematicReview/RCT/Other 分支
  - `search_and_retrieve` 无 pmids 或无 articles 时返回空列表
  - `is_healthy` 属性返回值覆盖

### src/services/redis_service.py
- 缺失行：52-55, 76-77, 103-106, 118-119, 133-139, 151, 159-161, 182, 190-192, 204, 215-220, 251-253
- 缺失分支：n/a（未启用分支覆盖）
- 用例建议：
  - `connect/save_session/load_session/delete_session/cache_external_result/load_cached_result` 的 RedisError 分支
  - `load_session/load_cached_result` JSONDecodeError 分支
  - `close_redis_service` 关闭连接并清空全局实例

### src/services/weather_service.py
- 缺失行：6-11, 13, 15, 18, 27, 30-33, 35-36, 38, 40, 44, 57-59, 61-63, 65, 68-69, 72, 77-80, 83-86, 89-90, 93-97, 99-101, 103-107, 109-116, 118-122, 124, 139, 141, 143-144, 146, 148, 150-151, 156, 158-160, 162, 186, 188-191, 194-199, 202, 205-206, 209-212, 215-216, 218, 221, 228, 233-235, 237, 255, 258-259, 262-264, 267-272, 275-276, 279-280, 283-284, 287-288, 291, 293-294, 296, 300, 303, 311-312, 314
- 缺失分支：n/a（未启用分支覆盖）
- 用例建议：
  - API URL/API key 缺失与返回码 401/403 的错误路径
  - Timeout/HTTPStatusError(403)/通用异常分支
  - 解析响应缺少 `now` 或字段类型异常的回退路径
  - `_generate_travel_tips` 覆盖雨雪/温度/风/湿度/雾霾与默认提示
  - `is_healthy` 与 `get_weather_service` 单例路径覆盖

### src/services/weather_service_openmeteo.py
- 缺失行：106-110, 112-116, 118-122, 155-157, 188-189, 220-222, 233-248, 250, 262, 264, 269-284, 286, 314-315, 319, 323, 327, 335, 347
- 缺失分支：n/a（未启用分支覆盖）
- 用例建议：
  - `_make_request` 的 timeout/HTTPStatusError/Exception 分支
  - `_parse_weather_response` 缺失 current 或解析异常分支
  - `_get_wind_direction` 边界度数（22.5/67.5/112.5/...）分支
  - `_get_beaufort_scale` 风速边界分段
  - `_generate_travel_tips` 雨雪/温度/风/湿度/雾霾与默认分支
  - `is_healthy` 与 `get_openmeteo_service` 单例路径覆盖

### src/utils/logging_config.py
- 缺失行：17, 19-21, 34-35, 38, 41-43, 47-48, 50, 80
- 缺失分支：n/a（未启用分支覆盖）
- 用例建议：
  - `set_correlation_id` 后 JSONFormatter 能写入 `correlation_id`
  - `setup_logging` 重置 handlers 并绑定 JSONFormatter
  - `get_correlation_id` 未设置时返回空字符串

### src/utils/metrics.py
- 缺失行：76-77, 107, 116, 125, 134, 143
- 缺失分支：n/a（未启用分支覆盖）
- 用例建议：
  - `record_request` 与 `record_triage_decision` 增加计数
  - `update_active_sessions`/`update_queue_depth` 设置 gauge
  - `get_metrics` 返回包含关键指标名的字节串
  - `get_content_type` 返回 `CONTENT_TYPE_LATEST`

### src/utils/safety_filters.py
- 缺失行：102-103, 106-107, 121, 123-124, 129
- 缺失分支：n/a（未启用分支覆盖）
- 用例建议：
  - 含用药/延误就医文本触发对应 violations
  - `sanitize_response` 在无违规与有违规两条路径

### src/utils/telemetry.py
- 缺失行：26-28, 30, 32, 37, 40-42, 45, 47-48, 50-52, 61
- 缺失分支：n/a（未启用分支覆盖）
- 用例建议：
  - `setup_telemetry` 未配置 endpoint 时返回 None
  - mock OTLPSpanExporter 正常返回 tracer
  - OTLPSpanExporter 抛异常时走失败分支并返回 None
  - `get_tracer` 返回 tracer 实例
