/* ══════════════════════════════════════════════════════════════
   PAGE RENDERERS
   ══════════════════════════════════════════════════════════════ */

function renderPageContent(pageId, activeTask, tasks, stats, budget, settings, approvals = [], agents = []) {
    switch (pageId) {
        case 'request':
            return renderRequestPage(activeTask, tasks, stats, budget, settings);
        case 'runtime':
            return renderRuntimePage(activeTask, tasks, stats, budget, approvals || [], agents || []);
        case 'pipeline':
            return renderPipelinePage();
        case 'outputs':
            return renderOutputsPage(tasks);
        default:
            return '<div class="empty">页面不存在</div>';
    }
}

function renderPage(pageId, activeTask, tasks, stats, budget, settings, approvals = [], agents = []) {
    const isActive = activeTabId === pageId;
    const content = renderPageContent(pageId, activeTask, tasks, stats, budget, settings, approvals, agents);
    return `<div class="page ${isActive ? 'active' : ''}" id="page-${pageId}">${content}</div>`;
}

function fmtDurationSec(sec) {
    if (!sec || sec <= 0) return '-';
    if (sec < 60) return `${sec}s`;
    if (sec < 3600) return `${Math.floor(sec / 60)}m ${sec % 60}s`;
    const hours = Math.floor(sec / 3600);
    const minutes = Math.floor((sec % 3600) / 60);
    return `${hours}h ${minutes}m`;
}

function fmtTokensK(tokens) {
    if (!tokens || tokens <= 0) return '-';
    if (tokens < 1000) return String(tokens);
    return `${(tokens / 1000).toFixed(1)}k`;
}

/* ══════════════════════════════════════════════════════════════
   REQUEST PAGE
   ══════════════════════════════════════════════════════════════ */

function renderRequestPage(activeTask, tasks, stats, budget, settings) {
    return `
        <div class="workspace-page request-scene">
            <section class="studio-panel request-composer-panel">
                <div class="studio-panel-header">
                    <div>
                        <div class="studio-panel-title">需求输入</div>
                        <div class="studio-panel-desc">填写需求说明并按需添加附件。系统会自动生成任务标题。</div>
                    </div>
                    <div class="studio-panel-actions request-composer-actions">
                        <label class="request-priority-inline" for="req-prioritize">
                            <input id="req-prioritize" type="checkbox" />
                            <span>优先执行</span>
                        </label>
                        <button class="btn primary" id="req-submit-btn" onclick="submitRequest()" disabled>提交请求</button>
                    </div>
                </div>

                <div class="request-form-grid">
                    <div class="field-group full request-main-field">
                        <div class="field-label">需求背景与约束</div>
                        <textarea id="req-text" class="request-main-textarea" placeholder="输入需求背景、目标仓库、验收条件等" oninput="updateRequestSubmitState()"></textarea>
                    </div>

                    <div class="request-support-row">
                        <div class="field-group full">
                            <div class="field-label">附件</div>
                            <div class="upload-panel request-upload-panel">
                                <div class="upload-panel-head">
                                    <button class="btn ghost" onclick="openRequestFilePicker()">选择文件</button>
                                    <button class="btn ghost sm" onclick="clearPendingRequestFiles()">清空附件</button>
                                </div>
                                <div class="upload-hint">支持常见文本、代码、表格、Office、PDF 和图片格式。最多 10 个文件，单文件不超过 10MB，总大小不超过 25MB。</div>
                                <div class="request-file-list" id="req-file-list">${renderSelectedRequestFiles()}</div>
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            <section class="studio-panel request-pipeline-panel">
                <div class="studio-panel-header">
                    <div>
                        <div class="studio-panel-title">选择 pipeline</div>
                        <div class="studio-panel-desc">先选择模板，需要时再统一进入模版管理。</div>
                    </div>
                    <div class="studio-panel-actions request-pipeline-actions">
                        <div class="request-template-toolbar">
                            <select id="req-template" onchange="onTemplateSelect(this.value)">
                                <option value="">加载中...</option>
                            </select>
                            <button class="btn ghost" onclick="openPage('pipeline')">管理模版</button>
                        </div>
                    </div>
                </div>

                <div id="template-preview-panel" class="template-preview-panel request-template-preview" style="display:none;">
                    <div class="template-preview-stages" id="template-preview-stages"></div>
                    <div class="template-preview-meta" id="template-preview-meta"></div>
                </div>
            </section>
        </div>
    `;
}

