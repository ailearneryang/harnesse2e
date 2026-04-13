/* ══════════════════════════════════════════════════════════════
   TAB & NAVIGATION SYSTEM
   ══════════════════════════════════════════════════════════════ */

function toggleSidebar() {
    const shell = document.getElementById('app');
    sidebarCollapsed = false;
    shell?.classList.remove('sidebar-collapsed');
    localStorage.setItem('sidebarCollapsed', 'false');
}

function enableNextPageTransition() {
    pageTransitionEnabled = true;
}

function toggleMobileSidebar() {
    const shell = document.getElementById('app');
    shell.classList.toggle('sidebar-open');
}

function buildNavItems(tasks, approvals, agents) {
    return [
        { group: 'main', label: '主界面', items: [
            { id: 'request', icon: '📝', label: '需求发起', count: '' },
            { id: 'runtime', icon: '🎯', label: '任务监控', count: tasks.filter(task => ['running', 'in_progress', 'waiting_human', 'paused'].includes(task.status)).length || '' },
            { id: 'outputs', icon: '📦', label: '产物查看', count: tasks.length || '' },
            { id: 'pipeline', icon: '🛠', label: 'Pipeline 编排', count: '' },
        ]},
    ];
}

function getRuntimeContext() {
    if (!runtime) return null;

    const tasks = runtime.tasks || [];
    const approvals = runtime.approvals || [];
    const agents = runtime.agents || [];
    const stats = runtime.stats || {};
    const runner = runtime.runner || {};
    const settings = runtime.settings || {};

    if (!editorLoaded) {
        STAGES = pipelineStageIds(SAVED_PIPELINE_STAGES?.length ? SAVED_PIPELINE_STAGES : (runtime.pipeline_order || DEFAULT_STAGES));
    }

    const activeTask = tasks.find(t => t.id === runner.current_task_id) || tasks[0];
    const budget = runtime.budget || {used: 0, limit: 500000, percent: 0, status: 'ok'};
    const isLive = runner.running && !runner.paused;
    const isPaused = runner.paused;
    const navItems = buildNavItems(tasks, approvals, agents);

    return { tasks, approvals, agents, stats, runner, settings, activeTask, budget, isLive, isPaused, navItems };
}

function renderRunnerWidget(activeTask, isLive, isPaused) {
    return `
        <div class="runner-row">
            <span class="dot ${isLive?'live':(isPaused?'paused':'')}"></span>
            <span class="runner-label">${isPaused?'Runner Paused':(isLive?'Runner Live':'Runner Stopped')}</span>
        </div>
        <div class="runner-detail">${activeTask ? esc(activeTask.title||'Untitled') : '暂无活动任务'}</div>
        <div class="runner-btns">
            <button class="btn primary sm" onclick="controlRunner('resume')" title="恢复">
                <span class="btn-icon" aria-hidden="true">▶</span>
                <span class="btn-text">恢复</span>
            </button>
            <button class="btn warn sm" onclick="controlRunner('pause')" title="暂停">
                <span class="btn-icon" aria-hidden="true">⏸</span>
                <span class="btn-text">暂停</span>
            </button>
            <button class="btn danger sm" onclick="controlRunner('stop')" title="停止">
                <span class="btn-icon" aria-hidden="true">■</span>
                <span class="btn-text">停止</span>
            </button>
        </div>
    `;
}

function renderNavSection(navItems) {
    return navItems.map(group => `
        <div class="nav-group">
            <div class="nav-label">${group.label}</div>
            ${group.items.map(n => `
                <a class="nav-link ${activeTabId===n.id?'active':''}" onclick="openPage('${n.id}')">
                    <span class="nav-link-icon">${n.icon}</span>
                    <span class="nav-link-text">${n.label}</span>
                    ${n.count!==''?`<span class="count">${n.count}</span>`:''}
                </a>
            `).join('')}
        </div>
    `).join('');
}

function renderSidebarFooter(settings, runner) {
    const displayTime = lastRuntimeSyncAt || runner.updated_at;
    const configuredRepo = settings.target_repo || '-';
    const resolvedRepo = runtime?.resolved_target_repo || configuredRepo;
    const showResolvedRepo = resolvedRepo && resolvedRepo !== configuredRepo;
    return `
        <div class="info-row"><span>Target Repo</span><span class="info-val">${esc(configuredRepo)}</span></div>
        ${showResolvedRepo ? `<div class="info-row"><span>Resolved</span><span class="info-val">${esc(resolvedRepo)}</span></div>` : ''}
        <div class="info-row"><span>Claude</span><span class="info-val">${settings.claude?.simulate?'Simulation':'CLI'}</span></div>
        <div class="info-row"><span>Synced</span><span class="info-val">${fmtTime(displayTime)}</span></div>
    `;
}

