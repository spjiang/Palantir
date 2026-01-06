<template>
  <div class="wrap">
    <header class="hdr">
      <div class="title">城市暴雨内涝指挥（演示级）</div>
      <div class="meta">
        <span>API: {{ apiBase }}</span>
        <span>智能体: {{ agentBase }}</span>
      </div>
      <div class="meta tabs">
        <button :class="{ active: activePage === 'flow' }" @click="activePage = 'flow'; goStep('map'); ensureIncident().catch(() => {})">闭环分步（五页）</button>
        <button :class="{ active: activePage === 'main' }" @click="activePage = 'main'">主演示页</button>
        <button :class="{ active: activePage === 'data' }" @click="activePage = 'data'"> L1 数据接入与治理</button>
        <button :class="{ active: activePage === 'ontology' }" @click="activePage = 'ontology'"> L2 本体/语义选型</button>
        <button :class="{ active: activePage === 'model' }" @click="activePage = 'model'">L3 风险推理/模型</button>
        <button :class="{ active: activePage === 'agent' }" @click="activePage = 'agent'">L4 智能体决策</button>
        <button :class="{ active: activePage === 'workflow' }" @click="activePage = 'workflow'"> L5 执行闭环/工作流</button>
        <button :class="{ active: activePage === 'report' }" @click="activePage = 'report'">L6 战报与追溯</button>
        <button :class="{ active: activePage === 'summary' }" @click="activePage = 'summary'">系统总结</button>
      </div>
    </header>

<main class="grid single" v-if="activePage === 'flow'">
      <section class="card wide">
        <div class="flow-hdr">
          <div>
            <h3>分步闭环（五页）</h3>
            <div class="muted small">1) 地图 TopN → 2) 暴雨参谋长对话 → 3) 任务 → 4) 回执 → 5) 战报</div>
          </div>
          <div class="flow-actions">
            <button class="ghost" @click="resetFlow">重置流程</button>
            <button class="ghost" @click="activePage = 'main'">回到原主演示</button>
          </div>
        </div>

        <div class="flow-progress">
          <div class="flow-bar">
            <div class="flow-bar-fill" :style="{ width: flowProgress + '%' }"></div>
          </div>
          <div class="flow-meta">
            <span class="chip">当前进度：{{ flowProgress }}%</span>
            <span class="chip muted">事件ID：{{ incidentId || "未创建" }}</span>
            <span class="chip muted">目标：{{ selectedTarget ? targetLabel(selectedTarget, areaId) : "未选择" }}</span>
            <span class="chip muted">区域：{{ areaLabel(areaId) }}</span>
          </div>
          <div class="flow-steps">
            <button :class="{ active: flowStep === 'map' }" @click="goStep('map')">1 地图(20%)</button>
            <button :class="{ active: flowStep === 'agent' }" @click="goStep('agent')" :disabled="!selectedTarget">2 对话(40%)</button>
            <button :class="{ active: flowStep === 'tasks' }" @click="goStep('tasks')" :disabled="!incidentId">3 任务(60%)</button>
            <button :class="{ active: flowStep === 'ack' }" @click="goStep('ack')" :disabled="!incidentId">4 回执(80%)</button>
            <button :class="{ active: flowStep === 'report' }" @click="goStep('report')" :disabled="!incidentId">5 战报(100%)</button>
          </div>
        </div>

        <!-- 1) 风险热力图（简化为 TopN 列表）+ 数字孪生 · 地图视图 -->
        <div v-if="flowStep === 'map'" class="flow-page">
          <h3>1) 风险热力图（简化为 TopN 列表）</h3>
          <div class="row">
            <label>区域</label>
            <select v-model="areaId">
              <option v-for="a in areaOptions" :key="a.value" :value="a.value">{{ a.label }}</option>
            </select>
            <button @click="loadTopN">刷新 TopN</button>
          </div>
          <div class="map-and-list">
            <div class="map-card">
              <div class="map-title">数字孪生 · 地图视图</div>
              <div ref="mapRef" class="map"></div>
              <div class="map-hint muted">点击预警点位（如 road-008）将自动跳转到「暴雨参谋长智能体（对话）」页面。</div>
            </div>
            <div class="list-card">
              <table class="tbl">
                <thead>
                  <tr>
                    <th>对象</th>
                    <th>等级</th>
                    <th>分数</th>
                    <th>置信度</th>
                    <th>解释因子</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="it in topN"
                    :key="it.target_id"
                    @click="pickTarget(it.target_id)"
                    :class="['level-' + (it.risk_level || ''), { active: it.target_id === selectedTarget }]"
                  >
                    <td>{{ targetLabel(it.target_id, it.area_id || areaId) }}</td>
                    <td>{{ it.risk_level }}</td>
                    <td>{{ it.risk_score.toFixed(2) }}</td>
                    <td>{{ it.confidence.toFixed(2) }}</td>
                    <td class="muted">{{ (it.explain_factors || []).slice(0, 3).join(" / ") }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
          <div class="row">
            <button class="ghost" :disabled="!selectedTarget" @click="goStep('agent')">下一步：进入对话</button>
          </div>
        </div>

        <!-- 2) 暴雨参谋长智能体（对话） -->
        <div v-else-if="flowStep === 'agent'" class="flow-page">
          <h3>2) 暴雨参谋长智能体（对话）</h3>
          <div class="row">
            <label>事件ID</label>
            <input v-model="incidentId" placeholder="留空可由智能体自动创建" />
            <button @click="createIncident" :disabled="creatingIncident">新建事件</button>
          </div>
          <div class="chips">
            <span class="chip muted">当前区域：{{ areaLabel(areaId) }}</span>
            <span class="chip" :class="{ muted: !selectedTarget }">
              当前目标：{{ selectedTarget ? targetLabel(selectedTarget, areaId) : "未选择" }}
            </span>
          </div>

          <div v-if="selectedTargetObj" class="plan-card">
            <div class="plan-title">选中预警详情（L3 风险推理输出）</div>
            <div class="plan-grid">
              <div class="plan-item">
                <span>对象</span>
                <strong>{{ targetLabel(selectedTargetObj.target_id, selectedTargetObj.area_id || areaId) }}</strong>
              </div>
              <div class="plan-item">
                <span>风险等级</span>
                <strong>{{ selectedTargetObj.risk_level }}</strong>
              </div>
              <div class="plan-item">
                <span>风险分数</span>
                <strong>{{ selectedTargetObj.risk_score.toFixed(2) }}</strong>
              </div>
              <div class="plan-item">
                <span>置信度</span>
                <strong>{{ selectedTargetObj.confidence.toFixed(2) }}</strong>
              </div>
              <div class="plan-item" style="grid-column: 1 / -1;">
                <span>解释因子</span>
                <strong class="muted">{{ (selectedTargetObj.explain_factors || []).slice(0, 6).join(" / ") || "暂无" }}</strong>
              </div>
            </div>

            <div v-if="loadingObjectState" class="muted small" style="margin-top:8px;">对象属性加载中...</div>
            <div v-else-if="objectStateCache[selectedTarget]" class="muted small" style="margin-top:8px;">
              <div><strong>对象属性</strong>：{{ objectStateCache[selectedTarget]?.attrs?.name || "-" }} / {{ objectStateCache[selectedTarget]?.attrs?.admin_area || "-" }}</div>
              <div><strong>关键特征</strong>：雨强 {{ objectStateCache[selectedTarget]?.features?.rain_now_mmph ?? "-" }} mm/h；1h雨量 {{ objectStateCache[selectedTarget]?.features?.rain_1h_mm ?? "-" }}；水位 {{ objectStateCache[selectedTarget]?.features?.water_level_m ?? "-" }} m；泵站 {{ objectStateCache[selectedTarget]?.features?.pump_status ?? "-" }}</div>
            </div>
          </div>

          <textarea v-model="chatInput" rows="4" placeholder="输入：例如“请研判并一键下发任务包”"></textarea>
          <div class="row">
            <button @click="sendChatOneClick" :disabled="!selectedTarget">发送（一键派单）</button>
            <button class="ghost" @click="confirmAgentAndNext" :disabled="!agentResult">专家确认无误 → 进入任务</button>
          </div>
          <div class="box">
            <div class="muted">智能体输出（结构化展示，供专家确认）：</div>

            <div v-if="agentResult" class="plan">
              <div class="plan-card">
                <div class="plan-title">研判摘要</div>
                <div class="plan-grid">
                  <div class="plan-item"><span>事件ID</span><strong>{{ agentResult.incident_id || incidentId || "-" }}</strong></div>
                  <div class="plan-item"><span>目标</span><strong>{{ targetLabel(agentResult.target_id || selectedTarget, agentResult.area_id || areaId) }}</strong></div>
                  <div class="plan-item"><span>区域</span><strong>{{ areaLabel(agentResult.area_id || areaId) }}</strong></div>
                  <div class="plan-item"><span>建议</span><strong>{{ agentResult.summary || agentResult.message || "-" }}</strong></div>
                </div>
              </div>

              <div v-if="agentResult.task_pack || agentResult.taskpack || agentResult.tasks" class="plan-card">
                <div class="plan-title">任务建议（预案式展示）</div>
                <div class="muted small">说明：以下为智能体的结构化建议；点击“专家确认无误”后再进入任务执行页。</div>
                <table class="tbl" v-if="(agentResult.task_pack?.tasks || agentResult.taskpack?.tasks || agentResult.tasks)">
                  <thead>
                    <tr>
                      <th>序号</th>
                      <th>任务类型</th>
                      <th>目标</th>
                      <th>责任单位</th>
                      <th>SLA（时限）</th>
                      <th>必传证据</th>
                      <th>备注</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr
                      v-for="(t, idx) in (agentResult.task_pack?.tasks || agentResult.taskpack?.tasks || agentResult.tasks)"
                      :key="idx"
                    >
                      <td class="muted">{{ idx + 1 }}</td>
                      <td>{{ t.task_type || t.type || "-" }}</td>
                      <td>
                        {{ targetLabel(t.target_object_id || t.target_id || agentResult.target_id || selectedTarget, agentResult.area_id || areaId) }}
                      </td>
                      <td>
                        <span class="org-badge" :class="'tone-' + ownerOrgView(t.owner_org || t.owner).tone" :title="ownerOrgView(t.owner_org || t.owner).desc">
                          {{ ownerOrgView(t.owner_org || t.owner).name }}
                        </span>
                      </td>
                      <td>{{ slaView(t.sla_minutes ?? t.sla) }}</td>
                      <td class="muted">{{ (t.required_evidence || t.evidence || []).join(" / ") }}</td>
                      <td class="muted">{{ t.detail || t.note || "-" }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <details class="plan-card">
                <summary class="plan-title">原始 JSON（调试）</summary>
                <pre class="pre">{{ agentOut }}</pre>
              </details>
            </div>

            <div v-else class="muted small">尚未发送或暂无输出。</div>
          </div>
        </div>

        <!-- 3) 任务 -->
        <div v-else-if="flowStep === 'tasks'" class="flow-page">
          <h3>3) 任务</h3>
          <div class="row">
            <label>事件ID</label>
            <input v-model="incidentId" placeholder="必填" />
            <button @click="loadTasks" :disabled="!incidentId">加载任务</button>
            <button class="ghost" @click="goStep('ack')" :disabled="tasks.length === 0">下一步：进入回执</button>
          </div>
          <table class="tbl">
            <thead>
              <tr>
                <th>任务ID</th>
                <th>类型</th>
                <th>目标</th>
                <th>责任单位</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="t in tasks" :key="t.task_id">
                <td class="muted">{{ t.task_id }}</td>
                <td>{{ t.task_type }}</td>
                <td>{{ targetLabel(t.target_object_id, areaId) }}</td>
                <td>
                  <span class="org-badge" :class="'tone-' + ownerOrgView(t.owner_org).tone" :title="ownerOrgView(t.owner_org).desc">
                    {{ ownerOrgView(t.owner_org).name }}
                  </span>
                </td>
                <td>{{ taskStatusView(t.status) }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- 4) 回执 -->
        <div v-else-if="flowStep === 'ack'" class="flow-page">
          <h3>4) 回执</h3>
          <div class="row">
            <button class="ghost" @click="loadTasks" :disabled="!incidentId">刷新任务</button>
            <button @click="ackAllDone" :disabled="tasks.length === 0">一键回执完成</button>
            <button class="ghost" @click="goStep('report')" :disabled="!incidentId">下一步：进入战报</button>
          </div>
          <table class="tbl">
            <thead>
              <tr>
                <th>任务ID</th>
                <th>类型</th>
                <th>目标</th>
                <th>责任单位</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="t in tasks" :key="t.task_id">
                <td class="muted">{{ t.task_id }}</td>
                <td>{{ t.task_type }}</td>
                <td>{{ targetLabel(t.target_object_id, areaId) }}</td>
                <td>
                  <span class="org-badge" :class="'tone-' + ownerOrgView(t.owner_org).tone" :title="ownerOrgView(t.owner_org).desc">
                    {{ ownerOrgView(t.owner_org).name }}
                  </span>
                </td>
                <td>{{ taskStatusView(t.status) }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- 5) 战报 -->
        <div v-else-if="flowStep === 'report'" class="flow-page">
          <h3>5) 战报</h3>
          <div class="row">
            <button @click="loadReport" :disabled="!incidentId">生成战报</button>
            <button class="ghost" @click="goStep('map')">回到第一步</button>
          </div>
        <div v-if="reportData" class="report-grid">
          <div class="report-card">
            <div class="rc-title">事件概览</div>
            <div class="rc-main">{{ reportData.title || reportData.incident_id }}</div>
            <div class="rc-sub">状态：{{ reportData.status }}</div>
            <div class="rc-sub">事件ID：{{ reportData.incident_id }}</div>
          </div>
          <div class="report-card">
            <div class="rc-title">任务指标</div>
            <div class="rc-metrics">
              <div><span>总数</span><strong>{{ reportData.metrics?.task_total ?? "-" }}</strong></div>
              <div><span>完成</span><strong>{{ reportData.metrics?.task_done ?? "-" }}</strong></div>
              <div><span>完成率</span><strong>{{ formatPercent(reportData.metrics?.task_done_rate) }}</strong></div>
            </div>
          </div>
          <div class="report-card timeline">
            <div class="rc-title">处置时间线（时间轴）</div>
            <ul class="timeline-list v2">
              <li v-for="(e, idx) in reportData.timeline" :key="idx" class="tl-item">
                <div class="tl-left">
                  <div class="tl-dot"></div>
                  <div class="tl-line" v-if="idx !== reportData.timeline.length - 1"></div>
                </div>
                <div class="tl-right">
                  <div class="tl-head">
                    <div class="tl-type" :title="String(e.type || '')">{{ eventTypeLabel(e.type) }}</div>
                    <div class="tl-time">{{ formatTime(e.time) }}</div>
                    <div class="tl-rel muted">{{ relativeTime(e.time) }}</div>
                  </div>
                  <div class="tl-kv" v-if="payloadEntries(e.payload).length">
                    <div v-for="kv in payloadEntries(e.payload)" :key="kv.k" class="kv-row">
                      <span class="kv-k">{{ fieldLabel(kv.k) }}</span>
                      <span class="kv-v muted" v-if="kv.k !== 'evidence'">{{ kv.v }}</span>
                      <span class="kv-v muted" v-else>
                        <details class="kv-details" @toggle="onEvidenceToggle($event, evidenceMapDomId('flow', idx), kv.raw)">
                          <summary>查看证据</summary>
                          <div class="evi-grid">
                            <div class="evi-photo" v-if="evidenceView(kv.raw).photo_src">
                              <img
                                :src="evidenceView(kv.raw).photo_src"
                                alt="证据照片"
                                loading="lazy"
                                @error="onEvidenceImgError"
                                @click="openImagePreview(evidenceView(kv.raw).photo_src)"
                              />
                            </div>
                            <div class="evi-photo placeholder" v-else>无照片</div>
                            <div class="evi-map" v-if="evidenceView(kv.raw).has_gps" :id="evidenceMapDomId('flow', idx)"></div>
                            <div class="evi-meta">
                              <div class="evi-row" v-if="evidenceView(kv.raw).has_gps">
                                <span class="chip blue">定位</span>
                                <span class="muted"
                                  >纬度 {{ evidenceView(kv.raw).lat }} ｜ 经度 {{ evidenceView(kv.raw).lng }}</span
                                >
                              </div>
                              <div class="evi-row" v-if="evidenceView(kv.raw).has_gps">
                                <a class="evi-link" :href="evidenceView(kv.raw).map_url" target="_blank" rel="noreferrer">打开地图</a>
                                <button class="btn tiny ghost" @click="copyText(evidenceView(kv.raw).gps_raw)">复制坐标</button>
                              </div>
                              <details class="kv-details sub">
                                <summary class="muted">查看证据（JSON）</summary>
                          <pre class="pre pre-mini">{{ prettyJson(kv.raw) }}</pre>
                              </details>
                            </div>
                          </div>
                        </details>
                      </span>
                    </div>
                  </div>
                  <div v-else class="muted small">无附加信息</div>
                </div>
              </li>
            </ul>
          </div>
        </div>
        <details class="box" v-if="reportOut">
          <summary class="muted">原始 JSON（调试）</summary>
          <pre class="pre">{{ reportOut }}</pre>
        </details>
        </div>
      </section>
    </main>

<main class="grid" v-else-if="activePage === 'main'">
      <section class="card wide">
        <h3>1) 风险热力图（简化为 TopN 列表）</h3>
        <div class="field-help">
          <div class="help-title">字段说明</div>
          <div class="help-content">
            <div class="help-item">
              <strong>risk_score（风险分数）</strong>：数值范围 0-10，表示对象的综合风险评分。分数越高表示风险越大，通常 8-10 为高风险（红），6-8 为中高风险（橙），4-6 为中风险（黄），0-4 为低风险（绿）。
            </div>
            <div class="help-item">
              <strong>risk_level（风险等级）</strong>：分为四个等级：<span class="level-chip red">红</span>（高风险）、<span class="level-chip orange">橙</span>（中高风险）、<span class="level-chip yellow">黄</span>（中风险）、<span class="level-chip green">绿</span>（低风险）。等级由 risk_score 映射而来，用于快速识别风险程度。
            </div>
            <div class="help-item">
              <strong>confidence（置信度）</strong>：数值范围 0-1，表示模型对风险评分的置信程度。置信度越高表示模型对评分越有信心，通常基于特征完整性和模型不确定性计算。0.8 以上表示高置信度，0.6-0.8 表示中等置信度，0.6 以下表示低置信度。
            </div>
            <div class="help-item">
              <strong>explain_factors（解释因子）</strong>：字符串数组，列出导致风险评分的主要因素。例如："雨强上升"、"水位超限"、"历史事件"等。这些因子通过 SHAP/LIME 等可解释性方法生成，帮助理解模型决策依据。
            </div>
          </div>
        </div>
        <div class="row">
          <label>区域</label>
          <select v-model="areaId">
            <option v-for="a in areaOptions" :key="a.value" :value="a.value">{{ a.label }}</option>
          </select>
          <button @click="loadTopN">刷新 TopN</button>
        </div>
        <div class="map-and-list">
          <div class="map-card">
            <div class="map-title">数字孪生 · 地图视图</div>
            <div ref="mapRef" class="map"></div>
            <div class="map-hint muted">示例坐标基于北京海淀区东北旺西路8号院附近，按风险色彩/大小呈现 TopN 点位；点击点位或列表联动。</div>
          </div>
          <div class="list-card">
        <table class="tbl">
          <thead>
            <tr>
              <th>对象</th>
              <th>等级</th>
              <th>分数</th>
              <th>置信度</th>
              <th>解释因子</th>
            </tr>
          </thead>
          <tbody>
                <tr
                  v-for="it in topN"
                  :key="it.target_id"
                  @click="pickTarget(it.target_id)"
                  :class="['level-' + (it.risk_level || ''), { active: it.target_id === selectedTarget }]"
                >
              <td>{{ targetLabel(it.target_id, it.area_id || areaId) }}</td>
              <td>{{ it.risk_level }}</td>
              <td>{{ it.risk_score.toFixed(2) }}</td>
              <td>{{ it.confidence.toFixed(2) }}</td>
              <td class="muted">{{ (it.explain_factors || []).slice(0, 3).join(" / ") }}</td>
            </tr>
          </tbody>
        </table>
          </div>
        </div>
        <div class="summary-tiles">
          <div class="s-tile">
            <div class="s-label">TopN 数量</div>
            <div class="s-value">{{ riskSummary.total }}</div>
          </div>
          <div class="s-tile">
            <div class="s-label">最高分</div>
            <div class="s-value">{{ riskSummary.maxScore.toFixed(2) || "-" }}</div>
            <div class="s-sub muted" v-if="riskSummary.maxId">目标：{{ targetLabel(riskSummary.maxId, areaId) }}</div>
          </div>
          <div class="s-tile">
            <div class="s-label">分布</div>
            <div class="s-tags">
              <span class="chip level-chip red">红 {{ riskSummary.counts.红 || 0 }}</span>
              <span class="chip level-chip orange">橙 {{ riskSummary.counts.橙 || 0 }}</span>
              <span class="chip level-chip yellow">黄 {{ riskSummary.counts.黄 || 0 }}</span>
              <span class="chip level-chip green">绿 {{ riskSummary.counts.绿 || 0 }}</span>
            </div>
          </div>
        </div>
        <div v-if="selectedTargetObj" class="twin">
          <div class="twin-header">
            <div class="twin-title">数字孪生视图 · {{ targetLabel(selectedTargetObj.target_id, selectedTargetObj.area_id || areaId) }}</div>
            <div class="twin-meta">风险 {{ selectedTargetObj.risk_level }} · 置信度 {{ selectedTargetObj.confidence.toFixed(2) }}</div>
          </div>
          <div class="twin-body">
            <div class="twin-tiles">
              <div class="tile big">
                <div class="tile-top">risk_score</div>
                <div class="tile-num">{{ selectedTargetObj.risk_score.toFixed(2) }}</div>
                <div class="tile-bar">
                  <div class="tile-bar-fill" :style="{ width: Math.min(selectedTargetObj.risk_score * 10, 100) + '%' }"></div>
                </div>
              </div>
              <div class="tile">
                <div class="tile-top">confidence</div>
                <div class="tile-num small">{{ selectedTargetObj.confidence.toFixed(2) }}</div>
              </div>
                <div class="tile">
                  <div class="tile-top">风险等级</div>
                  <div class="badge" :class="'level-' + selectedTargetObj.risk_level">{{ selectedTargetObj.risk_level }}</div>
              </div>
            </div>
            <div class="twin-factors">
              <div class="twin-subtitle">解释因子</div>
              <div class="factor-chips">
                <span v-for="(f, idx) in (selectedTargetObj.explain_factors || []).slice(0, 6)" :key="idx" class="chip">
                  {{ f }}
                </span>
                <span v-if="!selectedTargetObj.explain_factors || selectedTargetObj.explain_factors.length === 0" class="chip muted">暂无</span>
              </div>
              <div class="factor-help">
                <div class="help-title">因子说明</div>
                <div class="help-grid">
                  <div><strong>水位</strong><span>水位偏高或快速上升</span></div>
                  <div><strong>雨强</strong><span>短时降雨强度大</span></div>
                  <div><strong>累计雨量</strong><span>累积降水带来排水压力</span></div>
                  <div><strong>泵站故障</strong><span>泵站离线/故障导致排水能力下降</span></div>
                  <div><strong>道路拥堵</strong><span>交通指数高，影响疏散/处置</span></div>
                  <div><strong>低洼/排水弱</strong><span>地形低洼或排水能力不足</span></div>
                  <div><strong>风险分=xx</strong><span>模型输出的风险得分</span></div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section class="card wide">
        <h3>系统分层与节点（含数据接入与治理）</h3>
        <div class="layer-grid">
          <div v-for="layer in layerBlocks" :key="layer.name" class="layer-card">
            <div class="layer-title">{{ layer.name }}</div>
            <div class="layer-desc">{{ layer.desc }}</div>
            <ul class="layer-list">
              <li v-for="node in layer.nodes" :key="node.title">
                <div class="node-title">{{ node.title }}</div>
                <div class="node-detail">{{ node.detail }}</div>
              </li>
            </ul>
          </div>
        </div>
        <div class="hint">说明：为前端展示而简化的节点清单；实际数据流与接口见方案书 1.1.2。</div>
      </section>

      <section class="card">
        <h3>2) 暴雨参谋长智能体（对话）</h3>
        <div class="row">
          <label>事件ID</label>
          <input v-model="incidentId" placeholder="留空自动创建" />
          <button @click="createIncident">新建事件</button>
        </div>
        <div class="chips">
          <span class="chip muted">当前区域：{{ areaLabel(areaId) }}</span>
          <span class="chip" :class="{ muted: !selectedTarget }">当前目标：{{ selectedTarget || "未选择" }}</span>
        </div>
        <textarea v-model="chatInput" rows="4" placeholder="输入：例如“请研判并一键下发任务包”"></textarea>
        <div class="row">
          <button @click="sendChatOneClick">发送（一键派单）</button>
        </div>
        <div class="box">
          <div class="muted">智能体输出：</div>
          <pre class="pre">{{ agentOut }}</pre>
        </div>
      </section>

      <section class="card">
        <h3>3/4) 任务与回执</h3>
        <div class="row">
          <button @click="loadTasks" :disabled="!incidentId">加载任务</button>
          <button class="ghost" @click="ackAllDone" :disabled="tasks.length === 0">一键回执完成</button>
        </div>
        <table class="tbl">
          <thead>
            <tr>
              <th>任务ID</th>
              <th>类型</th>
              <th>目标</th>
              <th>责任单位</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="t in tasks" :key="t.task_id">
              <td class="muted">{{ t.task_id }}</td>
              <td>{{ t.task_type }}</td>
              <td>{{ targetLabel(t.target_object_id, areaId) }}</td>
              <td>
                <span class="org-badge" :class="'tone-' + ownerOrgView(t.owner_org).tone" :title="ownerOrgView(t.owner_org).desc">
                  {{ ownerOrgView(t.owner_org).name }}
                </span>
              </td>
              <td>{{ taskStatusView(t.status) }}</td>
            </tr>
          </tbody>
        </table>
      </section>

      <section class="card">
        <h3>5) 战报</h3>
        <div class="row">
          <button @click="loadReport" :disabled="!incidentId">生成战报</button>
        </div>
        <div v-if="reportData" class="report-grid">
          <div class="report-card">
            <div class="rc-title">事件概览</div>
            <div class="rc-main">{{ reportData.title || reportData.incident_id }}</div>
            <div class="rc-sub">状态：{{ reportData.status }}</div>
            <div class="rc-sub">事件ID：{{ reportData.incident_id }}</div>
          </div>
          <div class="report-card">
            <div class="rc-title">任务指标</div>
            <div class="rc-metrics">
              <div><span>总数</span><strong>{{ reportData.metrics?.task_total ?? "-" }}</strong></div>
              <div><span>完成</span><strong>{{ reportData.metrics?.task_done ?? "-" }}</strong></div>
              <div><span>完成率</span><strong>{{ formatPercent(reportData.metrics?.task_done_rate) }}</strong></div>
            </div>
          </div>
          <div class="report-card timeline">
            <div class="rc-title">处置时间线（时间轴）</div>
            <ul class="timeline-list v2">
              <li v-for="(e, idx) in reportData.timeline" :key="idx" class="tl-item">
                <div class="tl-left">
                  <div class="tl-dot"></div>
                  <div class="tl-line" v-if="idx !== reportData.timeline.length - 1"></div>
                </div>
                <div class="tl-right">
                  <div class="tl-head">
                  <div class="tl-type" :title="String(e.type || '')">{{ eventTypeLabel(e.type) }}</div>
                    <div class="tl-time">{{ formatTime(e.time) }}</div>
                    <div class="tl-rel muted">{{ relativeTime(e.time) }}</div>
                  </div>
                  <div class="tl-kv" v-if="payloadEntries(e.payload).length">
                    <div v-for="kv in payloadEntries(e.payload)" :key="kv.k" class="kv-row">
                      <span class="kv-k">{{ fieldLabel(kv.k) }}</span>
                      <span class="kv-v muted" v-if="kv.k !== 'evidence'">{{ kv.v }}</span>
                      <span class="kv-v muted" v-else>
                        <details class="kv-details" @toggle="onEvidenceToggle($event, evidenceMapDomId('main', idx), kv.raw)">
                          <summary>查看证据</summary>
                          <div class="evi-grid">
                            <div class="evi-photo" v-if="evidenceView(kv.raw).photo_src">
                              <img
                                :src="evidenceView(kv.raw).photo_src"
                                alt="证据照片"
                                loading="lazy"
                                @error="onEvidenceImgError"
                                @click="openImagePreview(evidenceView(kv.raw).photo_src)"
                              />
                            </div>
                            <div class="evi-photo placeholder" v-else>无照片</div>
                            <div class="evi-map" v-if="evidenceView(kv.raw).has_gps" :id="evidenceMapDomId('main', idx)"></div>
                            <div class="evi-meta">
                              <div class="evi-row" v-if="evidenceView(kv.raw).has_gps">
                                <span class="chip blue">定位</span>
                                <span class="muted"
                                  >纬度 {{ evidenceView(kv.raw).lat }} ｜ 经度 {{ evidenceView(kv.raw).lng }}</span
                                >
                              </div>
                              <div class="evi-row" v-if="evidenceView(kv.raw).has_gps">
                                <a class="evi-link" :href="evidenceView(kv.raw).map_url" target="_blank" rel="noreferrer">打开地图</a>
                                <button class="btn tiny ghost" @click="copyText(evidenceView(kv.raw).gps_raw)">复制坐标</button>
                              </div>
                              <details class="kv-details sub">
                                <summary class="muted">查看证据（JSON）</summary>
                          <pre class="pre pre-mini">{{ prettyJson(kv.raw) }}</pre>
                              </details>
                            </div>
                          </div>
                        </details>
                      </span>
                    </div>
                  </div>
                  <div v-else class="muted small">无附加信息</div>
                </div>
              </li>
            </ul>
          </div>
        </div>
        <details class="box" v-if="reportOut">
          <summary class="muted">原始 JSON（调试）</summary>
        <pre class="pre">{{ reportOut }}</pre>
        </details>
      </section>
    </main>

<main v-else-if="activePage === 'data'" class="grid single">
  <section class="card wide">
    <h3>数据接入与治理（L1 - 1.4 数据设计）</h3>
    <p class="muted">说明：当前演示页不变，本页用于展示数据接入、存储、质量与治理层的技术方案示意。</p>
    <div class="stack-grid">
      <div class="stack-card">
        <div class="stack-title">数据接入 / 连接器</div>
        <div class="stack-items">
          <div class="stack-item"><strong>雨量站</strong><span>HTTP/API、MQTT、文件轮询</span></div>
          <div class="stack-item"><strong>雷达数据</strong><span>FTP/SFTP、对象存储、实时流</span></div>
          <div class="stack-item"><strong>水位/泵站</strong><span>Modbus/OPC、IoT 平台、数据库直连</span></div>
          <div class="stack-item"><strong>路况/事件</strong><span>API 网关、消息队列（Kafka/RabbitMQ）</span></div>
        </div>
      </div>
      <div class="stack-card">
        <div class="stack-title">数据存储分层</div>
        <div class="stack-items">
          <div class="stack-item"><strong>Raw 原始层</strong><span>原始数据原样落库，保留完整上下文</span></div>
          <div class="stack-item"><strong>ODS 明细层</strong><span>清洗对齐后的操作型明细，统一口径</span></div>
          <div class="stack-item"><strong>TSDB 时序层</strong><span>高频指标/传感器时序存储（InfluxDB/TimescaleDB）</span></div>
        </div>
      </div>
      <div class="stack-card">
        <div class="stack-title">数据质量（DQ）</div>
        <div class="stack-items">
          <div class="stack-item"><strong>完整性</strong><span>字段缺失率、记录完整度</span></div>
          <div class="stack-item"><strong>及时性</strong><span>数据延迟、更新频率</span></div>
          <div class="stack-item"><strong>一致性</strong><span>跨源口径对齐、单位统一</span></div>
          <div class="stack-item"><strong>准确性</strong><span>异常值检测、范围校验</span></div>
        </div>
      </div>
      <div class="stack-card">
        <div class="stack-title">数据治理</div>
        <div class="stack-items">
          <div class="stack-item"><strong>血缘追溯</strong><span>数据来源、转换链路、依赖关系</span></div>
          <div class="stack-item"><strong>版本管理</strong><span>Schema 版本、数据快照、回滚能力</span></div>
          <div class="stack-item"><strong>窗口聚合</strong><span>时间窗口、滑动窗口、滚动窗口</span></div>
          <div class="stack-item"><strong>审计日志</strong><span>数据变更、访问记录、合规审计</span></div>
        </div>
      </div>
    </div>

    <div class="ont-grid">
      <div class="ont-card">
        <div class="ont-title">数据源配置</div>
        <div class="ont-desc muted">配置各类数据源的连接参数与采集规则</div>
        <div class="ont-form">
          <div class="form-row">
            <label>数据源名称</label>
            <input v-model="dataSourceName" placeholder="如 雨量站-001" />
          </div>
          <div class="form-row">
            <label>数据源类型</label>
            <select v-model="dataSourceType">
              <option>雨量</option>
              <option>雷达</option>
              <option>水位</option>
              <option>泵站</option>
              <option>路况</option>
              <option>事件</option>
            </select>
          </div>
          <div class="form-row">
            <label>连接方式</label>
            <select v-model="dataSourceConn">
              <option>HTTP/API</option>
              <option>MQTT</option>
              <option>FTP/SFTP</option>
              <option>数据库直连</option>
              <option>消息队列</option>
            </select>
          </div>
          <div class="form-row">
            <label>采集频率</label>
            <input v-model="dataSourceFreq" placeholder="如 5分钟、1小时" />
          </div>
          <button @click="addDataSource">保存到预览（本地）</button>
        </div>
        <div class="ont-list">
          <div v-for="(ds, idx) in dataSources" :key="idx" class="ont-item">
            <div><strong>{{ ds.name }}</strong> <span class="muted">({{ ds.type }})</span></div>
            <div class="muted">连接：{{ ds.conn }}｜频率：{{ ds.freq }}</div>
          </div>
          <div v-if="dataSources.length === 0" class="muted">尚未添加数据源（演示本地态）。</div>
        </div>
      </div>

      <div class="ont-card">
        <div class="ont-title">存储层配置</div>
        <div class="ont-desc muted">配置 Raw/ODS/TSDB 的存储策略与路由规则</div>
        <div class="ont-form">
          <div class="form-row">
            <label>数据源</label>
            <select v-model="storageSource">
              <option>雨量站-001</option>
              <option>雷达-001</option>
              <option>水位站-001</option>
            </select>
          </div>
          <div class="form-row">
            <label>存储层</label>
            <select v-model="storageLayer">
              <option>Raw（原始层）</option>
              <option>ODS（明细层）</option>
              <option>TSDB（时序层）</option>
            </select>
          </div>
          <div class="form-row">
            <label>清洗规则</label>
            <textarea v-model="storageRule" rows="2" placeholder="如：去重、单位转换、异常值过滤"></textarea>
          </div>
          <button @click="addStorageRule">保存到预览（本地）</button>
        </div>
        <div class="ont-list">
          <div v-for="(s, idx) in storageRules" :key="idx" class="ont-item">
            <div><strong>{{ s.source }}</strong> → <strong>{{ s.layer }}</strong></div>
            <div class="muted">{{ s.rule }}</div>
          </div>
          <div v-if="storageRules.length === 0" class="muted">尚未添加存储规则（演示本地态）。</div>
        </div>
      </div>

      <div class="ont-card">
        <div class="ont-title">DQ 规则配置</div>
        <div class="ont-desc muted">配置数据质量校验规则与标签策略</div>
        <div class="ont-form">
          <div class="form-row">
            <label>数据源/表</label>
            <input v-model="dqTarget" placeholder="如 雨量站-001" />
          </div>
          <div class="form-row">
            <label>DQ 维度</label>
            <select v-model="dqDimension">
              <option>完整性</option>
              <option>及时性</option>
              <option>一致性</option>
              <option>准确性</option>
            </select>
          </div>
          <div class="form-row">
            <label>校验规则</label>
            <textarea v-model="dqRule" rows="2" placeholder="如：字段非空、延迟<5分钟、值域[0,200]"></textarea>
          </div>
          <button @click="addDqRule">保存到预览（本地）</button>
        </div>
        <div class="ont-list">
          <div v-for="(dq, idx) in dqRules" :key="idx" class="ont-item">
            <div><strong>{{ dq.target }}</strong> <span class="muted">({{ dq.dimension }})</span></div>
            <div class="muted">{{ dq.rule }}</div>
          </div>
          <div v-if="dqRules.length === 0" class="muted">尚未添加 DQ 规则（演示本地态）。</div>
        </div>
      </div>
    </div>
  </section>