/* ══════════════════════════════════════════════════════════════
   RUNTIME PAGE
   ══════════════════════════════════════════════════════════════ */

function getActiveRuntimeAgent(activeTask, agents) {
    if (!activeTask) return null;
    return (agents || []).find(agent => agent.current_task_id === activeTask.id)
        || (agents || []).find(agent => agent.last_stage === activeTask.current_stage)
        || null;
}

function getTaskEventSlice(activeTask, limit = 8) {
    const allEvents = [...latestEvents].reverse();
    if (!activeTask) return allEvents.slice(0, limit);
    const matched = allEvents.filter(event => event.task_id === activeTask.id);
    return (matched.length ? matched : allEvents).slice(0, limit);
}

function renderRuntimePage(activeTask, tasks, stats, budget, approvals, agents) {
    const currentAgent = getActiveRuntimeAgent(activeTask, agents);
    const taskEvents = getTaskEventSlice(activeTask, 10);
    const taskApprovals = activeTask ? approvals.filter(item => item.task_id === activeTask.id) : approvals;
    const progress = taskPct(activeTask);

    return `
        <div class="workspace-page runtime-scene">
            <div class="runtime-top-grid">
                <section class="studio-panel runtime-task-panel runtime-task-panel-wide">
                    <div class="runtime-task-header">
                        <div>
                            <div class="panel-kicker">任务信息</div>
                            <div class="runtime-task-title">${esc(activeTask?.title || '等待新任务')}</div>
                        </div>
                        <div class="runtime-task-actions">
                            <button class="btn primary" onclick="controlRunner('resume')">恢复</button>
                            <button class="btn warn" onclick="controlRunner('pause')">暂停</button>
                            <button class="btn danger" onclick="controlRunner('stop')">停止</button>
                        </div>
                    </div>
                    <div class="runtime-task-desc">${esc(activeTask?.request_text || '当前没有正在执行的任务。你可以从“需求发起”页提交新请求，系统会在这里展示最新任务的执行状态。')}</div>
                    <div class="runtime-task-metrics">
                        <div class="runtime-task-metric"><span>状态</span><strong>${getStatusText(activeTask?.status)}</strong></div>
                        <div class="runtime-task-metric"><span>当前阶段</span><strong>${esc(getStageMeta(activeTask?.current_stage || taskPipelineStageIds(activeTask)[0] || 'intake').name)}</strong></div>
                        <div class="runtime-task-metric"><span>进度</span><strong>${progress}%</strong></div>
                        <div class="runtime-task-metric"><span>耗时</span><strong>${taskDuration(activeTask)}</strong></div>
                    </div>
                    ${activeTask?.status === 'running' ? `<div class="runtime-control-secondary"><button class="btn ghost sm" onclick="pauseTask('${esc(activeTask.id)}')">暂停当前任务</button><button class="btn ghost sm" onclick="deferTask('${esc(activeTask.id)}')">让出执行位</button></div>` : ''}
                </section>
            </div>

            <section class="studio-panel runtime-stage-panel">
                <div class="panel-kicker">当前任务状态</div>
                ${renderRuntimeStageRail(activeTask)}
            </section>

            <div class="runtime-main-grid">
                <section class="studio-panel runtime-monitor-panel">
                    <div class="panel-kicker">状态监控</div>
                    <div class="runtime-monitor-top">
                        <div class="runtime-agent-card">
                            <div class="runtime-agent-eyebrow">当前 Agent</div>
                            <div class="runtime-agent-name">${esc(currentAgent?.name || 'planner')}</div>
                            <div class="runtime-agent-role">${esc(currentAgent?.role || currentAgent?.description || '当前还没有活跃 Agent，任务启动后会在这里展示执行者信息。')}</div>
                            <div class="runtime-agent-meta">
                                <span class="badge ${statusCls(currentAgent?.status || activeTask?.status || 'idle')}">${esc(currentAgent?.status || 'idle')}</span>
                                <span class="badge idle">${esc(currentAgent?.model || 'system')}</span>
                                <span class="badge idle">已完成 ${esc(currentAgent?.completed_tasks || 0)} 次</span>
                            </div>
                        </div>

                        <div class="runtime-token-card">
                            <div class="runtime-token-item"><span>Token 已用</span><strong class="${tokenStatusCls(budget.status)}">${fmtTokens(budget.used)}</strong></div>
                            <div class="runtime-token-item"><span>Token 限额</span><strong>${fmtTokens(budget.limit)}</strong></div>
                            <div class="runtime-token-item"><span>使用率</span><strong>${budget.percent}%</strong></div>
                            <div class="runtime-token-item"><span>事件数</span><strong>${taskEvents.length}</strong></div>
                        </div>
                    </div>

                    <div class="runtime-log-shell">
                        ${taskEvents.length ? taskEvents.map(event => `
                            <div class="runtime-log-item ${esc(event.level || 'info')}">
                                <div class="runtime-log-top">
                                    <span>${fmtTime(event.timestamp)}</span>
                                    <span>${esc(event.source || 'system')}</span>
                                    ${event.stage ? `<span>${esc(getStageMeta(event.stage).name)}</span>` : ''}
                                </div>
                                <div class="runtime-log-message">${esc(event.message || '')}</div>
                            </div>
                        `).join('') : '<div class="empty no-icon"><div class="empty-title">暂无行为日志</div><div class="empty-desc">任务开始运行后，这里会持续显示当前 Agent 的关键事件。</div></div>'}
                    </div>
                </section>

                <div class="runtime-side-stack">
                    <section class="studio-panel runtime-output-panel">
                        <div class="panel-kicker">输出物</div>
                        ${renderRuntimeOutputPreview(activeTask)}
                    </section>

                    <section class="studio-panel runtime-approval-panel">
                        <div class="panel-kicker">任务审批</div>
                        ${renderRuntimeApprovalPanel(activeTask, taskApprovals)}
                    </section>
                </div>
            </div>
        </div>
    `;
}

