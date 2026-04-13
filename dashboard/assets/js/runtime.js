/* ══════════════════════════════════════════════════════════════
   API FUNCTIONS
   ══════════════════════════════════════════════════════════════ */

async function fetchRuntime(options = {}) {
    const { animate = false, partial = true, forceFullRender = false } = options;
    const r = await fetch('/api/runtime');
    runtime = await r.json();
    lastRuntimeSyncAt = new Date().toISOString();
    latestEvents = mergeEvents(latestEvents, runtime.events || []);
    if (!pipelineFetched) {
        try {
            const pr = await fetch('/api/pipeline');
            const pd = await pr.json();
            pipelineIsCustom = pd.is_custom ?? false;
            SAVED_PIPELINE_STAGES = pd.stages || [];
            STAGES = pipelineStageIds(SAVED_PIPELINE_STAGES.length ? SAVED_PIPELINE_STAGES : (pd.order || DEFAULT_STAGES));
            pipelineFetched = true;
        } catch (e) {}
    }
    if (forceFullRender || !document.getElementById('page-container') || !partial) {
        renderApp({ animate });
        return;
    }
    updateRuntimeUI({ animate });
}

function mergeEvents(existingEvents, incomingEvents) {
    const merged = new Map();
    [...(existingEvents || []), ...(incomingEvents || [])].forEach((event) => {
        if (!event || typeof event.seq !== 'number') return;
        merged.set(event.seq, event);
    });
    return [...merged.values()]
        .sort((left, right) => left.seq - right.seq)
        .slice(-200);
}

async function submitRequest() {
    const title = document.getElementById('req-title')?.value.trim();
    const text = document.getElementById('req-text')?.value.trim();
    const source = document.getElementById('req-source')?.value.trim() || 'web';
    const prioritizeRunning = !!document.getElementById('req-prioritize')?.checked;
    const templateId = document.getElementById('req-template')?.value || selectedTemplateId || '';
    if (!title) {
        updateRequestTitleState(true);
        showToast('请输入标题', true);
        return;
    }
    if (!text && !pendingRequestFiles.length) {
        showToast('请输入需求内容或上传文件', true);
        return;
    }

    const btn = document.querySelector('.composer-actions .btn.primary');
    if (btn) btn.classList.add('loading');

    try {
        let response;
        if (pendingRequestFiles.length) {
            const formData = new FormData();
            if (title) formData.append('title', title);
            if (text) formData.append('text', text);
            formData.append('source', source);
            if (prioritizeRunning) formData.append('prioritize_running', 'true');
            if (templateId) formData.append('pipeline_template_id', templateId);
            pendingRequestFiles.forEach(file => formData.append('files', file, file.name));
            response = await fetch('/api/requests', { method: 'POST', body: formData });
        } else {
            response = await fetch('/api/requests', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    title,
                    text,
                    source,
                    prioritize_running: prioritizeRunning,
                    pipeline_template_id: templateId || undefined,
                }),
            });
        }

        if (!response.ok) {
            const data = await response.json().catch(() => ({}));
            throw new Error(data.error || '提交失败');
        }

        const titleEl = document.getElementById('req-title');
        const textEl = document.getElementById('req-text');
        const prioritizeEl = document.getElementById('req-prioritize');
        const templateEl = document.getElementById('req-template');
        if (titleEl) titleEl.value = '';
        if (textEl) textEl.value = '';
        if (prioritizeEl) prioritizeEl.checked = false;
        if (templateEl) templateEl.value = '';
        selectedTemplateId = null;
        updateTemplatePreview();
        clearPendingRequestFiles();
        showToast(prioritizeRunning ? '请求已提交，系统会优先尝试中断当前 agent 执行以让出任务位' : '请求已提交');
        await fetchRuntime();
    } catch (e) {
        showToast(e.message || '提交失败', true);
    } finally {
        if (btn) btn.classList.remove('loading');
    }
}

function updateRequestTitleState(showError = false) {
    const input = document.getElementById('req-title');
    const field = document.getElementById('req-title-group');
    const hint = document.getElementById('req-title-hint');
    const submitBtn = document.getElementById('req-submit-btn');
    const hasTitle = !!(input?.value || '').trim();

    if (submitBtn) submitBtn.disabled = !hasTitle;
    if (field) field.classList.toggle('invalid', showError && !hasTitle);
    if (hint) {
        hint.textContent = showError && !hasTitle ? '标题为必填项' : ' ';
        hint.classList.toggle('error', showError && !hasTitle);
    }
}

async function controlRunner(action) {
    await fetch(`/api/control/${action}`, { method: 'POST' });
    const message = action === 'resume'
        ? 'Runner 已恢复'
        : action === 'pause'
            ? 'Runner 已暂停'
            : 'Runner 已停止';
    showToast(message);
    await fetchRuntime();
}

