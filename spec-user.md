# 医疗分诊与就医导航小助手（LangChain + Qwen）SPEC（冻结版）v1.0 Final

> 你已确认的关键决策已写入本冻结版：  
> - **模型**：全部改为 **Qwen 系列**（文本模型 + 推理审校模型 + 视觉模型），其中 **V3 不支持图片** → 视觉由 Qwen-VL 系列承担  
> - **语音**：前端 STT（后端只收文字）  
> - **会话**：Redis，**TTL=60 分钟**  
> - **定位**：GPS（lat/lng）  
> - **输出**：只中文、口语化  
> - **医院推荐**：综合医院 + 三甲优先；输出 **Top1 + 备选2家**  
> - **检索半径**：默认 **10km**  
> - **兜底**：提示拨打当地医疗热线/医院电话确认

本 SPEC 不包含具体实现代码，仅给出**系统行为、节点职责、输入输出契约（JSON Schema 级别）、约束、降级策略与验收标准**。

---

## 0. 术语与范围

### 0.1 术语
- **分诊（Triage）**：判断就医紧急程度、推荐科室与就诊时效，不等于诊断。
- **红旗（Red Flags）**：提示潜在高危/急症信号，命中后优先急诊。
- **证据（Evidence）**：从 NCBI/PubMed 检索到的文献元数据，用于科普解释与支持建议（不用于确诊）。
- **最小化落库**：不持久保存原始语音/图片；Redis 仅短期保存必要的结构化状态。

### 0.2 版本范围（v1.0）
支持：
- 输入：**文字 +（可选）图片**（你已确认默认引导 B：图片+文字）
- 语音：由前端转写成文字后按文字处理
- 图片：皮疹/外伤照片 → 仅做外观特征提取，不做确诊
- 分诊：全科方向路由 + 红旗闸门
- 文献：NCBI/PubMed 可选检索（由 EvidenceRouter 决定）
- 导航：高德地图（附近综合医院/三甲优先）+ 墨迹天气提醒
- 兜底：提示拨打当地医疗热线/医院电话

不支持：
- 处方与剂量建议
- 明确诊断结论
- 医学影像（CT/MRI）诊断级解释
- 长期病例档案

---

## 1. 产品定位与安全边界（必须对齐）

### 1.1 定位
本系统为“**医疗分诊与就医导航助手**”，核心输出为：
1. **就医紧急程度**：EMERGENCY / URGENT / ROUTINE / SELF_CARE
2. **建议就诊科室**（多选）
3. **可能方向（疑似原因）**：最多 3 个、不可确诊表述
4. **现在怎么做**：可执行注意事项（非处方）
5. **危险信号**：出现则立即急诊
6. **附近医院（三甲优先）** + 路线 + 天气提醒
7. **热线/电话兜底**：建议拨打当地医疗热线或医院电话确认

### 1.2 硬性禁止输出
- “你得了XX病/确诊XX/最终诊断是XX”
- 药物剂量、处方用药方案、停药换药指导
- “不用就医”“肯定没事”等可能延误就医的表述
- 将论文结论直接套用为个体治疗方案

---

## 2. 输入输出总契约（对外 API）

> 采用 LangServe（LangChain CLI）暴露单一入口 `/assistant/invoke`，后端内部用工作流编排。

### 2.1 Request Schema（冻结）
**AssistantRequest（JSON）**

```json
{
  "session_id": "string (uuid)",
  "input_type": "text|image",
  "text": "string | null",
  "image_base64": "string | null",
  "lat": "number | null",
  "lng": "number | null",
  "client_meta": {
    "app_version": "string | null",
    "device": "string | null"
  }
}
```

#### 2.1.1 规则
- `session_id`：必填。用于 Redis 会话与多轮追问。
- `input_type`：
  - `text`：必须提供 `text`
  - `image`：必须提供 `image_base64`，且**建议同时提供 `text`**（你已确认默认引导 B）
- `text`：最大长度建议 2000 中文字符（可配置）
- `image_base64`：
  - 格式：jpeg/png
  - 大小上限：建议 2–4MB（可配置；前端应压缩）