</main>

<main v-else-if="activePage === 'model'" class="grid single">
  <section class="card wide">
    <h3>风险推理（模型服务 L3 - 1.9.3）</h3>
    <p class="muted">说明：当前演示页不变，本页用于展示风险推理模型层的技术方案与业务流程。</p>
    
    <div class="flow-diagram">
      <div class="flow-title">业务流程：数据 → 特征 → 推理 → 输出</div>
      <div class="flow-steps">
        <div class="flow-step">
          <div class="step-num">1</div>
          <div class="step-content">
            <div class="step-title">数据输入</div>
            <div class="step-desc">从 ODS/TSDB 获取对象状态（雨量/水位/泵站/路况等特征）</div>
          </div>
        </div>
        <div class="flow-arrow">→</div>
        <div class="flow-step">
          <div class="step-num">2</div>
          <div class="step-content">
            <div class="step-title">特征工程</div>
            <div class="step-desc">特征提取、归一化、窗口聚合、缺失值处理</div>
          </div>
        </div>
        <div class="flow-arrow">→</div>
        <div class="flow-step">
          <div class="step-num">3</div>
          <div class="step-content">
            <div class="step-title">模型推理</div>
            <div class="step-desc">风险评分（0~10）、风险等级（红/橙/黄/绿）、置信度（0~1）</div>
          </div>
        </div>
        <div class="flow-arrow">→</div>
        <div class="flow-step">
          <div class="step-num">4</div>
          <div class="step-content">
            <div class="step-title">可解释性</div>
            <div class="step-desc">解释因子（Top3 贡献特征）、置信度说明</div>
          </div>
        </div>
        <div class="flow-arrow">→</div>
        <div class="flow-step">
          <div class="step-num">5</div>
          <div class="step-content">
            <div class="step-title">服务输出</div>
            <div class="step-desc">TopN API、热力图 API、单对象查询 API</div>
          </div>
        </div>
      </div>
    </div>

    <div class="stack-grid">
      <div class="stack-card">
        <div class="stack-title">模型类型</div>
        <div class="stack-items">
          <div class="stack-item"><strong>规则模型</strong><span>可解释线性/规则打分（演示级）</span></div>
          <div class="stack-item"><strong>机器学习</strong><span>XGBoost/LightGBM、随机森林、GBDT</span></div>
          <div class="stack-item"><strong>深度学习</strong><span>LSTM/GRU（时序）、CNN（空间）、Transformer</span></div>
          <div class="stack-item"><strong>混合模型</strong><span>规则+ML、集成学习、模型融合</span></div>
        </div>
      </div>
      <div class="stack-card">
        <div class="stack-title">推理引擎</div>
        <div class="stack-items">
          <div class="stack-item"><strong>Python 服务</strong><span>FastAPI + scikit-learn/XGBoost/PyTorch</span></div>
          <div class="stack-item"><strong>模型服务化</strong><span>MLflow、Seldon、Kubeflow Serving</span></div>
          <div class="stack-item"><strong>边缘推理</strong><span>ONNX Runtime、TensorRT、OpenVINO</span></div>
          <div class="stack-item"><strong>批处理</strong><span>Spark MLlib、Flink ML、Ray Serve</span></div>
        </div>
      </div>
      <div class="stack-card">
        <div class="stack-title">特征工程</div>
        <div class="stack-items">
          <div class="stack-item"><strong>特征提取</strong><span>统计特征、时序特征、空间特征、交叉特征</span></div>
          <div class="stack-item"><strong>特征选择</strong><span>相关性分析、重要性排序、降维（PCA/ICA）</span></div>
          <div class="stack-item"><strong>特征存储</strong><span>特征库/特征集市、特征版本管理</span></div>
          <div class="stack-item"><strong>在线特征</strong><span>实时特征计算、特征缓存、特征服务</span></div>
        </div>
      </div>
      <div class="stack-card">
        <div class="stack-title">可解释性</div>
        <div class="stack-items">
          <div class="stack-item"><strong>SHAP/LIME</strong><span>特征贡献度、局部/全局解释</span></div>
          <div class="stack-item"><strong>规则提取</strong><span>决策树可视化、规则列表</span></div>
          <div class="stack-item"><strong>注意力机制</strong><span>Transformer 注意力权重可视化</span></div>
          <div class="stack-item"><strong>置信度</strong><span>模型不确定性、预测区间、校准</span></div>
        </div>
      </div>
    </div>

    <div class="ont-grid">
      <div class="ont-card">
        <div class="ont-title">模型配置</div>
        <div class="ont-desc muted">配置模型类型、版本、参数与推理规则</div>
        <div class="ont-form">
          <div class="form-row">
            <label>模型名称</label>
            <input v-model="modelName" placeholder="如 内涝风险模型-v1" />
          </div>
          <div class="form-row">
            <label>模型类型</label>
            <select v-model="modelType">
              <option>规则模型</option>
              <option>XGBoost</option>
              <option>LightGBM</option>
              <option>LSTM</option>
              <option>Transformer</option>
            </select>
          </div>
          <div class="form-row">
            <label>风险阈值</label>
            <input v-model="modelThresholds" placeholder="如 红≥7.0, 橙≥5.0, 黄≥3.5" />
          </div>
          <div class="form-row">
            <label>特征列表</label>
            <textarea v-model="modelFeatures" rows="2" placeholder="如：rain_now_mmph, water_level_m, pump_status"></textarea>
          </div>
          <button @click="addModel">保存到预览（本地）</button>
        </div>
        <div class="ont-list">
          <div v-for="(m, idx) in models" :key="idx" class="ont-item">
            <div><strong>{{ m.name }}</strong> <span class="muted">({{ m.type }})</span></div>
            <div class="muted">阈值：{{ m.thresholds }}｜特征：{{ m.features }}</div>
          </div>
          <div v-if="models.length === 0" class="muted">尚未添加模型（演示本地态）。</div>
        </div>
      </div>

      <div class="ont-card">
        <div class="ont-title">特征配置</div>
        <div class="ont-desc muted">配置特征提取规则、窗口聚合、缺失值处理策略</div>
        <div class="ont-form">
          <div class="form-row">
            <label>特征名称</label>
            <input v-model="featureName" placeholder="如 rain_now_mmph" />
          </div>
          <div class="form-row">
            <label>数据源</label>
            <select v-model="featureSource">
              <option>ODS</option>
              <option>TSDB</option>
              <option>实时流</option>
            </select>
          </div>
          <div class="form-row">
            <label>窗口聚合</label>
            <input v-model="featureWindow" placeholder="如 1小时滑动窗口、5分钟滚动窗口" />
          </div>
          <div class="form-row">
            <label>处理规则</label>
            <textarea v-model="featureRule" rows="2" placeholder="如：缺失值填充、异常值过滤、单位转换"></textarea>
          </div>
          <button @click="addFeature">保存到预览（本地）</button>
        </div>
        <div class="ont-list">
          <div v-for="(f, idx) in features" :key="idx" class="ont-item">
            <div><strong>{{ f.name }}</strong> <span class="muted">({{ f.source }})</span></div>
            <div class="muted">窗口：{{ f.window }}｜规则：{{ f.rule }}</div>
          </div>
          <div v-if="features.length === 0" class="muted">尚未添加特征（演示本地态）。</div>
        </div>
      </div>

      <div class="ont-card">
        <div class="ont-title">推理任务</div>
        <div class="ont-desc muted">配置推理任务（TopN、热力图、单对象查询）的触发条件与输出格式</div>
        <div class="ont-form">
          <div class="form-row">
            <label>任务类型</label>
            <select v-model="inferTaskType">
              <option>TopN 风险</option>
              <option>热力图</option>
              <option>单对象查询</option>
            </select>
          </div>
          <div class="form-row">
            <label>触发条件</label>
            <input v-model="inferTrigger" placeholder="如 定时5分钟、事件触发、API调用" />
          </div>
          <div class="form-row">
            <label>输出格式</label>
            <textarea v-model="inferOutput" rows="2" placeholder="如：risk_score, risk_level, confidence, explain_factors"></textarea>
          </div>
          <button @click="addInferTask">保存到预览（本地）</button>
        </div>
        <div class="ont-list">
          <div v-for="(t, idx) in inferTasks" :key="idx" class="ont-item">
            <div><strong>{{ t.type }}</strong> <span class="muted">({{ t.trigger }})</span></div>
            <div class="muted">输出：{{ t.output }}</div>
          </div>
          <div v-if="inferTasks.length === 0" class="muted">尚未添加推理任务（演示本地态）。</div>
        </div>
      </div>
    </div>
  </section>
</main>

<main v-else-if="activePage === 'agent'" class="grid single">
  <section class="card wide">
    <h3>智能体决策（L4 - 1.6/1.9.4）</h3>
    <p class="muted">说明：当前演示页不变，本页用于展示智能体决策层的技术方案、业务流程与各节点功能。</p>
    
    <div class="flow-diagram">
      <div class="flow-title">业务流程：TopN 风险 → RAG 检索 → 任务包编排 → 派单</div>
      <div class="flow-steps">
        <div class="flow-step">
          <div class="step-num">1</div>
          <div class="step-content">
            <div class="step-title">输入 TopN 风险</div>
            <div class="step-desc">接收模型输出的 TopN 风险点位（含 risk_score/level/confidence/explain_factors）</div>
            <div class="step-agent muted small">智能体功能：解析风险数据，识别最高风险对象</div>
          </div>
        </div>
        <div class="flow-arrow">→</div>
        <div class="flow-step">
          <div class="step-num">2</div>
          <div class="step-content">
            <div class="step-title">RAG 证据检索</div>
            <div class="step-desc">检索预案/规程/历史战报/对象上下文，形成“有依据的建议”</div>
            <div class="step-agent muted small">智能体功能：向量检索、语义匹配、引用标注</div>
          </div>
        </div>
        <div class="flow-arrow">→</div>
        <div class="flow-step">
          <div class="step-num">3</div>
          <div class="step-content">
            <div class="step-title">任务包编排</div>
            <div class="step-desc">生成 TaskPack/tasks[]（owner_org/SLA/required_evidence/need_approval）</div>
            <div class="step-agent muted small">智能体功能：结构化输出、责任归属推理、SLA 计算</div>
          </div>
        </div>
        <div class="flow-arrow">→</div>
        <div class="flow-step">
          <div class="step-num">4</div>
          <div class="step-content">
            <div class="step-title">风控门禁</div>
            <div class="step-desc">高风险动作（封控/停运/跨部门联动）需人审确认</div>
            <div class="step-agent muted small">智能体功能：风险动作识别、审批流程触发</div>
          </div>
        </div>
        <div class="flow-arrow">→</div>
        <div class="flow-step">
          <div class="step-num">5</div>
          <div class="step-content">
            <div class="step-title">派单下发</div>
            <div class="step-desc">调用工作流 API 落库，通知责任单位/人员，启动 SLA 计时</div>
            <div class="step-agent muted small">智能体功能：API 调用、错误处理、重试策略</div>
          </div>
        </div>
      </div>
    </div>

    <div class="stack-grid">
      <div class="stack-card">
        <div class="stack-title">RAG / 检索增强</div>
        <div class="stack-items">
          <div class="stack-item"><strong>向量数据库</strong><span>Chroma、Milvus、Pinecone、Weaviate</span></div>
          <div class="stack-item"><strong>检索策略</strong><span>语义检索、混合检索（关键词+向量）、重排序</span></div>
          <div class="stack-item"><strong>知识库</strong><span>预案/规程/历史战报/对象关系库</span></div>
          <div class="stack-item"><strong>引用标注</strong><span>检索结果引用、来源追溯、置信度</span></div>
        </div>
      </div>
      <div class="stack-card">
        <div class="stack-title">LLM / 大模型</div>
        <div class="stack-items">
          <div class="stack-item"><strong>通用模型</strong><span>GPT-4、Claude、DeepSeek、通义千问</span></div>
          <div class="stack-item"><strong>工具调用</strong><span>Function Calling、Structured Output、ReAct</span></div>
          <div class="stack-item"><strong>提示工程</strong><span>Few-shot、Chain-of-Thought、角色设定</span></div>
          <div class="stack-item"><strong>降级策略</strong><span>无 Key 时规则式编排、模型失败回退</span></div>
        </div>
      </div>
      <div class="stack-card">
        <div class="stack-title">编排框架</div>
        <div class="stack-items">
          <div class="stack-item"><strong>LangChain</strong><span>工具链、Agent、Memory、Streaming</span></div>
          <div class="stack-item"><strong>AutoGen</strong><span>多智能体协作、角色分工</span></div>
          <div class="stack-item"><strong>Semantic Kernel</strong><span>插件化、规划器、执行器</span></div>
          <div class="stack-item"><strong>自定义编排</strong><span>状态机、工作流引擎集成</span></div>
        </div>
      </div>
      <div class="stack-card">
        <div class="stack-title">工具 / 能力</div>
        <div class="stack-items">
          <div class="stack-item"><strong>query_risk_topn</strong><span>查询 TopN 风险点位</span></div>
          <div class="stack-item"><strong>get_object_state</strong><span>获取对象状态快照</span></div>
          <div class="stack-item"><strong>create_task_pack</strong><span>任务包编排（结构化输出）</span></div>
          <div class="stack-item"><strong>trigger_workflow</strong><span>触发工作流派单 API</span></div>
        </div>
      </div>
    </div>

    <div class="ont-grid">
      <div class="ont-card">
        <div class="ont-title">工具配置</div>
        <div class="ont-desc muted">配置智能体可调用的工具（API、函数、服务）</div>
        <div class="ont-form">
          <div class="form-row">
            <label>工具名称</label>
            <input v-model="toolName" placeholder="如 query_risk_topn" />
          </div>
          <div class="form-row">
            <label>工具类型</label>
            <select v-model="toolType">
              <option>API 调用</option>
              <option>函数调用</option>
              <option>RAG 检索</option>
              <option>工作流触发</option>
            </select>
          </div>
          <div class="form-row">
            <label>描述</label>
            <textarea v-model="toolDesc" rows="2" placeholder="工具功能说明，用于 LLM 理解何时调用"></textarea>
          </div>
          <div class="form-row">
            <label>参数 Schema</label>
            <textarea v-model="toolSchema" rows="2" placeholder="JSON Schema，如：{area_id: string, n: number}"></textarea>
          </div>
          <button @click="addTool">保存到预览（本地）</button>
        </div>
        <div class="ont-list">
          <div v-for="(t, idx) in tools" :key="idx" class="ont-item">
            <div><strong>{{ t.name }}</strong> <span class="muted">({{ t.type }})</span></div>
            <div class="muted">{{ t.desc }}</div>
            <div class="muted small">Schema: {{ t.schema }}</div>
          </div>
          <div v-if="tools.length === 0" class="muted">尚未添加工具（演示本地态）。</div>
        </div>
      </div>

      <div class="ont-card">
        <div class="ont-title">RAG 知识库配置</div>
        <div class="ont-desc muted">配置知识库来源、检索策略、向量化模型</div>
        <div class="ont-form">
          <div class="form-row">
            <label>知识库名称</label>
            <input v-model="ragName" placeholder="如 应急预案库" />
          </div>
          <div class="form-row">
            <label>来源类型</label>
            <select v-model="ragSource">
              <option>预案文档</option>
              <option>规程手册</option>
              <option>历史战报</option>
              <option>对象关系</option>
            </select>
          </div>
          <div class="form-row">
            <label>向量数据库</label>
            <select v-model="ragVectorDB">
              <option>Chroma</option>
              <option>Milvus</option>
              <option>Pinecone</option>
              <option>Weaviate</option>
            </select>
          </div>
          <div class="form-row">
            <label>检索策略</label>
            <textarea v-model="ragStrategy" rows="2" placeholder="如：语义检索 Top5 + 重排序 Top3"></textarea>
          </div>
          <button @click="addRag">保存到预览（本地）</button>
        </div>
        <div class="ont-list">
          <div v-for="(r, idx) in rags" :key="idx" class="ont-item">
            <div><strong>{{ r.name }}</strong> <span class="muted">({{ r.source }})</span></div>
            <div class="muted">向量库：{{ r.vectorDB }}｜策略：{{ r.strategy }}</div>
          </div>
          <div v-if="rags.length === 0" class="muted">尚未添加知识库（演示本地态）。</div>
        </div>
      </div>

      <div class="ont-card">
        <div class="ont-title">任务包模板</div>
        <div class="ont-desc muted">配置任务包模板（owner_org/SLA/required_evidence 等字段规则）</div>
        <div class="ont-form">
          <div class="form-row">
            <label>模板名称</label>
            <input v-model="taskTemplateName" placeholder="如 封控任务模板" />
          </div>
          <div class="form-row">
            <label>任务类型</label>
            <select v-model="taskTemplateType">
              <option>现场巡查</option>
              <option>封控准备</option>
              <option>泵站启停</option>
              <option>联动处置</option>
            </select>
          </div>
          <div class="form-row">
            <label>默认责任单位</label>
            <select v-model="taskTemplateOwner">
              <option>区排水</option>
              <option>交警</option>
              <option>消防</option>
              <option>应急管理</option>
              <option>市政</option>
              <option>水务</option>
              <option>气象</option>
              <option>交通</option>
            </select>
          </div>
          <div class="form-row">
            <label>默认 SLA（分钟）</label>
            <input v-model="taskTemplateSla" placeholder="如 30" />
          </div>
          <div class="form-row">
            <label>必传证据</label>
            <textarea v-model="taskTemplateEvidence" rows="2" placeholder="如：定位, 照片, 视频"></textarea>
          </div>
          <div class="form-row">
            <label>需审批</label>
            <select v-model="taskTemplateApproval">
              <option>是</option>
              <option>否</option>
            </select>
          </div>
          <button @click="addTaskTemplate">保存到预览（本地）</button>
        </div>
        <div class="ont-list">
          <div v-for="(tt, idx) in taskTemplates" :key="idx" class="ont-item">
            <div><strong>{{ tt.name }}</strong> <span class="muted">({{ tt.type }})</span></div>
            <div class="muted">责任单位：{{ tt.owner }}｜SLA：{{ tt.sla }}分钟｜需审批：{{ tt.approval }}</div>
            <div class="muted small">证据：{{ tt.evidence }}</div>
          </div>
          <div v-if="taskTemplates.length === 0" class="muted">尚未添加模板（演示本地态）。</div>
        </div>
      </div>
    </div>
  </section>
</main>

<main v-else-if="activePage === 'workflow'" class="grid single">
  <section class="card wide">
    <h3>执行闭环（工作流 L5 - 1.7/1.9.5）</h3>
    <p class="muted">说明：当前演示页不变，本页用于展示执行闭环/工作流层的技术方案与业务节点流程。</p>
    
    <div class="flow-diagram">
      <div class="flow-title">业务流程：任务包接收 → 任务分发 → 执行跟踪 → 证据收集 → 完成确认 → 战报生成</div>
      <div class="flow-steps">
        <div class="flow-step">
          <div class="step-num">1</div>
          <div class="step-content">
            <div class="step-title">任务包接收</div>
            <div class="step-desc">接收智能体下发的 TaskPack（含 tasks[]、owner_org、SLA、required_evidence）</div>
            <div class="step-agent muted small">工作流功能：任务包解析、状态初始化、SLA 计时启动</div>
          </div>
        </div>
        <div class="flow-arrow">→</div>
        <div class="flow-step">
          <div class="step-num">2</div>
          <div class="step-content">
            <div class="step-title">任务分发</div>
            <div class="step-desc">按 owner_org 分发给责任单位/人员，发送通知（短信/APP/系统内）</div>
            <div class="step-agent muted small">工作流功能：路由规则、通知渠道、分派策略（轮询/负载均衡）</div>
          </div>
        </div>
        <div class="flow-arrow">→</div>
        <div class="flow-step">
          <div class="step-num">3</div>
          <div class="step-content">
            <div class="step-title">执行跟踪</div>
            <div class="step-desc">实时跟踪任务状态（待处理/进行中/待审核/已完成），SLA 超时告警</div>
            <div class="step-agent muted small">工作流功能：状态机流转、超时检测、告警推送、进度更新</div>
          </div>
        </div>
        <div class="flow-arrow">→</div>
        <div class="flow-step">
          <div class="step-num">4</div>
          <div class="step-content">
            <div class="step-title">证据收集</div>
            <div class="step-desc">收集 required_evidence（定位/照片/视频/签名），校验完整性</div>
            <div class="step-agent muted small">工作流功能：文件上传、格式校验、完整性检查、存储归档</div>
          </div>
        </div>
        <div class="flow-arrow">→</div>
        <div class="flow-step">
          <div class="step-num">5</div>
          <div class="step-content">
            <div class="step-title">完成确认</div>
            <div class="step-desc">执行人提交完成，需审批的任务触发审批流程，审批通过后标记完成</div>
            <div class="step-agent muted small">工作流功能：审批流程引擎、多级审批、会签/或签、驳回重办</div>
          </div>
        </div>
        <div class="flow-arrow">→</div>
        <div class="flow-step">
          <div class="step-num">6</div>
          <div class="step-content">
            <div class="step-title">战报生成</div>
            <div class="step-desc">生成 TimelineEvent（incident_created/alert_event/task_completed），更新对象状态</div>
            <div class="step-agent muted small">工作流功能：事件聚合、时间线构建、状态快照、数据回写</div>
          </div>
        </div>
      </div>
    </div>

    <div class="stack-grid">
      <div class="stack-card">
        <div class="stack-title">工作流引擎</div>
        <div class="stack-items">
          <div class="stack-item"><strong>Camunda</strong><span>BPMN 2.0 标准、流程建模、任务分配</span></div>
          <div class="stack-item"><strong>Zeebe</strong><span>云原生、高并发、分布式编排</span></div>
          <div class="stack-item"><strong>Conductor</strong><span>Netflix 开源、任务编排、重试机制</span></div>
          <div class="stack-item"><strong>Airflow</strong><span>DAG 编排、定时调度、依赖管理</span></div>
        </div>
      </div>
      <div class="stack-card">
        <div class="stack-title">状态机 / 流程</div>
        <div class="stack-items">
          <div class="stack-item"><strong>状态定义</strong><span>待处理 → 进行中 → 待审核 → 已完成 / 已驳回</span></div>
          <div class="stack-item"><strong>流转规则</strong><span>条件分支、并行网关、事件网关、子流程</span></div>
          <div class="stack-item"><strong>超时处理</strong><span>SLA 计时、超时告警、自动升级、超时重派</span></div>
          <div class="stack-item"><strong>异常处理</strong><span>重试策略、失败回退、补偿事务、人工介入</span></div>
        </div>
      </div>
      <div class="stack-card">
        <div class="stack-title">通知 / 消息</div>
        <div class="stack-items">
          <div class="stack-item"><strong>通知渠道</strong><span>短信、APP 推送、系统内消息、邮件</span></div>
          <div class="stack-item"><strong>消息队列</strong><span>RabbitMQ、Kafka、Redis Streams</span></div>
          <div class="stack-item"><strong>模板引擎</strong><span>消息模板、变量替换、多语言支持</span></div>
          <div class="stack-item"><strong>送达确认</strong><span>已读回执、送达状态、重试机制</span></div>
        </div>
      </div>
      <div class="stack-card">
        <div class="stack-title">审批 / 会签</div>
        <div class="stack-items">
          <div class="stack-item"><strong>审批流程</strong><span>单级/多级审批、会签/或签、条件审批</span></div>
          <div class="stack-item"><strong>审批人</strong><span>固定审批人、动态审批人、代理审批</span></div>
          <div class="stack-item"><strong>审批动作</strong><span>同意/驳回/转交/加签/撤回</span></div>
          <div class="stack-item"><strong>审批记录</strong><span>审批历史、意见记录、时间戳、签名</span></div>
        </div>
      </div>
      <div class="stack-card">
        <div class="stack-title">证据 / 附件</div>
        <div class="stack-items">
          <div class="stack-item"><strong>文件存储</strong><span>对象存储（OSS/S3）、CDN 加速、版本管理</span></div>
          <div class="stack-item"><strong>文件类型</strong><span>图片、视频、文档、定位、签名</span></div>
          <div class="stack-item"><strong>校验规则</strong><span>格式校验、大小限制、完整性检查、病毒扫描</span></div>
          <div class="stack-item"><strong>归档策略</strong><span>冷热分离、长期归档、合规保留</span></div>
        </div>
      </div>
      <div class="stack-card">
        <div class="stack-title">数据回写</div>
        <div class="stack-items">
          <div class="stack-item"><strong>TimelineEvent</strong><span>事件时间线、类型分类、载荷存储</span></div>
          <div class="stack-item"><strong>ObjectState</strong><span>对象状态快照、版本追溯、历史回放</span></div>
          <div class="stack-item"><strong>指标统计</strong><span>任务完成率、SLA 达成率、响应时间</span></div>
          <div class="stack-item"><strong>战报生成</strong><span>事件聚合、时间线构建、报告导出</span></div>
        </div>
      </div>
    </div>

    <div class="ont-grid">
      <div class="ont-card">
        <div class="ont-title">工作流定义</div>
        <div class="ont-desc muted">定义工作流模板（BPMN/JSON/YAML），包含节点、流转条件、超时规则</div>
        <div class="ont-form">
          <div class="form-row">
            <label>流程名称</label>
            <input v-model="workflowName" placeholder="如 封控任务流程" />
          </div>
          <div class="form-row">
            <label>流程类型</label>
            <select v-model="workflowType">
              <option>任务执行流程</option>
              <option>审批流程</option>
              <option>事件响应流程</option>
              <option>数据采集流程</option>
            </select>
          </div>
          <div class="form-row">
            <label>节点定义</label>
            <textarea v-model="workflowNodes" rows="3" placeholder="如：接收 → 分发 → 执行 → 审核 → 完成"></textarea>
          </div>
          <div class="form-row">
            <label>超时规则（分钟）</label>
            <input v-model="workflowTimeout" placeholder="如 30" />
          </div>
          <div class="form-row">
            <label>重试策略</label>
            <textarea v-model="workflowRetry" rows="2" placeholder="如：失败重试3次，间隔5分钟"></textarea>
          </div>
          <button @click="addWorkflow">保存到预览（本地）</button>
        </div>
        <div class="ont-list">
          <div v-for="(w, idx) in workflows" :key="idx" class="ont-item">
            <div><strong>{{ w.name }}</strong> <span class="muted">({{ w.type }})</span></div>
            <div class="muted">节点：{{ w.nodes }}｜超时：{{ w.timeout }}分钟</div>
            <div class="muted small">重试：{{ w.retry }}</div>
          </div>
          <div v-if="workflows.length === 0" class="muted">尚未添加工作流（演示本地态）。</div>
        </div>
      </div>

      <div class="ont-card">
        <div class="ont-title">通知配置</div>
        <div class="ont-desc muted">配置通知渠道、模板、触发条件</div>
        <div class="ont-form">
          <div class="form-row">
            <label>通知名称</label>
            <input v-model="notificationName" placeholder="如 任务分派通知" />
          </div>
          <div class="form-row">
            <label>通知渠道</label>
            <select v-model="notificationChannel">
              <option>短信</option>
              <option>APP 推送</option>
              <option>系统内消息</option>
              <option>邮件</option>
            </select>
          </div>
          <div class="form-row">
            <label>触发条件</label>
            <select v-model="notificationTrigger">
              <option>任务分派时</option>
              <option>SLA 超时前</option>
              <option>任务完成时</option>
              <option>审批待处理时</option>
            </select>
          </div>
          <div class="form-row">
            <label>消息模板</label>
            <textarea v-model="notificationTemplate" rows="3" placeholder="如：您有新的任务待处理：{task_name}，请在{timeout}分钟内完成"></textarea>
          </div>
          <button @click="addNotification">保存到预览（本地）</button>
        </div>
        <div class="ont-list">
          <div v-for="(n, idx) in notifications" :key="idx" class="ont-item">
            <div><strong>{{ n.name }}</strong> <span class="muted">({{ n.channel }})</span></div>
            <div class="muted">触发：{{ n.trigger }}</div>
            <div class="muted small">模板：{{ n.template }}</div>
          </div>
          <div v-if="notifications.length === 0" class="muted">尚未添加通知配置（演示本地态）。</div>
        </div>
      </div>

      <div class="ont-card">
        <div class="ont-title">审批流程配置</div>
        <div class="ont-desc muted">配置审批流程（审批人、审批规则、审批动作）</div>
        <div class="ont-form">
          <div class="form-row">
            <label>审批流程名称</label>
            <input v-model="approvalName" placeholder="如 高风险任务审批" />
          </div>
          <div class="form-row">
            <label>审批类型</label>
            <select v-model="approvalType">
              <option>单级审批</option>
              <option>多级审批</option>
              <option>会签</option>
              <option>或签</option>
            </select>
          </div>
          <div class="form-row">
            <label>审批人</label>
            <textarea v-model="approvalUsers" rows="2" placeholder="如：部门主管, 分管领导"></textarea>
          </div>
          <div class="form-row">
            <label>审批规则</label>
            <textarea v-model="approvalRule" rows="2" placeholder="如：高风险任务需部门主管+分管领导会签"></textarea>
          </div>
          <div class="form-row">
            <label>超时处理</label>
            <select v-model="approvalTimeout">
              <option>自动通过</option>
              <option>自动驳回</option>
              <option>升级审批</option>
              <option>保持待处理</option>
            </select>
          </div>
          <button @click="addApproval">保存到预览（本地）</button>
        </div>
        <div class="ont-list">
          <div v-for="(a, idx) in approvals" :key="idx" class="ont-item">
            <div><strong>{{ a.name }}</strong> <span class="muted">({{ a.type }})</span></div>
            <div class="muted">审批人：{{ a.users }}｜超时：{{ a.timeout }}</div>
            <div class="muted small">规则：{{ a.rule }}</div>
          </div>
          <div v-if="approvals.length === 0" class="muted">尚未添加审批流程（演示本地态）。</div>        </div>
      </div>
    </div>
  </section>
</main>