async function resolveApproval(taskId, approvalId, resolution, note = '') {
    await fetch(`/api/approvals/${taskId}/${approvalId}/resolve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ resolution, note }),
    });
    showToast(resolution === 'approved' ? '已批准' : '已拒绝');
    await fetchRuntime();
}

async function retryTask(taskId) {
    try {
        const r = await fetch(`/api/tasks/${taskId}/retry`, { method: 'POST' });
        if (r.ok) {
            showToast('任务已重新加入队列');
        } else {
            const data = await r.json().catch(() => ({}));
            showToast(data.error || '重试失败', true);
        }
    } catch (e) {
        showToast('重试请求失败', true);
    }
    await fetchRuntime();
}

async function resumeTask(taskId, prioritize = false) {
    try {
        const r = await fetch(`/api/tasks/${taskId}/resume`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ prioritize }),
        });
        if (r.ok) {
            showToast(prioritize ? '任务已恢复并优先排队' : '任务已恢复排队');
        } else {
            const data = await r.json().catch(() => ({}));
            showToast(data.error || '恢复失败', true);
        }
    } catch (e) {
        showToast('恢复请求失败', true);
    }
    await fetchRuntime();
}

async function pauseTask(taskId) {
    try {
        const r = await fetch(`/api/tasks/${taskId}/pause`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ reason: 'Pause requested from dashboard' }),
        });
        if (r.ok) {
            showToast('当前任务已暂停，新提交的请求可以直接执行');
        } else {
            const data = await r.json().catch(() => ({}));
            showToast(data.error || '暂停任务失败', true);
        }
    } catch (e) {
        showToast('暂停任务请求失败', true);
    }
    await fetchRuntime();
}

async function deferTask(taskId) {
    try {
        const r = await fetch(`/api/tasks/${taskId}/defer`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ reason: 'Manual defer requested from dashboard', immediate: true }),
        });
        if (r.ok) {
            showToast('系统会优先尝试立即中断当前 agent 执行，失败时退回到阶段边界让出');
        } else {
            const data = await r.json().catch(() => ({}));
            showToast(data.error || '暂停失败', true);
        }
    } catch (e) {
        showToast('暂停请求失败', true);
    }
    await fetchRuntime();
}

async function deleteTask(taskId) {
    if (!confirm('确定删除这个任务？')) return;
    await fetch(`/api/tasks/${taskId}`, { method: 'DELETE' });
    showToast('任务已删除');
    await fetchRuntime();
}

/* ══════════════════════════════════════════════════════════════
   MAIN RENDER FUNCTION - NEW TAB-BASED LAYOUT
   ══════════════════════════════════════════════════════════════ */

function renderApp(options = {}) {
    if (!runtime) return;

    const animate = options.animate ?? pageTransitionEnabled;
    const app = document.getElementById('app');
    const context = getRuntimeContext();
    if (!context) return;
    const { tasks, approvals, agents, stats, runner, settings, activeTask, budget, isLive, isPaused, navItems } = context;

    const savedTitle = document.getElementById('req-title')?.value ?? '';
    const savedText = document.getElementById('req-text')?.value ?? '';
    const savedSource = document.getElementById('req-source')?.value ?? 'web';
    const savedPrioritize = !!document.getElementById('req-prioritize')?.checked;
    const savedTemplateId = document.getElementById('req-template')?.value ?? selectedTemplateId ?? '';
    const savedPageScrollTop = document.getElementById('page-' + activeTabId)?.scrollTop ?? 0;

    app.classList.toggle('no-page-animation', !animate);

    app.innerHTML = `
    <div class="mobile-overlay" onclick="toggleMobileSidebar()"></div>
    <aside class="sidebar">
        <div class="sidebar-inner">
            <div class="sidebar-header">
                <div class="logo">
                    <div class="logo-icon">H</div>
                    <div class="logo-text-wrap">
                        <div class="logo-text">HARNESS</div>
                        <div class="logo-sub">Mission Console</div>
                    </div>
                </div>
                <button class="sidebar-toggle" onclick="toggleSidebar()" title="折叠/展开">◀</button>
            </div>

            <div class="runner-widget" id="runner-widget">
                ${renderRunnerWidget(activeTask, isLive, isPaused)}
            </div>

            <nav class="nav-section" id="nav-section">
                ${renderNavSection(navItems)}
            </nav>

            <div class="sidebar-footer" id="sidebar-footer">
                ${renderSidebarFooter(settings, runner)}
            </div>
        </div>
    </aside>

    <div class="main-container">
        <div class="workspace-topbar">
            <button class="mobile-menu-btn" onclick="toggleMobileSidebar()">☰</button>
            <div class="workspace-topbar-title">
                <div class="workspace-topbar-label">Harness Console</div>
                <div class="workspace-topbar-page">${esc(PAGES[activeTabId]?.label || '')}</div>
            </div>
            <div class="workspace-topbar-actions">
                <button class="btn ghost sm" onclick="fetchRuntime()">同步状态</button>
            </div>
        </div>

        <div class="page-container" id="page-container">
            <div class="page" data-page="request" id="page-request">${renderPageContent('request', activeTask, tasks, stats, budget, settings, approvals, agents)}</div>
            <div class="page" data-page="runtime" id="page-runtime">${renderPageContent('runtime', activeTask, tasks, stats, budget, settings, approvals, agents)}</div>
            <div class="page" data-page="outputs" id="page-outputs">${renderPageContent('outputs', activeTask, tasks, stats, budget, settings, approvals, agents)}</div>
            <div class="page" data-page="pipeline" id="page-pipeline">${renderPageContent('pipeline', activeTask, tasks, stats, budget, settings, approvals, agents)}</div>
        </div>
    </div>

    <div class="pipe-modal-overlay" id="add-stage-modal">
        <div class="pipe-modal">
            <div class="pipe-modal-header">
                <div class="pipe-modal-title">添加 Pipeline Stage</div>
                <button class="pipe-config-close" onclick="closeAddStageModal()">×</button>
            </div>
            <div class="pipe-modal-body" id="stage-options-body"></div>
            <div class="pipe-modal-footer">
                <button class="btn ghost" onclick="closeAddStageModal()">取消</button>
                <button class="btn primary" onclick="confirmAddStage()">添加</button>
            </div>
        </div>
    </div>
    `;

    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    const activePage = document.getElementById('page-' + activeTabId);
    if (activePage) {
        activePage.classList.add('active');
        activePage.scrollTop = savedPageScrollTop;
    }

    const ti = document.getElementById('req-title');
    const tx = document.getElementById('req-text');
    const sr = document.getElementById('req-source');
    const pr = document.getElementById('req-prioritize');
    if (ti) ti.value = savedTitle;
    if (tx) tx.value = savedText;
    if (sr) sr.value = savedSource;
    if (pr) pr.checked = savedPrioritize;
    selectedTemplateId = savedTemplateId || selectedTemplateId || null;
    updateTemplateSelector();
    const templateSelect = document.getElementById('req-template');
    if (templateSelect) templateSelect.value = savedTemplateId || '';
    updateTemplatePreview();
    updateRequestTitleState();

    if (sidebarCollapsed) {
        app.classList.add('sidebar-collapsed');
    }

    if (activeTabId === 'pipeline') {
        initPipelineEditor();
    }

    pageTransitionEnabled = false;
}

function updateRuntimeUI(options = {}) {
    if (!runtime) return;

    const animate = options.animate ?? false;
    const app = document.getElementById('app');
    const pageContainer = document.getElementById('page-container');
    if (!app || !pageContainer) {
        renderApp({ animate });
        return;
    }

    const context = getRuntimeContext();
    if (!context) return;
    const { tasks, approvals, agents, stats, runner, settings, activeTask, budget, isLive, isPaused, navItems } = context;

    const savedTitle = document.getElementById('req-title')?.value ?? '';
    const savedText = document.getElementById('req-text')?.value ?? '';
    const savedSource = document.getElementById('req-source')?.value ?? 'web';
    const savedPrioritize = !!document.getElementById('req-prioritize')?.checked;
    const savedTemplateId = document.getElementById('req-template')?.value ?? selectedTemplateId ?? '';
    const activePage = document.getElementById('page-' + activeTabId);
    const savedPageScrollTop = activePage?.scrollTop ?? 0;

    app.classList.toggle('no-page-animation', !animate);

    const runnerWidget = document.getElementById('runner-widget');
    if (runnerWidget) runnerWidget.innerHTML = renderRunnerWidget(activeTask, isLive, isPaused);

    const navSection = document.getElementById('nav-section');
    if (navSection) navSection.innerHTML = renderNavSection(navItems);

    const sidebarFooter = document.getElementById('sidebar-footer');
    if (sidebarFooter) sidebarFooter.innerHTML = renderSidebarFooter(settings, runner);

    if (activePage) {
        activePage.innerHTML = renderPageContent(activeTabId, activeTask, tasks, stats, budget, settings, approvals, agents);
        activePage.scrollTop = savedPageScrollTop;
    }

    const ti = document.getElementById('req-title');
    const tx = document.getElementById('req-text');
    const sr = document.getElementById('req-source');
    const pr = document.getElementById('req-prioritize');
    if (ti) ti.value = savedTitle;
    if (tx) tx.value = savedText;
    if (sr) sr.value = savedSource;
    if (pr) pr.checked = savedPrioritize;
    selectedTemplateId = savedTemplateId || selectedTemplateId || null;
    updateTemplateSelector();
    const templateSelect = document.getElementById('req-template');
    if (templateSelect) templateSelect.value = savedTemplateId || '';
    updateTemplatePreview();
    updateRequestTitleState();

    if (activeTabId === 'pipeline') {
        initPipelineEditor();
    }
}