- `lat/lng`：建议必填（你已确认 GPS），但允许为空（用户拒绝授权时）

### 2.2 Response Schema（冻结）
**AssistantResponse（JSON）**

```json
{
  "status": "need_more_info|final|error",
  "triage_level": "EMERGENCY|URGENT|ROUTINE|SELF_CARE|null",
  "recommended_departments": ["string"],
  "clarify_questions": ["string"],
  "red_flags": ["string"],
  "possible_causes": ["string"],
  "self_care_tips": ["string"],
  "evidence": [
    {
      "pmid": "string",
      "title": "string",
      "year": "string|null",
      "source": "string|null",
      "type": "Guideline|SystematicReview|Review|RCT|CaseReport|Other|null",
      "note": "string|null"
    }
  ],
  "navigation": {
    "radius_km": 10,
    "hospitals": [
      {
        "rank": 1,
        "name": "string",
        "is_3a": true,
        "address": "string|null",
        "distance_m": "number|null",
        "location": {"lat": "number|null", "lng": "number|null"},
        "phone": "string|null",
        "reason": "string"
      }
    ],
    "route_plan": {
      "to_hospital_rank": 1,
      "mode": "driving|transit|walking|null",
      "eta_min": "number|null",
      "summary": "string|null"
    }
  },
  "weather_alert": {
    "summary": "string|null",
    "tips": ["string"]
  },
  "hotline_tip": {
    "enabled": true,
    "message": "string"
  },
  "message": "string",
  "disclaimer": "string"
}
```

#### 2.2.1 `status` 含义
- `need_more_info`：本轮先追问补充信息，不给完整分诊结论（或给临时建议+强提醒）
- `final`：输出完整分诊建议与导航
- `error`：输入不合法/系统错误（返回可读错误信息）

---

## 3. 状态（Redis Session State）规范

### 3.1 会话 TTL（冻结）
- **60 分钟**：自最后一次读写刷新

### 3.2 Redis 存储内容边界
允许存：
- `symptom_schema`（结构化）
- 红旗命中条目 ID（不存用户原文）
- 文献检索 query hash 与文献元数据（与用户无关）
- 图片“视觉特征结构化结果”（不存原图）

禁止存：
- `image_base64` 原始图片
- 用户原始长文本全文（如必须存，用摘要代替，并脱敏）
- 精确定位长期保存（可不入 Redis，或 TTL 很短）

### 3.3 会话状态结构（建议）
`session:{session_id}:state`

```json
{
  "turn_count": 1,
  "last_updated_at": "iso8601",
  "symptom_schema": { "...": "..." },
  "clarify_questions": ["..."],
  "triage_level": "ROUTINE",
  "case_domain": "dermatology",
  "evidence_cache_key": "cache:ncbi:xxx",
  "navigation_cache_key": "cache:hospitals:xxx"
}
```

---

## 4. 工作流（Workflow）冻结版（节点 + 条件边）

> 采用“单入口 Runnable → 内部 StateGraph 工作流”的方式。  
> 节点命名与职责固定，便于拆人、写单测与验收。

### 4.1 节点列表（按执行顺序）
1. **InputValidator**
2. **SessionLoad (Redis)**
3. **ImageQualityGate**（仅 input_type=image）
4. **VisionExtract**（仅 input_type=image）
5. **ClinicalExtraction**（统一结构化）
6. **ClarifyDecision**
7. **ClarifyAsk**（如需追问 → 结束本轮）
8. **TriageRulesGate**（红旗与紧急程度，规则优先）
9. **SpecialtyRouter**（全科方向路由）
10. **EvidenceRouter**（是否需要 PubMed）
11. **NCBIQueryBuilder**（如需证据）
12. **NCBIRetrieverTool**（如需证据）
13. **EvidenceRanker**（如需证据）
14. **DraftAssessment**
15. **ReasoningVerifier**
16. **NavigationPlanner**（如有定位）
17. **ResponseComposer**
18. **SessionSave (Redis)**