<main v-else-if="activePage === 'report'" class="grid single">
  <section class="card wide">
    <h3>战报与追溯（L6 - 1.9.6/1.4.6）</h3>
    <p class="muted">说明：当前演示页不变，本页用于展示战报生成与追溯层的技术方案与业务节点流程，每个节点的处理步骤可直接查看。</p>
    
    <div class="flow-diagram">
      <div class="flow-title">业务流程：事件聚合 → 时间线构建 → 指标计算 → 状态追溯 → 报告生成 → 可视化展示</div>
      <div class="flow-steps">
        <div class="flow-step">
          <div class="step-num">1</div>
          <div class="step-content">
            <div class="step-title">事件聚合</div>
            <div class="step-desc">收集 TimelineEvent（incident_created/alert_event/task_completed/state_changed），按 incident_id 分组</div>
            <div class="step-agent muted small">处理步骤：</div>
            <div class="step-steps">
              <div class="step-step-item">① 查询 TimelineEvent 表，按 incident_id 过滤</div>
              <div class="step-step-item">② 按 created_at 时间排序</div>
              <div class="step-step-item">③ 按事件类型分类（创建/告警/任务/状态变更）</div>
              <div class="step-step-item">④ 构建事件列表，保留 payload 完整信息</div>
            </div>
          </div>
        </div>
        <div class="flow-arrow">→</div>
        <div class="flow-step">
          <div class="step-num">2</div>
          <div class="step-content">
            <div class="step-title">时间线构建</div>
            <div class="step-desc">按时间顺序组织事件，生成时间线视图（时间轴/里程碑/关键节点）</div>
            <div class="step-agent muted small">处理步骤：</div>
            <div class="step-steps">
              <div class="step-step-item">① 按 created_at 排序所有事件</div>
              <div class="step-step-item">② 识别关键里程碑（事件创建、首个告警、任务完成）</div>
              <div class="step-step-item">③ 计算事件间隔时间（duration）</div>
              <div class="step-step-item">④ 构建时间线 JSON 结构（时间点、事件类型、描述、关联对象）</div>
            </div>
          </div>
        </div>
        <div class="flow-arrow">→</div>
        <div class="flow-step">
          <div class="step-num">3</div>
          <div class="step-content">
            <div class="step-title">指标计算</div>
            <div class="step-desc">计算关键指标（任务完成率、SLA 达成率、响应时间、处置时长）</div>
            <div class="step-agent muted small">处理步骤：</div>
            <div class="step-steps">
              <div class="step-step-item">① 统计任务总数、已完成数、超时数</div>
              <div class="step-step-item">② 计算完成率 = 已完成数 / 总数 × 100%</div>
              <div class="step-step-item">③ 计算 SLA 达成率 = (总数 - 超时数) / 总数 × 100%</div>
              <div class="step-step-item">④ 计算平均响应时间 = Σ(任务开始时间 - 分派时间) / 任务数</div>
              <div class="step-step-item">⑤ 计算平均处置时长 = Σ(任务完成时间 - 任务开始时间) / 任务数</div>
            </div>
          </div>
        </div>
        <div class="flow-arrow">→</div>
        <div class="flow-step">
          <div class="step-num">4</div>
          <div class="step-content">
            <div class="step-title">状态追溯</div>
            <div class="step-desc">追溯对象状态变化历史（ObjectState 快照版本、状态回放、变更原因）</div>
            <div class="step-agent muted small">处理步骤：</div>
            <div class="step-steps">
              <div class="step-step-item">① 查询 ObjectState 表，按 object_id 过滤</div>
              <div class="step-step-item">② 按 updated_at 排序，获取状态快照序列</div>
              <div class="step-step-item">③ 对比相邻快照，识别状态变更（attrs/features 差异）</div>
              <div class="step-step-item">④ 关联 TimelineEvent，找出触发状态变更的事件</div>
              <div class="step-step-item">⑤ 构建状态变更链（时间点、变更前状态、变更后状态、触发事件）</div>
            </div>
          </div>
        </div>
        <div class="flow-arrow">→</div>
        <div class="flow-step">
          <div class="step-num">5</div>
          <div class="step-content">
            <div class="step-title">报告生成</div>
            <div class="step-desc">生成结构化战报（事件标题、时间线、指标、状态追溯、附件链接）</div>
            <div class="step-agent muted small">处理步骤：</div>
            <div class="step-steps">
              <div class="step-step-item">① 组装事件基本信息（incident_id、标题、创建时间、状态）</div>
              <div class="step-step-item">② 嵌入时间线数据（事件列表、里程碑）</div>
              <div class="step-step-item">③ 嵌入指标数据（完成率、SLA 达成率、响应时间、处置时长）</div>
              <div class="step-step-item">④ 嵌入状态追溯数据（对象状态变更链）</div>
              <div class="step-step-item">⑤ 生成报告 JSON/PDF/HTML 格式</div>
            </div>
          </div>
        </div>
        <div class="flow-arrow">→</div>
        <div class="flow-step">
          <div class="step-num">6</div>
          <div class="step-content">
            <div class="step-title">可视化展示</div>
            <div class="step-desc">前端渲染时间线、指标图表、状态变化曲线、交互式追溯</div>
            <div class="step-agent muted small">处理步骤：</div>
            <div class="step-steps">
              <div class="step-step-item">① 渲染时间线组件（垂直时间轴、事件卡片、里程碑标记）</div>
              <div class="step-step-item">② 渲染指标卡片（完成率、SLA 达成率、响应时间、处置时长）</div>
              <div class="step-step-item">③ 渲染状态追溯视图（状态快照列表、变更对比、触发事件）</div>
              <div class="step-step-item">④ 支持交互（点击事件查看详情、点击状态快照查看完整数据）</div>
              <div class="step-step-item">⑤ 支持导出（PDF、Excel、JSON）</div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="stack-grid">
      <div class="stack-card">
        <div class="stack-title">时间线存储</div>
        <div class="stack-items">
          <div class="stack-item"><strong>TimelineEvent</strong><span>事件表（id、incident_id、type、payload、created_at）</span></div>
          <div class="stack-item"><strong>事件类型</strong><span>incident_created、alert_event、task_completed、state_changed</span></div>
          <div class="stack-item"><strong>索引优化</strong><span>incident_id + created_at 联合索引、分区表（按时间）</span></div>
          <div class="stack-item"><strong>查询优化</strong><span>按 incident_id 查询、时间范围过滤、分页加载</span></div>
        </div>
      </div>
      <div class="stack-card">
        <div class="stack-title">状态快照</div>
        <div class="stack-items">
          <div class="stack-item"><strong>ObjectState</strong><span>对象状态表（object_id、attrs、features、dq_tags、updated_at）</span></div>
          <div class="stack-item"><strong>版本管理</strong><span>每次更新保留历史版本、版本号/时间戳标识</span></div>
          <div class="stack-item"><strong>变更检测</strong><span>对比相邻版本、识别字段变更、记录变更原因</span></div>
          <div class="stack-item"><strong>回放能力</strong><span>按时间点查询历史状态、状态回放动画</span></div>
        </div>
      </div>
      <div class="stack-card">
        <div class="stack-title">指标计算</div>
        <div class="stack-items">
          <div class="stack-item"><strong>实时指标</strong><span>任务完成率、SLA 达成率、响应时间、处置时长</span></div>
          <div class="stack-item"><strong>聚合计算</strong><span>SQL 聚合函数、窗口函数、时间序列聚合</span></div>
          <div class="stack-item"><strong>缓存策略</strong><span>Redis 缓存热点指标、定时刷新、失效策略</span></div>
          <div class="stack-item"><strong>指标导出</strong><span>CSV、Excel、JSON、API 接口</span></div>
        </div>
      </div>
      <div class="stack-card">
        <div class="stack-title">报告生成</div>
        <div class="stack-items">
          <div class="stack-item"><strong>模板引擎</strong><span>Jinja2、Handlebars、React Server Components</span></div>
          <div class="stack-item"><strong>格式支持</strong><span>JSON、HTML、PDF（WeasyPrint/Puppeteer）、Excel</span></div>
          <div class="stack-item"><strong>报告内容</strong><span>事件信息、时间线、指标、状态追溯、附件</span></div>
          <div class="stack-item"><strong>异步生成</strong><span>后台任务队列、进度查询、结果存储</span></div>
        </div>
      </div>
      <div class="stack-card">
        <div class="stack-title">可视化组件</div>
        <div class="stack-items">
          <div class="stack-item"><strong>时间线组件</strong><span>垂直时间轴、事件卡片、里程碑、交互式缩放</span></div>
          <div class="stack-item"><strong>图表库</strong><span>ECharts、D3.js、Chart.js、Recharts</span></div>
          <div class="stack-item"><strong>状态追溯</strong><span>状态快照列表、变更对比视图、时间轴回放</span></div>
          <div class="stack-item"><strong>交互功能</strong><span>点击查看详情、筛选过滤、导出下载</span></div>
        </div>
      </div>
      <div class="stack-card">
        <div class="stack-title">追溯查询</div>
        <div class="stack-items">
          <div class="stack-item"><strong>时间范围查询</strong><span>按时间区间查询事件、状态快照</span></div>
          <div class="stack-item"><strong>对象追溯</strong><span>按 object_id 查询状态历史、关联事件</span></div>
          <div class="stack-item"><strong>事件关联</strong><span>事件 → 状态变更、状态变更 → 触发事件</span></div>
          <div class="stack-item"><strong>全文检索</strong><span>Elasticsearch、PostgreSQL 全文索引、关键词搜索</span></div>
        </div>
      </div>
    </div>

    <div class="ont-grid">
      <div class="ont-card">
        <div class="ont-title">时间线配置</div>
        <div class="ont-desc muted">配置时间线展示规则（事件类型过滤、时间范围、里程碑定义）</div>
        <div class="ont-form">
          <div class="form-row">
            <label>时间线名称</label>
            <input v-model="timelineName" placeholder="如 事件处置时间线" />
          </div>
          <div class="form-row">
            <label>事件类型过滤</label>
            <textarea v-model="timelineEventTypes" rows="2" placeholder="如：incident_created, alert_event, task_completed"></textarea>
          </div>
          <div class="form-row">
            <label>里程碑定义</label>
            <textarea v-model="timelineMilestones" rows="2" placeholder="如：事件创建, 首个告警, 任务完成"></textarea>
          </div>
          <div class="form-row">
            <label>时间范围（小时）</label>
            <input v-model="timelineTimeRange" placeholder="如 24" />
          </div>
          <button @click="addTimeline">保存到预览（本地）</button>
        </div>
        <div class="ont-list">
          <div v-for="(t, idx) in timelines" :key="idx" class="ont-item">
            <div><strong>{{ t.name }}</strong></div>
            <div class="muted">事件类型：{{ t.eventTypes }}｜时间范围：{{ t.timeRange }}小时</div>
            <div class="muted small">里程碑：{{ t.milestones }}</div>
          </div>
          <div v-if="timelines.length === 0" class="muted">尚未添加时间线配置（演示本地态）。</div>
        </div>
      </div>

      <div class="ont-card">
        <div class="ont-title">指标配置</div>
        <div class="ont-desc muted">配置指标计算规则（指标定义、计算公式、刷新频率）</div>
        <div class="ont-form">
          <div class="form-row">
            <label>指标名称</label>
            <input v-model="metricName" placeholder="如 任务完成率" />
          </div>
          <div class="form-row">
            <label>指标类型</label>
            <select v-model="metricType">
              <option>完成率</option>
              <option>SLA 达成率</option>
              <option>响应时间</option>
              <option>处置时长</option>
            </select>
          </div>
          <div class="form-row">
            <label>计算公式</label>
            <textarea v-model="metricFormula" rows="2" placeholder="如：已完成数 / 总数 × 100%"></textarea>
          </div>
          <div class="form-row">
            <label>刷新频率（分钟）</label>
            <input v-model="metricRefresh" placeholder="如 5" />
          </div>
          <button @click="addMetric">保存到预览（本地）</button>
        </div>
        <div class="ont-list">
          <div v-for="(m, idx) in metrics" :key="idx" class="ont-item">
            <div><strong>{{ m.name }}</strong> <span class="muted">({{ m.type }})</span></div>
            <div class="muted">公式：{{ m.formula }}｜刷新：{{ m.refresh }}分钟</div>
          </div>
          <div v-if="metrics.length === 0" class="muted">尚未添加指标配置（演示本地态）。</div>
        </div>
      </div>

      <div class="ont-card">
        <div class="ont-title">报告模板</div>
        <div class="ont-desc muted">配置报告模板（模板内容、格式、导出选项）</div>
        <div class="ont-form">
          <div class="form-row">
            <label>模板名称</label>
            <input v-model="reportTemplateName" placeholder="如 事件处置战报模板" />
          </div>
          <div class="form-row">
            <label>报告格式</label>
            <select v-model="reportTemplateFormat">
              <option>JSON</option>
              <option>HTML</option>
              <option>PDF</option>
              <option>Excel</option>
            </select>
          </div>
          <div class="form-row">
            <label>包含内容</label>
            <textarea v-model="reportTemplateContent" rows="3" placeholder="如：事件信息, 时间线, 指标, 状态追溯"></textarea>
          </div>
          <div class="form-row">
            <label>模板文件</label>
            <input v-model="reportTemplateFile" placeholder="如 template.html" />
          </div>
          <button @click="addReportTemplate">保存到预览（本地）</button>
        </div>
        <div class="ont-list">
          <div v-for="(rt, idx) in reportTemplates" :key="idx" class="ont-item">
            <div><strong>{{ rt.name }}</strong> <span class="muted">({{ rt.format }})</span></div>
            <div class="muted">内容：{{ rt.content }}｜模板：{{ rt.file }}</div>
          </div>
          <div v-if="reportTemplates.length === 0" class="muted">尚未添加报告模板（演示本地态）。</div>
        </div>
      </div>
    </div>
  </section>
</main>

<main v-else-if="activePage === 'summary'" class="grid single">
  <section class="card wide">
    <h3>系统架构总结（L0-L6）</h3>
    <p class="muted">本页展示应急安全AI操作系统的完整架构层次（L0-L6），并从数据清单、语义建模、AI应用、飞轮效应、Token消耗等维度进行总结。</p>
    
    <div class="arch-diagram">
      <div class="arch-diagram-title">系统整体架构图</div>
      <div class="arch-layers">
        <div class="arch-layer-item layer-l0">
          <div class="layer-box">
            <div class="layer-id">L0</div>
            <div class="layer-name">界面层</div>
            <div class="layer-desc">Vue3 前端界面<br/>风险热力图、智能体对话、战报展示</div>
          </div>
          <div class="layer-arrow">↓</div>
        </div>
        
        <div class="arch-layer-item layer-l1">
          <div class="layer-box">
            <div class="layer-id">L1</div>
            <div class="layer-name">数据接入与治理</div>
            <div class="layer-desc">Raw/ODS/TSDB 数据存储<br/>数据质量检测、特征提取</div>
          </div>
          <div class="layer-arrow">↓</div>
        </div>
        
        <div class="arch-layer-item layer-l2">
          <div class="layer-box">
            <div class="layer-id">L2</div>
            <div class="layer-name">语义与状态（本体）</div>
            <div class="layer-desc">Neo4j/JanusGraph/RDF<br/>知识图谱、实体关系、状态快照</div>
          </div>
          <div class="layer-arrow">↓</div>
        </div>
        
        <div class="arch-layer-item layer-l3">
          <div class="layer-box">
            <div class="layer-id">L3</div>
            <div class="layer-name">风险推理（模型）</div>
            <div class="layer-desc">XGBoost/LightGBM/LSTM<br/>风险评分、置信度、解释因子</div>
          </div>
          <div class="layer-arrow">↓</div>
        </div>
        
        <div class="arch-layer-item layer-l4">
          <div class="layer-box">
            <div class="layer-id">L4</div>
            <div class="layer-name">智能体决策</div>
            <div class="layer-desc">LLM + RAG + Function Calling<br/>任务包编排、责任归属推理</div>
          </div>
          <div class="layer-arrow">↓</div>
        </div>
        
        <div class="arch-layer-item layer-l5">
          <div class="layer-box">
            <div class="layer-id">L5</div>
            <div class="layer-name">执行闭环（工作流）</div>
            <div class="layer-desc">Camunda/Zeebe/Conductor<br/>任务分派、状态跟踪、审批流程</div>
          </div>
          <div class="layer-arrow">↓</div>
        </div>
        
        <div class="arch-layer-item layer-l6">
          <div class="layer-box">
            <div class="layer-id">L6</div>
            <div class="layer-name">战报与追溯</div>
            <div class="layer-desc">TimelineEvent/ObjectState<br/>时间线构建、指标计算、报告生成</div>
          </div>
        </div>
      </div>
      
      <div class="arch-data-flow">
        <div class="flow-title">数据流向</div>
        <div class="flow-items">
          <div class="flow-item">
            <span class="flow-label">数据采集</span>
            <span class="flow-arrow">→</span>
            <span class="flow-label">L1 数据治理</span>
            <span class="flow-arrow">→</span>
            <span class="flow-label">L2 语义建模</span>
            <span class="flow-arrow">→</span>
            <span class="flow-label">L3 风险推理</span>
          </div>
          <div class="flow-item">
            <span class="flow-label">L3 风险评分</span>
            <span class="flow-arrow">→</span>
            <span class="flow-label">L4 智能体决策</span>
            <span class="flow-arrow">→</span>
            <span class="flow-label">L5 工作流执行</span>
            <span class="flow-arrow">→</span>
            <span class="flow-label">L6 战报生成</span>
          </div>
          <div class="flow-item">
            <span class="flow-label">L6 战报数据</span>
            <span class="flow-arrow">↗</span>
            <span class="flow-label">L4 RAG 知识库</span>
            <span class="flow-arrow">↗</span>
            <span class="flow-label">L0 界面展示</span>
          </div>
        </div>
      </div>
      
      <div class="agent-data-detail">
        <div class="detail-title">L4 智能体决策：数据输入与输出详解</div>
        
        <div class="detail-section">
          <div class="detail-subtitle">1. 研判输入数据（从 L3 风险推理层传入）</div>
          <div class="detail-content">
            <div class="data-structure">
              <div class="struct-label">TopN 风险数据（JSON 数组）</div>
              <pre class="code-block">[
  {
    "target_id": "a-001-road-001",      // 目标对象ID
    "area_id": "A-001",                 // 区域ID
    "risk_score": 8.5,                  // 风险分数（0-10）
    "risk_level": "红",                 // 风险等级（红/橙/黄/绿）
    "confidence": 0.85,                 // 置信度（0-1）
    "explain_factors": [                // 解释因子数组
      "雨强上升",
      "水位超限",
      "历史事件"
    ],
    "object_type": "road_segment",      // 对象类型
    "features": {                        // 特征数据
      "rain_now_mmph": 63,              // 当前雨强（mm/h）
      "rain_1h_mm": 120,                // 1小时累计雨量（mm）
      "water_level_mm": 450             // 水位（mm）
    },
    "attrs": {                           // 对象属性
      "name": "路段1",
      "admin_area": "江北新区",
      "location": "106.5,29.5"
    }
  },
  // ... 更多风险点位（TopN，通常取 Top 5-12）
]</pre>
            </div>
          </div>
        </div>
        
        <div class="detail-section">
          <div class="detail-subtitle">2. 传入大模型的数据结构（LLM Prompt）</div>
          <div class="detail-content">
            <div class="data-structure">
              <div class="struct-label">系统提示词（System Prompt）+ 用户消息（User Message）+ RAG 检索结果</div>
              <pre class="code-block">// System Prompt（系统角色设定）
{
  "role": "system",
  "content": "你是暴雨参谋长智能体，负责分析风险数据并生成任务包。
你的职责：
1. 分析 TopN 风险点位数据
2. 检索相关预案/规程/历史战报（RAG）
3. 生成结构化任务包（TaskPack）
4. 推理责任单位（owner_org）
5. 计算合理的 SLA 时限
..."
}

// User Message（用户请求 + TopN 数据）
{
  "role": "user",
  "content": "请研判以下风险点位并给出任务包建议：

风险点位数据：
[
  {
    "target_id": "a-001-road-001",
    "risk_score": 8.5,
    "risk_level": "红",
    "confidence": 0.85,
    "explain_factors": ["雨强上升", "水位超限"],
    "features": {
      "rain_now_mmph": 63,
      "rain_1h_mm": 120,
      "water_level_mm": 450
    },
    "attrs": {
      "name": "路段1",
      "admin_area": "江北新区"
    }
  }
]

请基于以上数据和相关预案，生成任务包。"
}

// RAG 检索结果（检索增强生成）
{
  "rag_results": [
    {
      "source": "应急预案-封控流程",
      "content": "当路段水位超过 400mm 且雨强超过 60mm/h 时，应启动封控预案...",
      "relevance_score": 0.92
    },
    {
      "source": "历史战报-2024-07-15",
      "content": "类似情况曾发生在江北新区路段1，当时采取的措施包括：1. 封控准备 2. 泵站启动...",
      "relevance_score": 0.88
    }
  ]
}</pre>
            </div>
            <div class="data-note">
              <strong>说明：</strong>大模型接收的数据包括：① 系统提示词（角色设定、任务说明、输出格式要求）② 用户消息（包含 TopN 风险数据）③ RAG 检索结果（相关预案/规程/历史战报）。总 Token 数约 2000-5000 tokens。
            </div>
          </div>
        </div>
        
        <div class="detail-section">
          <div class="detail-subtitle">3. 任务包下发输出数据（TaskPack JSON）</div>
          <div class="detail-content">
            <div class="data-structure">
              <div class="struct-label">任务包结构（Function Calling 结构化输出）</div>
              <pre class="code-block">{
  "incident_id": "inc-1766020476806",    // 事件ID（自动生成）
  "title": "江北新区 暴雨内涝处置事件",   // 事件标题
  "created_at": "2025-12-18T01:14:36Z", // 创建时间
  "status": "pending",                   // 状态（pending/processing/completed）
  
  "tasks": [                             // 任务列表
    {
      "task_id": "task-001",              // 任务ID
      "task_type": "封控准备",            // 任务类型
      "target_object_id": "a-001-road-001", // 目标对象ID
      "description": "对路段1进行封控准备，设置警示标志，疏导交通", // 任务描述
      
      "owner_org": "交警",                // 责任单位（智能体推理得出）
      "sla_minutes": 20,                  // SLA 时限（分钟，智能体计算）
      
      "required_evidence": [              // 必传证据
        "定位",
        "照片",
        "视频"
      ],
      
      "need_approval": true,              // 需审批（高风险任务）
      "approval_flow": "高风险任务审批",  // 审批流程名称
      
      "priority": "high",                 // 优先级（high/medium/low）
      "estimated_duration": 15            // 预估时长（分钟）
    },
    {
      "task_id": "task-002",
      "task_type": "泵站启动",
      "target_object_id": "pump-station-001",
      "description": "启动关联泵站，加速排水",
      "owner_org": "区排水",
      "sla_minutes": 15,
      "required_evidence": ["定位", "运行状态"],
      "need_approval": false,
      "priority": "high",
      "estimated_duration": 10
    }
    // ... 更多任务
  ],
  
  "metadata": {                          // 元数据
    "rag_sources": [                     // RAG 引用来源
      "应急预案-封控流程",
      "历史战报-2024-07-15"
    ],
    "reasoning": "基于风险等级'红'、雨强63mm/h、水位450mm，参考历史战报，生成封控和泵站启动任务", // 推理过程
    "confidence": 0.88                    // 任务包置信度
  }
}</pre>
            </div>
            <div class="data-note">
              <strong>说明：</strong>任务包通过 Function Calling 结构化输出，确保格式规范。包含：① 事件基本信息 ② 任务列表（每个任务包含类型、目标、责任单位、SLA、证据要求、审批标志）③ 元数据（RAG 来源、推理过程、置信度）。输出 Token 数约 500-2000 tokens。
            </div>
          </div>
        </div>
        
        <div class="detail-section">
          <div class="detail-subtitle">4. 数据流转过程</div>
          <div class="detail-content">
            <div class="process-flow">
              <div class="process-step">
                <div class="step-num">①</div>
                <div class="step-text">L3 风险推理层输出 TopN 风险数据（risk_score、risk_level、confidence、explain_factors）</div>
              </div>
              <div class="process-arrow">↓</div>
              <div class="process-step">
                <div class="step-num">②</div>
                <div class="step-text">L4 智能体接收 TopN 数据，用户发起研判请求（如"请研判 road-001 并给出任务包建议"）</div>
              </div>
              <div class="process-arrow">↓</div>
              <div class="process-step">
                <div class="step-num">③</div>
                <div class="step-text">L4 RAG 检索：基于风险数据检索相关预案/规程/历史战报（向量检索 Top5，重排序 Top3）</div>
              </div>
              <div class="process-arrow">↓</div>
              <div class="process-step">
                <div class="step-num">④</div>
                <div class="step-text">L4 构建 LLM Prompt：系统提示词 + 用户消息（含 TopN 数据） + RAG 检索结果</div>
              </div>
              <div class="process-arrow">↓</div>
              <div class="process-step">
                <div class="step-num">⑤</div>
                <div class="step-text">L4 调用 LLM（Function Calling）：输入 Prompt，输出结构化 TaskPack JSON</div>
              </div>
              <div class="process-arrow">↓</div>
              <div class="process-step">
                <div class="step-num">⑥</div>
                <div class="step-text">L4 输出 TaskPack：包含 tasks[]、owner_org、SLA、required_evidence、need_approval</div>
              </div>
              <div class="process-arrow">↓</div>
              <div class="process-step">
                <div class="step-num">⑦</div>
                <div class="step-text">L5 工作流层接收 TaskPack，解析任务列表，启动任务分派和状态跟踪</div>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <div class="l4-l5-linkage">
        <div class="linkage-title">L4 智能体决策 ↔ L5 执行闭环：联动关系与节点使用</div>
        
        <div class="linkage-section">
          <div class="linkage-subtitle">1. 数据传递接口</div>
          <div class="linkage-content">
            <div class="linkage-item">
              <div class="item-title">API 接口：任务包下发</div>
              <div class="item-desc">
                <strong>接口路径</strong>：<code>POST /workflow/taskpack</code><br/>
                <strong>请求方式</strong>：HTTP POST<br/>
                <strong>Content-Type</strong>：application/json<br/>
                <strong>调用方</strong>：L4 智能体决策层<br/>
                <strong>接收方</strong>：L5 工作流引擎
              </div>
            </div>
            
            <div class="linkage-item">
              <div class="item-title">请求体结构（TaskPack JSON）</div>
              <pre class="code-block">{
  "incident_id": "inc-1766020476806",
  "title": "江北新区 暴雨内涝处置事件",
  "created_at": "2025-12-18T01:14:36Z",
  "status": "pending",
  "tasks": [
    {
      "task_id": "task-001",
      "task_type": "封控准备",
      "target_object_id": "a-001-road-001",
      "description": "对路段1进行封控准备",
      "owner_org": "交警",
      "sla_minutes": 20,
      "required_evidence": ["定位", "照片", "视频"],
      "need_approval": true,
      "approval_flow": "高风险任务审批",
      "priority": "high"
    }
  ],
  "metadata": {
    "rag_sources": ["应急预案-封控流程"],
    "reasoning": "基于风险等级'红'生成任务包",
    "confidence": 0.88
  }
}</pre>
            </div>
            
            <div class="linkage-item">
              <div class="item-title">响应体结构</div>
              <pre class="code-block">{
  "success": true,
  "taskpack_id": "tp-1766020476806",
  "workflow_instance_id": "wf-instance-001",
  "tasks_created": 2,
  "message": "任务包已成功创建并启动工作流"
}</pre>
            </div>
          </div>
        </div>
        
        <div class="linkage-section">
          <div class="linkage-subtitle">2. 工作流节点使用</div>
          <div class="linkage-content">
            <div class="node-diagram">
              <div class="node-flow">
                <div class="node-item start-node">
                  <div class="node-label">开始节点</div>
                  <div class="node-desc">接收 TaskPack<br/>解析任务列表</div>
                </div>
                <div class="node-arrow">→</div>
                <div class="node-item gateway-node">
                  <div class="node-label">并行网关</div>
                  <div class="node-desc">并行创建多个任务实例<br/>tasks[] 数组遍历</div>
                </div>
                <div class="node-arrow">→</div>
                <div class="node-item task-node">
                  <div class="node-label">任务分派节点</div>
                  <div class="node-desc">根据 owner_org 分派<br/>发送通知（短信/APP）</div>
                </div>
                <div class="node-arrow">→</div>
                <div class="node-item condition-node">
                  <div class="node-label">条件判断</div>
                  <div class="node-desc">判断 need_approval<br/>true → 审批流程<br/>false → 直接执行</div>
                </div>
                <div class="node-arrow">→</div>
                <div class="node-item approval-node">
                  <div class="node-label">审批节点</div>
                  <div class="node-desc">根据 approval_flow<br/>触发审批流程<br/>（多级审批/会签）</div>
                </div>
                <div class="node-arrow">→</div>
                <div class="node-item execution-node">
                  <div class="node-label">执行节点</div>
                  <div class="node-desc">任务执行<br/>收集证据<br/>状态更新</div>
                </div>
                <div class="node-arrow">→</div>
                <div class="node-item timer-node">
                  <div class="node-label">SLA 计时节点</div>
                  <div class="node-desc">启动 SLA 计时<br/>sla_minutes 倒计时<br/>超时告警</div>
                </div>
                <div class="node-arrow">→</div>
                <div class="node-item evidence-node">
                  <div class="node-label">证据校验节点</div>
                  <div class="node-desc">校验 required_evidence<br/>完整性检查<br/>格式验证</div>
                </div>
                <div class="node-arrow">→</div>
                <div class="node-item end-node">
                  <div class="node-label">结束节点</div>
                  <div class="node-desc">任务完成<br/>生成 TimelineEvent<br/>更新 ObjectState</div>
                </div>
              </div>
            </div>
            
            <div class="linkage-item">
              <div class="item-title">节点详细说明</div>
              <div class="node-details">
                <div class="node-detail-item">
                  <strong>开始节点</strong>：接收 L4 下发的 TaskPack，解析 JSON 结构，提取 tasks[] 数组，初始化工作流实例。
                </div>
                <div class="node-detail-item">
                  <strong>并行网关</strong>：遍历 tasks[] 数组，为每个任务创建独立的工作流实例，实现并行处理多个任务。
                </div>
                <div class="node-detail-item">
                  <strong>任务分派节点</strong>：根据 tasks[].owner_org 字段，将任务分派给对应的责任单位，通过短信/APP推送/系统内消息发送通知。
                </div>
                <div class="node-detail-item">
                  <strong>条件判断节点</strong>：检查 tasks[].need_approval 字段，true 则进入审批流程，false 则直接进入执行节点。
                </div>
                <div class="node-detail-item">
                  <strong>审批节点</strong>：根据 tasks[].approval_flow 字段，加载对应的审批流程模板（多级审批/会签/或签），等待审批人处理。
                </div>
                <div class="node-detail-item">
                  <strong>执行节点</strong>：任务执行阶段，责任单位/人员执行任务，实时更新任务状态（待处理→进行中→待审核）。
                </div>
                <div class="node-detail-item">
                  <strong>SLA 计时节点</strong>：根据 tasks[].sla_minutes 字段启动倒计时，超时触发告警，自动升级任务优先级。
                </div>
                <div class="node-detail-item">
                  <strong>证据校验节点</strong>：校验 tasks[].required_evidence 数组中的证据类型是否全部提交，格式是否正确，完整性是否满足要求。
                </div>
                <div class="node-detail-item">
                  <strong>结束节点</strong>：任务完成，生成 TimelineEvent（type: "task_completed"），更新 ObjectState 状态快照，触发 L6 战报生成。
                </div>
              </div>
            </div>
          </div>
        </div>
        
        <div class="linkage-section">
          <div class="linkage-subtitle">3. 状态同步机制</div>
          <div class="linkage-content">
            <div class="sync-flow">
              <div class="sync-item">
                <div class="sync-title">L4 → L5：任务包下发</div>
                <div class="sync-desc">
                  <strong>触发时机</strong>：L4 智能体生成 TaskPack 后立即调用<br/>
                  <strong>数据内容</strong>：完整的 TaskPack JSON（含 tasks[]、owner_org、SLA、required_evidence、need_approval）<br/>
                  <strong>处理方式</strong>：L5 工作流引擎解析 TaskPack，创建工作流实例，启动任务分派
                </div>
              </div>
              
              <div class="sync-item">
                <div class="sync-title">L5 → L4：状态回调（可选）</div>
                <div class="sync-desc">
                  <strong>触发时机</strong>：任务状态变更时（待处理→进行中→已完成）<br/>
                  <strong>数据内容</strong>：任务状态更新通知（task_id、status、updated_at）<br/>
                  <strong>处理方式</strong>：L4 智能体可记录任务执行状态，用于后续优化
                </div>
              </div>
              
              <div class="sync-item">
                <div class="sync-title">L5 → L6：事件生成</div>
                <div class="sync-desc">
                  <strong>触发时机</strong>：任务完成、状态变更、审批通过时<br/>
                  <strong>数据内容</strong>：TimelineEvent（incident_id、type、payload、created_at）<br/>
                  <strong>处理方式</strong>：L6 战报层接收事件，构建时间线，生成战报
                </div>
              </div>
              
              <div class="sync-item">
                <div class="sync-title">L6 → L4：知识库回馈</div>
                <div class="sync-desc">
                  <strong>触发时机</strong>：战报生成后，异步写入知识库<br/>
                  <strong>数据内容</strong>：历史战报文档（事件标题、处置过程、任务执行结果）<br/>
                  <strong>处理方式</strong>：L4 RAG 知识库向量化存储，供后续检索使用
                </div>
              </div>
            </div>
          </div>
        </div>
        
        <div class="linkage-section">
          <div class="linkage-subtitle">4. 关键字段映射关系</div>
          <div class="linkage-content">
            <div class="mapping-table">
              <table class="linkage-table">
                <thead>
                  <tr>
                    <th>L4 智能体决策字段</th>
                    <th>L5 工作流节点使用</th>
                    <th>说明</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td><code>tasks[].task_id</code></td>
                    <td>任务实例ID</td>
                    <td>工作流中每个任务实例的唯一标识</td>
                  </tr>
                  <tr>
                    <td><code>tasks[].task_type</code></td>
                    <td>任务类型节点</td>
                    <td>用于路由到不同的任务处理流程</td>
                  </tr>
                  <tr>
                    <td><code>tasks[].owner_org</code></td>
                    <td>任务分派节点</td>
                    <td>确定任务分派给哪个责任单位</td>
                  </tr>
                  <tr>
                    <td><code>tasks[].sla_minutes</code></td>
                    <td>SLA 计时节点</td>
                    <td>设置任务完成时限，超时触发告警</td>
                  </tr>
                  <tr>
                    <td><code>tasks[].required_evidence</code></td>
                    <td>证据校验节点</td>
                    <td>校验任务完成时必须提交的证据类型</td>
                  </tr>
                  <tr>
                    <td><code>tasks[].need_approval</code></td>
                    <td>条件判断节点</td>
                    <td>决定是否进入审批流程</td>
                  </tr>
                  <tr>
                    <td><code>tasks[].approval_flow</code></td>
                    <td>审批节点</td>
                    <td>指定使用的审批流程模板</td>
                  </tr>
                  <tr>
                    <td><code>tasks[].priority</code></td>
                    <td>优先级队列</td>
                    <td>影响任务分派的优先级顺序</td>
                  </tr>
                  <tr>
                    <td><code>incident_id</code></td>
                    <td>事件关联</td>
                    <td>关联所有任务到同一个事件</td>
                  </tr>
                  <tr>
                    <td><code>metadata.rag_sources</code></td>
                    <td>追溯信息</td>
                    <td>记录任务包生成的依据来源</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
        
        <div class="linkage-section">
          <div class="linkage-subtitle">5. 错误处理与重试机制</div>
          <div class="linkage-content">
            <div class="error-handling">
              <div class="error-item">
                <div class="error-title">L4 调用 L5 失败</div>
                <div class="error-desc">
                  <strong>场景</strong>：L4 调用 <code>POST /workflow/taskpack</code> 失败（网络错误、服务不可用）<br/>
                  <strong>处理</strong>：
                  <ul>
                    <li>L4 本地缓存 TaskPack，标记为"待下发"状态</li>
                    <li>启动重试机制：指数退避重试（1分钟、2分钟、4分钟...）</li>
                    <li>重试 3 次后仍失败，记录错误日志，通知管理员</li>
                    <li>管理员可手动触发重新下发</li>
                  </ul>
                </div>
              </div>
              
              <div class="error-item">
                <div class="error-title">L5 解析 TaskPack 失败</div>
                <div class="error-desc">
                  <strong>场景</strong>：L5 接收到的 TaskPack JSON 格式错误、必填字段缺失<br/>
                  <strong>处理</strong>：
                  <ul>
                    <li>L5 返回 400 Bad Request，包含详细错误信息</li>
                    <li>L4 接收错误响应，记录错误日志</li>
                    <li>L4 可尝试修复数据后重新下发，或通知用户重新生成任务包</li>
                  </ul>
                </div>
              </div>
              
              <div class="error-item">
                <div class="error-title">任务执行超时</div>
                <div class="error-desc">
                  <strong>场景</strong>：任务超过 SLA 时限未完成<br/>
                  <strong>处理</strong>：
                  <ul>
                    <li>L5 SLA 计时节点触发超时事件</li>
                    <li>自动升级：通知上级主管，提升任务优先级</li>
                    <li>生成 TimelineEvent（type: "task_timeout"）</li>
                    <li>L6 战报层记录超时事件，影响 SLA 达成率指标</li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
        </div>
        
        <div class="linkage-section">
          <div class="linkage-subtitle">6. 工作流配置示例（BPMN/JSON）</div>
          <div class="linkage-content">
            <div class="linkage-item">
              <div class="item-title">BPMN 2.0 工作流定义示例</div>
              <div class="item-desc">
                工作流引擎（如 Camunda）使用 BPMN 2.0 标准定义流程，L4 下发的 TaskPack 数据会映射到工作流的流程变量中。
              </div>
              <pre class="code-block">// 工作流流程变量（Process Variables）
{
  "taskpack": {
    "incident_id": "inc-1766020476806",
    "tasks": [...]
  },
  "current_task": {
    "task_id": "task-001",
    "owner_org": "交警",
    "sla_minutes": 20,
    "required_evidence": ["定位", "照片", "视频"],
    "need_approval": true
  }
}

