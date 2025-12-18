<template>
  <div class="wrap">
    <header class="hdr">
      <div class="title">城市暴雨内涝指挥（演示级）</div>
      <div class="meta">
        <span>API: {{ apiBase }}</span>
        <span>智能体: {{ agentBase }}</span>
      </div>
      <div class="meta tabs">
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

<main class="grid" v-if="activePage === 'main'">
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
            <div class="map-hint muted">示例坐标基于重庆城区，按风险色彩/大小呈现 TopN 点位；点击点位或列表联动。</div>
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
                  <td>{{ it.target_id }}</td>
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
            <div class="s-sub muted" v-if="riskSummary.maxId">目标：{{ riskSummary.maxId }}</div>
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
            <div class="twin-title">数字孪生视图 · {{ selectedTargetObj.target_id }}</div>
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
          <span class="chip muted">当前区域：{{ areaId }}</span>
          <span class="chip" :class="{ muted: !selectedTarget }">当前目标：{{ selectedTarget || "未选择" }}</span>
        </div>
        <textarea v-model="chatInput" rows="4" placeholder="输入：例如“请研判并一键下发任务包”"></textarea>
        <div class="row">
          <button @click="sendChat">发送</button>
          <button class="ghost" @click="fillOneClick">一键派单口令</button>
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
              <td>{{ t.target_object_id }}</td>
              <td>{{ t.owner_org }}</td>
              <td>{{ t.status }}</td>
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
            <div class="rc-title">事件</div>
            <div class="rc-main">{{ reportData.title || reportData.incident_id }}</div>
            <div class="rc-sub">状态：{{ reportData.status }}</div>
          </div>
          <div class="report-card">
            <div class="rc-title">任务指标</div>
            <div class="rc-metrics">
              <div><span>总数</span><strong>{{ reportData.metrics?.task_total ?? "-" }}</strong></div>
              <div><span>完成</span><strong>{{ reportData.metrics?.task_done ?? "-" }}</strong></div>
              <div><span>完成率</span><strong>{{ (reportData.metrics?.task_done_rate ?? 0) | percent }}</strong></div>
            </div>
          </div>
          <div class="report-card timeline">
            <div class="rc-title">时间线</div>
            <ul class="timeline-list">
              <li v-for="(e, idx) in reportData.timeline" :key="idx">
                <div class="tl-time">{{ formatTime(e.time) }}</div>
                <div class="tl-body">
                  <div class="tl-type">{{ e.type }}</div>
                  <div class="tl-payload muted">{{ stringify(e.payload) }}</div>
                </div>
              </li>
            </ul>
          </div>
        </div>
        <div class="box">
          <div class="muted">原始 JSON：</div>
          <pre class="pre">{{ reportOut }}</pre>
        </div>
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
        <div class="ont-desc muted">定义本体中的实体类型（如路段、泵站、事件等）及其属性</div>
        <div class="ont-form">
          <div class="form-row">
            <label>实体ID</label>
            <input v-model="ontologyEntityId" placeholder="如 road-segment" />
          </div>
          <div class="form-row">
            <label>名称</label>
            <input v-model="ontologyEntityLabel" placeholder="如 路段" />
          </div>
          <div class="form-row">
            <label>类型</label>
            <select v-model="ontologyEntityType">
              <option>实体</option>
              <option>事件</option>
              <option>设施</option>
              <option>资源</option>
            </select>
          </div>
          <div class="form-row">
            <label>属性</label>
            <textarea v-model="ontologyEntityAttrs" rows="2" placeholder="逗号分隔，如：名称, 位置, 责任单位"></textarea>
          </div>
          <button @click="addOntologyEntity">保存到预览（本地）</button>
        </div>
        <div class="ont-list">
          <div v-for="(e, idx) in ontologyEntities" :key="idx" class="ont-item">
            <div><strong>{{ e.label }}</strong> <span class="muted">({{ e.id }})</span></div>
            <div class="muted">类型：{{ e.type }}｜属性：{{ e.attrs }}</div>
          </div>
          <div v-if="ontologyEntities.length === 0" class="muted">尚未添加实体（演示本地态）。</div>
        </div>
      </div>

      <div class="ont-card">
        <div class="ont-title">关系管理</div>
        <div class="ont-desc muted">定义实体之间的关系（如路段→泵站、事件→责任单位等）</div>
        <div class="ont-form">
          <div class="form-row">
            <label>起点实体</label>
            <input v-model="ontologyRelFrom" placeholder="如 road-segment" />
          </div>
          <div class="form-row">
            <label>终点实体</label>
            <input v-model="ontologyRelTo" placeholder="如 pump-station" />
          </div>
          <div class="form-row">
            <label>关系类型</label>
            <input v-model="ontologyRelType" placeholder="如 供排水关联" />
          </div>
          <div class="form-row">
            <label>描述</label>
            <textarea v-model="ontologyRelDesc" rows="2" placeholder="关系说明"></textarea>
          </div>
          <button @click="addOntologyRelation">保存到预览（本地）</button>
        </div>
        <div class="ont-list">
          <div v-for="(r, idx) in ontologyRelations" :key="idx" class="ont-item">
            <div><strong>{{ r.from }}</strong> → <strong>{{ r.to }}</strong> <span class="muted">({{ r.type }})</span></div>
            <div class="muted">{{ r.desc }}</div>
          </div>
          <div v-if="ontologyRelations.length === 0" class="muted">尚未添加关系（演示本地态）。</div>
        </div>
      </div>

      <div class="ont-card">
        <div class="ont-title">查询 / 校验（示意）</div>
        <div class="muted small">
          - 图谱：Gremlin / Cypher / GSQL 查询<br />
          - RDF：SPARQL 端点；SHACL/OWL 约束校验<br />
          - 关系型：视图/存储过程/物化视图；Redis 缓存热点对象<br />
          - 可接入：版本/血缘/审计接口
        </div>
      </div>
    </div>
  </section>