function setFeedFilter(filter) {
    if (feedFilter === filter) return;
    feedFilter = filter;
    updateRuntimeUI({ animate: false });
}

function isSkillEvent(event) {
    const data = event?.data || {};
    return ['skill_invocation','skill_file_read','agent_session_init'].includes(event?.type)
        || !!data.skill_name
        || !!data.local_skill_present
        || (Array.isArray(data.available_skills) && data.available_skills.length > 0)
        || (Array.isArray(data.global_skills) && data.global_skills.length > 0);
}

function filterFeedEvents(events) {
    let filtered = [...(events || [])].reverse().slice(0, 150);
    if (feedFilter === 'skill') return filtered.filter(isSkillEvent);
    if (feedFilter !== 'all') return filtered.filter(e => e.level === feedFilter);
    return filtered;
}

function uniqueStrings(values) {
    return [...new Set((values || []).filter(v => typeof v === 'string' && v.trim()))];
}

function renderStageSkillSummary(events, activeAgent) {
    const relevantEvents = events || [];
    const visibleSkills = uniqueStrings(relevantEvents.flatMap(event => event?.data?.available_skills || []));
    const configuredSkills = uniqueStrings(relevantEvents.flatMap(event => event?.data?.global_skills || []));
    const observedSkills = uniqueStrings(relevantEvents.map(event => event?.data?.skill_name).filter(Boolean));
    const explicitInvocations = relevantEvents.filter(event => event?.type === 'skill_invocation').length;
    const skillReads = relevantEvents.filter(event => event?.type === 'skill_file_read').length;
    const localSkillConfigured = relevantEvents.some(event => event?.data?.local_skill_present) || false;

    const title = observedSkills.length
        ? `已观测 ${observedSkills.length} 个 skill`
        : (visibleSkills.length ? `可见 ${visibleSkills.length} 个 skill` : '暂无 skill 信号');

    const summary = observedSkills.length
        ? `显式技能信号 ${explicitInvocations} 次调用，${skillReads} 次 skill 文件读取。`
        : (visibleSkills.length
            ? '当前只观测到会话可见 skill，尚未看到显式调用或 skill 文件读取。'
            : ((activeAgent?.id || activeAgent?.name) ? '当前阶段尚未返回可见或调用中的 skill 信息。' : '当前阶段还没有 agent / skill 观测数据。'));

    const tags = [];
    if (localSkillConfigured) tags.push('<span class="feed-meta-tag skill">Local skill configured</span>');
    configuredSkills.slice(0, 4).forEach(skill => tags.push(`<span class="feed-meta-tag skill">Configured: ${esc(skill)}</span>`));
    visibleSkills.slice(0, 4).forEach(skill => tags.push(`<span class="feed-meta-tag skill">Visible: ${esc(skill)}</span>`));
    observedSkills.slice(0, 6).forEach(skill => tags.push(`<span class="feed-meta-tag skill">Observed: ${esc(skill)}</span>`));

    return {
        title,
        summary,
        tags: tags.length ? `<div class="pipeline-current-meta-list">${tags.join('')}</div>` : '',
    };
}

function openPage(pageId, addTab = true) {
    if (!PAGES[pageId]) return;

    openTabs = [{ id: pageId, label: PAGES[pageId].label, icon: PAGES[pageId].icon }];
    activeTabId = pageId;
    document.getElementById('app')?.classList.remove('sidebar-open');
    if (pageId === 'outputs' && !historyData) {
        loadHistory();
    }

    enableNextPageTransition();
    renderApp();
}

function closeTab(tabId, event) {
    if (event) event.stopPropagation();
}

function switchTab(tabId) {
    openPage(tabId, false);
}