// BPMN 节点配置示例
- 开始节点：接收 taskpack 变量
- 并行网关：遍历 taskpack.tasks[]，为每个任务创建子流程
- 任务分派节点：使用 current_task.owner_org 分派任务
- 条件判断：检查 current_task.need_approval
- SLA 计时节点：设置定时器，时长 = current_task.sla_minutes 分钟
- 证据校验节点：校验 current_task.required_evidence 数组</pre>
            </div>
            
            <div class="linkage-item">
              <div class="item-title">工作流实例创建</div>
              <div class="item-desc">
                当 L4 调用 <code>POST /workflow/taskpack</code> 时，L5 工作流引擎会：
                <ul>
                  <li>解析 TaskPack JSON，提取所有字段</li>
                  <li>创建工作流实例（Workflow Instance），关联 incident_id</li>
                  <li>为每个任务（tasks[]）创建子流程实例</li>
                  <li>将任务字段映射到流程变量（Process Variables）</li>
                  <li>启动工作流执行，进入第一个节点（开始节点）</li>
                </ul>
              </div>
            </div>
          </div>
        </div>
        
        <div class="linkage-section">
          <div class="linkage-subtitle">7. 联动时序图</div>
          <div class="linkage-content">
            <div class="sequence-diagram">
              <pre class="code-block">L4 智能体决策          L5 工作流引擎          L6 战报层
    |                      |                      |
    |--1. POST /workflow/taskpack-->|                      |
    |   (TaskPack JSON)     |                      |
    |                      |--2. 解析 TaskPack    |
    |                      |--3. 创建工作流实例   |
    |                      |--4. 启动任务分派     |
    |                      |                      |
    |<--5. 响应 (taskpack_id)---|                      |
    |                      |                      |
    |                      |--6. 任务状态变更     |
    |                      |--7. 生成 TimelineEvent-->|
    |                      |                      |
    |                      |--8. 任务完成         |
    |                      |--9. 生成 TimelineEvent-->|
    |                      |                      |
    |                      |                      |--10. 构建时间线
    |                      |                      |--11. 生成战报
    |                      |                      |
    |                      |<--12. 战报数据回馈----|
    |                      |                      |
    |--13. RAG 知识库更新--|                      |
    |   (异步)              |                      |</pre>
            </div>
          </div>
        </div>
      </div>
    </div>
    
    <div class="summary-field-help">
      <div class="field-help-title">系统字段说明</div>
      
      <div class="field-help-section">
        <div class="section-title">风险评分相关字段</div>
        <div class="field-help-grid">
          <div class="field-help-item">
            <div class="field-name">risk_score（风险分数）</div>
            <div class="field-desc">数值范围 0-10，表示对象的综合风险评分。分数越高表示风险越大，通常 8-10 为高风险（红），6-8 为中高风险（橙），4-6 为中风险（黄），0-4 为低风险（绿）。由 L3 风险推理模型计算得出。</div>
          </div>
          <div class="field-help-item">
            <div class="field-name">risk_level（风险等级）</div>
            <div class="field-desc">分为四个等级：<span class="level-chip red">红</span>（高风险）、<span class="level-chip orange">橙</span>（中高风险）、<span class="level-chip yellow">黄</span>（中风险）、<span class="level-chip green">绿</span>（低风险）。等级由 risk_score 映射而来，用于快速识别风险程度，便于决策和任务分派。</div>
          </div>
          <div class="field-help-item">
            <div class="field-name">confidence（置信度）</div>
            <div class="field-desc">数值范围 0-1，表示模型对风险评分的置信程度。置信度越高表示模型对评分越有信心，通常基于特征完整性和模型不确定性计算。0.8 以上表示高置信度，0.6-0.8 表示中等置信度，0.6 以下表示低置信度。低置信度时建议人工复核。</div>
          </div>
          <div class="field-help-item">
            <div class="field-name">explain_factors（解释因子）</div>
            <div class="field-desc">字符串数组，列出导致风险评分的主要因素。例如："雨强上升"、"水位超限"、"历史事件"等。这些因子通过 SHAP/LIME 等可解释性方法生成，帮助理解模型决策依据，便于人工验证和决策。</div>
          </div>
        </div>
      </div>

      <div class="field-help-section">
        <div class="section-title">标识字段</div>
        <div class="field-help-grid">
          <div class="field-help-item">
            <div class="field-name">incident_id（事件ID）</div>
            <div class="field-desc">唯一标识一个应急事件的字符串，格式如 "inc-1766020476806"。用于关联该事件的所有时间线事件、任务包、状态变更等数据。一个事件可以包含多个任务包和多个时间线事件。</div>
          </div>
          <div class="field-help-item">
            <div class="field-name">target_id（目标对象ID）</div>
            <div class="field-desc">风险评分的目标对象标识，格式如 "a-001-road-001"。通常由区域ID和对象类型+编号组成，用于唯一标识一个需要评估风险的对象（如路段、泵站等）。</div>
          </div>
          <div class="field-help-item">
            <div class="field-name">object_id（对象ID）</div>
            <div class="field-desc">系统中对象的唯一标识，格式如 "a-002-road-001"。与 target_id 类似，但更通用，用于标识系统中的各种实体（路段、泵站、区域等）。</div>
          </div>
          <div class="field-help-item">
            <div class="field-name">area_id（区域ID）</div>
            <div class="field-desc">地理区域的标识，格式如 "A-001"、"A-002"。用于按区域筛选和展示风险数据，一个区域可以包含多个对象（路段、泵站等）。</div>
          </div>
        </div>
      </div>

      <div class="field-help-section">
        <div class="section-title">任务包相关字段</div>
        <div class="field-help-grid">
          <div class="field-help-item">
            <div class="field-name">TaskPack（任务包）</div>
            <div class="field-desc">由 L4 智能体决策层生成的结构化任务包对象，包含 tasks[]（任务列表）、owner_org（责任单位）、SLA（服务级别协议/时限）、required_evidence（必传证据）、need_approval（需审批标志）等字段。用于将风险研判结果转换为可执行的任务。</div>
          </div>
          <div class="field-help-item">
            <div class="field-name">tasks[]（任务列表）</div>
            <div class="field-desc">任务包中包含的任务数组，每个任务包含 task_id、task_type（任务类型）、target_object_id（目标对象）、owner_org（责任单位）、status（状态）、SLA（时限）等字段。一个任务包可以包含多个任务。</div>
          </div>
          <div class="field-help-item">
            <div class="field-name">owner_org（责任单位）</div>
            <div class="field-desc">负责执行任务的组织单位，如 "交警"、"区排水"、"消防"、"应急管理" 等。由 L4 智能体根据对象类型、风险等级、地理位置推理得出，用于任务分派。</div>
          </div>
          <div class="field-help-item">
            <div class="field-name">SLA（服务级别协议/时限）</div>
            <div class="field-desc">任务完成的时间限制，单位为分钟，如 20、30、60。由 L4 智能体根据风险等级和任务类型计算得出。超过 SLA 时限未完成的任务会触发超时告警。</div>
          </div>
          <div class="field-help-item">
            <div class="field-name">required_evidence（必传证据）</div>
            <div class="field-desc">完成任务必须提交的证据类型列表，如 ["定位", "照片", "视频", "签名"]。由 L4 智能体根据任务类型确定，L5 工作流层会校验证据完整性。</div>
          </div>
          <div class="field-help-item">
            <div class="field-name">need_approval（需审批）</div>
            <div class="field-desc">布尔值，表示任务是否需要审批。高风险动作（如封控、停运、跨部门联动）通常需要审批。需要审批的任务在 L5 工作流层会触发审批流程。</div>
          </div>
        </div>
      </div>

      <div class="field-help-section">
        <div class="section-title">事件和状态字段</div>
        <div class="field-help-grid">
          <div class="field-help-item">
            <div class="field-name">TimelineEvent（时间线事件）</div>
            <div class="field-desc">记录事件时间线的数据表，包含 id（事件ID）、incident_id（关联的事件ID）、type（事件类型）、payload（载荷数据）、created_at（创建时间）等字段。事件类型包括：incident_created（事件创建）、alert_event（告警事件）、task_completed（任务完成）、state_changed（状态变更）。</div>
          </div>
          <div class="field-help-item">
            <div class="field-name">ObjectState（对象状态）</div>
            <div class="field-desc">对象状态的快照表，包含 object_id（对象ID）、object_type（对象类型）、area_id（区域ID）、attrs（属性JSON）、features（特征JSON）、dq_tags（数据质量标签JSON）、updated_at（更新时间）等字段。每次状态更新都会保留历史版本，用于状态追溯。</div>
          </div>
          <div class="field-help-item">
            <div class="field-name">attrs（属性）</div>
            <div class="field-desc">对象的静态属性，以 JSON 格式存储，如 {"name": "路段1", "admin_area": "江北新区", "location": "..."}。包含对象的名称、位置、责任单位等基本信息。</div>
          </div>
          <div class="field-help-item">
            <div class="field-name">features（特征）</div>
            <div class="field-desc">对象的动态特征数据，以 JSON 格式存储，如 {"rain_now_mmph": 63, "rain_1h_mm": 120, "water_level_mm": 450}。这些特征用于 L3 风险推理模型的输入，实时更新。</div>
          </div>
          <div class="field-help-item">
            <div class="field-name">payload（载荷）</div>
            <div class="field-desc">时间线事件的详细数据，以 JSON 格式存储。不同事件类型的 payload 结构不同，如 incident_created 的 payload 包含 {"title": "事件标题"}，alert_event 的 payload 包含 {"level": "红", "reason": "雨强上升"}。</div>
          </div>
        </div>
      </div>

      <div class="field-help-section">
        <div class="section-title">数据质量字段</div>
        <div class="field-help-grid">
          <div class="field-help-item">
            <div class="field-name">dq_tags（数据质量标签）</div>
            <div class="field-desc">数据质量标签，以 JSON 格式存储，如 {"freshness": 0.95, "validity": true, "completeness": 0.9, "accuracy": 0.85}。用于标识数据的质量状况，包括新鲜度（数据时效性）、有效性（数据是否有效）、完整性（数据是否完整）、准确性（数据是否准确）等维度。</div>
          </div>
        </div>
      </div>

      <div class="field-help-section">
        <div class="section-title">时间戳字段</div>
        <div class="field-help-grid">
          <div class="field-help-item">
            <div class="field-name">created_at（创建时间）</div>
            <div class="field-desc">记录创建的时间戳，格式为 ISO 8601 标准时间（带时区），如 "2025-12-18T01:14:36.869407+00:00"。用于时间线排序、时间范围查询、事件间隔计算等。</div>
          </div>
          <div class="field-help-item">
            <div class="field-name">updated_at（更新时间）</div>
            <div class="field-desc">记录最后更新的时间戳，格式与 created_at 相同。用于状态快照的时间排序、状态变更检测、数据新鲜度计算等。</div>
          </div>
        </div>
      </div>
    </div>
    
    <div class="summary-arch">
      <div class="arch-layer">
        <div class="layer-header">
          <span class="layer-label">L0</span>
          <span class="layer-title">界面层</span>
        </div>
        <div class="layer-content">
          <div class="summary-dimension">
            <div class="dim-title">1. 数据清单、数据量</div>
            <div class="dim-content">
              <ul>
                <li><strong>TopN 风险数据</strong>：实时展示 Top 12 风险点位，包含 risk_score、risk_level、confidence、explain_factors</li>
                <li><strong>事件数据</strong>：incident_id、事件标题、创建时间、状态</li>
                <li><strong>任务包数据</strong>：TaskPack 结构（tasks[]、owner_org、SLA、required_evidence）</li>
                <li><strong>战报数据</strong>：时间线事件、指标统计、状态追溯</li>
                <li><strong>数据量</strong>：前端展示数据量约 1-5KB/请求，实时刷新频率 5-30 秒</li>
              </ul>
            </div>
          </div>
          <div class="summary-dimension">
            <div class="dim-title">2. 语义建模的实现、展现</div>
            <div class="dim-content">
              <ul>
                <li><strong>对象关系可视化</strong>：风险点位与区域、路段与泵站的关联关系</li>
                <li><strong>知识图谱示例</strong>：
                  <pre class="graph-example">区域(A-001) --包含--> 路段(road-001)
路段(road-001) --关联--> 泵站(pump-001)
路段(road-001) --触发--> 事件(incident-001)
事件(incident-001) --生成--> 任务包(task-pack-001)</pre>
                </li>
                <li><strong>本体展示</strong>：实体类型（路段、泵站、事件、任务）、关系类型（包含、关联、触发、生成）</li>
              </ul>
            </div>
          </div>
          <div class="summary-dimension">
            <div class="dim-title">3. AI/大模型具体解决的哪些事儿</div>
            <div class="dim-content">
              <ul>
                <li><strong>智能对话</strong>：暴雨参谋长智能体理解用户意图，解析风险研判请求</li>
                <li><strong>任务包生成</strong>：基于风险数据自动生成结构化任务包（责任单位、SLA、证据要求）</li>
                <li><strong>一键派单</strong>：将自然语言指令转换为系统可执行的任务包</li>
              </ul>
            </div>
          </div>
          <div class="summary-dimension">
            <div class="dim-title">4. AI带来的飞轮效应</div>
            <div class="dim-content">
              <ul>
                <li><strong>用户反馈循环</strong>：用户使用智能体 → 系统记录对话数据 → 优化提示词 → 提升准确率</li>
                <li><strong>数据积累</strong>：每次任务执行产生数据 → 丰富训练样本 → 提升模型效果</li>
                <li><strong>知识沉淀</strong>：历史战报积累 → RAG 知识库扩充 → 智能体建议更准确</li>
              </ul>
            </div>
          </div>
          <div class="summary-dimension">
            <div class="dim-title">5. Token的消耗</div>
            <div class="dim-content">
              <ul>
                <li><strong>单次对话</strong>：约 500-2000 tokens（输入：风险数据 + 用户问题，输出：任务包 JSON）</li>
                <li><strong>RAG 检索</strong>：检索 Top5 文档，约 1000-3000 tokens（上下文）</li>
                <li><strong>日均消耗</strong>：假设 100 次对话/天，约 15-50 万 tokens/天</li>
              </ul>
            </div>
          </div>
        </div>
      </div>

      <div class="arch-layer">
        <div class="layer-header">
          <span class="layer-label">L1</span>
          <span class="layer-title">数据接入与治理（1.4 数据设计）</span>
        </div>
        <div class="layer-content">
          <div class="summary-dimension">
            <div class="dim-title">1. 数据清单、数据量</div>
            <div class="dim-content">
              <ul>
                <li><strong>Raw 层</strong>：原始传感器数据（雨量、雷达、水位、泵站、路况），数据量约 10-100 万条/天</li>
                <li><strong>ODS 层</strong>：操作数据存储，清洗后的结构化数据，数据量约 5-50 万条/天</li>
                <li><strong>TSDB 层</strong>：时序数据库（TimescaleDB），存储时间序列特征，数据量约 1000 万条/月</li>
                <li><strong>数据源</strong>：雨量站、雷达站、水位站、泵站、路况传感器，总计约 50-200 个数据源</li>
              </ul>
            </div>
          </div>
          <div class="summary-dimension">
            <div class="dim-title">2. 语义建模的实现、展现</div>
            <div class="dim-content">
              <ul>
                <li><strong>数据血缘</strong>：Raw → ODS → TSDB 的数据流转关系</li>
                <li><strong>DQ 标签</strong>：数据质量标签（freshness、validity、completeness、accuracy）</li>
                <li><strong>知识图谱示例</strong>：
                  <pre class="graph-example">数据源(雨量站-001) --采集--> Raw(rain_raw_001)
Raw(rain_raw_001) --清洗--> ODS(rain_ods_001)
ODS(rain_ods_001) --聚合--> TSDB(rain_tsdb_001)
TSDB(rain_tsdb_001) --特征提取--> 特征(feature_001)</pre>
                </li>
              </ul>
            </div>
          </div>
          <div class="summary-dimension">
            <div class="dim-title">3. AI/大模型具体解决的哪些事儿</div>
            <div class="dim-content">
              <ul>
                <li><strong>数据质量检测</strong>：AI 识别异常数据、缺失值、异常值</li>
                <li><strong>自动数据清洗</strong>：基于规则和模型的数据清洗策略</li>
                <li><strong>特征工程</strong>：自动提取时间序列特征（滑动窗口、统计特征）</li>
              </ul>
            </div>
          </div>
          <div class="summary-dimension">
            <div class="dim-title">4. AI带来的飞轮效应</div>
            <div class="dim-content">
              <ul>
                <li><strong>数据质量提升</strong>：AI 检测异常 → 人工修正 → 模型学习 → 检测更准确</li>
                <li><strong>特征优化</strong>：特征使用反馈 → 优化特征工程 → 提升模型效果</li>
              </ul>
            </div>
          </div>
          <div class="summary-dimension">
            <div class="dim-title">5. Token的消耗</div>
            <div class="dim-content">
              <ul>
                <li><strong>数据质量检测</strong>：少量 Token（主要用于规则配置，非 LLM 调用）</li>
                <li><strong>特征工程</strong>：无 Token 消耗（传统机器学习特征提取）</li>
              </ul>
            </div>
          </div>
        </div>
      </div>

      <div class="arch-layer">
        <div class="layer-header">
          <span class="layer-label">L2</span>
          <span class="layer-title">语义与状态（1.3 本体 Ontology）</span>
        </div>
        <div class="layer-content">
          <div class="summary-dimension">
            <div class="dim-title">1. 数据清单、数据量</div>
            <div class="dim-content">
              <ul>
                <li><strong>实体数据</strong>：路段、泵站、区域、事件等实体，约 1000-5000 个实体</li>
                <li><strong>关系数据</strong>：实体间关系（包含、关联、触发等），约 5000-20000 条关系</li>
                <li><strong>属性数据</strong>：实体属性（名称、位置、责任单位等），约 10-50 个属性/实体</li>
                <li><strong>状态快照</strong>：ObjectState 表，约 10 万条历史状态记录</li>
              </ul>
            </div>
          </div>
          <div class="summary-dimension">
            <div class="dim-title">2. 语义建模的实现、展现</div>
            <div class="dim-content">
              <ul>
                <li><strong>知识图谱</strong>：Neo4j/JanusGraph/TigerGraph 存储实体和关系</li>
                <li><strong>RDF 三元组</strong>：Apache Jena/Fuseki、GraphDB 存储标准语义模型</li>
                <li><strong>知识图谱示例</strong>：
                  <pre class="graph-example">区域(江北新区) --包含--> 路段(road-001)
路段(road-001) --关联--> 泵站(pump-station-001)
路段(road-001) --位于--> 位置(坐标:106.5,29.5)
路段(road-001) --责任单位--> 组织(区排水)
路段(road-001) --触发--> 事件(incident-001)
事件(incident-001) --风险等级--> 风险(红)
风险(红) --置信度--> 置信度(0.85)</pre>
                </li>
                <li><strong>SPARQL 查询</strong>：标准语义查询，如查询"所有高风险路段及其关联泵站"</li>
              </ul>
            </div>
          </div>
          <div class="summary-dimension">
            <div class="dim-title">3. AI/大模型具体解决的哪些事儿</div>
            <div class="dim-content">
              <ul>
                <li><strong>实体识别</strong>：从文本中提取实体（路段、泵站、事件）</li>
                <li><strong>关系抽取</strong>：识别实体间关系（关联、包含、触发）</li>
                <li><strong>语义理解</strong>：理解用户查询意图，转换为 SPARQL 查询</li>
                <li><strong>知识补全</strong>：基于已有知识推理缺失关系</li>
              </ul>
            </div>
          </div>
          <div class="summary-dimension">
            <div class="dim-title">4. AI带来的飞轮效应</div>
            <div class="dim-content">
              <ul>
                <li><strong>知识图谱扩充</strong>：AI 抽取实体关系 → 人工审核 → 图谱扩充 → 抽取更准确</li>
                <li><strong>查询优化</strong>：用户查询 → AI 理解意图 → 优化查询 → 结果更精准</li>
              </ul>
            </div>
          </div>
          <div class="summary-dimension">
            <div class="dim-title">5. Token的消耗</div>
            <div class="dim-content">
              <ul>
                <li><strong>实体识别</strong>：单次约 200-500 tokens（输入文本，输出实体列表）</li>
                <li><strong>关系抽取</strong>：单次约 300-800 tokens（输入实体对，输出关系）</li>
                <li><strong>SPARQL 生成</strong>：单次约 500-1500 tokens（输入自然语言，输出 SPARQL）</li>
                <li><strong>日均消耗</strong>：假设 50 次查询/天，约 5-15 万 tokens/天</li>
              </ul>
            </div>
          </div>
        </div>
      </div>

      <div class="arch-layer">
        <div class="layer-header">
          <span class="layer-label">L3</span>
          <span class="layer-title">风险推理（模型服务 1.9.3）</span>
        </div>
        <div class="layer-content">
          <div class="summary-dimension">
            <div class="dim-title">1. 数据清单、数据量</div>
            <div class="dim-content">
              <ul>
                <li><strong>特征数据</strong>：时间序列特征（rain_now_mmph、rain_1h_mm、water_level_mm 等），约 20-50 个特征/对象</li>
                <li><strong>训练数据</strong>：历史风险事件标注数据，约 1-10 万条样本</li>
                <li><strong>推理数据</strong>：实时特征数据，约 1000-5000 条/次推理</li>
                <li><strong>模型输出</strong>：risk_score（0-10）、risk_level（红/橙/黄/绿）、confidence（0-1）、explain_factors</li>
              </ul>
            </div>
          </div>
          <div class="summary-dimension">
            <div class="dim-title">2. 语义建模的实现、展现</div>
            <div class="dim-content">
              <ul>
                <li><strong>特征关系图</strong>：特征之间的相关性、重要性关系</li>
                <li><strong>知识图谱示例</strong>：
                  <pre class="graph-example">对象(road-001) --特征--> 特征(rain_now_mmph: 63)
对象(road-001) --特征--> 特征(water_level_mm: 450)
特征(rain_now_mmph) --影响--> 风险(risk_score: 8.5)
特征(water_level_mm) --影响--> 风险(risk_score: 8.5)
风险(risk_score: 8.5) --等级--> 风险等级(红)
风险(risk_score: 8.5) --置信度--> 置信度(0.85)
风险(risk_score: 8.5) --解释因子--> 因子(雨强上升, 水位超限)</pre>
                </li>
                <li><strong>SHAP/LIME 解释</strong>：展示每个特征对风险评分的贡献度</li>
              </ul>
            </div>
          </div>
          <div class="summary-dimension">
            <div class="dim-title">3. AI/大模型具体解决的哪些事儿</div>
            <div class="dim-content">
              <ul>
                <li><strong>风险评分</strong>：XGBoost/LightGBM/LSTM 模型预测风险评分</li>
                <li><strong>风险等级分类</strong>：将风险评分映射为红/橙/黄/绿等级</li>
                <li><strong>置信度计算</strong>：基于特征完整性和模型不确定性计算置信度</li>
                <li><strong>解释因子生成</strong>：SHAP/LIME 解释模型决策，生成 explain_factors</li>
                <li><strong>TopN 排序</strong>：按风险评分排序，返回 TopN 高风险对象</li>
              </ul>
            </div>
          </div>
          <div class="summary-dimension">
            <div class="dim-title">4. AI带来的飞轮效应</div>
            <div class="dim-content">
              <ul>
                <li><strong>模型优化</strong>：预测结果 → 实际事件验证 → 模型重训练 → 预测更准确</li>
                <li><strong>特征工程</strong>：模型解释 → 发现重要特征 → 特征优化 → 模型提升</li>
                <li><strong>数据积累</strong>：每次事件产生标注数据 → 训练集扩充 → 模型效果提升</li>
              </ul>
            </div>
          </div>
          <div class="summary-dimension">
            <div class="dim-title">5. Token的消耗</div>
            <div class="dim-content">
              <ul>
                <li><strong>模型推理</strong>：无 Token 消耗（传统机器学习模型，非 LLM）</li>
                <li><strong>解释生成</strong>：少量 Token（如用 LLM 生成自然语言解释，约 100-300 tokens/次）</li>
              </ul>
            </div>
          </div>
        </div>
      </div>

      <div class="arch-layer">
        <div class="layer-header">
          <span class="layer-label">L4</span>
          <span class="layer-title">智能体决策（1.6/1.9.4）</span>
        </div>
        <div class="layer-content">
          <div class="summary-dimension">
            <div class="dim-title">1. 数据清单、数据量</div>
            <div class="dim-content">
              <ul>
                <li><strong>TopN 风险数据</strong>：输入 TopN 风险点位（含 risk_score/level/confidence/explain_factors）</li>
                <li><strong>RAG 知识库</strong>：预案/规程/历史战报文档，约 100-1000 篇文档，向量化后约 10-100 万向量</li>
                <li><strong>任务包数据</strong>：输出 TaskPack（tasks[]、owner_org、SLA、required_evidence、need_approval）</li>
                <li><strong>对话历史</strong>：用户对话记录，约 1000-10000 条/月</li>
              </ul>
            </div>
          </div>
          <div class="summary-dimension">
            <div class="dim-title">2. 语义建模的实现、展现</div>
            <div class="dim-content">
              <ul>
                <li><strong>任务包关系图</strong>：任务包与风险对象、责任单位的关联</li>
                <li><strong>知识图谱示例</strong>：
                  <pre class="graph-example">风险对象(road-001) --触发--> 智能体决策
智能体决策 --检索--> RAG知识库(预案-001)
RAG知识库(预案-001) --引用--> 知识片段(封控流程)
智能体决策 --生成--> 任务包(task-pack-001)
任务包(task-pack-001) --包含--> 任务(task-001: 封控准备)
任务(task-001) --责任单位--> 组织(交警)
任务(task-001) --SLA--> 时限(20分钟)</pre>
                </li>
                <li><strong>RAG 检索链路</strong>：用户问题 → 向量检索 → 文档片段 → 引用标注</li>
              </ul>
            </div>
          </div>
          <div class="summary-dimension">
            <div class="dim-title">3. AI/大模型具体解决的哪些事儿</div>
            <div class="dim-content">
              <ul>
                <li><strong>意图理解</strong>：理解用户自然语言请求（如"请研判 road-006 并给出任务包建议"）</li>
                <li><strong>RAG 检索</strong>：向量检索相关预案/规程/历史战报，形成"有依据的建议"</li>
                <li><strong>任务包编排</strong>：基于风险数据和 RAG 检索结果，生成结构化任务包</li>
                <li><strong>责任归属推理</strong>：根据对象类型、风险等级、地理位置推理责任单位</li>
                <li><strong>SLA 计算</strong>：根据风险等级、任务类型计算合理的 SLA 时限</li>
                <li><strong>结构化输出</strong>：Function Calling 生成标准 JSON 格式任务包</li>
              </ul>
            </div>
          </div>
          <div class="summary-dimension">
            <div class="dim-title">4. AI带来的飞轮效应</div>
            <div class="dim-content">
              <ul>
                <li><strong>知识库扩充</strong>：每次任务执行产生战报 → 知识库扩充 → RAG 检索更准确 → 任务包质量提升</li>
                <li><strong>提示词优化</strong>：任务包执行反馈 → 优化提示词 → 生成更准确 → 执行成功率提升</li>
                <li><strong>责任归属优化</strong>：任务执行结果 → 验证责任单位正确性 → 优化推理规则 → 准确率提升</li>
                <li><strong>对话能力提升</strong>：用户对话数据 → 微调模型 → 理解更准确 → 用户体验提升</li>
              </ul>
            </div>
          </div>
          <div class="summary-dimension">
            <div class="dim-title">5. Token的消耗</div>
            <div class="dim-content">
              <ul>
                <li><strong>单次对话</strong>：约 2000-5000 tokens（输入：TopN 数据 + RAG 检索结果 + 用户问题，输出：任务包 JSON）</li>
                <li><strong>RAG 检索</strong>：检索 Top5 文档，约 2000-5000 tokens（上下文）</li>
                <li><strong>工具调用</strong>：Function Calling 约 500-1000 tokens（函数定义 + 参数）</li>
                <li><strong>日均消耗</strong>：假设 100 次对话/天，约 45-110 万 tokens/天</li>
                <li><strong>月均消耗</strong>：约 1350-3300 万 tokens/月</li>
              </ul>
            </div>
          </div>
        </div>
      </div>

      <div class="arch-layer">
        <div class="layer-header">
          <span class="layer-label">L5</span>
          <span class="layer-title">执行闭环（工作流 1.7/1.9.5）</span>
        </div>
        <div class="layer-content">
          <div class="summary-dimension">
            <div class="dim-title">1. 数据清单、数据量</div>
            <div class="dim-content">
              <ul>
                <li><strong>任务包数据</strong>：接收的 TaskPack，约 100-1000 个/天</li>
                <li><strong>任务数据</strong>：任务列表（tasks[]），约 500-5000 个任务/天</li>
                <li><strong>状态数据</strong>：任务状态（待处理/进行中/待审核/已完成），状态变更记录约 2000-20000 条/天</li>
                <li><strong>证据数据</strong>：上传的附件（定位/照片/视频/签名），约 1000-10000 个文件/天</li>
                <li><strong>审批数据</strong>：审批记录，约 100-1000 条/天</li>
              </ul>
            </div>
          </div>
          <div class="summary-dimension">
            <div class="dim-title">2. 语义建模的实现、展现</div>
            <div class="dim-content">
              <ul>
                <li><strong>工作流关系图</strong>：任务包 → 任务 → 状态 → 审批 → 完成</li>
                <li><strong>知识图谱示例</strong>：
                  <pre class="graph-example">任务包(task-pack-001) --包含--> 任务(task-001)
任务(task-001) --分派--> 责任单位(交警)
任务(task-001) --状态流转--> 状态(待处理 → 进行中 → 已完成)
任务(task-001) --收集--> 证据(定位, 照片)
任务(task-001) --触发--> 审批(approval-001)
审批(approval-001) --审批人--> 人员(部门主管)
审批(approval-001) --结果--> 状态(已通过)</pre>
                </li>
                <li><strong>状态机模型</strong>：任务状态流转图（待处理 → 进行中 → 待审核 → 已完成）</li>
              </ul>
            </div>
          </div>
          <div class="summary-dimension">
            <div class="dim-title">3. AI/大模型具体解决的哪些事儿</div>
            <div class="dim-content">
              <ul>
                <li><strong>智能分派</strong>：根据任务类型、地理位置、负载均衡智能分派任务</li>
                <li><strong>超时预测</strong>：基于历史数据预测任务可能超时，提前告警</li>
                <li><strong>证据校验</strong>：AI 识别证据完整性、格式正确性</li>
                <li><strong>审批路由</strong>：根据任务风险等级、金额等智能路由审批流程</li>
              </ul>
            </div>
          </div>
          <div class="summary-dimension">
            <div class="dim-title">4. AI带来的飞轮效应</div>
            <div class="dim-content">
              <ul>
                <li><strong>分派优化</strong>：任务执行结果 → 验证分派合理性 → 优化分派策略 → 效率提升</li>
                <li><strong>超时预测优化</strong>：实际超时数据 → 训练预测模型 → 预测更准确 → 提前干预</li>
                <li><strong>流程优化</strong>：流程执行数据 → 识别瓶颈 → 优化流程 → 效率提升</li>
              </ul>
            </div>
          </div>
          <div class="summary-dimension">
            <div class="dim-title">5. Token的消耗</div>
            <div class="dim-content">
              <ul>
                <li><strong>智能分派</strong>：少量 Token（如用 LLM 推理分派策略，约 500-1000 tokens/次）</li>
                <li><strong>证据校验</strong>：图像识别无 Token（CV 模型），文本校验约 200-500 tokens/次</li>
                <li><strong>日均消耗</strong>：假设 1000 个任务/天，约 7-15 万 tokens/天</li>
              </ul>
            </div>
          </div>
        </div>
      </div>

      <div class="arch-layer">
        <div class="layer-header">
          <span class="layer-label">L6</span>
          <span class="layer-title">战报与追溯（1.9.6/1.4.6）</span>
        </div>
        <div class="layer-content">
          <div class="summary-dimension">
            <div class="dim-title">1. 数据清单、数据量</div>
            <div class="dim-content">
              <ul>
                <li><strong>TimelineEvent</strong>：事件时间线记录，约 10000-100000 条/月</li>
                <li><strong>ObjectState</strong>：对象状态快照，约 100000-1000000 条/月</li>
                <li><strong>指标数据</strong>：任务完成率、SLA 达成率、响应时间、处置时长，实时计算</li>
                <li><strong>报告数据</strong>：生成的战报（JSON/HTML/PDF），约 100-1000 份/月</li>
              </ul>
            </div>
          </div>
          <div class="summary-dimension">
            <div class="dim-title">2. 语义建模的实现、展现</div>
            <div class="dim-content">
              <ul>
                <li><strong>时间线关系图</strong>：事件时间线、状态变更链</li>
                <li><strong>知识图谱示例</strong>：
                  <pre class="graph-example">事件(incident-001) --时间线--> TimelineEvent(tl-001: 事件创建)