</main>
  </div>
</template>

<script setup lang="ts">
import axios from "axios";
import { ref, computed, onMounted, watch } from "vue";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

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
  { label: "A-001（演示默认）", value: "A-001" },
  { label: "A-002（演示）", value: "A-002" },
  { label: "A-003（演示）", value: "A-003" },
];
const incidentId = ref<string>("");
const selectedTarget = ref<string>("");

const activePage = ref<"main" | "data" | "model" | "agent" | "workflow" | "report" | "ontology" | "summary">("main");

// 本体管理演示（前端本地状态，不影响现有页面）
const ontologyEntityId = ref("road-segment");
const ontologyEntityLabel = ref("路段");
const ontologyEntityType = ref("实体");
const ontologyEntityAttrs = ref("名称, 位置, 责任单位, 设施类型");
const ontologyEntities = ref<{ id: string; label: string; type: string; attrs: string }[]>([]);

const ontologyRelFrom = ref("road-segment");
const ontologyRelTo = ref("pump-station");
const ontologyRelType = ref("供排水关联");
const ontologyRelDesc = ref("路段关联附近泵站用于排涝");
const ontologyRelations = ref<{ from: string; to: string; type: string; desc: string }[]>([]);

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

// 演示：为 road-001..008 生成重庆周边的示例坐标
const targetCoords: Record<string, [number, number]> = {
  // A-001（老数据兼容）
  "road-001": [29.563, 106.551],
  "road-002": [29.565, 106.56],
  "road-003": [29.57, 106.54],
  "road-004": [29.555, 106.57],
  "road-005": [29.575, 106.565],
  "road-006": [29.568, 106.548],
  "road-007": [29.558, 106.535],
  "road-008": [29.552, 106.558],
  "road-009": [29.548, 106.545],
  "road-010": [29.573, 106.552],
  "road-011": [29.566, 106.533],
  "road-012": [29.559, 106.568],
  // 新区域前缀 A-002/A-003
  "a-002-road-001": [29.58, 106.57],
  "a-002-road-002": [29.582, 106.565],
  "a-002-road-003": [29.584, 106.555],
  "a-002-road-004": [29.578, 106.548],
  "a-002-road-005": [29.586, 106.54],
  "a-002-road-006": [29.59, 106.53],
  "a-002-road-007": [29.593, 106.545],
  "a-002-road-008": [29.587, 106.555],
  "a-002-road-009": [29.581, 106.535],
  "a-002-road-010": [29.585, 106.52],
  "a-002-road-011": [29.592, 106.525],
  "a-002-road-012": [29.589, 106.515],
  "a-003-road-001": [29.54, 106.53],
  "a-003-road-002": [29.542, 106.54],
  "a-003-road-003": [29.544, 106.55],
  "a-003-road-004": [29.536, 106.52],
  "a-003-road-005": [29.538, 106.51],
  "a-003-road-006": [29.545, 106.505],
  "a-003-road-007": [29.548, 106.515],
  "a-003-road-008": [29.552, 106.52],
  "a-003-road-009": [29.546, 106.495],
  "a-003-road-010": [29.549, 106.488],
  "a-003-road-011": [29.541, 106.49],
  "a-003-road-012": [29.535, 106.5],
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
  renderMap();
}