function renderRuntimeStageRail(activeTask) {
    const stageIds = taskPipelineStageIds(activeTask);
    const stageMap = activeTask?.stages || {};

    if (!stageIds.length) {
        return '<div class="empty no-icon"><div class="empty-title">暂无 pipeline 状态</div><div class="empty-desc">提交任务后，这里会按阶段展示当前执行进度。</div></div>';
    }

    return `
        <div class="runtime-stage-rail">
            ${stageIds.map((stageId, index) => {
                const meta = getStageMeta(stageId);
                const stageData = stageMap[stageId] || { status: 'pending' };
                const stateClass = activeTask?.current_stage === stageId && ['running', 'in_progress', 'pending'].includes(stageData.status)
                    ? 'current'
                    : statusCls(stageData.status || 'pending');
                const status = stageData.status || (activeTask?.current_stage === stageId ? 'running' : 'pending');
                return `
                    <div class="runtime-stage-node ${stateClass}">
                        <div class="runtime-stage-badge">${index + 1}</div>
                        <div class="runtime-stage-icon">${meta.icon}</div>
                        <div class="runtime-stage-name">${esc(meta.name)}</div>
                        <div class="runtime-stage-status">${esc(getStatusText(status))}</div>
                    </div>
                    ${index < stageIds.length - 1 ? '<div class="runtime-stage-link"></div>' : ''}
                `;
            }).join('')}
        </div>
    `;
}