TimelineEvent(tl-001) --触发--> TimelineEvent(tl-002: 告警)
TimelineEvent(tl-002) --关联--> 对象(road-001)
对象(road-001) --状态变更--> ObjectState(state-001: 风险等级 黄→红)
ObjectState(state-001) --触发事件--> TimelineEvent(tl-003: 状态变更)
TimelineEvent(tl-003) --关联--> 任务包(task-pack-001)
任务包(task-pack-001) --完成--> TimelineEvent(tl-004: 任务完成)</pre>
                </li>
                <li><strong>状态追溯链</strong>：对象状态变更的完整链路（时间点、变更前状态、变更后状态、触发事件）</li>
              </ul>
            </div>
          </div>
          <div class="summary-dimension">
            <div class="dim-title">3. AI/大模型具体解决的哪些事儿</div>
            <div class="dim-content">
              <ul>
                <li><strong>事件聚合</strong>：智能识别相关事件，按 incident_id 聚合</li>
                <li><strong>时间线生成</strong>：AI 识别关键里程碑，生成时间线视图</li>
                <li><strong>报告生成</strong>：基于模板和数据结构，生成结构化战报（JSON/HTML/PDF）</li>
                <li><strong>自然语言总结</strong>：LLM 生成事件摘要、处置总结</li>
                <li><strong>智能检索</strong>：基于自然语言的战报检索、事件追溯</li>
              </ul>
            </div>
          </div>
          <div class="summary-dimension">
            <div class="dim-title">4. AI带来的飞轮效应</div>
            <div class="dim-content">
              <ul>
                <li><strong>报告质量提升</strong>：用户反馈 → 优化报告模板 → 报告更清晰 → 用户满意度提升</li>
                <li><strong>知识沉淀</strong>：历史战报积累 → 知识库扩充 → RAG 检索更准确 → 智能体建议更准确</li>
                <li><strong>追溯能力提升</strong>：追溯查询数据 → 优化索引 → 查询更快 → 用户体验提升</li>
              </ul>
            </div>
          </div>
          <div class="summary-dimension">
            <div class="dim-title">5. Token的消耗</div>
            <div class="dim-content">
              <ul>
                <li><strong>报告生成</strong>：单次约 1000-3000 tokens（输入：事件数据 + 时间线 + 指标，输出：报告文本）</li>
                <li><strong>自然语言总结</strong>：单次约 500-2000 tokens（输入：事件数据，输出：摘要）</li>
                <li><strong>智能检索</strong>：单次约 500-1500 tokens（输入：自然语言查询，输出：检索结果）</li>
                <li><strong>日均消耗</strong>：假设 100 次报告生成/天，约 20-65 万 tokens/天</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="summary-total">
      <h4>系统总体 Token 消耗估算</h4>
      <div class="total-content">
        <div class="total-item">
          <strong>L0 界面层</strong>：约 15-50 万 tokens/天
        </div>
        <div class="total-item">
          <strong>L1 数据接入与治理</strong>：约 0-1 万 tokens/天（少量）
        </div>
        <div class="total-item">
          <strong>L2 语义与状态</strong>：约 5-15 万 tokens/天
        </div>
        <div class="total-item">
          <strong>L3 风险推理</strong>：约 0-1 万 tokens/天（少量）
        </div>
        <div class="total-item">
          <strong>L4 智能体决策</strong>：约 45-110 万 tokens/天（主要消耗）
        </div>
        <div class="total-item">
          <strong>L5 执行闭环</strong>：约 7-15 万 tokens/天
        </div>
        <div class="total-item">
          <strong>L6 战报与追溯</strong>：约 20-65 万 tokens/天
        </div>
        <div class="total-summary">
          <strong>系统总计</strong>：约 <span class="highlight">92-257 万 tokens/天</span>，约 <span class="highlight">2760-7710 万 tokens/月</span>
        </div>
      </div>
    </div>
  </section>
</main>

<main v-else-if="activePage === 'ontology'" class="grid single">
  <section class="card wide">
    <h3>本体与语义平台选型（新页面）</h3>
    <p class="muted">说明：当前演示页不变，本页用于展示语义/本体层的技术方案示意。</p>
    <div class="stack-grid">
      <div class="stack-card">
        <div class="stack-title">图数据库 / 知识图谱</div>
        <div class="stack-items">
          <div class="stack-item"><strong>Neo4j</strong><span>关系/路径查询、可视化</span></div>
          <div class="stack-item"><strong>JanusGraph</strong><span>分布式大图，后端可配 Cassandra/HBase</span></div>
          <div class="stack-item"><strong>TigerGraph</strong><span>高性能 OLTP/OLAP 图查询</span></div>
        </div>
      </div>
      <div class="stack-card">
        <div class="stack-title">RDF / 三元组</div>
        <div class="stack-items">
          <div class="stack-item"><strong>Apache Jena / Fuseki</strong><span>SPARQL / RDF 标准语义建模</span></div>
          <div class="stack-item"><strong>GraphDB</strong><span>企业级 RDF 存储与推理</span></div>
          <div class="stack-item"><strong>SPARQL 端点</strong><span>标准查询接口 + 本体约束校验</span></div>
        </div>
      </div>
      <div class="stack-card">
        <div class="stack-title">关系型 + 缓存</div>
        <div class="stack-items">
          <div class="stack-item"><strong>PostgreSQL / Timescale</strong><span>对象快照、时序特征、视图</span></div>
          <div class="stack-item"><strong>Redis</strong><span>热点对象/状态缓存、地理索引</span></div>
          <div class="stack-item"><strong>API 层</strong><span>对象状态查询 / 关系展开 / 版本追溯</span></div>
        </div>
      </div>
    </div>

    <div class="ont-grid">
      <div class="ont-card">
        <div class="ont-title">对象 / 实体管理</div>
        <div class="ont-desc muted">
          更贴近真实：支持实体继承、版本/状态、属性定义（类型/必填/来源/说明）、编辑/删除与筛选（本地演示态）。
        </div>

        <div class="ont-toolbar">
          <input v-model="ontologyEntityFilters.keyword" placeholder="搜索：ID/名称/标签/属性名…" />
          <select v-model="ontologyEntityFilters.category">
            <option value="">全部分类</option>
            <option>实体</option>
            <option>事件</option>
            <option>设施</option>
            <option>组织</option>
            <option>资源</option>
          </select>
          <select v-model="ontologyEntityFilters.status">
            <option value="">全部状态</option>
            <option>草稿</option>
            <option>已发布</option>
            <option>已停用</option>
          </select>
          <button class="btn" @click="startNewOntologyEntity">新建实体</button>
        </div>

        <div v-if="ontologyEntityEditing.open" class="ont-editor">
          <div class="ont-editor-head">
            <strong>{{ ontologyEntityEditing.mode === 'edit' ? '编辑实体' : '新建实体' }}</strong>
            <span class="muted small">（本地演示态，不影响现有页面）</span>
          </div>
        <div class="ont-form">
          <div class="form-row">
              <label>实体ID（唯一）</label>
              <div class="inline-grid">
                <input v-model="ontologyEntityForm.id" placeholder="如 road-segment / entity-001" />
                <button class="btn ghost" @click="regenOntologyEntityId">重新生成</button>
              </div>
          </div>
          <div class="form-row">
            <label>名称</label>
              <input v-model="ontologyEntityForm.label" placeholder="如 路段" />
          </div>
          <div class="form-row">
              <label>分类</label>
              <select v-model="ontologyEntityForm.category">
              <option>实体</option>
              <option>事件</option>
              <option>设施</option>
                <option>组织</option>
              <option>资源</option>
            </select>
          </div>
          <div class="form-row">
              <label>父类 / 继承</label>
              <select v-model="ontologyEntityForm.parent">
                <option value="">无</option>
                <option v-for="e in ontologyEntities" :key="e.id" :value="e.id">{{ e.label }}（{{ e.id }}）</option>
              </select>
          </div>
            <div class="form-row">
              <label>状态</label>
              <select v-model="ontologyEntityForm.status">
                <option>草稿</option>
                <option>已发布</option>
                <option>已停用</option>
              </select>
        </div>
            <div class="form-row">
              <label>版本</label>
              <input v-model="ontologyEntityForm.version" placeholder="如 v1.0.0" />
          </div>
            <div class="form-row">
              <label>维护单位</label>
              <select v-model="ontologyEntityForm.owner_org">
                <option v-for="o in ontologyOwnerOrgOptions" :key="o" :value="o">{{ o }}</option>
              </select>
            </div>
            <div class="form-row">
              <label>标签（逗号分隔）</label>
              <input v-model="ontologyEntityForm.tags" placeholder="如 空间对象, 设施, 资产" />
              <div class="preset-row">
                <span class="muted small">快捷选择：</span>
                <button v-for="t in ontologyTagPresets" :key="t" class="btn tiny ghost" @click="toggleOntologyTag(t)">{{ t }}</button>
                <button class="btn tiny ghost" @click="clearOntologyTags">清空</button>
              </div>
            </div>
            <div class="form-row">
              <label>说明</label>
              <textarea v-model="ontologyEntityForm.desc" rows="2" placeholder="用于说明实体的语义边界、使用场景与注意事项"></textarea>
            </div>
            <div class="form-row">
              <label>属性定义（每行一条：属性名 | 类型 | 必填(0/1) | 来源 | 说明）</label>
              <div class="preset-row">
                <span class="muted small">模板：</span>
                <select v-model="ontologyEntityPropPresetKey">
                  <option value="">选择模板…</option>
                  <option v-for="p in ontologyEntityPropPresets" :key="p.key" :value="p.key">{{ p.label }}</option>
                </select>
                <button class="btn tiny ghost" @click="applyEntityPropPreset('replace')" :disabled="!ontologyEntityPropPresetKey">覆盖填充</button>
                <button class="btn tiny ghost" @click="applyEntityPropPreset('append')" :disabled="!ontologyEntityPropPresetKey">追加</button>
                <button class="btn tiny ghost" @click="applyEntityPropPreset('clear')">清空</button>
              </div>
              <textarea
                v-model="ontologyEntityForm.props_text"
                rows="5"
                placeholder="name | string | 1 | 主数据 | 路段名称&#10;length_m | number | 0 | GIS | 路段长度（米）"
              ></textarea>
            </div>
            <div class="ont-actions">
              <button class="btn primary" @click="saveOntologyEntity">{{ ontologyEntityEditing.mode === 'edit' ? '更新' : '创建' }}</button>
              <button class="btn ghost" @click="cancelOntologyEntityEdit">取消</button>
            </div>
          </div>
        </div>

        <div class="ont-table-wrap">
          <table class="ont-table">
            <thead>
              <tr>
                <th>实体</th>
                <th>分类/继承</th>
                <th>状态/版本</th>
                <th>属性</th>
                <th>更新时间</th>
                <th style="width: 160px;">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="e in filteredOntologyEntities" :key="e.id">
                <td>
                  <div class="cell-title"><strong>{{ e.label }}</strong></div>
                  <div class="muted small">{{ e.id }}<span v-if="e.owner_org"> ｜ {{ e.owner_org }}</span></div>
                  <div v-if="e.tags && e.tags.length" class="chip-row">
                    <span v-for="t in e.tags.slice(0, 3)" :key="t" class="chip">{{ t }}</span>
                    <span v-if="e.tags.length > 3" class="chip muted">+{{ e.tags.length - 3 }}</span>
                  </div>
                </td>
                <td>
                  <div class="chip-row">
                    <span class="chip blue">{{ e.category }}</span>
                    <span v-if="e.parent" class="chip">继承：{{ ontologyEntityLabelById(e.parent) }}</span>
                  </div>
                </td>
                <td>
                  <div class="chip-row">
                    <span class="chip" :class="e.status === '已发布' ? 'green' : e.status === '已停用' ? 'gray' : 'yellow'">{{ e.status }}</span>
                    <span class="chip muted">{{ e.version }}</span>
                  </div>
                </td>
                <td class="muted small">
                  <div>{{ e.props.length }} 项</div>
                  <div v-if="e.props.length" class="muted small">{{ e.props.slice(0, 2).map((p) => p.name).join('、') }}<span v-if="e.props.length > 2">…</span></div>
                </td>
                <td class="muted small">{{ e.updated_at }}</td>
                <td>
                  <div class="btn-row">
                    <button class="btn tiny" @click="editOntologyEntity(e.id)">编辑</button>
                    <button class="btn tiny ghost" @click="duplicateOntologyEntity(e.id)">复制</button>
                    <button class="btn tiny danger" @click="deleteOntologyEntity(e.id)">删除</button>
                  </div>
                </td>
              </tr>
              <tr v-if="filteredOntologyEntities.length === 0">
                <td colspan="6" class="muted small">无匹配实体。你可以点“新建实体”或者调整筛选条件。</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="ont-card">
        <div class="ont-title">关系管理</div>
        <div class="ont-desc muted">
          更贴近真实：关系支持谓词/反向关系、方向、基数（min/max）、约束片段（SHACL 示意）、关系属性（如距离/权重/证据要求）与预览。
        </div>

        <div class="ont-toolbar">
          <input v-model="ontologyRelFilters.keyword" placeholder="搜索：关系ID/名称/谓词/起点/终点…" />
          <select v-model="ontologyRelFilters.status">
            <option value="">全部状态</option>
            <option>草稿</option>
            <option>已发布</option>
            <option>已停用</option>
          </select>
          <button class="btn" @click="startNewOntologyRelation">新建关系</button>
        </div>

        <div v-if="ontologyRelEditing.open" class="ont-editor">
          <div class="ont-editor-head">
            <strong>{{ ontologyRelEditing.mode === 'edit' ? '编辑关系' : '新建关系' }}</strong>
            <span class="muted small">（建议从实体列表里选 Domain/Range）</span>
          </div>
        <div class="ont-form">
          <div class="form-row">
              <label>关系ID（唯一）</label>
              <div class="inline-grid">
                <input v-model="ontologyRelForm.id" placeholder="如 located_in / rel-001" />
                <button class="btn ghost" @click="regenOntologyRelId">重新生成</button>
              </div>
          </div>
          <div class="form-row">
              <label>关系名称</label>
              <input v-model="ontologyRelForm.label" placeholder="如 位于/隶属" />
          </div>
          <div class="form-row">
              <label>谓词（Predicate）</label>
              <input v-model="ontologyRelForm.predicate" placeholder="如 ex:locatedIn / hasOwner / nearBy" />
          </div>
          <div class="form-row">
              <label>起点（Domain）</label>
              <select v-model="ontologyRelForm.from">
                <option v-for="e in ontologyEntities" :key="e.id" :value="e.id">{{ e.label }}（{{ e.id }}）</option>
              </select>
          </div>
            <div class="form-row">
              <label>终点（Range）</label>
              <select v-model="ontologyRelForm.to">
                <option v-for="e in ontologyEntities" :key="e.id" :value="e.id">{{ e.label }}（{{ e.id }}）</option>
              </select>
        </div>
            <div class="form-row">
              <label>方向</label>
              <select v-model="ontologyRelForm.direction">
                <option>单向</option>
                <option>双向</option>
              </select>
          </div>
            <div class="form-row">
              <label>反向关系（可选）</label>
              <input v-model="ontologyRelForm.inverse_of" placeholder="如 contains（对应 located_in 的反向）" />
            </div>
            <div class="form-row">
              <label>基数（Domain→Range）</label>
              <div class="inline-grid">
                <input v-model="ontologyRelForm.card_from_min" placeholder="min" />
                <input v-model="ontologyRelForm.card_from_max" placeholder="max（n 表示不限制）" />
              </div>
            </div>
            <div class="form-row">
              <label>状态 / 版本</label>
              <div class="inline-grid">
                <select v-model="ontologyRelForm.status">
                  <option>草稿</option>
                  <option>已发布</option>
                  <option>已停用</option>
                </select>
                <input v-model="ontologyRelForm.version" placeholder="如 v1.0.0" />
              </div>
            </div>
            <div class="form-row">
              <label>说明</label>
              <textarea v-model="ontologyRelForm.desc" rows="2" placeholder="关系语义边界、适用条件、可选证据等"></textarea>
            </div>
            <div class="form-row">
              <label>关系属性（每行一条：属性名 | 类型 | 必填(0/1) | 来源 | 说明）</label>
              <div class="preset-row">
                <span class="muted small">模板：</span>
                <select v-model="ontologyRelPropPresetKey">
                  <option value="">选择模板…</option>
                  <option v-for="p in ontologyRelPropPresets" :key="p.key" :value="p.key">{{ p.label }}</option>
                </select>
                <button class="btn tiny ghost" @click="applyRelPropPreset('replace')" :disabled="!ontologyRelPropPresetKey">覆盖填充</button>
                <button class="btn tiny ghost" @click="applyRelPropPreset('append')" :disabled="!ontologyRelPropPresetKey">追加</button>
                <button class="btn tiny ghost" @click="applyRelPropPreset('clear')">清空</button>
              </div>
              <div class="preset-row">
                <span class="muted small">快捷：</span>
                <button v-for="p in ontologyRelPropQuickAdd" :key="p.name" class="btn tiny ghost" @click="appendRelPropLine(p)">
                  +{{ p.name }}
                </button>
              </div>
              <textarea v-model="ontologyRelForm.props_text" rows="4" placeholder="distance_m | number | 0 | GIS | 设施间距离（米）"></textarea>
            </div>
            <div class="form-row">
              <label>约束片段（SHACL/规则示意，可选）</label>
              <textarea
                v-model="ontologyRelForm.constraint_shacl"
                rows="4"
                placeholder="ex:RoadSegmentShape a sh:NodeShape ;&#10;  sh:property [ sh:path ex:locatedIn ; sh:class ex:AdminArea ; sh:minCount 1 ] ."
              ></textarea>
            </div>
            <div class="ont-actions">
              <button class="btn primary" @click="saveOntologyRelation">{{ ontologyRelEditing.mode === 'edit' ? '更新' : '创建' }}</button>
              <button class="btn ghost" @click="cancelOntologyRelationEdit">取消</button>
            </div>
          </div>
        </div>

        <div class="ont-split">
          <div class="ont-table-wrap">
            <table class="ont-table">
              <thead>
                <tr>
                  <th>关系</th>
                  <th>Domain → Range</th>
                  <th>约束</th>
                  <th>更新时间</th>
                  <th style="width: 160px;">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="r in filteredOntologyRelations" :key="r.id" @click="selectOntologyRelation(r.id)" :class="selectedOntologyRelId === r.id ? 'row-active' : ''">
                  <td>
                    <div class="cell-title"><strong>{{ r.label }}</strong></div>
                    <div class="muted small">{{ r.id }} ｜ {{ r.predicate }}</div>
                    <div class="chip-row">
                      <span class="chip" :class="r.status === '已发布' ? 'green' : r.status === '已停用' ? 'gray' : 'yellow'">{{ r.status }}</span>
                      <span class="chip muted">{{ r.version }}</span>
                      <span class="chip blue">{{ r.direction }}</span>
                      <span v-if="r.inverse_of" class="chip">inverse: {{ r.inverse_of }}</span>
                    </div>
                  </td>
                  <td class="muted small">
                    <div><strong>{{ ontologyEntityLabelById(r.from) }}</strong> → <strong>{{ ontologyEntityLabelById(r.to) }}</strong></div>
                    <div>{{ r.from }} → {{ r.to }}</div>
                  </td>
                  <td class="muted small">
                    <div>基数：{{ r.card_from_min }}..{{ r.card_from_max }}</div>
                    <div>属性：{{ r.props.length }} 项</div>
                  </td>
                  <td class="muted small">{{ r.updated_at }}</td>
                  <td>
                    <div class="btn-row">
                      <button class="btn tiny" @click.stop="editOntologyRelation(r.id)">编辑</button>
                      <button class="btn tiny ghost" @click.stop="duplicateOntologyRelation(r.id)">复制</button>
                      <button class="btn tiny danger" @click.stop="deleteOntologyRelation(r.id)">删除</button>
                    </div>
                  </td>
                </tr>
                <tr v-if="filteredOntologyRelations.length === 0">
                  <td colspan="5" class="muted small">无匹配关系。你可以点“新建关系”或者调整筛选条件。</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div class="ont-preview">
            <div class="ont-title">关系预览 / 校验</div>
            <div class="ont-preview-actions">
              <button class="btn tiny ghost" @click="ontologyGraphRelayout">重新布局</button>
              <button class="btn tiny ghost" @click="ontologyGraphFit">适配视图</button>
            </div>
            <div class="ont-graph" ref="ontologyGraphRef"></div>
            <div class="muted small">
              <div><strong>选中关系：</strong>{{ selectedOntologyRelId ? selectedOntologyRelId : '（未选择）' }}</div>
              <pre class="graph-example">{{ selectedOntologyRelPreview }}</pre>
              <div class="muted small" v-if="ontologyIssues.length">
                <strong>校验发现：</strong>
                <ul>
                  <li v-for="(it, i) in ontologyIssues.slice(0, 8)" :key="i">{{ it }}</li>
                </ul>
                <div v-if="ontologyIssues.length > 8" class="muted">… 还有 {{ ontologyIssues.length - 8 }} 条</div>
              </div>
              <div class="muted small" v-else>
                <strong>校验发现：</strong>未发现明显问题（本地规则：重复 ID、未知实体引用、基数格式等）。
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="ont-card">
        <div class="ont-title">查询 / 校验（示意）</div>
        <div class="muted small">
          - 图谱：Gremlin / Cypher / GSQL 查询<br />
          - RDF：SPARQL 端点；SHACL/OWL 约束校验<br />
          - 关系型：视图/存储过程/物化视图；Redis 缓存热点对象<br />
          - 可接入：版本/血缘/审计接口（entity_version / relation_version / lineage_refs）
        </div>
      </div>
    </div>
      </section>
    </main>
<!-- 全局：图片大图预览弹框（证据照片等） -->
<div v-if="imagePreview.open" class="img-modal" @click.self="closeImagePreview">
  <div class="img-modal-card" role="dialog" aria-modal="true">
    <div class="img-modal-head">
      <strong>图片预览</strong>
      <button class="btn tiny ghost" @click="closeImagePreview">关闭</button>
    </div>
    <div class="img-modal-body">
      <img :src="imagePreview.src" alt="预览大图" @error="onPreviewImgError" />
    </div>
  </div>
</div>
  </div>
</template>

<script setup lang="ts">
import axios from "axios";
import { ref, computed, onMounted, watch, reactive, nextTick, onBeforeUnmount } from "vue";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import cytoscape from "cytoscape";
import evidencePoliceUrl from "./assets/evidence-police.jpg";
import evidenceDrainageUrl from "./assets/evidence-drainage.jpg";

// 默认走同源代理（见 vite.config.ts 的 server.proxy），避免必须暴露 7000/7001 端口给外部网络
const apiBase = import.meta.env.VITE_API_BASE_URL || "/api";
const agentBase = import.meta.env.VITE_AGENT_BASE_URL || "/agent";

const layerBlocks = [
  {
    name: "L1 数据接入与治理",
    desc: "采集、落库、质量与口径统一",
    nodes: [
      { title: "接入连接器", detail: "雨量/雷达/水位/泵站/路况/事件" },
      { title: "Raw 落地", detail: "原始数据原样落库，保存完整上下文" },
      { title: "ODS 明细", detail: "清洗对齐后的操作型明细层，统一口径" },
      { title: "TSDB 时序", detail: "高频指标/传感器时序存储与查询" },
      { title: "DQ 标签", detail: "完整性/及时性/一致性等质量标记与评分" },
    ],
  },
  {
    name: "L2 语义与状态（本体）",
    desc: "对象/关系/责任归属与状态快照",
    nodes: [
      { title: "实体/关系", detail: "路段/泵站/管网/责任单位/预案等知识" },
      { title: "空间归属", detail: "责任片区/汇水区/行政区/服务范围" },
      { title: "状态快照", detail: "get_object_state 对象当前属性/特征/质量标记" },
    ],
  },
  {
    name: "L3 风险推理（模型）",
    desc: "风险评分 + 解释 + 置信度",
    nodes: [
      { title: "risk_score / level", detail: "按路段/网格输出风险分与等级" },
      { title: "explain_factors", detail: "雨强、水位、泵站工况、低洼地形等解释因子" },
      { title: "confidence", detail: "置信度，反映模型判断确定性" },
      { title: "TopN / 热力图 API", detail: "对上层服务提供热力图与 TopN 接口" },
    ],
  },
  {
    name: "L4 智能体决策",
    desc: "有依据的建议 → 任务包",
    nodes: [
      { title: "RAG 证据检索", detail: "预案/规程/历史战报/对象上下文" },
      {
        title: "任务包编排",
        detail:
          "create_task_pack -> TaskPack/tasks[]，生成派单所需字段：owner_org（责任单位/队伍）、sla_minutes（完成时限）、required_evidence[]（必传证据：定位/照片/视频/测量值等）、need_approval（是否需人审），可选 title/detail",
      },
      {
        title: "下发接口对接",
        detail: "调用工作流派单 API 落库；失败需带错误回传与重试策略（可选人工兜底）",
      },
      { title: "简报草稿（可选）", detail: "draft_briefing 引用证据生成摘要" },
    ],
  },
  {
    name: "L5 执行闭环（工作流）",
    desc: "审批、派单、SLA、回执校验",
    nodes: [
      { title: "风控门禁/人审", detail: "封控/停运/跨部门联动需审核，人工确认后派单" },
      {
        title: "派单与状态机",
        detail:
          "创建任务落库，通知渠道（消息/短信/APP），SLA 计时，超时升级，required_evidence 校验（缺证拒收或补传）",
      },
      { title: "回执校验", detail: "核对证据/状态，更新任务/事件时间线，异常回退或升级" },
      { title: "证据库", detail: "照片/视频/定位等附件存储与引用 ID" },
    ],
  },
  {
    name: "L6 战报与追溯",
    desc: "时间线/指标/依据可追溯",
    nodes: [
      { title: "时间线汇总", detail: "预警/模型/智能体/审批/派单/回执" },
      { title: "指标与战报", detail: "任务完成率、响应时长等导出" },
      { title: "血缘与审计", detail: "lineage/version_refs 支撑依据可追溯" },
    ],
  },
];

const areaId = ref("A-001");
const areaOptions = [
  { label: "海淀区·东北旺（A-001）", value: "A-001" },
  { label: "海淀区·西北旺（A-002）", value: "A-002" },
  { label: "海淀区·上地（A-003）", value: "A-003" },
];
const incidentId = ref<string>("");
const selectedTarget = ref<string>("");

// 展示层：把区域/对象 ID 映射成更贴近真实的中文名称（不影响后端数据与接口参数）
const objectLabelCache = ref<Record<string, { name?: string; admin_area?: string }>>({});
const objectStateCache = ref<Record<string, any>>({});
const loadingObjectState = ref(false);
function areaLabel(area: string | undefined | null) {
  const key = (area || "").trim();
  const table: Record<string, string> = {
    "A-001": "海淀区·东北旺",
    "A-002": "海淀区·西北旺",
    "A-003": "海淀区·上地",
  };
  if (table[key]) return table[key];
  const found = areaOptions.find((a) => a.value === key);
  // label 里可能带括号说明，这里取括号前缀更像“真实名称”
  const raw = found?.label || key || "-";
  return raw.replace(/（.*?）/g, "");
}

function toSeedObjectId(targetId: string, area: string | undefined | null) {
  // 把旧 demo 的 road-008 转为后端种子数据格式：a-001-road-008
  const id = (targetId || "").trim();
  const a = (area || "").trim();
  const m = id.match(/^road-(\d{1,3})$/i);
  if (!m || !a) return null;
  const n = String(parseInt(m[1], 10)).padStart(3, "0");
  return `${a.toLowerCase()}-road-${n}`;
}

function fallbackTargetCn(targetId: string) {
  // 兼容两种格式：a-001-road-008 / road-008
  const m = targetId.match(/(?:^|-)road-(\d{1,3})$/i) || targetId.match(/^road-(\d{1,3})$/i);
  if (m?.[1]) {
    const idx = parseInt(m[1], 10);
    const roadNames = [
      "东北旺西路",
      "东北旺中路",
      "后厂村路",
      "软件园二号路",
      "信息路",
      "上地西路",
      "西北旺东路",
      "永丰路",
    ];
    const rn = roadNames[(idx - 1) % roadNames.length];
    return `${rn}（第${idx}段）`;
  }
  return targetId;
}

function targetLabel(targetId: string | undefined | null, area?: string | undefined | null) {
  const id = (targetId || "").trim();
  if (!id) return "-";
  const seedId = toSeedObjectId(id, area || null);
  const cached = objectLabelCache.value[id] || (seedId ? objectLabelCache.value[seedId] : undefined);
  const name = cached?.name || fallbackTargetCn(id);
  const admin = cached?.admin_area || areaLabel(area || "");
  // 优先展示“行政区/片区 + 对象名称”，更贴近真实；同时保留原 ID 在 title 里
  return admin && admin !== "-" ? `${admin} · ${name}` : name;
}

async function warmObjectLabels(ids: string[], area?: string) {
  const uniq = Array.from(new Set(ids.filter(Boolean)));
  const expanded = uniq.flatMap((id) => {
    const seedId = toSeedObjectId(id, area || null);
    return seedId ? [id, seedId] : [id];
  });
  const need = Array.from(new Set(expanded)).filter((id) => !objectLabelCache.value[id]);
  if (need.length === 0) return;
  await Promise.all(
    need.map(async (id) => {
      try {
        const { data } = await axios.get(`${apiBase}/objects/${id}`);
        objectLabelCache.value[id] = {
          name: data?.attrs?.name,
          admin_area: data?.attrs?.admin_area || (data?.area_id ? areaLabel(data?.area_id) : undefined),
        };
        // 如果是 seedId，也把同一份中文名回写给 road-xxx（便于老数据展示）
        if (area) {
          const reverse = id.match(/^(a-\d{3})-road-(\d{3})$/i);
          if (reverse) {
            const legacy = `road-${parseInt(reverse[2], 10)}`;
            if (!objectLabelCache.value[legacy]) {
              objectLabelCache.value[legacy] = objectLabelCache.value[id];
            }
          }
        }
      } catch {
        // 可能是旧 demo id（如 road-008），忽略即可走 fallback
        objectLabelCache.value[id] = {};
      }
    })
  );
}

async function ensureObjectState(objectId: string) {
  const id = (objectId || "").trim();
  if (!id) return;
  if (objectStateCache.value[id]) return;
  if (loadingObjectState.value) return;
  loadingObjectState.value = true;
  try {
    const { data } = await axios.get(`${apiBase}/objects/${id}`);
    objectStateCache.value[id] = data;
    // 顺便把中文名缓存补齐，便于全局展示统一
    if (data?.attrs?.name || data?.attrs?.admin_area) {
      objectLabelCache.value[id] = {
        name: data?.attrs?.name,
        admin_area: data?.attrs?.admin_area || (data?.area_id ? areaLabel(data?.area_id) : undefined),
      };
    }
  } catch {
    objectStateCache.value[id] = null;
  } finally {
    loadingObjectState.value = false;
  }
}

const activePage = ref<"flow" | "main" | "data" | "model" | "agent" | "workflow" | "report" | "ontology" | "summary">("main");

const flowStep = ref<"map" | "agent" | "tasks" | "ack" | "report">("map");
const creatingIncident = ref(false);
const agentResult = ref<any | null>(null);
const agentResultError = ref<string>("");
const agentConfirmed = ref(false);

function ownerOrgView(org: string | undefined | null) {
  const key = (org || "").trim();
  const table: Record<string, { name: string; desc: string; tone: "blue" | "green" | "orange" | "red" | "gray" }> = {
    "区排水": { name: "区排水抢险队", desc: "巡查积水、疏通排水口、泵站联动与排涝处置", tone: "blue" },
    "交警": { name: "交警交通管制", desc: "封控/绕行引导、交通疏导与现场秩序维护", tone: "orange" },
    // 兼容大模型可能输出的单位（先做展示映射，不影响后端）
    "应急管理": { name: "应急管理指挥", desc: "统筹指挥、会商研判、跨部门协同与资源调度", tone: "red" },
    "消防": { name: "消防救援", desc: "涉险救援、排险处置、人员转移与应急救护协同", tone: "red" },
    "城管": { name: "城管市政", desc: "市政设施巡检、路面障碍清理与现场保障", tone: "green" },
    "供电": { name: "电力抢修", desc: "涉水停电处置、线路巡检与应急供电保障", tone: "gray" },
    "通信": { name: "通信保障", desc: "基站/链路保障、应急通信车与指挥通信保障", tone: "gray" },
  };
  return table[key] || { name: key || "-", desc: "未配置说明（可按需补充映射）", tone: "gray" };
}

function slaView(sla: any) {
  const n = Number(sla);
  if (!Number.isFinite(n) || n <= 0) return "-";
  const level = n <= 20 ? "紧急" : n <= 30 ? "高优先" : n <= 60 ? "常规" : "可延期";
  return `${n} 分钟（${level}）`;
}

function taskStatusView(status: string | undefined | null) {
  const s = (status || "").trim().toLowerCase();
  const table: Record<string, string> = {
    pending: "待执行",
    created: "已创建",
    in_progress: "执行中",
    processing: "执行中",
    running: "执行中",
    done: "已完成",
    completed: "已完成",
    success: "已完成",
    failed: "失败",
    rejected: "已驳回",
    cancelled: "已取消",
    canceled: "已取消",
  };
  return table[s] || (status || "-");
}
const flowProgress = computed(() => {
  return flowStep.value === "map"
    ? 20
    : flowStep.value === "agent"
      ? 40
      : flowStep.value === "tasks"
        ? 60
        : flowStep.value === "ack"
          ? 80
          : 100;
});

async function ensureIncident() {
  if (incidentId.value || creatingIncident.value) return;
  creatingIncident.value = true;
  try {
    await createIncident();
  } finally {
    creatingIncident.value = false;
  }
}

function goStep(step: "map" | "agent" | "tasks" | "ack" | "report") {
  flowStep.value = step;
  if (step !== "map") {
    ensureIncident().catch(() => {});
  }
  // 进入地图页时确保地图刷新（避免切换后地图未渲染）
  if (step === "map") {
    setTimeout(() => renderMap(), 0);
  }
}

function resetFlow() {
  flowStep.value = "map";
  incidentId.value = "";
  selectedTarget.value = "";
  chatInput.value = "请研判并一键下发任务包";
  agentOut.value = "";
  agentResult.value = null;
  agentResultError.value = "";
  agentConfirmed.value = false;
  tasks.value = [];
  reportOut.value = "";
  reportData.value = null;
  setTimeout(() => renderMap(), 0);
}

// 本体管理演示（前端本地状态，不影响现有页面）
type OntologyProp = { name: string; datatype: string; required: boolean; source: string; desc: string };
type OntologyEntity = {
  id: string;
  label: string;
  category: string;
  parent: string;
  status: "草稿" | "已发布" | "已停用";
  version: string;
  owner_org: string;
  tags: string[];
  desc: string;
  props: OntologyProp[];
  created_at: string;
  updated_at: string;
};
type OntologyRelation = {
  id: string;
  label: string;
  predicate: string;
  from: string;
  to: string;
  direction: "单向" | "双向";
  inverse_of: string;
  status: "草稿" | "已发布" | "已停用";
  version: string;
  card_from_min: string;
  card_from_max: string;
  desc: string;
  props: OntologyProp[];
  constraint_shacl: string;
  created_at: string;
  updated_at: string;
};

function tsShort(d = new Date()) {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
function parseTags(s: string) {
  return (s || "")
    .split(",")
    .map((x) => x.trim())
    .filter(Boolean);
}
function parsePropsText(text: string): OntologyProp[] {
  const raw = (text || "").trim();
  if (!raw) return [];
  return raw
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const parts = line.split("|").map((x) => x.trim());
      const [name, datatype, required, source, desc] = parts;
      return {
        name: name || "prop",
        datatype: datatype || "string",
        required: required === "1" || required?.toLowerCase?.() === "true",
        source: source || "",
        desc: desc || "",
      };
    });
}
function propsToText(props: OntologyProp[]) {
  return (props || [])
    .map((p) => `${p.name} | ${p.datatype} | ${p.required ? "1" : "0"} | ${p.source || ""} | ${p.desc || ""}`.trim())
    .join("\n");
}
function ontologyEntityLabelById(id: string) {
  const found = ontologyEntities.value.find((e) => e.id === id);
  return found ? found.label : id || "-";
}