function pickTarget(targetId: string) {
  selectedTarget.value = targetId;
  chatInput.value = `请研判 ${targetId} 并给出任务包建议`;
}

async function createIncident() {
  const { data } = await axios.post(`${apiBase}/workflow/incidents`, { area_id: areaId.value, title: "城市暴雨内涝处置事件（演示）" });
  incidentId.value = data.incident_id;
}

async function sendChat() {
  agentOut.value = "请求中...";
  const { data } = await axios.post(`${agentBase}/agent/chat`, {
    incident_id: incidentId.value || null,
    area_id: areaId.value,
    target_id: selectedTarget.value || null,
    message: chatInput.value,
  });
  if (data.incident_id) {
    incidentId.value = data.incident_id;
  }
  agentOut.value = JSON.stringify(data, null, 2);
  // 若智能体自动创建了事件
  if (!incidentId.value) {
    // 从 tasks 里推断不到，这里就用后端的“最新事件”能力简化：直接再新建一个事件让用户可控
    // 演示：如果智能体触发派单，用户通常会先点“新建事件”；这里保持简单不反推。
  }
}

function fillOneClick() {
  chatInput.value = selectedTarget.value
    ? `请研判 ${selectedTarget.value} 并一键下发任务包`
    : "请研判并一键下发任务包";
}

function addOntologyEntity() {
  ontologyEntities.value.unshift({
    id: ontologyEntityId.value.trim() || "entity-id",
    label: ontologyEntityLabel.value.trim() || "未命名",
    type: ontologyEntityType.value,
    attrs: ontologyEntityAttrs.value.trim(),
  });
}

function addOntologyRelation() {
  ontologyRelations.value.unshift({
    from: ontologyRelFrom.value.trim() || "A",
    to: ontologyRelTo.value.trim() || "B",
    type: ontologyRelType.value.trim() || "关系",
    desc: ontologyRelDesc.value.trim(),
  });
}

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
    await axios.post(`${apiBase}/workflow/tasks/${t.task_id}/ack`, {
      actor: "demo-mobile",
      status: "done",
      note: "演示回执：已完成",
      evidence: { gps: "31.23,121.47", photo: "placeholder" },
    });
  }
  await loadTasks();
}

async function loadReport() {
  const { data } = await axios.get(`${apiBase}/reports/incidents/${incidentId.value}`);
  reportData.value = data;
  reportOut.value = JSON.stringify(data, null, 2);
}

loadTopN().catch(() => {});

function renderMap() {
  if (!mapRef.value) return;
  if (!map) {
    map = L.map(mapRef.value, {
      zoomControl: true,
      scrollWheelZoom: true,
      attributionControl: false,
    }).setView([29.563, 106.551], 12);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
    }).addTo(map);
  }

  // 清理旧标记
  Object.values(markers).forEach((m) => m.remove());
  markers = {};

  const areaCenters: Record<string, [number, number]> = {
    "A-001": [29.563, 106.551],
    "A-002": [29.585, 106.54],
    "A-003": [29.54, 106.52],
  };

  const getCoord = (id: string, area: string | undefined) => {
    if (targetCoords[id]) return targetCoords[id];
    const center = areaCenters[area || "A-001"] || [29.563, 106.551];
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
        `<strong>${item.target_id}</strong><br/>风险: ${item.risk_level}<br/>分数: ${item.risk_score.toFixed(
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
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 12px;
  margin-top: 12px;
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