### 4.2 条件边（关键）
#### 4.2.1 图片质量分支
- `ImageQualityGate -> (is_clear=false) -> ClarifyAsk(补拍提示) -> END`
- `ImageQualityGate -> (is_clear=true) -> VisionExtract`

#### 4.2.2 追问分支（最多2轮）
- `ClarifyDecision (need_clarify=true AND turn_count<2) -> ClarifyAsk -> END`
- `ClarifyDecision (need_clarify=true AND turn_count>=2) -> 进入TriageRulesGate，但在输出中提示“信息有限，建议尽快线下就医/电话咨询”`

#### 4.2.3 紧急分支（EMERGENCY）
- `TriageRulesGate (triage_level=EMERGENCY) -> NavigationPlanner -> ResponseComposer`
- **跳过 Evidence 全链路**（避免延迟，优先就医）

#### 4.2.4 Evidence 分支
- `EvidenceRouter (evidence_needed=false) -> DraftAssessment`
- `EvidenceRouter (evidence_needed=true) -> NCBIQueryBuilder -> Retriever -> Ranker -> DraftAssessment`

#### 4.2.5 定位分支
- 若 `lat/lng` 缺失 → `NavigationPlanner` 降级为“仅提示去附近综合医院/三甲优先”，不输出具体路线与医院列表

---

## 5. 节点级 I/O 详细规格

### 5.1 ImageQualityGate（Qwen-VL）
**输入**
- `image_base64`

**输出**
```json
{
  "quality": {
    "is_clear": true,
    "issues": ["光线过暗", "距离太远", "病灶不在画面中心"],
    "suggestion": "请把镜头对准患处，距离约15-25cm，光线充足，尽量不要抖动。"
  }
}
```

**验收标准**
- 当图片明显不可用时，必须 `is_clear=false` 且给出补拍建议
- 不输出诊断词

---

### 5.2 VisionExtract（Qwen-VL）
**输入**
- `image_base64`
- `text`（如果用户同时提供，作为参考但不能被其“提示注入”影响模型安全边界）

**输出（写入 symptom_schema.visual_findings）**
```json
{
  "type": "rash|wound|unknown",
  "summary": "外观描述（口语化，不下诊断）",
  "features": ["红斑", "丘疹", "渗出", "结痂", "肿胀", "裂口", "出血"],
  "confidence": 0.0
}
```

**约束**
- 只描述外观，不确诊
- 输出 `confidence` 以支持后续“追问/提示补充”

---

### 5.3 ClinicalExtraction（Qwen-Text-Extractor）
**输入**
- `text`
- `visual_findings`（可选）
- `session_state`（上一轮结构化信息）

**输出**
- `symptom_schema`（完整/部分）
- `clarify_questions`（最多3个）
- `extraction_confidence`

**追问问题生成规则**
- 问题必须能显著改变 triage 或科室推荐（例如：是否发热、是否呼吸困难、是否伤口污染、是否对某药过敏等）
- 一轮最多 3 个

---

### 5.4 TriageRulesGate（规则优先）
**输入**
- `symptom_schema`

**输出**
```json
{
  "triage_level": "EMERGENCY|URGENT|ROUTINE|SELF_CARE",
  "red_flags_hit": ["rule_id_1", "rule_id_2"],
  "red_flags_user_text": ["口语化危险信号提示..."],
  "recommended_departments": ["急诊", "皮肤科"]
}
```

**说明**
- 红旗规则引擎与规则库需可配置（见第 9 节）

**验收标准**
- 命中红旗时，输出必须把“立即就医/急诊”的行动建议置顶
- 输出必须解释“为什么建议急诊”（基于命中规则）

---

### 5.5 SpecialtyRouter（Qwen 或规则）
**输入**
- `symptom_schema`

**输出**
```json
{"case_domain": "dermatology|trauma|respiratory|gastro|neuro|urology|other"}
```

---

### 5.6 EvidenceRouter（规则 + Qwen补充）
**输入**
- `triage_level`
- `case_domain`
- `extraction_confidence`