const ontologyEntities = ref<OntologyEntity[]>([
  {
    id: "road-segment",
    label: "路段",
    category: "实体",
    parent: "",
    status: "已发布",
    version: "v1.0.0",
    owner_org: "市排水中心",
    tags: ["空间对象", "资产"],
    desc: "道路网格化管理对象，可关联雨量/水位/责任单位/处置任务。",
    props: parsePropsText(
      "name | string | 1 | 主数据 | 路段名称\nadmin_area | string | 1 | GIS | 行政区\nlength_m | number | 0 | GIS | 路段长度（米）\nelevation_m | number | 0 | DEM | 平均高程（米）"
    ),
    created_at: tsShort(new Date(Date.now() - 1000 * 60 * 60 * 24 * 30)),
    updated_at: tsShort(new Date(Date.now() - 1000 * 60 * 12)),
  },
  {
    id: "pump-station",
    label: "泵站",
    category: "设施",
    parent: "",
    status: "已发布",
    version: "v1.0.0",
    owner_org: "排水运维公司",
    tags: ["设施", "运行状态"],
    desc: "排涝泵站，包含设备清单、工况与报警事件。",
    props: parsePropsText(
      "name | string | 1 | 主数据 | 泵站名称\nlocation | geo | 1 | GIS | 坐标/位置\ncapacity_m3s | number | 0 | 台账 | 设计流量（m³/s）\nstatus | enum | 1 | SCADA | 运行状态（开/停/故障）"
    ),
    created_at: tsShort(new Date(Date.now() - 1000 * 60 * 60 * 24 * 28)),
    updated_at: tsShort(new Date(Date.now() - 1000 * 60 * 60 * 3)),
  },
  {
    id: "admin-area",
    label: "行政区/责任片区",
    category: "组织",
    parent: "",
    status: "已发布",
    version: "v1.0.0",
    owner_org: "城运中心",
    tags: ["管理域"],
    desc: "用于空间归属、责任划分与统计口径。",
    props: parsePropsText("name | string | 1 | 主数据 | 区域名称\ncode | string | 1 | 主数据 | 区域编码"),
    created_at: tsShort(new Date(Date.now() - 1000 * 60 * 60 * 24 * 40)),
    updated_at: tsShort(new Date(Date.now() - 1000 * 60 * 60 * 24 * 1)),
  },
  {
    id: "incident",
    label: "事件",
    category: "事件",
    parent: "",
    status: "已发布",
    version: "v1.0.0",
    owner_org: "城运中心",
    tags: ["处置", "时间线"],
    desc: "内涝/积水等处置事件，承载时间线、证据与任务包。",
    props: parsePropsText(
      "title | string | 1 | 工作流 | 事件标题\nlevel | enum | 1 | 工作流 | 事件级别\ncreated_at | datetime | 1 | 工作流 | 创建时间\nstatus | enum | 1 | 工作流 | 状态机"
    ),
    created_at: tsShort(new Date(Date.now() - 1000 * 60 * 60 * 24 * 10)),
    updated_at: tsShort(new Date(Date.now() - 1000 * 60 * 60 * 4)),
  },
]);

const ontologyOwnerOrgOptions = [
  "市排水中心",
  "排水运维公司",
  "城运中心",
  "应急管理局",
  "交警",
  "街道办",
] as const;

const ontologyTagPresets = ["空间对象", "设施", "资产", "运行状态", "时间线", "处置", "组织", "管理域"] as const;

const ontologyEntityPropPresets = [
  {
    key: "road",
    label: "路段（RoadSegment）",
    text:
      "name | string | 1 | 主数据 | 路段名称\nadmin_area | string | 1 | GIS | 行政区\nlength_m | number | 0 | GIS | 路段长度（米）\nelevation_m | number | 0 | DEM | 平均高程（米）\nroad_grade | enum | 0 | 主数据 | 道路等级\nresponsible_org | string | 0 | 主数据 | 责任单位",
  },
  {
    key: "pump",
    label: "泵站（PumpStation）",
    text:
      "name | string | 1 | 主数据 | 泵站名称\nlocation | geo | 1 | GIS | 坐标/位置\ncapacity_m3s | number | 0 | 台账 | 设计流量（m³/s）\nstatus | enum | 1 | SCADA | 运行状态（开/停/故障）\nlast_maint_at | datetime | 0 | 运维 | 最近维护时间\nalarm_level | enum | 0 | SCADA | 告警等级",
  },
  {
    key: "incident",
    label: "事件（Incident）",
    text:
      "title | string | 1 | 工作流 | 事件标题\nlevel | enum | 1 | 工作流 | 事件级别\nstatus | enum | 1 | 工作流 | 状态机\ncreated_at | datetime | 1 | 工作流 | 创建时间\nsource | string | 0 | 工作流 | 事件来源（告警/人工/模型）\nevidence_refs | string | 0 | 证据库 | 证据引用ID列表",
  },
  {
    key: "admin",
    label: "片区/组织（AdminArea/Org）",
    text: "name | string | 1 | 主数据 | 名称\ncode | string | 1 | 主数据 | 编码\nleader | string | 0 | 主数据 | 负责人\ncontact | string | 0 | 主数据 | 联系方式",
  },
] as const;

const ontologyEntityPropPresetKey = ref<string>("road");

const ontologyRelPropPresets = [
  {
    key: "spatial",
    label: "空间/距离（Spatial）",
    text:
      "distance_m | number | 0 | GIS | 设施间距离（米）\nroute_eta_min | number | 0 | 计算 | 预计到达时间（分钟）\nconfidence | number | 0 | 计算 | 关联置信度（0-1）",
  },
  {
    key: "evidence",
    label: "证据/审计（Evidence/Audit）",
    text:
      "evidence_refs | string | 0 | 证据库 | 证据引用ID列表\nsource_system | string | 0 | 系统 | 关联来源系统\ncreated_at | datetime | 0 | 系统 | 关系创建时间\nupdated_at | datetime | 0 | 系统 | 关系更新时间",
  },
  {
    key: "weight",
    label: "权重/评分（Weight/Score）",
    text:
      "weight | number | 0 | 计算 | 关联权重\nscore | number | 0 | 模型 | 关系评分\nreason | string | 0 | 模型 | 评分依据/解释",
  },
  {
    key: "workflow",
    label: "工作流联动（Workflow）",
    text:
      "role | string | 0 | 工作流 | 角色（主目标/关联目标等）\nneed_approval | boolean | 0 | 工作流 | 是否需要审批\nsla_minutes | number | 0 | 工作流 | 关联的SLA（分钟）",
  },
] as const;

const ontologyRelPropQuickAdd = [
  { name: "distance_m", datatype: "number", required: false, source: "GIS", desc: "设施间距离（米）" },
  { name: "confidence", datatype: "number", required: false, source: "计算", desc: "关联置信度（0-1）" },
  { name: "evidence_refs", datatype: "string", required: false, source: "证据库", desc: "证据引用ID列表" },
  { name: "weight", datatype: "number", required: false, source: "计算", desc: "关联权重" },
] as const;

const ontologyRelPropPresetKey = ref<string>("spatial");

const ontologyRelations = ref<OntologyRelation[]>([
  {
    id: "located_in",
    label: "位于/隶属",
    predicate: "ex:locatedIn",
    from: "road-segment",
    to: "admin-area",
    direction: "单向",
    inverse_of: "contains",
    status: "已发布",
    version: "v1.0.0",
    card_from_min: "1",
    card_from_max: "1",
    desc: "路段必须归属一个责任片区，用于统计与派单归属。",
    props: parsePropsText("confidence | number | 0 | 计算 | 归属置信度（0-1）"),
    constraint_shacl:
      "ex:RoadSegmentShape a sh:NodeShape ;\n  sh:targetClass ex:RoadSegment ;\n  sh:property [ sh:path ex:locatedIn ; sh:class ex:AdminArea ; sh:minCount 1 ; sh:maxCount 1 ] .",
    created_at: tsShort(new Date(Date.now() - 1000 * 60 * 60 * 24 * 29)),
    updated_at: tsShort(new Date(Date.now() - 1000 * 60 * 60 * 6)),
  },
  {
    id: "near_pump_station",
    label: "邻近泵站",
    predicate: "ex:nearPumpStation",
    from: "road-segment",
    to: "pump-station",
    direction: "单向",
    inverse_of: "",
    status: "草稿",
    version: "v0.9.0",
    card_from_min: "0",
    card_from_max: "n",
    desc: "用于排涝联动：路段可关联 0..n 个泵站，支持按距离/可达性排序。",
    props: parsePropsText("distance_m | number | 0 | GIS | 设施间距离（米）\nroute_eta_min | number | 0 | 计算 | 预计到达时间（分钟）"),
    constraint_shacl: "",
    created_at: tsShort(new Date(Date.now() - 1000 * 60 * 60 * 24 * 8)),
    updated_at: tsShort(new Date(Date.now() - 1000 * 60 * 60 * 2)),
  },
  {
    id: "incident_targets",
    label: "事件涉及对象",
    predicate: "ex:targets",
    from: "incident",
    to: "road-segment",
    direction: "单向",
    inverse_of: "",
    status: "已发布",
    version: "v1.0.0",
    card_from_min: "1",
    card_from_max: "n",
    desc: "事件可涉及多个目标对象（路段/点位等），为研判与任务包生成提供上下文。",
    props: parsePropsText("role | string | 0 | 工作流 | 目标角色（主目标/关联目标）"),
    constraint_shacl: "",
    created_at: tsShort(new Date(Date.now() - 1000 * 60 * 60 * 24 * 9)),
    updated_at: tsShort(new Date(Date.now() - 1000 * 60 * 60 * 1)),
  },
]);

const ontologyEntityFilters = reactive({ keyword: "", category: "", status: "" });
const ontologyRelFilters = reactive({ keyword: "", status: "" });
const selectedOntologyRelId = ref<string>("");

// 关系图谱预览（Cytoscape）
const ontologyGraphRef = ref<HTMLDivElement | null>(null);
let ontologyCy: cytoscape.Core | null = null;

function buildOntologyGraphElements() {
  const nodes = ontologyEntities.value.map((e) => ({
    data: {
      id: `ent:${e.id}`,
      raw_id: e.id,
      label: e.label,
      category: e.category,
      status: e.status,
    },
  }));
  const edges = ontologyRelations.value.map((r) => ({
    data: {
      id: `rel:${r.id}`,
      raw_id: r.id,
      source: `ent:${r.from}`,
      target: `ent:${r.to}`,
      label: r.label,
      predicate: r.predicate,
      status: r.status,
      selected: selectedOntologyRelId.value === r.id ? "1" : "0",
    },
  }));
  return [...nodes, ...edges];
}

function ensureOntologyGraph() {
  if (ontologyCy || !ontologyGraphRef.value) return;
  ontologyCy = cytoscape({
    container: ontologyGraphRef.value,
    elements: buildOntologyGraphElements(),
    layout: { name: "cose", animate: true, fit: true },
    style: [
      {
        selector: "node",
        style: {
          "background-color": "rgba(59, 130, 246, 0.7)",
          "border-color": "rgba(147, 51, 234, 0.45)",
          "border-width": 1,
          color: "#e5ecff",
          "font-size": 11,
          label: "data(label)",
          "text-valign": "center",
          "text-halign": "center",
          width: 44,
          height: 44,
        },
      },
      {
        selector: 'node[status = "已停用"]',
        style: { "background-color": "rgba(148, 163, 184, 0.5)" },
      },
      {
        selector: "edge",
        style: {
          width: 2,
          "line-color": "rgba(96, 165, 250, 0.55)",
          "target-arrow-color": "rgba(96, 165, 250, 0.75)",
          "target-arrow-shape": "triangle",
          "curve-style": "bezier",
          label: "data(label)",
          "font-size": 10,
          color: "rgba(226, 232, 240, 0.9)",
          "text-background-color": "rgba(15, 23, 42, 0.75)",
          "text-background-opacity": 1,
          "text-background-padding": 2,
        },
      },
      {
        selector: 'edge[selected = "1"]',
        style: {
          width: 4,
          "line-color": "rgba(147, 51, 234, 0.75)",
          "target-arrow-color": "rgba(147, 51, 234, 0.9)",
        },
      },
      {
        selector: 'edge[status = "已停用"]',
        style: { "line-color": "rgba(148, 163, 184, 0.45)", "target-arrow-color": "rgba(148, 163, 184, 0.6)" },
      },
    ],
    userZoomingEnabled: true,
    userPanningEnabled: true,
    boxSelectionEnabled: true,
    wheelSensitivity: 0.18,
  });

  // 点击边：选中关系（同步右侧文本/校验）
  ontologyCy.on("tap", "edge", (evt) => {
    const raw = evt.target?.data?.("raw_id");
    if (raw) selectedOntologyRelId.value = String(raw);
  });

  // 默认选中第一条关系
  if (!selectedOntologyRelId.value && ontologyRelations.value.length) {
    selectedOntologyRelId.value = ontologyRelations.value[0].id;
  }
}

function refreshOntologyGraph(shouldRelayout = false) {
  if (!ontologyCy) return;
  ontologyCy.batch(() => {
    ontologyCy!.elements().remove();
    ontologyCy!.add(buildOntologyGraphElements() as any);
  });
  if (shouldRelayout) {
    ontologyCy.layout({ name: "cose", animate: true, fit: true }).run();
  } else {
    // 更新选中高亮即可，保持当前布局与用户拖拽结果
    ontologyCy.style().update();
  }
}

function ontologyGraphFit() {
  if (!ontologyCy) return;
  ontologyCy.fit(undefined, 30);
}
function ontologyGraphRelayout() {
  if (!ontologyCy) return;
  ontologyCy.layout({ name: "cose", animate: true, fit: true }).run();
}

const ontologyEntityEditing = reactive<{ open: boolean; mode: "new" | "edit"; editingId: string }>({
  open: false,
  mode: "new",
  editingId: "",
});
const ontologyRelEditing = reactive<{ open: boolean; mode: "new" | "edit"; editingId: string }>({
  open: false,
  mode: "new",
  editingId: "",
});

const ontologyEntityForm = reactive<{
  id: string;
  label: string;
  category: string;
  parent: string;
  status: "草稿" | "已发布" | "已停用";
  version: string;
  owner_org: string;
  tags: string;
  desc: string;
  props_text: string;
}>({
  id: "road-segment",
  label: "路段",
  category: "实体",
  parent: "",
  status: "草稿",
  version: "v1.0.0",
  owner_org: ontologyOwnerOrgOptions[0],
  tags: "空间对象, 资产",
  desc: "",
  props_text: "name | string | 1 | 主数据 | 路段名称",
});

const ontologyRelForm = reactive<{
  id: string;
  label: string;
  predicate: string;
  from: string;
  to: string;
  direction: "单向" | "双向";
  inverse_of: string;
  status: "草稿" | "已发布" | "已停用";
  version: string;
  card_from_min: string;
  card_from_max: string;
  desc: string;
  props_text: string;
  constraint_shacl: string;
}>({
  id: "near_pump_station",
  label: "邻近泵站",
  predicate: "ex:nearPumpStation",
  from: "road-segment",
  to: "pump-station",
  direction: "单向",
  inverse_of: "",
  status: "草稿",
  version: "v0.9.0",
  card_from_min: "0",
  card_from_max: "n",
  desc: "",
  props_text: "distance_m | number | 0 | GIS | 设施间距离（米）",
  constraint_shacl: "",
});

const filteredOntologyEntities = computed(() => {
  const kw = (ontologyEntityFilters.keyword || "").trim().toLowerCase();
  return ontologyEntities.value.filter((e) => {
    if (ontologyEntityFilters.category && e.category !== ontologyEntityFilters.category) return false;
    if (ontologyEntityFilters.status && e.status !== ontologyEntityFilters.status) return false;
    if (!kw) return true;
    const hay = [
      e.id,
      e.label,
      e.category,
      e.owner_org,
      e.tags.join(","),
      e.desc,
      e.props.map((p) => p.name).join(","),
    ]
      .join(" ")
      .toLowerCase();
    return hay.includes(kw);
  });
});
const filteredOntologyRelations = computed(() => {
  const kw = (ontologyRelFilters.keyword || "").trim().toLowerCase();
  return ontologyRelations.value.filter((r) => {
    if (ontologyRelFilters.status && r.status !== ontologyRelFilters.status) return false;
    if (!kw) return true;
    const hay = [r.id, r.label, r.predicate, r.from, r.to, r.inverse_of, r.desc].join(" ").toLowerCase();
    return hay.includes(kw);
  });
});

const selectedOntologyRelPreview = computed(() => {
  const id = selectedOntologyRelId.value;
  const r = ontologyRelations.value.find((x) => x.id === id) || ontologyRelations.value[0];
  if (!r) return "（暂无关系定义）";
  const fromLabel = ontologyEntityLabelById(r.from);
  const toLabel = ontologyEntityLabelById(r.to);
  const card = `${r.card_from_min}..${r.card_from_max}`;
  const lines = [
    `${fromLabel}(${r.from}) --[${r.label} | ${r.predicate} | ${card}]--> ${toLabel}(${r.to})`,
    "",
    `direction: ${r.direction}`,
    r.inverse_of ? `inverse_of: ${r.inverse_of}` : "inverse_of: -",
    `status/version: ${r.status} / ${r.version}`,
    r.desc ? `desc: ${r.desc}` : "desc: -",
    "",
    `props(${r.props.length}): ${r.props.length ? r.props.map((p) => p.name).join(", ") : "-"}`,
    "",
    r.constraint_shacl ? `constraint:\n${r.constraint_shacl}` : "constraint: -",
  ];
  return lines.join("\n");
});

// 进入/离开页面时初始化与销毁图谱；数据变更时刷新元素
watch(
  () => activePage.value,
  async (p) => {
    if (p === "ontology") {
      await nextTick();
      ensureOntologyGraph();
      refreshOntologyGraph(true);
      ontologyGraphFit();
    } else {
      if (ontologyCy) {
        ontologyCy.destroy();
        ontologyCy = null;
      }
    }
  }
);
watch(
  () => [ontologyEntities.value, ontologyRelations.value],
  async () => {
    if (activePage.value !== "ontology") return;
    await nextTick();
    ensureOntologyGraph();
    refreshOntologyGraph(true);
  },
  { deep: true }
);
watch(
  () => selectedOntologyRelId.value,
  () => {
    if (activePage.value !== "ontology") return;
    // 只更新选中样式，不强制重新布局
    refreshOntologyGraph(false);
  }
);

onBeforeUnmount(() => {
  if (ontologyCy) {
    ontologyCy.destroy();
    ontologyCy = null;
  }
  // 关闭图片预览，避免残留
  imagePreview.open = false;
  imagePreview.src = "";
});

const ontologyIssues = computed(() => {
  const issues: string[] = [];
  const entityIds = ontologyEntities.value.map((e) => e.id);
  const relIds = ontologyRelations.value.map((r) => r.id);

  // 重复 ID
  const dup = (arr: string[]) => arr.filter((x, i) => arr.indexOf(x) !== i);
  dup(entityIds).forEach((id) => issues.push(`实体ID重复：${id}`));
  dup(relIds).forEach((id) => issues.push(`关系ID重复：${id}`));

  // 关系引用实体存在性
  ontologyRelations.value.forEach((r) => {
    if (!entityIds.includes(r.from)) issues.push(`关系 ${r.id} 的 Domain 不存在：${r.from}`);
    if (!entityIds.includes(r.to)) issues.push(`关系 ${r.id} 的 Range 不存在：${r.to}`);
    if (r.card_from_min && !/^\d+$/.test(r.card_from_min)) issues.push(`关系 ${r.id} 的 min 基数格式异常：${r.card_from_min}`);
    if (r.card_from_max && !(r.card_from_max === "n" || /^\d+$/.test(r.card_from_max)))
      issues.push(`关系 ${r.id} 的 max 基数格式异常：${r.card_from_max}`);
  });

  return issues;
});

function resetOntologyEntityFormFrom(e?: OntologyEntity) {
  ontologyEntityForm.id = e?.id || "";
  ontologyEntityForm.label = e?.label || "";
  ontologyEntityForm.category = e?.category || "实体";
  ontologyEntityForm.parent = e?.parent || "";
  ontologyEntityForm.status = e?.status || "草稿";
  ontologyEntityForm.version = e?.version || "v1.0.0";
  ontologyEntityForm.owner_org = e?.owner_org || ontologyOwnerOrgOptions[0];
  ontologyEntityForm.tags = (e?.tags || []).join(", ");
  ontologyEntityForm.desc = e?.desc || "";
  ontologyEntityForm.props_text = propsToText(e?.props || []);
}

function categoryPrefix(category: string) {
  const map: Record<string, string> = {
    实体: "entity",
    事件: "event",
    设施: "facility",
    组织: "org",
    资源: "resource",
  };
  return map[category] || "entity";
}
function suggestEntityId(category: string) {
  const prefix = categoryPrefix(category);
  const re = new RegExp(`^${prefix}-(\\d{3})$`);
  let max = 0;
  ontologyEntities.value.forEach((e) => {
    const m = String(e.id || "").match(re);
    if (m?.[1]) max = Math.max(max, Number(m[1]));
  });
  const next = String(max + 1).padStart(3, "0");
  return `${prefix}-${next}`;
}
function regenOntologyEntityId() {
  ontologyEntityForm.id = suggestEntityId(ontologyEntityForm.category || "实体");
}
function normalizeTagList(s: string) {
  return (s || "")
    .split(",")
    .map((x) => x.trim())
    .filter(Boolean);
}
function setTagList(tags: string[]) {
  ontologyEntityForm.tags = tags.join(", ");
}
function toggleOntologyTag(tag: string) {
  const tags = normalizeTagList(ontologyEntityForm.tags);
  const idx = tags.indexOf(tag);
  if (idx >= 0) tags.splice(idx, 1);
  else tags.push(tag);
  setTagList(tags);
}
function clearOntologyTags() {
  ontologyEntityForm.tags = "";
}

function presetTextByKey(key: string) {
  const found = ontologyEntityPropPresets.find((x) => x.key === key);
  return found?.text || "";
}
function applyEntityPropPreset(mode: "replace" | "append" | "clear") {
  if (mode === "clear") {
    ontologyEntityForm.props_text = "";
    return;
  }
  const text = presetTextByKey(ontologyEntityPropPresetKey.value);
  if (!text) return;
  if (mode === "replace") {
    ontologyEntityForm.props_text = text;
    return;
  }
  const cur = (ontologyEntityForm.props_text || "").trim();
  ontologyEntityForm.props_text = cur ? `${cur}\n${text}` : text;
}
function startNewOntologyEntity() {
  ontologyEntityEditing.open = true;
  ontologyEntityEditing.mode = "new";
  ontologyEntityEditing.editingId = "";
  resetOntologyEntityFormFrom({
    id: suggestEntityId("实体"),
    label: "",
    category: "实体",
    parent: "",
    status: "草稿",
    version: "v1.0.0",
    owner_org: ontologyOwnerOrgOptions[0],
    tags: [],
    desc: "",
    props: [],
    created_at: tsShort(),
    updated_at: tsShort(),
  });
  ontologyEntityPropPresetKey.value = "road";
  // 默认给一个模板，避免空白更像真实系统
  ontologyEntityForm.props_text = presetTextByKey("road");
}
function editOntologyEntity(id: string) {
  const found = ontologyEntities.value.find((x) => x.id === id);
  if (!found) return;
  ontologyEntityEditing.open = true;
  ontologyEntityEditing.mode = "edit";
  ontologyEntityEditing.editingId = id;
  resetOntologyEntityFormFrom(found);
}
function cancelOntologyEntityEdit() {
  ontologyEntityEditing.open = false;
  ontologyEntityEditing.editingId = "";
}
function saveOntologyEntity() {
  const id = (ontologyEntityForm.id || "").trim();
  const label = (ontologyEntityForm.label || "").trim();
  if (!id || !label) return;
  const now = tsShort();
  const entity: OntologyEntity = {
    id,
    label,
    category: ontologyEntityForm.category || "实体",
    parent: ontologyEntityForm.parent || "",
    status: ontologyEntityForm.status || "草稿",
    version: (ontologyEntityForm.version || "v1.0.0").trim(),
    owner_org: (ontologyEntityForm.owner_org || "").trim(),
    tags: parseTags(ontologyEntityForm.tags),
    desc: (ontologyEntityForm.desc || "").trim(),
    props: parsePropsText(ontologyEntityForm.props_text),
    created_at: now,
    updated_at: now,
  };

  if (ontologyEntityEditing.mode === "edit" && ontologyEntityEditing.editingId) {
    const idx = ontologyEntities.value.findIndex((x) => x.id === ontologyEntityEditing.editingId);
    if (idx >= 0) {
      // 保留原创建时间；若改了 ID，则同步更新关系引用
      const prev = ontologyEntities.value[idx];
      entity.created_at = prev.created_at;
      ontologyEntities.value[idx] = entity;
      if (prev.id !== entity.id) {
        ontologyRelations.value = ontologyRelations.value.map((r) => ({
          ...r,
          from: r.from === prev.id ? entity.id : r.from,
          to: r.to === prev.id ? entity.id : r.to,
          updated_at: tsShort(),
        }));
      }
    }
  } else {
    if (ontologyEntities.value.some((x) => x.id === entity.id)) return;
    ontologyEntities.value.unshift(entity);
  }
  ontologyEntityEditing.open = false;
}
function deleteOntologyEntity(id: string) {
  ontologyEntities.value = ontologyEntities.value.filter((x) => x.id !== id);
  // 关系引用变成“未知”更真实：这里不自动删除，只提示校验
}
function duplicateOntologyEntity(id: string) {
  const found = ontologyEntities.value.find((x) => x.id === id);
  if (!found) return;
  const now = tsShort();
  const copy: OntologyEntity = {
    ...found,
    id: `${found.id}_copy`,
    label: `${found.label}（复制）`,
    status: "草稿",
    version: found.version,
    created_at: now,
    updated_at: now,
  };
  ontologyEntities.value.unshift(copy);
}

function resetOntologyRelFormFrom(r?: OntologyRelation) {
  ontologyRelForm.id = r?.id || "";
  ontologyRelForm.label = r?.label || "";
  ontologyRelForm.predicate = r?.predicate || "";
  ontologyRelForm.from = r?.from || (ontologyEntities.value[0]?.id || "");
  ontologyRelForm.to = r?.to || (ontologyEntities.value[1]?.id || ontologyEntities.value[0]?.id || "");
  ontologyRelForm.direction = r?.direction || "单向";
  ontologyRelForm.inverse_of = r?.inverse_of || "";
  ontologyRelForm.status = r?.status || "草稿";
  ontologyRelForm.version = r?.version || "v1.0.0";
  ontologyRelForm.card_from_min = r?.card_from_min || "0";
  ontologyRelForm.card_from_max = r?.card_from_max || "n";
  ontologyRelForm.desc = r?.desc || "";
  ontologyRelForm.props_text = propsToText(r?.props || []);
  ontologyRelForm.constraint_shacl = r?.constraint_shacl || "";
}

function suggestRelId() {
  const re = /^rel-(\d{3})$/;
  let max = 0;
  ontologyRelations.value.forEach((r) => {
    const m = String(r.id || "").match(re);
    if (m?.[1]) max = Math.max(max, Number(m[1]));
  });
  return `rel-${String(max + 1).padStart(3, "0")}`;
}
function regenOntologyRelId() {
  ontologyRelForm.id = suggestRelId();
}
function relPresetTextByKey(key: string) {
  const found = ontologyRelPropPresets.find((x) => x.key === key);
  return found?.text || "";
}
function applyRelPropPreset(mode: "replace" | "append" | "clear") {
  if (mode === "clear") {
    ontologyRelForm.props_text = "";
    return;
  }
  const text = relPresetTextByKey(ontologyRelPropPresetKey.value);
  if (!text) return;
  if (mode === "replace") {
    ontologyRelForm.props_text = text;
    return;
  }
  const cur = (ontologyRelForm.props_text || "").trim();
  ontologyRelForm.props_text = cur ? `${cur}\n${text}` : text;
}
function appendRelPropLine(p: { name: string; datatype: string; required: boolean; source: string; desc: string }) {
  const line = `${p.name} | ${p.datatype} | ${p.required ? "1" : "0"} | ${p.source} | ${p.desc}`;
  const cur = (ontologyRelForm.props_text || "").trim();
  // 避免重复追加同名属性行（粗略匹配行首）
  const exists = cur
    .split("\n")
    .map((x) => x.trim())
    .some((x) => x.startsWith(`${p.name} |`) || x === p.name);
  if (exists) return;
  ontologyRelForm.props_text = cur ? `${cur}\n${line}` : line;
}
function startNewOntologyRelation() {
  ontologyRelEditing.open = true;
  ontologyRelEditing.mode = "new";
  ontologyRelEditing.editingId = "";
  resetOntologyRelFormFrom({
    id: suggestRelId(),
    label: "",
    predicate: "ex:",
    from: ontologyEntities.value[0]?.id || "",
    to: ontologyEntities.value[1]?.id || ontologyEntities.value[0]?.id || "",
    direction: "单向",
    inverse_of: "",
    status: "草稿",
    version: "v1.0.0",
    card_from_min: "0",
    card_from_max: "n",
    desc: "",
    props: [],
    constraint_shacl: "",
    created_at: tsShort(),
    updated_at: tsShort(),
  });
  ontologyRelPropPresetKey.value = "spatial";
  ontologyRelForm.props_text = relPresetTextByKey("spatial");
}
function editOntologyRelation(id: string) {
  const found = ontologyRelations.value.find((x) => x.id === id);
  if (!found) return;
  ontologyRelEditing.open = true;
  ontologyRelEditing.mode = "edit";
  ontologyRelEditing.editingId = id;
  resetOntologyRelFormFrom(found);
}
function cancelOntologyRelationEdit() {
  ontologyRelEditing.open = false;
  ontologyRelEditing.editingId = "";
}
function saveOntologyRelation() {
  const id = (ontologyRelForm.id || "").trim();
  const label = (ontologyRelForm.label || "").trim();
  if (!id || !label) return;
  const now = tsShort();
  const rel: OntologyRelation = {
    id,
    label,
    predicate: (ontologyRelForm.predicate || "").trim(),
    from: ontologyRelForm.from,
    to: ontologyRelForm.to,
    direction: ontologyRelForm.direction || "单向",
    inverse_of: (ontologyRelForm.inverse_of || "").trim(),
    status: ontologyRelForm.status || "草稿",
    version: (ontologyRelForm.version || "v1.0.0").trim(),
    card_from_min: (ontologyRelForm.card_from_min || "0").trim(),
    card_from_max: (ontologyRelForm.card_from_max || "n").trim(),
    desc: (ontologyRelForm.desc || "").trim(),
    props: parsePropsText(ontologyRelForm.props_text),
    constraint_shacl: (ontologyRelForm.constraint_shacl || "").trim(),
    created_at: now,
    updated_at: now,
  };

  if (ontologyRelEditing.mode === "edit" && ontologyRelEditing.editingId) {
    const idx = ontologyRelations.value.findIndex((x) => x.id === ontologyRelEditing.editingId);
    if (idx >= 0) {
      const prev = ontologyRelations.value[idx];
      rel.created_at = prev.created_at;
      ontologyRelations.value[idx] = rel;
    }
  } else {
    if (ontologyRelations.value.some((x) => x.id === rel.id)) return;
    ontologyRelations.value.unshift(rel);
  }
  selectedOntologyRelId.value = rel.id;
  ontologyRelEditing.open = false;
}
function deleteOntologyRelation(id: string) {
  ontologyRelations.value = ontologyRelations.value.filter((x) => x.id !== id);
  if (selectedOntologyRelId.value === id) selectedOntologyRelId.value = "";
}
function duplicateOntologyRelation(id: string) {
  const found = ontologyRelations.value.find((x) => x.id === id);
  if (!found) return;
  const now = tsShort();
  const copy: OntologyRelation = {
    ...found,
    id: `${found.id}_copy`,
    label: `${found.label}（复制）`,
    status: "草稿",
    created_at: now,
    updated_at: now,
  };
  ontologyRelations.value.unshift(copy);
}
function selectOntologyRelation(id: string) {
  selectedOntologyRelId.value = id;
}

// 数据接入与治理演示（前端本地状态）
const dataSourceName = ref("雨量站-001");
const dataSourceType = ref("雨量");
const dataSourceConn = ref("HTTP/API");
const dataSourceFreq = ref("5分钟");
const dataSources = ref<{ name: string; type: string; conn: string; freq: string }[]>([]);

const storageSource = ref("雨量站-001");
const storageLayer = ref("Raw（原始层）");
const storageRule = ref("去重、单位统一为 mm/h");
const storageRules = ref<{ source: string; layer: string; rule: string }[]>([]);

const dqTarget = ref("雨量站-001");
const dqDimension = ref("完整性");
const dqRule = ref("字段非空、延迟<5分钟");
const dqRules = ref<{ target: string; dimension: string; rule: string }[]>([]);

// 风险推理/模型演示（前端本地状态）
const modelName = ref("内涝风险模型-v1");
const modelType = ref("规则模型");
const modelThresholds = ref("红≥7.0, 橙≥5.0, 黄≥3.5");
const modelFeatures = ref("rain_now_mmph, water_level_m, pump_status, elevation_m");
const models = ref<{ name: string; type: string; thresholds: string; features: string }[]>([]);

const featureName = ref("rain_now_mmph");
const featureSource = ref("TSDB");
const featureWindow = ref("1小时滑动窗口");
const featureRule = ref("缺失值填充、异常值过滤");
const features = ref<{ name: string; source: string; window: string; rule: string }[]>([]);

const inferTaskType = ref("TopN 风险");
const inferTrigger = ref("API调用");
const inferOutput = ref("risk_score, risk_level, confidence, explain_factors");
const inferTasks = ref<{ type: string; trigger: string; output: string }[]>([]);

// 智能体决策演示（前端本地状态）
const toolName = ref("query_risk_topn");
const toolType = ref("API 调用");
const toolDesc = ref("查询 TopN 风险点位（含风险/置信度/解释因子）");
const toolSchema = ref("{area_id: string, n: number}");
const tools = ref<{ name: string; type: string; desc: string; schema: string }[]>([]);

const ragName = ref("应急预案库");
const ragSource = ref("预案文档");
const ragVectorDB = ref("Chroma");
const ragStrategy = ref("语义检索 Top5 + 重排序 Top3");
const rags = ref<{ name: string; source: string; vectorDB: string; strategy: string }[]>([]);

const taskTemplateName = ref("封控任务模板");
const taskTemplateType = ref("封控准备");
const taskTemplateOwner = ref("交警");
const taskTemplateSla = ref("20");
const taskTemplateEvidence = ref("定位, 照片");
const taskTemplateApproval = ref("是");
const taskTemplates = ref<{ name: string; type: string; owner: string; sla: string; evidence: string; approval: string }[]>([]);

// 执行闭环/工作流演示（前端本地状态）
const workflowName = ref("封控任务流程");
const workflowType = ref("任务执行流程");
const workflowNodes = ref("接收 → 分发 → 执行 → 审核 → 完成");
const workflowTimeout = ref("30");
const workflowRetry = ref("失败重试3次，间隔5分钟");
const workflows = ref<{ name: string; type: string; nodes: string; timeout: string; retry: string }[]>([]);