function renderPipelineVisual(task) {
    const stages = task?.stages || {};
    const currentStage = task?.current_stage || '';
    const taskStatus = task?.status || '';
    const stageList = taskPipelineStageIds(task);
    
    if (!task || stageList.length === 0) {
        return `<div class="pipeline-visual pipeline-empty">
            <div class="pipeline-empty-icon">📋</div>
            <div class="pipeline-empty-text">暂无活动任务</div>
            <div class="pipeline-empty-hint">提交新请求开始任务流程</div>
        </div>`;
    }
    
    const isCompleted = ['completed', 'done'].includes(taskStatus);
    const isFailed = ['failed', 'error'].includes(taskStatus);
    const isRunning = ['running', 'in_progress'].includes(taskStatus);
    const currentStageData = stages[currentStage] || {};
    const currentStageIndex = Math.max(stageList.indexOf(currentStage), 0);
    const currentStageStatus = currentStageData.status || (isCompleted ? 'completed' : (isFailed ? 'failed' : (currentStage ? 'running' : 'pending')));
    const currentStageDuration = stageDuration(currentStageData, taskStatus) || taskDuration(task);
    const completedStages = completedCount(task);
    const activeAgent = (runtime?.agents || []).find(agent => agent.current_task_id === task?.id && agent.last_stage === currentStage)
        || (runtime?.agents || []).find(agent => agent.current_task_id === task?.id)
        || (runtime?.agents || []).find(agent => agent.last_stage === currentStage);
    const stageEvents = [...latestEvents]
        .reverse()
        .filter(event => event.task_id === task?.id && (!currentStage || event.stage === currentStage || !event.stage));
    const taskEvents = stageEvents.slice(0, 3);
    const currentSummary = currentStageData.summary || currentStageData.last_message || task?.request_text || '';
    const summaryPreview = currentSummary.length > 160 ? `${currentSummary.slice(0, 160)}...` : currentSummary;
    const stageSkillSummary = renderStageSkillSummary(stageEvents, activeAgent);
    
    let html = '<div class="pipeline-visual">';
    
    if (isCompleted || isFailed) {
        const statusIcon = isCompleted ? '✓' : '✗';
        const statusText = isCompleted ? '任务已完成' : '任务失败';
        const statusClass = isCompleted ? 'completed' : 'failed';
        const retryBtn = isFailed ? `<button class="psh-retry-btn" onclick="retryTask('${task.id}')" title="重试任务">🔄 重试</button>` : '';
        html += `<div class="pipeline-status-header ${statusClass}">
            <span class="psh-icon">${statusIcon}</span>
            <span class="psh-text">${statusText}</span>
            <span class="psh-time">${taskDuration(task)}</span>
            ${retryBtn}
        </div>`;
    }
    
    let fallbackInfo = null;
    const currentIdx = stageList.indexOf(currentStage);
    for (let index = currentIdx + 1; index < stageList.length; index++) {
        const stageData = stages[stageList[index]] || {};
        const retries = stageData.retry_count || stageData.attempts || 0;
        if (retries > 1 || ['failed','error'].includes(stageData.status)) {
            fallbackInfo = { from: stageList[index], fromIdx: index, to: currentStage, toIdx: currentIdx };
            break;
        }
    }
    
    if (fallbackInfo && isRunning) {
        html += `<div class="pipeline-fallback-banner">
            <span class="pfb-icon">↩</span>
            <span class="pfb-text">回退执行: <strong>${esc(humanStage(fallbackInfo.from))}</strong> → <strong>${esc(humanStage(fallbackInfo.to))}</strong></span>
        </div>`;
    }

    if (currentStage) {
        html += `<div class="pipeline-current-banner">
            <div class="pipeline-current-main">
                <div class="pipeline-current-icon">${getStageIcon(currentStage)}</div>
                <div class="pipeline-current-copy">
                    <div class="pipeline-current-kicker">当前步骤</div>
                    <div class="pipeline-current-title">${esc(humanStage(currentStage))}</div>
                    <div class="pipeline-current-subtitle">${esc(task.title || 'Untitled')} · ${getStatusText(currentStageStatus)}</div>
                </div>
            </div>
            <div class="pipeline-current-meta">
                <span class="pipeline-current-chip">位置 <strong>${currentStageIndex + 1} / ${stageList.length}</strong></span>
                <span class="pipeline-current-chip">已完成 <strong>${completedStages}</strong></span>
                <span class="pipeline-current-chip">耗时 <strong>${esc(currentStageDuration || '—')}</strong></span>
            </div>
        </div>`;
        html += `<div class="pipeline-current-detail-grid">
            <div class="pipeline-current-detail">
                <div class="pipeline-current-detail-label">当前 Agent</div>
                <div class="pipeline-current-detail-value">${esc(activeAgent?.name || activeAgent?.id || '未分配')}</div>
                <div class="pipeline-current-detail-text ${activeAgent?.last_message ? '' : 'muted'}">${esc(activeAgent?.last_message || activeAgent?.role || '当前还没有 agent 动态')}</div>
            </div>
            <div class="pipeline-current-detail">
                <div class="pipeline-current-detail-label">最近事件</div>
                <div class="pipeline-current-detail-value">${taskEvents.length ? `最近 ${taskEvents.length} 条` : '暂无事件'}</div>
                ${taskEvents.length ? `<div class="pipeline-current-event-list">${taskEvents.map(event => `
                    <div class="pipeline-current-event-item">
                        <div class="pipeline-current-event-top">
                            <span class="pipeline-current-event-source">${esc(event.source || 'system')}</span>
                            <span>${fmtTime(event.timestamp)}</span>
                        </div>
                        <div class="pipeline-current-event-msg">${esc(event.message || '')}</div>
                        ${renderFeedMeta(event)}
                    </div>
                `).join('')}</div>` : `<div class="pipeline-current-detail-text muted">等待下一条 runtime event</div>`}
            </div>
            <div class="pipeline-current-detail">
                <div class="pipeline-current-detail-label">Skill 观测</div>
                <div class="pipeline-current-detail-value">${esc(stageSkillSummary.title)}</div>
                <div class="pipeline-current-detail-text ${stageSkillSummary.summary ? '' : 'muted'}">${esc(stageSkillSummary.summary || '暂无 skill 观测')}</div>
                ${stageSkillSummary.tags}
            </div>
            <div class="pipeline-current-detail">
                <div class="pipeline-current-detail-label">当前摘要</div>
                <div class="pipeline-current-detail-value">${esc(getStatusText(currentStageStatus))}</div>
                <div class="pipeline-current-detail-text ${summaryPreview ? '' : 'muted'}">${esc(summaryPreview || '当前步骤还没有产出摘要，通常表示执行刚开始。')}</div>
            </div>
        </div>`;
    }
    
    html += '<div class="pipeline-stages">';
    
    stageList.forEach((stage, idx) => {
        const stageData = stages[stage] || {};
        const status = stageData.status || 'pending';
        const isCurrent = stage === currentStage;
        const isLast = idx === stageList.length - 1;
        const duration = stageDuration(stageData, taskStatus);
        const retryCount = Math.max((stageData.retry_count || 0), (stageData.attempts || 0) - 1, 0);
        const isFallbackSource = fallbackInfo?.from === stage;
        
        let nodeStatus = 'pending';
        if (['completed','done','passed'].includes(status)) nodeStatus = 'passed';
        else if (['failed','error'].includes(status)) nodeStatus = 'failed';
        else if (['running','in_progress'].includes(status) || isCurrent) nodeStatus = 'running';
        else if (['waiting','waiting_human'].includes(status)) nodeStatus = 'waiting_human';
        
        const showRetry = nodeStatus === 'failed' && isFailed;
        
        html += `
            <div class="pipeline-stage ${nodeStatus} ${isCurrent ? 'current' : ''} ${isFallbackSource ? 'fallback-source' : ''}">
                <div class="pipeline-stage-node">
                    ${getStageIcon(stage)}
                    ${retryCount > 0 ? `<span class="retry-badge" title="已重试 ${retryCount} 次">${retryCount}</span>` : ''}
                    ${showRetry ? `<button class="stage-retry-btn" onclick="event.stopPropagation();retryTask('${task.id}')" title="从此阶段重试">↻</button>` : ''}
                </div>
                <div class="pipeline-stage-info">
                    <div class="psi-name">${esc(humanStage(stage))}</div>
                    <div class="psi-status ${nodeStatus}">${getStatusText(status)}${retryCount > 0 ? ` · 重试${retryCount}` : ''}</div>
                    ${duration ? `<div class="psi-time">${duration}</div>` : ''}
                </div>
            </div>
            ${!isLast ? '<div class="pipeline-stage-connector"><div class="connector-line"></div></div>' : ''}
        `;
    });
    
    html += '</div></div>';
    return html;
}