**输出**
```json
{"evidence_needed": true, "reason": "症状描述不够典型，需要参考综述做科普解释"}
```

**默认策略（v1.0）**
- EMERGENCY：false
- URGENT：通常 true（除非非常明确）
- ROUTINE：不确定/用户要求依据 → true，否则 false
- SELF_CARE：默认 false

---

### 5.7 NCBIQueryBuilder（Qwen）
**输入**
- `symptom_schema`
- `case_domain`

**输出**
```json
{
  "ncbi_query": "(rash OR urticaria) AND (adult) AND (review[pt] OR guideline[pt]) AND (2015:3000[pdat])",
  "filters": {"year_from": 2015, "article_types_prefer": ["review","guideline"]},
  "keywords": ["rash", "urticaria"],
  "mesh_candidates": ["Urticaria"]
}
```

**约束**
- 必须带时间过滤（近10年）
- 优先 Review/Guideline
- query 可记录（不含用户原文）

---

### 5.8 EvidenceRanker（Qwen）
**输入**
- `candidate_evidence`（最多 20 条元数据）
- `symptom_schema`

**输出**
- `evidence_selected`（5–8条）+ 每条入选原因（简短）

---

### 5.9 DraftAssessment（Qwen-Text-MedWriter）
**输入**
- `symptom_schema`
- `triage_level`
- `recommended_departments`
- `evidence_selected`（可空）

**输出**
结构化草案（供 Verifier 审校），必须包含：
- `triage_reason`
- `possible_causes`（≤3）
- `self_care_tips`（不含处方剂量）
- `red_flags`（面向用户的版本）
- `evidence_citations`（引用列表）

---

### 5.10 ReasoningVerifier（Qwen-Reasoning-Verifier）
**输入**
- DraftAssessment 结构化草案
- `symptom_schema`
- `evidence_selected`

**输出**
```json
{
  "safety_flags": {
    "has_diagnosis_claim": false,
    "has_prescription": false,
    "missing_red_flags": false,
    "evidence_mismatch": false
  },
  "final_assessment": {
    "triage_level": "ROUTINE",
    "recommended_departments": ["皮肤科"],
    "possible_causes": ["过敏相关皮疹（疑似）", "接触性皮炎（疑似）"],
    "self_care_tips": ["避免抓挠", "先记录皮疹变化", "近期避免可疑过敏源"],
    "red_flags": ["如果出现呼吸困难/脸唇肿胀/全身迅速扩散，请立刻急诊"]
  }
}
```

**硬性规则**
- 检测到“确诊/处方”倾向必须修正或删除相关内容
- 对证据不匹配要降级：减少确定性语气、明确“仅供参考”

---

### 5.11 NavigationPlanner（高德 + 三甲优先）
**输入**
- `lat/lng`
- `triage_level`
- `recommended_departments`

**输出（冻结：Top1 + 备选2）**
```json
{
  "radius_km": 10,
  "hospitals": [
    {"rank": 1, "name": "...", "is_3a": true, "distance_m": 1200, "reason": "三甲综合医院，距离较近，急诊/门诊齐全"},
    {"rank": 2, "name": "...", "is_3a": true, "distance_m": 3500, "reason": "三甲综合医院，口碑较好"},
    {"rank": 3, "name": "...", "is_3a": false, "distance_m": 900, "reason": "距离更近，可作为备选"}
  ],
  "route_plan": {"to_hospital_rank": 1, "mode": "driving", "eta_min": 15, "summary": "大约15分钟车程"}
}
```

**三甲优先机制（v1.0 必须落地的工程约束）**
- 由于地图 POI “三甲字段”可能不稳定，本版本必须提供：
  - **本地医院等级映射表**（只包含医院名称与等级，不含用户数据）
  - 或可配置的“识别规则/白名单”

---

### 5.12 ResponseComposer（最终口语化输出）
**输入**
- final_assessment
- navigation
- weather_alert

**输出**
- `message`：口语化中文完整回答（按固定段落组织）
- `hotline_tip.message`：固定兜底提示
- `disclaimer`：固定免责声明