const notificationName = ref("任务分派通知");
const notificationChannel = ref("APP 推送");
const notificationTrigger = ref("任务分派时");
const notificationTemplate = ref("您有新的任务待处理：{task_name}，请在{timeout}分钟内完成");
const notifications = ref<{ name: string; channel: string; trigger: string; template: string }[]>([]);

const approvalName = ref("高风险任务审批");
const approvalType = ref("多级审批");
const approvalUsers = ref("部门主管, 分管领导");
const approvalRule = ref("高风险任务需部门主管+分管领导会签");
const approvalTimeout = ref("升级审批");
const approvals = ref<{ name: string; type: string; users: string; rule: string; timeout: string }[]>([]);

// 战报与追溯演示（前端本地状态）
const timelineName = ref("事件处置时间线");
const timelineEventTypes = ref("incident_created, alert_event, task_completed");
const timelineMilestones = ref("事件创建, 首个告警, 任务完成");
const timelineTimeRange = ref("24");
const timelines = ref<{ name: string; eventTypes: string; milestones: string; timeRange: string }[]>([]);

const metricName = ref("任务完成率");
const metricType = ref("完成率");
const metricFormula = ref("已完成数 / 总数 × 100%");
const metricRefresh = ref("5");
const metrics = ref<{ name: string; type: string; formula: string; refresh: string }[]>([]);

const reportTemplateName = ref("事件处置战报模板");
const reportTemplateFormat = ref("HTML");
const reportTemplateContent = ref("事件信息, 时间线, 指标, 状态追溯");
const reportTemplateFile = ref("template.html");
const reportTemplates = ref<{ name: string; format: string; content: string; file: string }[]>([]);

const topN = ref<any[]>([]);
const tasks = ref<any[]>([]);

const chatInput = ref("请研判并一键下发任务包");
const agentOut = ref("");
const reportOut = ref("");
const reportData = ref<any | null>(null);

const selectedTargetObj = computed(() => {
  if (!topN.value || topN.value.length === 0) return null;
  const found = topN.value.find((it) => it.target_id === selectedTarget.value);
  return found || topN.value[0];
});

const riskSummary = computed(() => {
  const total = topN.value.length;
  const counts = { 红: 0, 橙: 0, 黄: 0, 绿: 0 };
  let maxScore = 0;
  let maxId = "";
  topN.value.forEach((it: any) => {
    if (counts[it.risk_level] !== undefined) counts[it.risk_level] += 1;
    if (it.risk_score > maxScore) {
      maxScore = it.risk_score;
      maxId = it.target_id;
    }
  });
  return { total, counts, maxScore, maxId };
});

// 演示：为 road/a-001-road/a-002-road/a-003-road 生成北京海淀（东北旺西路8号院附近）的示例坐标
const targetCoords: Record<string, [number, number]> = {
  // A-001（老数据兼容）
  "road-001": [39.9991, 116.3269],
  "road-002": [40.001, 116.3288],
  "road-003": [39.9978, 116.3292],
  "road-004": [39.9985, 116.3247],
  "road-005": [40.0002, 116.3239],
  "road-006": [39.9969, 116.3261],
  "road-007": [39.9998, 116.3229],
  "road-008": [40.0009, 116.3254],
  "road-009": [39.9976, 116.3259],
  "road-010": [39.9989, 116.3301],
  "road-011": [40.0016, 116.3262],
  "road-012": [39.9965, 116.3238],

  // A-001（后端种子数据的真实 object_id 格式：a-001-road-xxx）
  "a-001-road-001": [39.9991, 116.3269],
  "a-001-road-002": [40.001, 116.3288],
  "a-001-road-003": [39.9978, 116.3292],
  "a-001-road-004": [39.9985, 116.3247],
  "a-001-road-005": [40.0002, 116.3239],
  "a-001-road-006": [39.9969, 116.3261],
  "a-001-road-007": [39.9998, 116.3229],
  "a-001-road-008": [40.0009, 116.3254],
  "a-001-road-009": [39.9976, 116.3259],
  "a-001-road-010": [39.9989, 116.3301],
  "a-001-road-011": [40.0016, 116.3262],
  "a-001-road-012": [39.9965, 116.3238],

  // 新区域前缀 A-002/A-003（同样放在北京附近，做轻微偏移区分）
  "a-002-road-001": [40.0105, 116.3365],
  "a-002-road-002": [40.0122, 116.338],
  "a-002-road-003": [40.0097, 116.3392],
  "a-002-road-004": [40.011, 116.3348],
  "a-002-road-005": [40.013, 116.3355],
  "a-002-road-006": [40.0089, 116.3368],
  "a-002-road-007": [40.0109, 116.3334],
  "a-002-road-008": [40.012, 116.3361],
  "a-002-road-009": [40.0092, 116.3358],
  "a-002-road-010": [40.0113, 116.3401],
  "a-002-road-011": [40.0135, 116.3369],
  "a-002-road-012": [40.0087, 116.3342],

  "a-003-road-001": [39.9905, 116.3165],
  "a-003-road-002": [39.9921, 116.3182],
  "a-003-road-003": [39.9896, 116.3191],
  "a-003-road-004": [39.9913, 116.3148],
  "a-003-road-005": [39.9932, 116.3159],
  "a-003-road-006": [39.9889, 116.3169],
  "a-003-road-007": [39.9909, 116.3132],
  "a-003-road-008": [39.992, 116.3161],
  "a-003-road-009": [39.9892, 116.3152],
  "a-003-road-010": [39.991, 116.3201],
  "a-003-road-011": [39.9936, 116.3168],
  "a-003-road-012": [39.9885, 116.3142],
};

const mapRef = ref<HTMLDivElement | null>(null);
let map: L.Map | null = null;
let markers: Record<string, L.CircleMarker> = {};

async function loadTopN() {
  const { data } = await axios.get(`${apiBase}/risk/topn`, { params: { area_id: areaId.value, n: 12 } });
  topN.value = data.items || [];
  if (!selectedTarget.value && topN.value.length > 0) {
    selectedTarget.value = topN.value[0].target_id || "";
  }
  // 预热对象中文名缓存（更贴近真实展示）
  warmObjectLabels(
    (topN.value || []).map((it: any) => String(it.target_id || "")),
    areaId.value
  ).catch(() => {});
  renderMap();
}

function pickTarget(targetId: string) {
  // 内部统一使用后端真实 object_id（例如 a-001-road-008）；但对用户展示中文名称
  const seedId = toSeedObjectId(targetId, areaId.value);
  selectedTarget.value = seedId || targetId;
  warmObjectLabels([selectedTarget.value, targetId], areaId.value).catch(() => {});
  ensureObjectState(selectedTarget.value).catch(() => {});
  chatInput.value = `请研判 ${targetLabel(selectedTarget.value, areaId.value)} 并给出任务包建议`;
  agentConfirmed.value = false;
  agentResult.value = null;
  agentResultError.value = "";
  agentOut.value = "";
  // 分步闭环：点击预警（如 road-008）即跳转到对话页
  if (activePage.value === "flow") {
    flowStep.value = "agent";
  }
}

async function createIncident() {
  const { data } = await axios.post(`${apiBase}/workflow/incidents`, { area_id: areaId.value, title: "城市暴雨内涝处置事件（演示）" });
  incidentId.value = data.incident_id;
}

async function sendChat() {
  agentOut.value = "请求中...";
  agentResult.value = null;
  agentResultError.value = "";
  agentConfirmed.value = false;
  const { data } = await axios.post(`${agentBase}/agent/chat`, {
    incident_id: incidentId.value || null,
    area_id: areaId.value,
    target_id: selectedTarget.value || null,
    message: chatInput.value,
  });
  if (data.incident_id) {
    incidentId.value = data.incident_id;
  }
  agentResult.value = data;
  agentOut.value = JSON.stringify(data, null, 2);
  // 若智能体自动创建了事件
  if (!incidentId.value) {
    // 从 tasks 里推断不到，这里就用后端的“最新事件”能力简化：直接再新建一个事件让用户可控
    // 演示：如果智能体触发派单，用户通常会先点“新建事件”；这里保持简单不反推。
  }
  // 注意：对话页不自动进入下一步；需要专家确认后再跳转
}

function ensureOneClickPrompt(msg: string) {
  const base = (msg || "").trim();
  const tgt = selectedTarget.value ? targetLabel(selectedTarget.value, areaId.value) : "";
  const hasOneClick = /一键(派单|下发)/.test(base) || /下发任务包/.test(base);
  if (!base) {
    return selectedTarget.value ? `请研判 ${tgt} 并一键下发任务包` : "请研判并一键下发任务包";
  }
  if (hasOneClick) return base;
  // 保留用户输入，同时确保包含“一键派单”语义
  return `${base}（并一键下发任务包）`;
}

async function sendChatOneClick() {
  chatInput.value = ensureOneClickPrompt(chatInput.value);
  return await sendChat();
}

function confirmAgentAndNext() {
  if (!agentResult.value) return;
  agentConfirmed.value = true;
  if (activePage.value === "flow") {
    flowStep.value = "tasks";
    loadTasks().catch(() => {});
  }
}

function fillOneClick() {
  chatInput.value = ensureOneClickPrompt(chatInput.value);
}

// 兼容：旧的“保存到预览”按钮逻辑已被更真实的 CRUD 替代；保留空实现以避免误引用
function addOntologyEntity() {}
function addOntologyRelation() {}

function addDataSource() {
  dataSources.value.unshift({
    name: dataSourceName.value.trim() || "未命名",
    type: dataSourceType.value,
    conn: dataSourceConn.value,
    freq: dataSourceFreq.value.trim() || "未设置",
  });
}

function addStorageRule() {
  storageRules.value.unshift({
    source: storageSource.value,
    layer: storageLayer.value,
    rule: storageRule.value.trim() || "无规则",
  });
}

function addDqRule() {
  dqRules.value.unshift({
    target: dqTarget.value.trim() || "未指定",
    dimension: dqDimension.value,
    rule: dqRule.value.trim() || "无规则",
  });
}

function addModel() {
  models.value.unshift({
    name: modelName.value.trim() || "未命名",
    type: modelType.value,
    thresholds: modelThresholds.value.trim() || "未设置",
    features: modelFeatures.value.trim() || "无",
  });
}

function addFeature() {
  features.value.unshift({
    name: featureName.value.trim() || "未命名",
    source: featureSource.value,
    window: featureWindow.value.trim() || "未设置",
    rule: featureRule.value.trim() || "无规则",
  });
}

function addInferTask() {
  inferTasks.value.unshift({
    type: inferTaskType.value,
    trigger: inferTrigger.value.trim() || "未设置",
    output: inferOutput.value.trim() || "无",
  });
}

function addTool() {
  tools.value.unshift({
    name: toolName.value.trim() || "未命名",
    type: toolType.value,
    desc: toolDesc.value.trim() || "无描述",
    schema: toolSchema.value.trim() || "无",
  });
}

function addRag() {
  rags.value.unshift({
    name: ragName.value.trim() || "未命名",
    source: ragSource.value,
    vectorDB: ragVectorDB.value,
    strategy: ragStrategy.value.trim() || "未设置",
  });
}

function addTaskTemplate() {
  taskTemplates.value.unshift({
    name: taskTemplateName.value.trim() || "未命名",
    type: taskTemplateType.value,
    owner: taskTemplateOwner.value.trim() || "未指定",
    sla: taskTemplateSla.value.trim() || "60",
    evidence: taskTemplateEvidence.value.trim() || "无",
    approval: taskTemplateApproval.value,
  });
}

function addWorkflow() {
  workflows.value.unshift({
    name: workflowName.value.trim() || "未命名",
    type: workflowType.value,
    nodes: workflowNodes.value.trim() || "未设置",
    timeout: workflowTimeout.value.trim() || "60",
    retry: workflowRetry.value.trim() || "未设置",
  });
}

function addNotification() {
  notifications.value.unshift({
    name: notificationName.value.trim() || "未命名",
    channel: notificationChannel.value,
    trigger: notificationTrigger.value,
    template: notificationTemplate.value.trim() || "无模板",
  });
}

function addApproval() {
  approvals.value.unshift({
    name: approvalName.value.trim() || "未命名",
    type: approvalType.value,
    users: approvalUsers.value.trim() || "未指定",
    rule: approvalRule.value.trim() || "无规则",
    timeout: approvalTimeout.value,
  });
}

function addTimeline() {
  timelines.value.unshift({
    name: timelineName.value.trim() || "未命名",
    eventTypes: timelineEventTypes.value.trim() || "无",
    milestones: timelineMilestones.value.trim() || "无",
    timeRange: timelineTimeRange.value.trim() || "24",
  });
}

function addMetric() {
  metrics.value.unshift({
    name: metricName.value.trim() || "未命名",
    type: metricType.value,
    formula: metricFormula.value.trim() || "无",
    refresh: metricRefresh.value.trim() || "5",
  });
}

function addReportTemplate() {
  reportTemplates.value.unshift({
    name: reportTemplateName.value.trim() || "未命名",
    format: reportTemplateFormat.value,
    content: reportTemplateContent.value.trim() || "无",
    file: reportTemplateFile.value.trim() || "template.html",
  });
}

function formatTime(t: string | undefined) {
  if (!t) return "-";
  try {
    const d = new Date(t);
    return d.toLocaleString();
  } catch {
    return t;
  }
}

function relativeTime(t: string | undefined) {
  if (!t) return "";
  try {
    const d = new Date(t).getTime();
    const now = Date.now();
    const diff = Math.max(0, now - d);
    const sec = Math.round(diff / 1000);
    if (sec < 60) return `${sec} 秒前`;
    const min = Math.round(sec / 60);
    if (min < 60) return `${min} 分钟前`;
    const hr = Math.round(min / 60);
    if (hr < 24) return `${hr} 小时前`;
    const day = Math.round(hr / 24);
    return `${day} 天前`;
  } catch {
    return "";
  }
}

function payloadEntries(p: any) {
  if (!p || typeof p !== "object") return [];
  try {
    return Object.entries(p).map(([k, v]) => {
      return { k, raw: v, v: formatKvValue(v) };
    });
  } catch {
    return [];
  }
}

function formatKvValue(v: any) {
  if (v === null || v === undefined) return "-";
  if (typeof v === "string" || typeof v === "number" || typeof v === "boolean") return String(v);
  try {
    return JSON.stringify(v);
  } catch {
    return String(v);
  }
}

function prettyJson(v: any) {
  try {
    return JSON.stringify(v, null, 2);
  } catch {
    return String(v ?? "");
  }
}

// 证据展示：尽量把 photo/gps 从 JSON 中“可视化”
const EVIDENCE_DEMO_PHOTO =
  "data:image/svg+xml,%3Csvg%20xmlns%3D'http%3A//www.w3.org/2000/svg'%20width%3D'640'%20height%3D'360'%3E%3Crect%20width%3D'640'%20height%3D'360'%20fill%3D'%230f172a'/%3E%3Cpath%20d%3D'M40%20300%20L210%20160%20L320%20240%20L430%20140%20L600%20300%20Z'%20fill%3D'%231e40af'/%3E%3Ccircle%20cx%3D'510'%20cy%3D'120'%20r%3D'32'%20fill%3D'%2393c5fd'/%3E%3Ctext%20x%3D'40'%20y%3D'70'%20fill%3D'%23e2e8f0'%20font-size%3D'22'%20font-family%3D'Arial'%3E%E8%AF%81%E6%8D%AE%E7%85%A7%E7%89%87%EF%BC%88%E6%BC%94%E7%A4%BA%EF%BC%89%3C/text%3E%3Ctext%20x%3D'40'%20y%3D'105'%20fill%3D'%2393c5fd'%20font-size%3D'14'%20font-family%3D'Arial'%3EGPS%20%2B%20Photo%20Preview%3C/text%3E%3C/svg%3E";
// 证据图片：用 Vite 资源导入，避免 public/中文路径与 Dockerfile 未 COPY public 导致的 404
const EVIDENCE_PHOTO_POLICE = evidencePoliceUrl;
const EVIDENCE_PHOTO_DRAINAGE = evidenceDrainageUrl;

// 全局图片预览弹框（用于证据照片等）
const imagePreview = reactive<{ open: boolean; src: string }>({ open: false, src: "" });
function openImagePreview(src: string) {
  const s = (src || "").trim();
  if (!s) return;
  imagePreview.src = s;
  imagePreview.open = true;
}
function closeImagePreview() {
  imagePreview.open = false;
  imagePreview.src = "";
}
function onPreviewImgError(evt: Event) {
  const img = evt.target as HTMLImageElement | null;
  if (!img) return;
  img.src = EVIDENCE_DEMO_PHOTO;
}

function parseGpsAny(gps: any): { raw: string; lat: number | null; lng: number | null } {
  if (gps === null || gps === undefined) return { raw: "", lat: null, lng: null };
  // 字符串："lat,lng" 或 "lat lng"
  if (typeof gps === "string") {
    const raw = gps.trim();
    const parts = raw.split(/[,\s]+/).map((x) => x.trim()).filter(Boolean);
    const lat = parts[0] ? Number(parts[0]) : NaN;
    const lng = parts[1] ? Number(parts[1]) : NaN;
    return {
      raw,
      lat: Number.isFinite(lat) ? lat : null,
      lng: Number.isFinite(lng) ? lng : null,
    };
  }
  // 数组：[lat, lng]
  if (Array.isArray(gps) && gps.length >= 2) {
    const lat = Number(gps[0]);
    const lng = Number(gps[1]);
    const raw = `${gps[0]},${gps[1]}`;
    return { raw, lat: Number.isFinite(lat) ? lat : null, lng: Number.isFinite(lng) ? lng : null };
  }
  // 对象：{lat,lng} 或 {latitude,longitude}
  if (typeof gps === "object") {
    const lat = Number((gps as any).lat ?? (gps as any).latitude);
    const lng = Number((gps as any).lng ?? (gps as any).lon ?? (gps as any).longitude);
    const raw = `${(gps as any).lat ?? (gps as any).latitude ?? ""},${(gps as any).lng ?? (gps as any).longitude ?? ""}`.trim();
    return { raw, lat: Number.isFinite(lat) ? lat : null, lng: Number.isFinite(lng) ? lng : null };
  }
  return { raw: String(gps ?? ""), lat: null, lng: null };
}

function normalizeEvidence(raw: any): { gps: any; photo: any } {
  if (raw && typeof raw === "object") {
    // 兼容 evidence 可能被包了一层：{ evidence: { gps, photo } }
    const inner = (raw as any).evidence && typeof (raw as any).evidence === "object" ? (raw as any).evidence : raw;
    return { gps: (inner as any).gps, photo: (inner as any).photo };
  }
  // 如果后端把 evidence 存成字符串 JSON
  if (typeof raw === "string") {
    try {
      const obj = JSON.parse(raw);
      return normalizeEvidence(obj);
    } catch {
      return { gps: null, photo: null };
    }
  }
  return { gps: null, photo: null };
}

function isLikelyImageSrc(s: string) {
  const v = (s || "").trim();
  if (!v) return false;
  if (v.startsWith("data:image/")) return true;
  if (/^https?:\/\//i.test(v)) return true;
  if (v.startsWith("/") || v.startsWith("./") || v.startsWith("../")) return true;
  if (/\.(png|jpg|jpeg|webp|gif)(\?.*)?$/i.test(v)) return true;
  return false;
}

function extractPhotoSrc(photo: any): string {
  if (!photo) return "";
  // 数组：取第一张
  if (Array.isArray(photo) && photo.length) return extractPhotoSrc(photo[0]);
  // 字符串：URL / data / placeholder
  if (typeof photo === "string") {
    const s = photo.trim();
    if (!s) return "";
    if (s === "placeholder") return EVIDENCE_DEMO_PHOTO;
    if (isLikelyImageSrc(s)) return s;
    // base64（无前缀）
    if (/^[A-Za-z0-9+/=]+$/.test(s) && s.length > 200) return `data:image/jpeg;base64,${s}`;
    return "";
  }
  // 对象：常见字段兼容
  if (typeof photo === "object") {
    const s =
      String((photo as any).url || (photo as any).src || (photo as any).data || (photo as any).base64 || (photo as any).path || "").trim();
    return extractPhotoSrc(s);
  }
  return "";
}

function onEvidenceImgError(evt: Event) {
  const img = evt.target as HTMLImageElement | null;
  if (!img) return;
  // 避免死循环
  if (img.dataset && img.dataset.fallbackApplied === "1") return;
  if (img.dataset) img.dataset.fallbackApplied = "1";
  img.src = EVIDENCE_DEMO_PHOTO;
}

function evidenceView(raw: any) {
  const ev = normalizeEvidence(raw);
  const gpsParsed = parseGpsAny(ev.gps);
  const hasGps = gpsParsed.lat !== null && gpsParsed.lng !== null;
  const lat = hasGps ? gpsParsed.lat!.toFixed(6) : "";
  const lng = hasGps ? gpsParsed.lng!.toFixed(6) : "";
  // 高德 marker（lng,lat）
  const mapUrl = hasGps ? `https://uri.amap.com/marker?position=${lng},${lat}&name=%E4%BB%BB%E5%8A%A1%E5%AE%9A%E4%BD%8D` : "";
  const photoSrc = extractPhotoSrc(ev.photo);
  return {
    has_gps: hasGps,
    lat,
    lng,
    lat_num: hasGps ? gpsParsed.lat : null,
    lng_num: hasGps ? gpsParsed.lng : null,
    gps_raw: gpsParsed.raw || (hasGps ? `${lat},${lng}` : ""),
    map_url: mapUrl,
    photo_src: photoSrc,
  };
}

// 证据内嵌地图（数字孪生风格）：Leaflet 小地图 + 点位
type EvidenceMapEntry = { map: L.Map; marker: L.CircleMarker };
const evidenceMaps = new Map<string, EvidenceMapEntry>();

function evidenceMapDomId(scope: string, idx: number) {
  return `evi-map-${scope}-${idx}`;
}

function destroyEvidenceMap(domId: string) {
  const entry = evidenceMaps.get(domId);
  if (!entry) return;
  try {
    entry.map.remove();
  } catch {
    // ignore
  }
  evidenceMaps.delete(domId);
}

async function ensureEvidenceMap(domId: string, lat: number, lng: number) {
  await nextTick();
  const el = document.getElementById(domId);
  if (!el) return;

  const existing = evidenceMaps.get(domId);
  if (existing) {
    existing.map.setView([lat, lng], Math.max(existing.map.getZoom(), 16), { animate: true });
    existing.marker.setLatLng([lat, lng]);
    setTimeout(() => existing.map.invalidateSize(), 0);
    return;
  }

  const m = L.map(el, {
    zoomControl: true,
    scrollWheelZoom: true,
    attributionControl: false,
  }).setView([lat, lng], 16);

  // 与主“数字孪生地图”保持一致的底图来源
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
  }).addTo(m);

  const marker = L.circleMarker([lat, lng], {
    color: "#a855f7",
    radius: 10,
    weight: 2,
    fillOpacity: 0.45,
  }).addTo(m);

  evidenceMaps.set(domId, { map: m, marker });
  setTimeout(() => m.invalidateSize(), 0);
}

async function onEvidenceToggle(evt: Event, domId: string, raw: any) {
  const details = evt.target as HTMLDetailsElement | null;
  const opened = !!details?.open;
  if (!opened) {
    destroyEvidenceMap(domId);
    return;
  }
  const ev = evidenceView(raw);
  if (ev.has_gps && typeof ev.lat_num === "number" && typeof ev.lng_num === "number") {
    await ensureEvidenceMap(domId, ev.lat_num, ev.lng_num);
  }
}

async function copyText(text: string) {
  const t = (text || "").trim();
  if (!t) return;
  try {
    await navigator.clipboard.writeText(t);
  } catch {
    // 兜底：无权限/不支持时忽略
  }
}

function fieldLabel(key: string) {
  const k = String(key || "");
  const table: Record<string, string> = {
    title: "标题",
    target: "目标",
    target_id: "目标",
    target_object_id: "目标",
    area_id: "区域",
    task_id: "任务ID",
    task_type: "任务类型",
    type: "类型",
    owner_org: "责任单位",
    owner: "责任单位",
    sla_minutes: "时限（分钟）",
    sla: "时限",
    status: "状态",
    actor: "执行人",
    note: "备注",
    evidence: "证据",
    gps: "定位",
    photo: "照片",
    video: "视频",
    created_at: "创建时间",
    time: "时间",
  };
  return table[k] || k;
}

function eventTypeLabel(type: any) {
  const t = String(type || "").trim();
  const table: Record<string, string> = {
    incident_created: "事件创建",
    alert_event: "告警事件",
    task_created: "任务创建",
    task_ack: "任务回执",
    task_completed: "任务完成",
    state_changed: "状态变更",
    task_timeout: "任务超时",
  };
  return table[t] || t || "-";
}

function formatPercent(rate: any) {
  let n = Number(rate ?? 0);
  if (!Number.isFinite(n)) n = 0;
  // 兼容后端返回 0-1 或 0-100
  if (n <= 1) n = n * 100;
  n = Math.max(0, Math.min(100, n));
  const s = Math.abs(n - Math.round(n)) < 1e-9 ? String(Math.round(n)) : n.toFixed(1);
  return `${s}%`;
}

function stringify(obj: any) {
  try {
    return JSON.stringify(obj);
  } catch {
    return String(obj ?? "");
  }
}

async function loadTasks() {
  const { data } = await axios.get(`${apiBase}/workflow/incidents/${incidentId.value}/tasks`);
  tasks.value = data;
}

async function ackAllDone() {
  for (const t of tasks.value) {
    const org = String(t?.owner_org || "");
    const photo =
      org.includes("交警") || org.toLowerCase().includes("police")
        ? EVIDENCE_PHOTO_POLICE
        : org.includes("排水") || org.includes("水务") || org.includes("泵") || org.includes("运维")
          ? EVIDENCE_PHOTO_DRAINAGE
          : "placeholder";
    await axios.post(`${apiBase}/workflow/tasks/${t.task_id}/ack`, {
      actor: "demo-mobile",
      status: "done",
      note: "演示回执：已完成",
      evidence: { gps: "39.9991,116.3269", photo },
    });
  }
  await loadTasks();
  // 分步闭环：回执完成后进入战报页
  if (activePage.value === "flow") {
    flowStep.value = "report";
  }
}

async function loadReport() {
  const { data } = await axios.get(`${apiBase}/reports/incidents/${incidentId.value}`);
  reportData.value = data;
  reportOut.value = JSON.stringify(data, null, 2);
}

loadTopN().catch(() => {});

function renderMap() {
  if (!mapRef.value) return;
  // 可能在“主演示页”与“闭环分步页”之间切换，map 容器会变化；此时需销毁旧 map 再重建
  if (map && mapRef.value && map.getContainer && map.getContainer() !== mapRef.value) {
    map.remove();
    map = null;
    markers = {};
  }
  if (!map) {
    map = L.map(mapRef.value, {
      zoomControl: true,
      scrollWheelZoom: true,
      attributionControl: false,
    }).setView([39.9991, 116.3269], 15);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
    }).addTo(map);
  }

  // 清理旧标记
  Object.values(markers).forEach((m) => m.remove());
  markers = {};

  const areaCenters: Record<string, [number, number]> = {
    "A-001": [39.9991, 116.3269],
    "A-002": [40.0105, 116.3365],
    "A-003": [39.9905, 116.3165],
  };

  const getCoord = (id: string, area: string | undefined) => {
    if (targetCoords[id]) return targetCoords[id];
    const center = areaCenters[area || "A-001"] || [39.9991, 116.3269];
    const hash = id.split("").reduce((s, c) => s + c.charCodeAt(0), 0);
    const lat = center[0] + ((hash % 10) - 5) * 0.002;
    const lng = center[1] + (((hash / 10) % 10) - 5) * 0.002;
    return [lat, lng] as [number, number];
  };

  topN.value.forEach((item) => {
    const coord = getCoord(item.target_id, item.area_id);
    const color =
      item.risk_level === "红"
        ? "#dc2626" // 红
        : item.risk_level === "橙"
          ? "#f97316" // 橙（更亮、更偏黄）
          : item.risk_level === "黄"
            ? "#fbbf24" // 黄
            : "#15803d"; // 深绿
    const radius = Math.max(6, Math.min(14, item.risk_score)); // 用风险分控制大小
    const marker = L.circleMarker(coord, {
      color,
      radius,
      weight: item.target_id === selectedTarget.value ? 3 : 1.5,
      fillOpacity: 0.55,
    })
      .addTo(map!)
      .bindPopup(
        `<strong>${targetLabel(item.target_id, item.area_id || areaId.value)}</strong><br/>风险: ${item.risk_level}<br/>分数: ${item.risk_score.toFixed(
          2,
        )}<br/>置信度: ${item.confidence.toFixed(2)}<br/>解释: ${(item.explain_factors || []).slice(0, 3).join(" / ")}`
      )
      .on("click", () => {
        pickTarget(item.target_id);
      });
    markers[item.target_id] = marker;
  });

  // 若有选中的点，则居中并高亮
  if (selectedTarget.value && markers[selectedTarget.value]) {
    markers[selectedTarget.value].openPopup();
    map.setView(markers[selectedTarget.value].getLatLng(), 13, { animate: true });
  }
}

watch(
  () => selectedTarget.value,
  () => {
    renderMap();
  }
);

watch(
  () => [activePage.value, flowStep.value, selectedTarget.value] as const,
  () => {
    if (activePage.value === "flow" && flowStep.value === "agent" && selectedTarget.value) {
      ensureObjectState(selectedTarget.value).catch(() => {});
    }
  }
);
</script>

<style scoped>
.wrap {
  font-family: "Inter", "Segoe UI", system-ui, -apple-system, Helvetica, Arial, sans-serif;
  padding: 16px;
  color: #e5ecff;
  background: radial-gradient(80% 120% at 20% 20%, rgba(76, 123, 255, 0.18), transparent),
    radial-gradient(70% 100% at 80% 10%, rgba(16, 185, 129, 0.15), transparent),
    #0c1220;
  min-height: 100vh;
}
.hdr {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 12px;
  padding: 14px 14px;
  border-radius: 14px;
  background: linear-gradient(135deg, rgba(64, 82, 255, 0.25), rgba(26, 190, 225, 0.2));
  border: 1px solid rgba(255, 255, 255, 0.08);
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.25);
  backdrop-filter: blur(8px);
}
.title {
  font-size: 20px;
  font-weight: 800;
  letter-spacing: 0.3px;
}
.meta {
  display: flex;
  gap: 12px;
  color: #c5d1ff;
  font-size: 12px;
}
.tabs button {
  border: 1px solid rgba(255, 255, 255, 0.18);
  background: transparent;
  color: #d8e5ff;
  padding: 6px 10px;
  border-radius: 10px;
}
.tabs button.active {
  background: linear-gradient(135deg, #4f8bff, #3dd6d0);
  color: #0c1220;
}

.flow-hdr {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
}
.flow-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
.flow-progress {
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  padding: 12px;
  background: rgba(255, 255, 255, 0.03);
  margin-bottom: 14px;
}
.flow-bar {
  height: 10px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
  overflow: hidden;
}
.flow-bar-fill {
  height: 100%;
  background: linear-gradient(135deg, #4f8bff, #3dd6d0);
  width: 0%;
  transition: width 220ms ease;
}
.flow-meta {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 10px;
}
.flow-steps {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 10px;
}
.flow-steps button {
  border: 1px solid rgba(255, 255, 255, 0.18);
  background: rgba(255, 255, 255, 0.02);
  color: #d8e5ff;
  padding: 6px 10px;
  border-radius: 10px;
}
.flow-steps button.active {
  background: linear-gradient(135deg, #4f8bff, #3dd6d0);
  color: #0c1220;
}
.flow-page {
  margin-top: 10px;
}

.plan {
  margin-top: 10px;
  display: grid;
  gap: 12px;
}
.plan-card {
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  padding: 12px;
  background: rgba(255, 255, 255, 0.03);
}
.plan-title {
  font-weight: 800;
  color: #e5ecff;
  margin-bottom: 10px;
}
.plan-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 10px;
}
.plan-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 10px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.06);
}
.plan-item span {
  color: #9fb2d4;
  font-size: 12px;
}
.plan-item strong {
  color: #e5ecff;
  font-size: 13px;
  line-height: 1.35;
}
.plan-card summary.plan-title {
  cursor: pointer;
  user-select: none;
}

.org-badge {
  display: inline-flex;
  align-items: center;
  max-width: 240px;
  padding: 4px 8px;
  border-radius: 999px;
  font-size: 12px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  background: rgba(255, 255, 255, 0.04);
  color: #e5ecff;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.org-badge.tone-blue {
  background: rgba(79, 139, 255, 0.18);
  border-color: rgba(79, 139, 255, 0.35);
}
.org-badge.tone-green {
  background: rgba(16, 185, 129, 0.18);
  border-color: rgba(16, 185, 129, 0.35);
}
.org-badge.tone-orange {
  background: rgba(249, 115, 22, 0.18);
  border-color: rgba(249, 115, 22, 0.35);
}
.org-badge.tone-red {
  background: rgba(220, 38, 38, 0.18);
  border-color: rgba(220, 38, 38, 0.35);
}
.org-badge.tone-gray {
  background: rgba(148, 163, 184, 0.14);
  border-color: rgba(148, 163, 184, 0.28);
}
.grid {
  margin-top: 14px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}