function renderRuntimeOutputPreview(activeTask) {
    if (!activeTask) {
        return '<div class="empty no-icon"><div class="empty-title">暂无输出物</div><div class="empty-desc">任务开始执行后，会在这里展示已生成产物的摘要与入口。</div></div>';
    }

    const cachedArtifacts = artifactCache[activeTask.id];
    if (!cachedArtifacts) {
        return `
            <div class="runtime-output-empty">
                <div class="runtime-output-text">点击后展示文档内容预览，并支持跳转到完整产物查看页。</div>
                <div class="runtime-output-actions">
                    <button class="btn ghost" onclick="loadArtifacts('${esc(activeTask.id)}')">加载当前任务产物</button>
                    <button class="btn primary" onclick="openPage('outputs')">打开产物查看</button>
                </div>
            </div>
        `;
    }

    const filePreview = Object.entries(cachedArtifacts)
        .flatMap(([stage, files]) => (files || []).slice(0, 2).map(file => ({ stage, ...file })))
        .slice(0, 4);

    if (!filePreview.length) {
        return '<div class="empty no-icon"><div class="empty-title">该任务暂无产物</div><div class="empty-desc">当前任务尚未生成文件输出。</div></div>';
    }

    return `
        <div class="runtime-output-list">
            ${filePreview.map(file => `
                <div class="runtime-output-item">
                    <div>
                        <div class="runtime-output-name">${esc(file.name)}</div>
                        <div class="runtime-output-meta">${esc(getStageMeta(file.stage).name)} · ${esc(file.path || '')}</div>
                    </div>
                    <button class="btn ghost sm" onclick="openPage('outputs')">查看</button>
                </div>
            `).join('')}
        </div>
    `;
}

function renderRuntimeApprovalPanel(activeTask, approvals) {
    if (!activeTask) {
        return '<div class="empty no-icon"><div class="empty-title">暂无审批</div><div class="empty-desc">只有在任务需要人工判断或失败重试时，这里才会出现操作区。</div></div>';
    }

    if (approvals.length) {
        return approvals.map(item => {
            const taskId = JSON.stringify(String(item.task_id || ''));
            const approvalId = JSON.stringify(String(item.id || ''));
            const noteId = `approval-note-${String(item.id || '').replace(/[^a-zA-Z0-9_-]/g, '_')}`;
            return `
                <div class="runtime-approval-item">
                    <div class="runtime-approval-title">${esc(item.task_title || activeTask.title || '待处理审批')}</div>
                    <div class="runtime-approval-reason">${esc(item.reason || '审批通过后，任务会继续向下执行。')}</div>
                    <textarea id="${noteId}" class="runtime-approval-note" placeholder="用户输入对 agent 的补充指令，可留空"></textarea>
                    <div class="runtime-approval-actions">
                        <button class="btn primary sm" onclick='resolveApproval(${taskId}, ${approvalId}, "approved", document.getElementById(${JSON.stringify(noteId)})?.value || "")'>通过</button>
                        <button class="btn danger sm" onclick='resolveApproval(${taskId}, ${approvalId}, "rejected", document.getElementById(${JSON.stringify(noteId)})?.value || "")'>拒绝</button>
                    </div>
                </div>
            `;
        }).join('');
    }

    if (['failed', 'paused', 'waiting_human'].includes(activeTask.status)) {
        return `
            <div class="runtime-approval-item quiet">
                <div class="runtime-approval-title">当前没有审批单</div>
                <div class="runtime-approval-reason">如果任务已经失败或停在人工处理状态，可以直接重试或恢复排队。</div>
                <div class="runtime-approval-actions">
                    ${activeTask.status === 'failed' ? `<button class="btn primary sm" onclick="retryTask('${esc(activeTask.id)}')">重试</button>` : ''}
                    ${['paused', 'waiting_human'].includes(activeTask.status) ? `<button class="btn primary sm" onclick="resumeTask('${esc(activeTask.id)}', true)">恢复并优先</button>` : ''}
                </div>
            </div>
        `;
    }

    return '<div class="empty no-icon"><div class="empty-title">当前无需审批</div><div class="empty-desc">任务遇到人工确认点时，会在这里说明原因并提供继续执行入口。</div></div>';
}

/* ══════════════════════════════════════════════════════════════
   OUTPUTS PAGE
   ══════════════════════════════════════════════════════════════ */

function getMergedOutputTasks(tasks) {
    const liveTasks = (tasks || []).map(task => ({
        id: task.id,
        title: task.title || task.id,
        status: task.status || 'pending',
        current_stage: task.current_stage,
        request_text: task.request_text || '',
        source: task.source || 'web',
        duration_seconds: null,
        total_tokens: null,
    }));
    const historyTasks = (historyData || []).map(task => ({
        id: task.task_id,
        title: task.title || task.task_id,
        status: task.status || 'completed',
        current_stage: (task.stages_failed && task.stages_failed[0]) || (task.stages_passed && task.stages_passed[task.stages_passed.length - 1]) || '',
        request_text: task.request_text || '',
        source: 'history',
        duration_seconds: task.duration_seconds,
        total_tokens: task.total_tokens,
    }));
    const merged = new Map();
    [...liveTasks, ...historyTasks].forEach(task => {
        if (!task.id || merged.has(task.id)) return;
        merged.set(task.id, task);
    });
    return [...merged.values()];
}