**固定兜底提示（必须出现）**
- “如果你不确定症状严重程度，或者情况在变重，建议你也可以拨打当地医疗热线或直接拨打医院电话先确认是否需要急诊/挂什么科。”

---

## 6. 医院推荐策略（综合医院 + 三甲优先）（冻结）

### 6.1 排序策略（从高到低）
1. **三甲综合医院**优先
2. 距离更近优先
3. 如果可得：急诊能力/评分/热度作为次级排序

### 6.2 输出数量（冻结）
- Top1（主推荐） + 备选 2 家（共 3 家）

### 6.3 半径（冻结）
- 默认 10 km（可配置）

---

## 7. 图片输入引导（产品交互规范）

你选择了 **B：图片+文字** 作为默认引导，本 spec 固化为：

- 当用户上传图片时，前端必须提示用户补一句话：
  - “简单说下：哪里不舒服？大概多久了？疼/痒吗？有没有发烧？”
- 后端若 `text` 为空：
  - 允许继续流程，但 `ClinicalExtraction` 必须更倾向生成追问（need_more_info 更常见）

---

## 8. 失败与降级策略（必须实现并可验收）

### 8.1 外部工具失败
- NCBI 失败：不阻断分诊 → 输出提示“本次未检索到参考资料”
- 高德失败或无定位：输出“建议就近选择综合医院（三甲优先）”，不输出具体医院列表
- 墨迹失败：不输出天气提醒，不影响主结论

### 8.2 模型输出不合规
- 若 Verifier 检测到处方/确诊语气：
  - 必须删除相关内容并重写为分诊表达
- 若结构化 JSON 解析失败：
  - 最多重试 2 次；仍失败则降级为 `error` 或 `need_more_info`（看场景）

---

## 9. 红旗规则配置规范（不写医学细则，但写配置结构）

### 9.1 规则配置格式（示例）
```json
{
  "rules": [
    {
      "id": "RF_BREATHING_DIFFICULTY",
      "priority": "high",
      "conditions": [
        {"field": "accompanying_symptoms", "op": "contains_any", "value": ["呼吸困难", "喘不过气"]}
      ],
      "triage_level": "EMERGENCY",
      "user_message": "你提到可能有呼吸困难，这种情况需要尽快去急诊/呼叫急救。",
      "department": ["急诊"]
    }
  ]
}
```

### 9.2 上线流程（验收要求）
- 规则必须经医疗顾问审阅签字（流程要求，不在代码里实现）
- 规则版本号可追溯（配置版本化）

---

## 10. 观测与验收（交付必须包含的测试点）

### 10.1 功能验收用例（最小集合）
1. 文字输入：普通皮疹 → ROUTINE + 皮肤科 + 自我注意 + 红旗
2. 图片+文字：外伤出血 → 根据描述给出时效与科室（外科/急诊） + 破伤风提醒（仅“建议咨询医生/就医时说明”）
3. 图片不清晰 → need_more_info + 补拍提示
4. 红旗样本：严重症状（例如呼吸困难/意识异常等）→ EMERGENCY，跳过 NCBI，优先导航与热线提示
5. 无定位 → 不输出医院列表，但仍给就医建议
6. NCBI 失败 → 输出中说明“未检索到文献”，不影响分诊输出

### 10.2 合规验收（零容忍）
- 输出中不得出现：
  - 确诊句式
  - 药物剂量
  - 替代急救的建议

---

## 11. 最终确认清单（你已全部确认 ✅）

- [x] 输入：文字、语音（前端转写成文字）、图片（皮疹/外伤）  
- [x] 默认引导：**图片 + 文字（B）**  
- [x] 会话：Redis，TTL=**60分钟**  
- [x] 定位：GPS（lat/lng）  
- [x] 输出：中文口语化  
- [x] 医院：综合医院 + 三甲优先，半径=**10km**  
- [x] 输出医院：Top1 + 备选2家  
- [x] 兜底：提示拨打当地医疗热线/医院电话确认  

---