.grid.single {
  grid-template-columns: 1fr;
}
.stack-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 12px;
  margin-top: 12px;
}
.stack-card {
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  padding: 12px;
  background: rgba(255, 255, 255, 0.04);
}
.stack-title {
  font-weight: 700;
  margin-bottom: 8px;
  color: #e5ecff;
}
.stack-items {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.stack-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.06);
}
.stack-item strong {
  color: #e5ecff;
  font-size: 13px;
}
.stack-item span {
  color: #9fb2d4;
  font-size: 12px;
}
.flow-diagram {
  margin-top: 16px;
  margin-bottom: 16px;
  padding: 16px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.02);
}
.flow-title {
  font-weight: 700;
  margin-bottom: 12px;
  text-align: center;
}
.flow-steps {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
}
.flow-step {
  flex: 1;
  min-width: 140px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 12px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
}
.step-num {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: linear-gradient(135deg, #4f8bff, #3dd6d0);
  color: #0c1220;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 800;
  font-size: 14px;
}
.step-content {
  text-align: center;
}
.step-title {
  font-weight: 700;
  margin-bottom: 4px;
  font-size: 13px;
}
.step-desc {
  font-size: 12px;
  color: #9fb2d4;
}
.step-agent {
  margin-top: 6px;
  padding-top: 6px;
  border-top: 1px dashed rgba(255, 255, 255, 0.1);
  font-size: 11px;
}
.step-steps {
  margin-top: 8px;
  padding-left: 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.step-step-item {
  font-size: 11px;
  color: #cbd5e1;
  line-height: 1.5;
  padding: 2px 0;
  border-left: 2px solid rgba(59, 130, 246, 0.3);
  padding-left: 8px;
  background: rgba(59, 130, 246, 0.05);
  border-radius: 2px;
}

/* 总结页面样式 */
.arch-diagram {
  margin-bottom: 32px;
  padding: 24px;
  background: linear-gradient(135deg, rgba(15, 23, 42, 0.8), rgba(30, 41, 59, 0.8));
  border: 1px solid rgba(59, 130, 246, 0.3);
  border-radius: 12px;
}
.arch-diagram-title {
  font-size: 18px;
  font-weight: 600;
  color: #93c5fd;
  text-align: center;
  margin-bottom: 24px;
  padding-bottom: 12px;
  border-bottom: 1px solid rgba(59, 130, 246, 0.3);
}
.arch-layers {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  margin-bottom: 32px;
}
.arch-layer-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
  max-width: 600px;
}
.layer-box {
  width: 100%;
  padding: 16px 20px;
  background: rgba(15, 23, 42, 0.6);
  border: 2px solid rgba(59, 130, 246, 0.3);
  border-radius: 8px;
  display: flex;
  align-items: center;
  gap: 16px;
  transition: all 0.3s ease;
}
.layer-box:hover {
  background: rgba(15, 23, 42, 0.8);
  border-color: rgba(59, 130, 246, 0.5);
  transform: translateX(4px);
}
.layer-id {
  min-width: 50px;
  height: 50px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #3b82f6, #9333ea);
  color: white;
  font-weight: bold;
  font-size: 18px;
  border-radius: 8px;
  box-shadow: 0 4px 6px rgba(59, 130, 246, 0.3);
}
.layer-name {
  flex: 1;
  font-size: 16px;
  font-weight: 600;
  color: #e2e8f0;
}
.layer-desc {
  font-size: 12px;
  color: #9fb2d4;
  line-height: 1.5;
  text-align: right;
}
.layer-arrow {
  font-size: 24px;
  color: rgba(59, 130, 246, 0.5);
  margin: 4px 0;
  animation: pulse 2s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 0.5; }
  50% { opacity: 1; }
}
.layer-l0 .layer-box { border-color: rgba(59, 130, 246, 0.4); }
.layer-l1 .layer-box { border-color: rgba(34, 197, 94, 0.4); }
.layer-l2 .layer-box { border-color: rgba(251, 191, 36, 0.4); }
.layer-l3 .layer-box { border-color: rgba(249, 115, 22, 0.4); }
.layer-l4 .layer-box { border-color: rgba(147, 51, 234, 0.4); }
.layer-l5 .layer-box { border-color: rgba(236, 72, 153, 0.4); }
.layer-l6 .layer-box { border-color: rgba(59, 130, 246, 0.4); }

.arch-data-flow {
  margin-top: 32px;
  padding: 20px;
  background: rgba(15, 23, 42, 0.4);
  border-radius: 8px;
  border: 1px dashed rgba(59, 130, 246, 0.3);
}
.flow-title {
  font-size: 14px;
  font-weight: 600;
  color: #60a5fa;
  margin-bottom: 16px;
  text-align: center;
}
.flow-items {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.flow-item {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  gap: 8px;
  padding: 12px;
  background: rgba(15, 23, 42, 0.6);
  border-radius: 6px;
}
.flow-label {
  font-size: 13px;
  color: #cbd5e1;
  padding: 4px 8px;
  background: rgba(59, 130, 246, 0.1);
  border-radius: 4px;
}
.flow-arrow {
  font-size: 16px;
  color: #60a5fa;
  font-weight: bold;
}

.agent-data-detail {
  margin-top: 32px;
  padding: 24px;
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(147, 51, 234, 0.3);
  border-radius: 12px;
}
.detail-title {
  font-size: 18px;
  font-weight: 600;
  color: #a78bfa;
  margin-bottom: 24px;
  padding-bottom: 12px;
  border-bottom: 2px solid rgba(147, 51, 234, 0.3);
  text-align: center;
}
.detail-section {
  margin-bottom: 32px;
}
.detail-section:last-child {
  margin-bottom: 0;
}
.detail-subtitle {
  font-size: 16px;
  font-weight: 600;
  color: #c4b5fd;
  margin-bottom: 16px;
  padding-left: 12px;
  border-left: 3px solid rgba(147, 51, 234, 0.5);
}
.detail-content {
  padding-left: 20px;
}
.data-structure {
  margin-bottom: 16px;
}
.struct-label {
  font-size: 14px;
  font-weight: 600;
  color: #93c5fd;
  margin-bottom: 8px;
}
.code-block {
  background: rgba(15, 23, 42, 0.9);
  border: 1px solid rgba(59, 130, 246, 0.3);
  border-radius: 6px;
  padding: 16px;
  font-family: 'Courier New', 'Monaco', 'Consolas', monospace;
  font-size: 12px;
  line-height: 1.6;
  color: #60a5fa;
  overflow-x: auto;
  white-space: pre-wrap;
  word-wrap: break-word;
}
.data-note {
  margin-top: 12px;
  padding: 12px;
  background: rgba(59, 130, 246, 0.1);
  border-left: 3px solid rgba(59, 130, 246, 0.5);
  border-radius: 4px;
  font-size: 13px;
  color: #cbd5e1;
  line-height: 1.6;
}
.data-note strong {
  color: #93c5fd;
}
.process-flow {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 16px;
  background: rgba(15, 23, 42, 0.4);
  border-radius: 8px;
}
.process-step {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px;
  background: rgba(147, 51, 234, 0.1);
  border: 1px solid rgba(147, 51, 234, 0.3);
  border-radius: 6px;
}
.process-step .step-num {
  min-width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #9333ea, #7c3aed);
  color: white;
  font-weight: bold;
  font-size: 14px;
  border-radius: 50%;
  flex-shrink: 0;
}
.process-step .step-text {
  flex: 1;
  font-size: 13px;
  color: #cbd5e1;
  line-height: 1.6;
}
.process-arrow {
  text-align: center;
  font-size: 20px;
  color: rgba(147, 51, 234, 0.6);
  margin: 4px 0;
}

.l4-l5-linkage {
  margin-top: 32px;
  padding: 24px;
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(236, 72, 153, 0.3);
  border-radius: 12px;
}
.linkage-title {
  font-size: 18px;
  font-weight: 600;
  color: #f472b6;
  margin-bottom: 24px;
  padding-bottom: 12px;
  border-bottom: 2px solid rgba(236, 72, 153, 0.3);
  text-align: center;
}
.linkage-section {
  margin-bottom: 32px;
}
.linkage-section:last-child {
  margin-bottom: 0;
}
.linkage-subtitle {
  font-size: 16px;
  font-weight: 600;
  color: #f9a8d4;
  margin-bottom: 16px;
  padding-left: 12px;
  border-left: 3px solid rgba(236, 72, 153, 0.5);
}
.linkage-content {
  padding-left: 20px;
}
.linkage-item {
  margin-bottom: 20px;
  padding: 16px;
  background: rgba(15, 23, 42, 0.4);
  border: 1px solid rgba(236, 72, 153, 0.2);
  border-radius: 6px;
}
.item-title {
  font-size: 14px;
  font-weight: 600;
  color: #f9a8d4;
  margin-bottom: 8px;
}
.item-desc {
  font-size: 13px;
  color: #cbd5e1;
  line-height: 1.6;
}
.item-desc code {
  background: rgba(236, 72, 153, 0.2);
  padding: 2px 6px;
  border-radius: 3px;
  font-family: 'Courier New', monospace;
  color: #f9a8d4;
}

.node-diagram {
  padding: 20px;
  background: rgba(15, 23, 42, 0.4);
  border-radius: 8px;
  overflow-x: auto;
}
.node-flow {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: fit-content;
}
.node-item {
  min-width: 120px;
  padding: 12px;
  background: rgba(236, 72, 153, 0.1);
  border: 2px solid rgba(236, 72, 153, 0.3);
  border-radius: 6px;
  text-align: center;
}
.node-label {
  font-size: 13px;
  font-weight: 600;
  color: #f9a8d4;
  margin-bottom: 6px;
}
.node-desc {
  font-size: 11px;
  color: #cbd5e1;
  line-height: 1.4;
}
.node-details {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 12px;
}
.node-detail-item {
  padding: 10px 12px;
  background: rgba(236, 72, 153, 0.05);
  border-left: 2px solid rgba(236, 72, 153, 0.3);
  border-radius: 4px;
  font-size: 13px;
  color: #cbd5e1;
  line-height: 1.6;
}
.node-detail-item strong {
  color: #f9a8d4;
  font-weight: 600;
}
.node-arrow {
  font-size: 18px;
  color: rgba(236, 72, 153, 0.6);
  font-weight: bold;
  flex-shrink: 0;
}
.start-node {
  background: rgba(34, 197, 94, 0.1);
  border-color: rgba(34, 197, 94, 0.3);
}
.start-node .node-label {
  color: #86efac;
}
.gateway-node {
  background: rgba(251, 191, 36, 0.1);
  border-color: rgba(251, 191, 36, 0.3);
}
.gateway-node .node-label {
  color: #fde047;
}
.task-node {
  background: rgba(59, 130, 246, 0.1);
  border-color: rgba(59, 130, 246, 0.3);
}
.task-node .node-label {
  color: #93c5fd;
}
.condition-node {
  background: rgba(249, 115, 22, 0.1);
  border-color: rgba(249, 115, 22, 0.3);
}
.condition-node .node-label {
  color: #fdba74;
}
.approval-node {
  background: rgba(147, 51, 234, 0.1);
  border-color: rgba(147, 51, 234, 0.3);
}
.approval-node .node-label {
  color: #c4b5fd;
}
.execution-node {
  background: rgba(59, 130, 246, 0.1);
  border-color: rgba(59, 130, 246, 0.3);
}
.execution-node .node-label {
  color: #93c5fd;
}
.timer-node {
  background: rgba(220, 38, 38, 0.1);
  border-color: rgba(220, 38, 38, 0.3);
}
.timer-node .node-label {
  color: #fca5a5;
}
.evidence-node {
  background: rgba(34, 197, 94, 0.1);
  border-color: rgba(34, 197, 94, 0.3);
}
.evidence-node .node-label {
  color: #86efac;
}
.end-node {
  background: rgba(34, 197, 94, 0.1);
  border-color: rgba(34, 197, 94, 0.3);
}
.end-node .node-label {
  color: #86efac;
}

.sync-flow {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.sync-item {
  padding: 16px;
  background: rgba(15, 23, 42, 0.4);
  border-left: 3px solid rgba(236, 72, 153, 0.5);
  border-radius: 4px;
}
.sync-title {
  font-size: 14px;
  font-weight: 600;
  color: #f9a8d4;
  margin-bottom: 8px;
}
.sync-desc {
  font-size: 13px;
  color: #cbd5e1;
  line-height: 1.6;
}
.sync-desc strong {
  color: #f9a8d4;
}
.sync-desc ul {
  margin: 8px 0;
  padding-left: 20px;
}
.sync-desc li {
  margin-bottom: 4px;
}

.mapping-table {
  overflow-x: auto;
}
.linkage-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.linkage-table thead {
  background: rgba(236, 72, 153, 0.2);
}
.linkage-table th {
  padding: 12px;
  text-align: left;
  font-weight: 600;
  color: #f9a8d4;
  border-bottom: 2px solid rgba(236, 72, 153, 0.3);
}
.linkage-table td {
  padding: 10px 12px;
  color: #cbd5e1;
  border-bottom: 1px solid rgba(236, 72, 153, 0.1);
}
.linkage-table tbody tr:hover {
  background: rgba(236, 72, 153, 0.05);
}
.linkage-table code {
  background: rgba(236, 72, 153, 0.2);
  padding: 2px 6px;
  border-radius: 3px;
  font-family: 'Courier New', monospace;
  color: #f9a8d4;
}

.error-handling {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.error-item {
  padding: 16px;
  background: rgba(220, 38, 38, 0.1);
  border-left: 3px solid rgba(220, 38, 38, 0.5);
  border-radius: 4px;
}
.error-title {
  font-size: 14px;
  font-weight: 600;
  color: #fca5a5;
  margin-bottom: 8px;
}
.error-desc {
  font-size: 13px;
  color: #cbd5e1;
  line-height: 1.6;
}
.error-desc strong {
  color: #fca5a5;
}
.error-desc ul {
  margin: 8px 0;
  padding-left: 20px;
}
.error-desc li {
  margin-bottom: 4px;
}

.sequence-diagram {
  padding: 16px;
  background: rgba(15, 23, 42, 0.4);
  border-radius: 6px;
}

.summary-field-help {
  margin-bottom: 24px;
  padding: 20px;
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.1), rgba(147, 51, 234, 0.1));
  border: 1px solid rgba(59, 130, 246, 0.3);
  border-radius: 8px;
}
.field-help-title {
  font-size: 20px;
  font-weight: 600;
  color: #93c5fd;
  margin-bottom: 20px;
  padding-bottom: 12px;
  border-bottom: 2px solid rgba(59, 130, 246, 0.3);
}
.field-help-section {
  margin-bottom: 24px;
}
.field-help-section:last-child {
  margin-bottom: 0;
}
.section-title {
  font-size: 16px;
  font-weight: 600;
  color: #60a5fa;
  margin-bottom: 12px;
  padding-left: 8px;
  border-left: 3px solid rgba(59, 130, 246, 0.5);
}
.field-help-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 16px;
}
.field-help-item {
  padding: 16px;
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(59, 130, 246, 0.2);
  border-radius: 6px;
}
.field-name {
  font-size: 15px;
  font-weight: 600;
  color: #60a5fa;
  margin-bottom: 8px;
}
.field-desc {
  font-size: 13px;
  line-height: 1.7;
  color: #cbd5e1;
}
.field-desc .level-chip {
  display: inline-block;
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 11px;
  font-weight: 600;
  margin: 0 2px;
}
.field-desc .level-chip.red {
  background: rgba(220, 38, 38, 0.2);
  color: #fca5a5;
  border: 1px solid rgba(220, 38, 38, 0.4);
}
.field-desc .level-chip.orange {
  background: rgba(249, 115, 22, 0.2);
  color: #fdba74;
  border: 1px solid rgba(249, 115, 22, 0.4);
}
.field-desc .level-chip.yellow {
  background: rgba(251, 191, 36, 0.2);
  color: #fde047;
  border: 1px solid rgba(251, 191, 36, 0.4);
}
.field-desc .level-chip.green {
  background: rgba(21, 128, 61, 0.2);
  color: #86efac;
  border: 1px solid rgba(21, 128, 61, 0.4);
}
.summary-arch {
  display: flex;
  flex-direction: column;
  gap: 24px;
  margin-top: 20px;
}
.arch-layer {
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  background: rgba(15, 23, 42, 0.5);
  overflow: hidden;
}
.layer-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 20px;
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.2), rgba(147, 51, 234, 0.2));
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}
.layer-label {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  background: linear-gradient(135deg, #3b82f6, #9333ea);
  color: white;
  font-weight: bold;
  font-size: 16px;
  border-radius: 8px;
}
.layer-title {
  font-size: 18px;
  font-weight: 600;
  color: #e2e8f0;
}
.layer-content {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.summary-dimension {
  border-left: 3px solid rgba(59, 130, 246, 0.5);
  padding-left: 16px;
  padding-bottom: 16px;
}
.dim-title {
  font-size: 16px;
  font-weight: 600;
  color: #60a5fa;
  margin-bottom: 12px;
}
.dim-content {
  color: #cbd5e1;
  font-size: 14px;
  line-height: 1.8;
}
.dim-content ul {
  margin: 0;
  padding-left: 20px;
}
.dim-content li {
  margin-bottom: 8px;
}
.dim-content strong {
  color: #93c5fd;
}
.graph-example {
  background: rgba(15, 23, 42, 0.8);
  border: 1px solid rgba(59, 130, 246, 0.3);
  border-radius: 4px;
  padding: 12px;
  margin: 8px 0;
  font-family: 'Courier New', monospace;
  font-size: 12px;
  color: #60a5fa;
  white-space: pre-wrap;
  overflow-x: auto;
}
.summary-total {
  margin-top: 32px;
  padding: 24px;
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.15), rgba(147, 51, 234, 0.15));
  border: 1px solid rgba(59, 130, 246, 0.3);
  border-radius: 8px;
}
.summary-total h4 {
  font-size: 20px;
  font-weight: 600;
  color: #e2e8f0;
  margin-bottom: 16px;
}
.total-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.total-item {
  padding: 12px;
  background: rgba(15, 23, 42, 0.5);
  border-radius: 4px;
  color: #cbd5e1;
  font-size: 14px;
}
.total-item strong {
  color: #93c5fd;
}
.total-summary {
  margin-top: 8px;
  padding: 16px;
  background: rgba(59, 130, 246, 0.2);
  border-radius: 4px;
  font-size: 16px;
  color: #e2e8f0;
  text-align: center;
}
.total-summary strong {
  color: #93c5fd;
}
.highlight {
  color: #fbbf24;
  font-weight: bold;
  font-size: 18px;
}
.flow-arrow {
  font-size: 20px;
  color: #4f8bff;
  font-weight: 800;
}
@media (max-width: 980px) {
  .flow-steps {
    flex-direction: column;
  }
  .flow-arrow {
    transform: rotate(90deg);
  }
}
.ont-grid {
  /* L2 本体页：改为上下结构，保证每个模块都能完整展示 */
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 12px;
}
.ont-toolbar {
  display: grid;
  grid-template-columns: 1fr 140px 140px auto;
  gap: 8px;
  align-items: center;
}
.ont-toolbar input,
.ont-toolbar select {
  width: 100%;
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 10px;
  padding: 8px;
  font-size: 12px;
  background: rgba(255, 255, 255, 0.05);
  color: #e5ecff;
}
.ont-editor {
  border: 1px solid rgba(59, 130, 246, 0.25);
  border-radius: 12px;
  padding: 10px;
  background: rgba(59, 130, 246, 0.08);
}
.ont-editor-head {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 8px;
}
.ont-actions {
  display: flex;
  gap: 8px;
  margin-top: 6px;
}
.ont-table-wrap {
  overflow: auto;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  background: rgba(15, 23, 42, 0.35);
}
.ont-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}
.ont-table thead th {
  text-align: left;
  padding: 10px 10px;
  color: #93c5fd;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(15, 23, 42, 0.55);
  position: sticky;
  top: 0;
  z-index: 1;
}
.ont-table tbody td {
  padding: 10px 10px;
  vertical-align: top;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  color: #cbd5e1;
}
.ont-table tbody tr:hover {
  background: rgba(59, 130, 246, 0.08);
}
.ont-table tbody tr.row-active {
  background: rgba(147, 51, 234, 0.12);
  outline: 1px solid rgba(147, 51, 234, 0.25);
}
.cell-title {
  line-height: 1.25;
}
.chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 6px;
}
.chip {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.04);
  color: #cbd5e1;
  font-size: 11px;
  white-space: nowrap;
}
.chip.blue {
  border-color: rgba(59, 130, 246, 0.35);
  background: rgba(59, 130, 246, 0.12);
  color: #93c5fd;
}
.chip.green {
  border-color: rgba(21, 128, 61, 0.4);
  background: rgba(21, 128, 61, 0.18);
  color: #86efac;
}
.chip.yellow {
  border-color: rgba(251, 191, 36, 0.35);
  background: rgba(251, 191, 36, 0.12);
  color: #fde68a;
}
.chip.gray {
  border-color: rgba(148, 163, 184, 0.3);
  background: rgba(148, 163, 184, 0.08);
  color: #cbd5e1;
}
.btn-row {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.btn {
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 10px;
  padding: 7px 10px;
  font-size: 12px;
  background: rgba(255, 255, 255, 0.05);
  color: #e5ecff;
}
.btn:hover {
  border-color: rgba(59, 130, 246, 0.35);
  background: rgba(59, 130, 246, 0.12);
}
.btn.primary {
  border-color: rgba(59, 130, 246, 0.45);
  background: rgba(59, 130, 246, 0.18);
}
.btn.ghost {
  background: transparent;
}
.btn.danger {
  border-color: rgba(239, 68, 68, 0.4);
  background: rgba(239, 68, 68, 0.12);
}
.btn.tiny {
  padding: 4px 8px;
  font-size: 11px;
  border-radius: 9px;
}
.ont-split {
  /* 关系管理内部也改为上下结构：上列表下预览 */
  display: flex;
  flex-direction: column;
  gap: 10px;
  align-items: stretch;
}
.ont-preview {
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  padding: 10px;
  background: rgba(255, 255, 255, 0.03);
}
.ont-preview-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  margin-top: -4px;
  margin-bottom: 8px;
}
.ont-graph {
  width: 100%;
  height: 260px;
  border: 1px dashed rgba(255, 255, 255, 0.12);
  border-radius: 10px;
  background: rgba(15, 23, 42, 0.55);
}
.ont-graph:empty {
  min-height: 260px;
}
.inline-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}
.preset-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-top: 6px;
}
.preset-row select {
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 10px;
  padding: 6px 8px;
  font-size: 12px;
  background: rgba(255, 255, 255, 0.05);
  color: #e5ecff;
}
.evi-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 10px;
  margin-top: 10px;
}
.evi-photo {
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  overflow: hidden;
  background: rgba(15, 23, 42, 0.55);
}
.evi-photo img {
  display: block;
  width: 100%;
  height: auto;
  max-height: 220px;
  object-fit: cover;
  cursor: zoom-in;
}
.evi-photo.placeholder {
  padding: 16px;
  color: rgba(226, 232, 240, 0.75);
  font-size: 12px;
  text-align: center;
}
.evi-map {
  width: 100%;
  height: 220px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  overflow: hidden;
  background: rgba(15, 23, 42, 0.55);
}
.evi-map:empty {
  min-height: 220px;
}
.evi-meta {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.evi-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
.evi-link {
  color: #93c5fd;
  text-decoration: underline;
}
.kv-details.sub summary {
  cursor: pointer;
}

/* 全局图片预览弹框 */
.img-modal {
  position: fixed;
  inset: 0;
  background: rgba(2, 6, 23, 0.72);
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
}
.img-modal-card {
  width: min(1100px, 96vw);
  max-height: 90vh;
  background: rgba(15, 23, 42, 0.92);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 14px;
  overflow: hidden;
  box-shadow: 0 20px 70px rgba(0, 0, 0, 0.45);
}
.img-modal-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}
.img-modal-body {
  padding: 12px;
  overflow: auto;
  max-height: calc(90vh - 52px);
}
.img-modal-body img {
  display: block;
  width: 100%;
  height: auto;
  border-radius: 10px;
  background: rgba(2, 6, 23, 0.35);
}

@media (min-width: 980px) {
  .evi-grid {
    grid-template-columns: 1fr 1fr;
    align-items: start;
  }
  .evi-meta {
    grid-column: 1 / -1;
  }
}
@media (max-width: 980px) {
  .ont-toolbar {
    grid-template-columns: 1fr;
  }
  /* 旧的左右结构已移除，这里无需再改 */
}
.ont-card {
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  padding: 10px;
  background: rgba(255, 255, 255, 0.04);
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.ont-title {
  font-weight: 700;
  margin-bottom: 4px;
}
.ont-desc {
  font-size: 12px;
  margin-bottom: 10px;
}
.ont-form {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.form-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.form-row label {
  font-size: 12px;
  color: #9fb2d4;
  width: auto;
}
.ont-form input,
.ont-form select,
.ont-form textarea {
  width: 100%;
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 10px;
  padding: 8px;
  font-size: 12px;
  background: rgba(255, 255, 255, 0.05);
  color: #e5ecff;
}
.ont-form button {
  align-self: flex-start;
  margin-top: 4px;
}
.ont-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.ont-item {
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  padding: 8px;
  background: rgba(255, 255, 255, 0.03);
}
.ont-item strong {
  color: #e5ecff;
}
.small {
  font-size: 12px;
}
.card {
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 14px;
  padding: 14px;
  background: rgba(255, 255, 255, 0.04);
  overflow: hidden;
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.25);
  backdrop-filter: blur(10px);
}
.card.wide {
  grid-column: 1 / -1;
}
.map-and-list {
  display: grid;
  grid-template-columns: 1fr 1fr;
  align-items: start;
  gap: 12px;
  margin-bottom: 12px;
}
.map-card,
.list-card {
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  padding: 10px;
  background: rgba(255, 255, 255, 0.04);
  display: flex;
  flex-direction: column;
}
.map-title {
  font-weight: 700;
  margin-bottom: 6px;
}
.map {
  width: 100%;
  min-height: 260px;
  height: 100%;
  flex: 1 1 auto;
  border-radius: 10px;
  overflow: hidden;
}
.map-hint {
  margin-top: 6px;
  font-size: 12px;
}
/* Leaflet 默认图标修正 */
:global(.leaflet-container) {
  background: #0c1220;
  height: 100%;
}
:global(.leaflet-popup-content) {
  color: #0c1220;
}
.list-card table tr.active {
  background: rgba(79, 139, 255, 0.12);
}
.twin {
  margin-top: 10px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 12px;
  padding: 12px;
  background: linear-gradient(135deg, rgba(79, 139, 255, 0.08), rgba(61, 214, 208, 0.05));
}
.twin-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}
.twin-title {
  font-weight: 700;
}
.twin-meta {
  color: #9fb2d4;
  font-size: 12px;
}
.twin-body {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.twin-tiles {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 8px;
}
.tile {
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 10px;
  padding: 10px;
  background: rgba(255, 255, 255, 0.03);
}
.tile.big {
  grid-column: span 2;
}
.tile-top {
  color: #9fb2d4;
  font-size: 12px;
  margin-bottom: 6px;
}
.tile-num {
  font-size: 20px;
  font-weight: 800;
}
.tile-num.small {
  font-size: 16px;
}
.tile-bar {
  height: 6px;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 999px;
  margin-top: 8px;
  overflow: hidden;
}
.tile-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #4f8bff, #3dd6d0);
}
.badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.12);
}
.badge.level-红 {
  background: rgba(238, 9, 9, 0.2);
  border-color: rgba(220, 38, 38, 0.6);
  color: #fff;
}
.badge.level-橙 {
  background: rgba(229, 107, 19, 0.2);
  border-color: rgba(249, 115, 22, 0.6);
  color: #fff;
}
.badge.level-黄 {
  background: rgba(251, 191, 36, 0.2);
  border-color: rgba(251, 191, 36, 0.6);
  color: #fff;
}
.badge.level-绿 {
  background: rgba(21, 128, 61, 0.2);
  border-color: rgba(21, 128, 61, 0.6);
  color: #fff;
}
.twin-factors {
  border: 1px dashed rgba(255, 255, 255, 0.14);
  border-radius: 10px;
  padding: 10px;
  background: rgba(255, 255, 255, 0.02);
}
.twin-subtitle {
  font-weight: 700;
  margin-bottom: 6px;
}
.factor-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.factor-help {
  margin-top: 8px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  padding-top: 8px;
}
.help-title {
  font-weight: 600;
  margin-bottom: 6px;
}
.field-help {
  margin-bottom: 16px;
  padding: 12px 16px;
  background: rgba(59, 130, 246, 0.1);
  border: 1px solid rgba(59, 130, 246, 0.3);
  border-radius: 6px;
}
.field-help .help-title {
  font-size: 14px;
  font-weight: 600;
  color: #93c5fd;
  margin-bottom: 10px;
}
.field-help .help-content {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.field-help .help-item {
  font-size: 13px;
  line-height: 1.6;
  color: #cbd5e1;
}
.field-help .help-item strong {
  color: #60a5fa;
  font-weight: 600;
}
.field-help .level-chip {
  display: inline-block;
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 11px;
  font-weight: 600;
  margin: 0 2px;
}
.field-help .level-chip.red {
  background: rgba(220, 38, 38, 0.2);
  color: #fca5a5;
  border: 1px solid rgba(220, 38, 38, 0.4);
}
.field-help .level-chip.orange {
  background: rgba(249, 115, 22, 0.2);
  color: #fdba74;
  border: 1px solid rgba(249, 115, 22, 0.4);
}
.field-help .level-chip.yellow {
  background: rgba(251, 191, 36, 0.2);
  color: #fde047;
  border: 1px solid rgba(251, 191, 36, 0.4);
}
.field-help .level-chip.green {
  background: rgba(21, 128, 61, 0.2);
  color: #86efac;
  border: 1px solid rgba(21, 128, 61, 0.4);
}
.help-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 6px;
  font-size: 12px;
}
.help-grid strong {
  display: inline-block;
  min-width: 68px;
  color: #e5ecff;
}
.help-grid span {
  color: #9fb2d4;
}
.summary-tiles {
  margin-top: 12px;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 10px;
}
.s-tile {
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 10px;
  padding: 10px;
  background: rgba(255, 255, 255, 0.03);
}
.s-label {
  color: #9fb2d4;
  font-size: 12px;
  margin-bottom: 4px;
}
.s-value {
  font-size: 20px;
  font-weight: 800;
}
.s-sub {
  font-size: 12px;
}
.s-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.level-chip.red {
  background: rgba(220, 38, 38, 0.24);
  border-color: rgba(220, 38, 38, 0.6);
}
.level-chip.orange {
  background: rgba(249, 115, 22, 0.24);
  border-color: rgba(249, 115, 22, 0.6);
}
.level-chip.yellow {
  background: rgba(251, 191, 36, 0.24);
  border-color: rgba(251, 191, 36, 0.6);
}
.level-chip.green {
  background: rgba(21, 128, 61, 0.24);
  border-color: rgba(21, 128, 61, 0.6);
}
.row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 8px 0;
}
label {
  width: 48px;
  color: #9fb2d4;
  font-size: 12px;
}
input,
textarea {
  width: 100%;
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 10px;
  padding: 8px;
  font-size: 12px;
  background: rgba(255, 255, 255, 0.05);
  color: #e5ecff;
}
input::placeholder,
textarea::placeholder {
  color: #8fa0c4;
}
select {
  width: 200px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 10px;
  padding: 8px;
  font-size: 12px;
  background: rgba(255, 255, 255, 0.05);
  color: #e5ecff;
}
button {
  border: 1px solid rgba(255, 255, 255, 0.18);
  background: linear-gradient(135deg, #4f8bff, #3dd6d0);
  color: #0c1220;
  border-radius: 10px;
  padding: 8px 10px;
  font-size: 12px;
  cursor: pointer;
  transition: transform 0.05s ease, box-shadow 0.1s ease;
}
button.ghost {
  background: transparent;
  color: #d8e5ff;
  border-color: rgba(255, 255, 255, 0.2);
}
button:hover {
  transform: translateY(-1px);
  box-shadow: 0 8px 18px rgba(79, 139, 255, 0.25);
}
.tbl {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}
.tbl th,
.tbl td {
  text-align: left;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  padding: 8px 6px;
}
.tbl tbody tr:hover {
  background: rgba(255, 255, 255, 0.04);
  cursor: pointer;
}
.tbl tbody tr.level-红 {
  background: rgba(220, 38, 38, 0.32);
}
.tbl tbody tr.level-橙 {
  background: rgba(249, 115, 22, 0.32);
}
.tbl tbody tr.level-黄 {
  background: rgba(251, 191, 36, 0.32);
}
.tbl tbody tr.level-绿 {
  background: rgba(21, 128, 61, 0.32);
}
.muted {
  color: #9fb2d4;
}
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: 6px 0 8px;
}
.chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
  color: #dfe8ff;
  font-size: 12px;
  border: 1px solid rgba(255, 255, 255, 0.15);
}
.layer-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 10px;
  margin-top: 8px;
}
.layer-card {
  border: 1px dashed rgba(255, 255, 255, 0.12);
  border-radius: 10px;
  padding: 10px;
  background: rgba(255, 255, 255, 0.02);
}
.layer-title {
  font-weight: 700;
  margin-bottom: 4px;
}
.layer-desc {
  color: #9fb2d4;
  font-size: 12px;
  margin-bottom: 6px;
}
.layer-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.layer-list li {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  padding: 6px 8px;
}
.node-title {
  font-weight: 600;
  font-size: 13px;
}
.node-detail {
  color: #9fb2d4;
  font-size: 12px;
}
.hint {
  margin-top: 8px;
  color: #9fb2d4;
  font-size: 12px;
}
.box {
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  padding: 8px;
  background: rgba(255, 255, 255, 0.03);
}
.report-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 10px;
  margin-bottom: 8px;
}
.report-card {
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 10px;
  padding: 10px;
  background: rgba(255, 255, 255, 0.04);
}
.report-card.timeline {
  grid-column: 1 / -1;
}
.rc-title {
  font-weight: 700;
  margin-bottom: 6px;
}
.rc-main {
  font-size: 16px;
  font-weight: 700;
}
.rc-sub {
  color: #9fb2d4;
  font-size: 12px;
}
.rc-metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(80px, 1fr));
  gap: 6px;
}
.rc-metrics span {
  display: block;
  color: #9fb2d4;
  font-size: 11px;
}
.rc-metrics strong {
  font-size: 16px;
}
.timeline-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.timeline-list li {
  display: flex;
  gap: 8px;
  border-left: 2px solid rgba(255, 255, 255, 0.12);
  padding-left: 10px;
}
.tl-time {
  font-size: 12px;
  color: #9fb2d4;
  min-width: 150px;
}
.tl-body {
  flex: 1;
}
.tl-type {
  font-weight: 600;
}
.tl-payload {
  font-size: 12px;
  word-break: break-all;
}

/* 战报时间线（时间轴 v2：更强调时间效果与可读性） */
.timeline-list.v2 {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.timeline-list.v2 li.tl-item {
  display: grid;
  grid-template-columns: 18px 1fr;
  gap: 10px;
  padding: 10px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.06);
}
.tl-left {
  display: flex;
  flex-direction: column;
  align-items: center;
}
.tl-dot {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background: linear-gradient(135deg, #4f8bff, #3dd6d0);
  box-shadow: 0 0 0 4px rgba(79, 139, 255, 0.15);
  margin-top: 4px;
}
.tl-line {
  width: 2px;
  flex: 1;
  background: rgba(255, 255, 255, 0.12);
  margin-top: 6px;
  border-radius: 99px;
}
.tl-head {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 4px 10px;
  align-items: baseline;
}
.timeline-list.v2 .tl-time {
  min-width: auto;
  color: #c5d1ff;
  text-align: right;
}
.tl-rel {
  grid-column: 2;
  font-size: 12px;
  text-align: right;
}
.timeline-list.v2 .tl-type {
  font-weight: 800;
}
.tl-kv {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.kv-row {
  display: grid;
  grid-template-columns: 120px 1fr;
  gap: 10px;
}
.kv-k {
  color: #c5d1ff;
  font-size: 12px;
}
.kv-v {
  color: #9fb2d4;
  font-size: 12px;
  word-break: break-word;
}
.pre {
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 12px;
  line-height: 1.4;
}
@media (max-width: 980px) {
  .grid {
    grid-template-columns: 1fr;
  }
}
</style>