function renderOutputsPage(tasks) {
    const outputTasks = getMergedOutputTasks(tasks);
    const selectedTask = outputTasks.find(task => task.id === artifactTaskId) || outputTasks[0] || null;
    const selectedTaskId = artifactTaskId || selectedTask?.id || '';
    const selectedLessons = selectedTask ? (lessonsData || []).filter(item => item.task_id === selectedTask.id) : [];
    const visibleLessons = selectedLessons.length ? selectedLessons : (lessonsData || []).slice(0, 6);

    return `
        <div class="workspace-page outputs-scene">
            <div class="scene-header outputs-scene-header">
                <div>
                    <div class="scene-kicker">产物查看</div>
                    <h1 class="scene-title">各阶段产物文件，按任务与 stage 分组</h1>
                    <div class="scene-subtitle">左侧选择任务，中间查看产物详情，右侧回看这类任务沉淀出来的经验教训。</div>
                </div>
                <div class="scene-header-meta">
                    <div class="scene-meta-card"><span class="scene-meta-label">任务数</span><strong>${outputTasks.length}</strong></div>
                    <div class="scene-meta-card"><span class="scene-meta-label">经验教训</span><strong>${(lessonsData || []).length}</strong></div>
                    <div class="scene-meta-card"><span class="scene-meta-label">历史记录</span><strong>${(historyData || []).length}</strong></div>
                </div>
            </div>

            <div class="outputs-layout-grid">
                <section class="studio-panel outputs-task-panel">
                    <div class="studio-panel-header compact">
                        <div>
                            <div class="studio-panel-title">选择任务</div>
                            <div class="studio-panel-desc">默认高亮最新任务，点击后加载对应产物。</div>
                        </div>
                    </div>
                    <div class="outputs-task-list">
                        ${outputTasks.length ? outputTasks.map(task => `
                            <button class="outputs-task-item ${selectedTaskId === task.id ? 'active' : ''}" onclick="selectOutputTask('${esc(task.id)}')">
                                <div class="outputs-task-title-row">
                                    <span class="outputs-task-title">${esc(task.title)}</span>
                                    <span class="badge ${statusCls(task.status)}">${esc(task.status)}</span>
                                </div>
                                <div class="outputs-task-meta">${esc(task.current_stage ? getStageMeta(task.current_stage).name : '暂无阶段')} · ${esc(task.source || 'web')}</div>
                            </button>
                        `).join('') : '<div class="empty no-icon"><div class="empty-title">暂无任务</div><div class="empty-desc">任务执行后，这里会按任务列出产物入口。</div></div>'}
                    </div>
                </section>

                <section class="studio-panel outputs-detail-panel">
                    <div class="studio-panel-header compact">
                        <div>
                            <div class="studio-panel-title">产物详情</div>
                            <div class="studio-panel-desc">点击左侧任务后，在这里展开文档内容预览并支持下载。</div>
                        </div>
                        ${selectedTask ? `<div class="outputs-detail-actions"><button class="btn ghost sm" onclick="loadArtifacts('${esc(selectedTask.id)}')">刷新产物</button></div>` : ''}
                    </div>
                    <div class="outputs-selected-meta">
                        ${selectedTask ? `
                            <div class="outputs-selected-title">${esc(selectedTask.title)}</div>
                            <div class="outputs-selected-subtitle">${esc(selectedTask.request_text || '暂无任务描述')}</div>
                        ` : '<div class="empty no-icon"><div class="empty-title">默认显示最新任务</div><div class="empty-desc">当前还没有可查看的任务产物。</div></div>'}
                    </div>
                    <div class="outputs-artifact-body" id="artifact-body">
                        ${selectedTask ? (artifactCache[selectedTask.id] ? renderArtifactsContent(artifactCache[selectedTask.id]) : '<div class="empty no-icon"><div class="empty-title">点击加载产物详情</div><div class="empty-desc">默认任务已经高亮，点击“刷新产物”或左侧任务项即可请求产物内容。</div></div>') : '<div class="empty no-icon"><div class="empty-title">暂无产物详情</div><div class="empty-desc">任务开始执行并生成文档后，这里会展示按阶段分组的结果文件。</div></div>'}
                    </div>
                </section>

                <section class="studio-panel outputs-knowledge-panel">
                    <div class="studio-panel-header compact">
                        <div>
                            <div class="studio-panel-title">${selectedLessons.length ? '该任务中学习到的知识内容' : '最近沉淀的知识'}</div>
                            <div class="studio-panel-desc">失败原因、定位线索与预防策略会在这里累积，方便后续复用。</div>
                        </div>
                    </div>
                    <div class="outputs-knowledge-list">
                        ${visibleLessons.length ? visibleLessons.map(lesson => `
                            <div class="knowledge-card">
                                <div class="knowledge-card-head">
                                    <span class="badge idle">${esc(lesson.stage ? getStageMeta(lesson.stage).name : 'unknown')}</span>
                                    <span class="badge waiting_human">${esc(lesson.failure_type || 'unknown')}</span>
                                </div>
                                <div class="knowledge-card-title">${esc(lesson.failure_summary || '暂无摘要')}</div>
                                <div class="knowledge-card-body">${esc(lesson.root_cause || lesson.prevention_strategy || '当前记录没有更多详情。')}</div>
                                ${lesson.prevention_strategy ? `<div class="knowledge-card-cta">💡 ${esc(lesson.prevention_strategy)}</div>` : ''}
                            </div>
                        `).join('') : '<div class="empty no-icon"><div class="empty-title">暂无知识沉淀</div><div class="empty-desc">运行过的任务在失败、回退或人工干预后，会逐步把经验教训沉淀到这里。</div></div>'}
                    </div>
                </section>
            </div>
        </div>
    `;
}

/* ══════════════════════════════════════════════════════════════
   PIPELINE PAGE
   ══════════════════════════════════════════════════════════════ */

function renderPipelinePage() {
    return `
        <div class="page-header">
            <div class="page-header-left">
                <div>
                    <h1 class="page-title">🛠 Pipeline 编排</h1>
                    <div class="page-subtitle">可视化编排 · 点击节点配置回退规则 · <span id="pipe-mode-tag" style="color:var(--text-muted)"></span></div>
                </div>
            </div>
            <div class="page-header-actions">
                <button class="btn ghost sm" onclick="resetPipelineEditor()">撤销编辑</button>
                <button class="btn ghost sm" onclick="restoreDefaultPipeline()" id="pipe-restore-btn" style="display:none">恢复默认</button>
                <button class="btn ghost sm" onclick="saveAsTemplate()">另存为模板</button>
                <button class="btn primary sm" onclick="savePipeline()">保存配置</button>
            </div>
        </div>

        <div id="pipe-editor-body"></div>

        <div class="pipe-preview-section" style="margin-top:24px;padding-top:24px;border-top:1px dashed var(--border)">
            <div class="pipe-preview-header">
                <span class="pipe-preview-title">📺 实时预览</span>
                <span class="pipe-preview-hint">显示保存后 Mission Center 中的效果</span>
            </div>
            <div id="pipe-preview-content"></div>
        </div>
    `;
}

/* ══════════════════════════════════════════════════════════════
   HISTORY & MEMORY
   ══════════════════════════════════════════════════════════════ */

let historyData = null;
let statsData = null;
let lessonsData = null;

async function loadHistory() {
    const historyBody = document.getElementById('history-body');
    if (historyBody) {
        historyBody.innerHTML = '<div class="history-loading" style="text-align:center;padding:40px;color:var(--text-muted)"><div class="loading-spinner lg" style="margin:0 auto 16px"></div>加载中...</div>';
    }

    try {
        const [historyRes, statsRes, lessonsRes] = await Promise.all([
            fetch('/api/memory/history?limit=30'),
            fetch('/api/memory/statistics'),
            fetch('/api/memory/lessons?limit=10'),
        ]);
        historyData = await historyRes.json();
        statsData = await statsRes.json();
        lessonsData = await lessonsRes.json();

        if (historyBody) historyBody.innerHTML = renderHistory();
        if (!historyBody && activeTabId === 'outputs') renderApp();
    } catch (error) {
        if (historyBody) {
            historyBody.innerHTML = `<div class="empty"><div class="empty-title">加载失败</div><div class="empty-desc">${esc(error.message)}</div></div>`;
        }
        if (!historyBody && activeTabId === 'outputs') renderApp();
    }
}

async function importHistory() {
    const historyBody = document.getElementById('history-body');
    if (historyBody) {
        historyBody.innerHTML = '<div class="history-loading" style="text-align:center;padding:40px;color:var(--text-muted)"><div class="loading-spinner lg" style="margin:0 auto 16px"></div>正在导入历史任务...</div>';
    }

    try {
        const response = await fetch('/api/memory/import', { method: 'POST' });
        const data = await response.json();
        showToast(`已导入 ${data.imported} 个历史任务`);
        await loadHistory();
    } catch (error) {
        showToast(`导入失败: ${error.message}`, true);
        if (historyBody) {
            historyBody.innerHTML = `<div class="empty"><div class="empty-title">导入失败</div><div class="empty-desc">${esc(error.message)}</div></div>`;
        }
    }
}

function renderHistory() {
    const stats = statsData || {};
    const tasks = historyData || [];
    const lessons = lessonsData || [];

    if (stats.total_tasks === 0 && tasks.length === 0) {
        return `
            <div class="history-empty">
                <div class="he-icon">📋</div>
                <div class="he-title">暂无历史记录</div>
                <div class="he-desc">完成任务后将自动记录，或点击“导入历史”从现有任务导入</div>
                <button class="btn primary" onclick="importHistory()">导入历史任务</button>
            </div>
        `;
    }

    return `
        <div class="history-container">
            <div class="history-stats">
                <div class="history-stat-card"><div class="hsc-icon">📊</div><div class="hsc-content"><div class="hsc-value">${stats.total_tasks || 0}</div><div class="hsc-label">历史任务</div></div></div>
                <div class="history-stat-card success"><div class="hsc-icon">✅</div><div class="hsc-content"><div class="hsc-value">${stats.success_rate || 0}%</div><div class="hsc-label">成功率</div></div></div>
                <div class="history-stat-card"><div class="hsc-icon">⏱️</div><div class="hsc-content"><div class="hsc-value">${fmtDurationSec(stats.avg_duration_seconds || 0)}</div><div class="hsc-label">平均耗时</div></div></div>
                <div class="history-stat-card"><div class="hsc-icon">🎯</div><div class="hsc-content"><div class="hsc-value">${fmtTokensK(stats.avg_tokens_per_task || 0)}</div><div class="hsc-label">平均Token</div></div></div>
            </div>
            <div class="history-two-col">
                <div class="history-tasks">
                    <div class="ht-section-title">📋 任务历史</div>
                    ${tasks.length ? `<div class="history-task-list">${tasks.map(task => `<div class="history-task-item ${esc(task.status)}"><div class="hti-header"><span class="hti-status ${task.status === 'completed' ? 'success' : 'failed'}">${task.status === 'completed' ? '✓' : '✗'}</span><span class="hti-title">${esc(task.title)}</span><span class="hti-time">${fmtTime(task.created_at)}</span></div><div class="hti-meta"><span class="hti-duration">⏱ ${fmtDurationSec(task.duration_seconds)}</span><span class="hti-tokens">🎯 ${fmtTokensK(task.total_tokens)}</span><span class="hti-stages">📦 ${(task.stages_passed || []).length} passed</span></div></div>`).join('')}</div>` : '<div class="empty">暂无历史任务</div>'}
                </div>
                <div class="history-lessons">
                    <div class="ht-section-title">💡 经验教训</div>
                    ${lessons.length ? `<div class="lessons-list">${lessons.map(lesson => `<div class="lesson-item"><div class="li-header"><span class="li-stage">${esc(lesson.stage ? getStageMeta(lesson.stage).name : 'unknown')}</span><span class="li-type">${esc(lesson.failure_type || 'unknown')}</span></div><div class="li-summary">${esc((lesson.failure_summary || '').slice(0, 100))}${(lesson.failure_summary || '').length > 100 ? '...' : ''}</div>${lesson.prevention_strategy ? `<div class="li-prevention"><span class="li-prevent-icon">💡</span><span>${esc(lesson.prevention_strategy)}</span></div>` : ''}</div>`).join('')}</div>` : '<div class="empty">暂无经验教训</div>'}
                </div>
            </div>
        </div>
    `;
}

/* ══════════════════════════════════════════════════════════════
   ARTIFACTS
   ══════════════════════════════════════════════════════════════ */

function selectOutputTask(taskId) {
    artifactTaskId = taskId;
    if (activeTabId !== 'outputs') {
        openPage('outputs');
    } else {
        renderApp();
    }
    loadArtifacts(taskId).catch(error => {
        showToast(error.message || '加载产物失败', true);
    });
}

async function loadArtifacts(taskId) {
    artifactTaskId = taskId;
    openArtifacts.clear();
    const artifactBody = document.getElementById('artifact-body');

    if (!taskId) {
        if (artifactBody) {
            artifactBody.innerHTML = '<div class="empty"><div class="empty-title">选择一个任务</div><div class="empty-desc">从左侧任务列表选择任务查看其产物</div></div>';
        }
        return;
    }

    if (artifactBody) {
        artifactBody.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-muted)"><div class="loading-spinner lg" style="margin:0 auto 16px"></div>加载中...</div>';
    }

    if (!artifactCache[taskId]) {
        const response = await fetch(`/api/tasks/${taskId}/artifacts`);
        artifactCache[taskId] = await response.json();
    }

    if (artifactBody) {
        artifactBody.innerHTML = renderArtifactsContent(artifactCache[taskId]);
    }
}

function toggleArtifact(id) {
    if (openArtifacts.has(id)) openArtifacts.delete(id);
    else openArtifacts.add(id);
    const element = document.getElementById(id);
    if (element) element.classList.toggle('open');
}

function downloadArtifact(name, content) {
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = name;
    anchor.click();
    URL.revokeObjectURL(url);
}

function renderArtifactsContent(data) {
    if (!data || !Object.keys(data).length) {
        return '<div class="empty"><div class="empty-title">暂无产物</div><div class="empty-desc">该任务还没有生成任何产物文件</div></div>';
    }

    let counter = 0;
    return `<div class="artifact-stages">${STAGES.map(stage => {
        const files = data[stage];
        if (!files || !files.length) return '';
        return `<div>
            <div class="artifact-stage-header" onclick="this.nextElementSibling.style.display=this.nextElementSibling.style.display==='none'?'grid':'none'">
                <span class="artifact-stage-name">${getStageIcon(stage)} ${esc(getStageMeta(stage).name)}</span>
                <span class="artifact-stage-count">${files.length} 文件</span>
            </div>
            <div class="artifact-files" style="display:none">${files.map((file, index) => {
                const elementId = 'af-' + (counter++);
                const isJson = file.name.endsWith('.json');
                const display = isJson ? (() => {
                    try {
                        return JSON.stringify(JSON.parse(file.content), null, 2);
                    } catch (error) {
                        return file.content;
                    }
                })() : file.content;
                const isOpen = openArtifacts.has(elementId);
                return `<div class="artifact-file">
                    <div class="artifact-file-header" onclick="toggleArtifact('${elementId}')">
                        <div>
                            <div class="artifact-file-name">${esc(file.name)}</div>
                            <div class="artifact-file-path">${esc(file.path)}</div>
                        </div>
                        <div style="display:flex;gap:8px;align-items:center">
                            <button class="btn ghost sm" onclick="event.stopPropagation();downloadArtifact(${JSON.stringify(file.name)}, artifactCache[${JSON.stringify(artifactTaskId)}][${JSON.stringify(stage)}][${index}].content)">下载</button>
                            <span class="artifact-file-toggle">${isOpen ? '▲' : '▼'}</span>
                        </div>
                    </div>
                    <div class="artifact-content ${isOpen ? 'open' : ''}" id="${elementId}"><pre>${esc(display)}</pre></div>
                </div>`;
            }).join('')}</div>
        </div>`;
    }).join('')}</div>`;
}

function renderArtifacts(data) {
    return renderArtifactsContent(data);
}
