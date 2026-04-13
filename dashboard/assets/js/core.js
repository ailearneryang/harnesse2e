/* ══════════════════════════════════════════════════════════════
   HARNESS CONSOLE - B端 SPA 架构重构版
   特性：
   - 多标签页系统（类似浏览器 tabs）
   - 左侧可折叠导航（类似飞书/Jira）
   - 独立页面路由（非锚点滚动）
   - 响应式设计 + 小屏自动折叠
   ══════════════════════════════════════════════════════════════ */

/* ── State ── */
let runtime = null;
let eventSource = null;
let latestEvents = [];
let feedFilter = 'all';
let artifactTaskId = '';
let artifactCache = {};
let openArtifacts = new Set();
const RUNTIME_POLL_INTERVAL_MS = 60000;
let needsVisibilitySync = false;
let lastRuntimeSyncAt = null;
let pendingRequestFiles = [];
let requestFileInput = null;
const REQUEST_FILE_ACCEPT = '.txt,.md,.markdown,.rst,.log,.json,.yaml,.yml,.xml,.csv,.tsv,.html,.htm,.ini,.cfg,.conf,.toml,.py,.js,.ts,.tsx,.jsx,.java,.go,.rs,.sh,.sql,.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.png,.jpg,.jpeg,.gif,.webp';

/* ── Tab & Navigation State ── */
let sidebarCollapsed = false;
let openTabs = [{ id: 'request', label: '需求发起', icon: '📝' }];
let activeTabId = 'request';
let pageTransitionEnabled = false;

/* ── Page Definitions ── */
const PAGES = {
    request: { label: '需求发起', icon: '📝', group: 'main' },
    runtime: { label: '任务监控', icon: '🎯', group: 'main' },
    outputs: { label: '产物查看', icon: '📦', group: 'main' },
    pipeline: { label: 'Pipeline 编排', icon: '🛠', group: 'main' },
};

/* ── Helpers ── */
const esc = v => String(v ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
const humanStage = s => String(s||'pending').replace(/_/g,' ');
const DEFAULT_STAGES = ['intake','planning','requirements','design','development','code_review','security_review','testing','delivery'];
let STAGES = DEFAULT_STAGES;
let SAVED_PIPELINE_STAGES = null;

function formatStageName(stageId) {
    return String(stageId || 'pending')
        .split(/[-_]/g)
        .filter(Boolean)
        .map(part => part.charAt(0).toUpperCase() + part.slice(1))
        .join(' ');
}

function getStageCatalog() {
    return typeof ALL_STAGES !== 'undefined' && Array.isArray(ALL_STAGES) ? ALL_STAGES : [];
}

function getStageMeta(stageId) {
    const stage = getStageCatalog().find(item => item.id === stageId);
    return {
        id: stageId,
        name: stage?.name || formatStageName(stageId),
        agent: stage?.agent || '-',
        icon: stage?.icon || getStageIcon(stageId),
    };
}

function getSelectedTemplateDefinition() {
    if (!pipelineTemplates.length) return null;
    if (selectedTemplateId) return pipelineTemplates.find(t => t.id === selectedTemplateId) || null;
    return pipelineTemplates.find(t => t.is_default) || pipelineTemplates[0] || null;
}

/* ── Pipeline Template State ── */
let pipelineTemplates = [];
let selectedTemplateId = null;
let templateManagerVisible = false;

async function fetchPipelineTemplates() {
    try {
        const r = await fetch('/api/pipeline-templates?include_stages=true');
        const data = await r.json();
        pipelineTemplates = data.templates || [];
        selectedTemplateId = data.default_id || null;
        updateTemplateSelector();
        updateTemplatePreview();
    } catch (e) {
        console.error('Failed to fetch templates:', e);
    }
}

function updateTemplateSelector() {
    const select = document.getElementById('req-template');
    if (!select) return;
    
    const defaultTpl = pipelineTemplates.find(t => t.is_default);
    const defaultLabel = defaultTpl ? `${defaultTpl.name} (默认)` : '默认';
    
    select.innerHTML = `<option value="">${defaultLabel}</option>` + 
        pipelineTemplates.map(t => 
            `<option value="${esc(t.id)}" ${t.id === selectedTemplateId ? 'selected' : ''}>${esc(t.name)}${t.is_default ? ' ★' : ''} (${t.stage_count}阶段)</option>`
        ).join('');
}

function onTemplateSelect(templateId) {
    selectedTemplateId = templateId || null;
    updateTemplatePreview();
}

function updateTemplatePreview() {
    const panel = document.getElementById('template-preview-panel');
    const stagesEl = document.getElementById('template-preview-stages');
    const metaEl = document.getElementById('template-preview-meta');
    if (!panel || !stagesEl || !metaEl) return;
    
    const template = pipelineTemplates.find(t => 
        selectedTemplateId ? t.id === selectedTemplateId : t.is_default
    );
    
    if (!template) {
        panel.style.display = 'none';
        return;
    }
    
    panel.style.display = 'block';
    
    const stageIds = template.stage_ids || [];
    stagesEl.innerHTML = stageIds.map((id, i) => 
        `<span class="template-preview-stage">${esc(humanStage(id))}</span>${i < stageIds.length - 1 ? '<span class="template-preview-arrow">→</span>' : ''}`
    ).join('');
    
    metaEl.innerHTML = `
        <span class="template-preview-meta-item"><strong>${template.stage_count}</strong> 阶段</span>
        <span class="template-preview-meta-item">已使用 <strong>${template.usage_count}</strong> 次</span>
        ${template.description ? `<span class="template-preview-meta-item">${esc(template.description)}</span>` : ''}
    `;
}

function openTemplateManager() {
    templateManagerVisible = true;
    renderTemplateManager();
}

function closeTemplateManager() {
    templateManagerVisible = false;
    const modal = document.getElementById('template-manager-modal');
    if (modal) modal.remove();
}

function renderTemplateManager() {
    const existing = document.getElementById('template-manager-modal');
    if (existing) existing.remove();
    
    const builtinTemplates = pipelineTemplates.filter(t => t.is_builtin);
    const customTemplates = pipelineTemplates.filter(t => !t.is_builtin);
    
    const modal = document.createElement('div');
    modal.id = 'template-manager-modal';
    modal.className = 'template-manager-modal';
    modal.onclick = (e) => { if (e.target === modal) closeTemplateManager(); };
    
    modal.innerHTML = `
        <div class="template-manager-content">
            <div class="template-manager-header">
                <div class="template-manager-title">Pipeline 模板管理</div>
                <button class="btn ghost sm" onclick="closeTemplateManager()">✕</button>
            </div>
            <div class="template-manager-body">
                <div class="template-list-section">
                    <div class="template-list-section-title">内置模板</div>
                    ${builtinTemplates.map(t => renderTemplateItem(t, true)).join('')}
                </div>
                ${customTemplates.length ? `
                <div class="template-list-section">
                    <div class="template-list-section-title">自定义模板</div>
                    ${customTemplates.map(t => renderTemplateItem(t, false)).join('')}
                </div>
                ` : ''}
            </div>
            <div class="template-manager-footer">
                <button class="btn ghost" onclick="closeTemplateManager()">关闭</button>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
}

function renderTemplateItem(template, isBuiltin) {
    const isDefault = template.is_default;
    
    return `
        <div class="template-item ${isDefault ? 'default' : ''}" onclick="selectAndUseTemplate('${esc(template.id)}')">
            <div class="template-item-main">
                <div class="template-item-name">
                    ${esc(template.name)}
                    ${isDefault ? '<span class="badge">默认</span>' : ''}
                </div>
                <div class="template-item-desc">${esc(template.description || '无描述')}</div>
                <div class="template-item-meta">${template.stage_count} 阶段 · 已使用 ${template.usage_count} 次</div>
            </div>
            <div class="template-item-actions" onclick="event.stopPropagation()">
                ${!isDefault ? `<button class="btn ghost sm" onclick="setDefaultTemplate('${esc(template.id)}')">设为默认</button>` : ''}
                ${!isBuiltin ? `<button class="btn ghost sm" onclick="deleteTemplate('${esc(template.id)}')">删除</button>` : ''}
            </div>
        </div>
    `;
}

function selectAndUseTemplate(templateId) {
    selectedTemplateId = templateId;
    const select = document.getElementById('req-template');
    if (select) select.value = templateId;
    updateTemplatePreview();
    closeTemplateManager();
    showToast('已选择模板');
}

async function setDefaultTemplate(templateId) {
    try {
        const r = await fetch(`/api/pipeline-templates/${templateId}/set-default`, { method: 'POST' });
        if (!r.ok) {
            const data = await r.json().catch(() => ({}));
            throw new Error(data.error || '设置失败');
        }
        await fetchPipelineTemplates();
        renderTemplateManager();
        showToast('已设为默认模板');
    } catch (e) {
        showToast(e.message || '操作失败', true);
    }
}

async function deleteTemplate(templateId) {
    if (!confirm('确定要删除此模板吗？')) return;
    try {
        const r = await fetch(`/api/pipeline-templates/${templateId}`, { method: 'DELETE' });
        if (!r.ok) {
            const data = await r.json().catch(() => ({}));
            throw new Error(data.error || '删除失败');
        }
        await fetchPipelineTemplates();
        renderTemplateManager();
        showToast('模板已删除');
    } catch (e) {
        showToast(e.message || '操作失败', true);
    }
}

function formatRequestFileSize(bytes) {
    const value = Number(bytes) || 0;
    if (value < 1024) return `${value} B`;
    if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
    return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function renderSelectedRequestFiles() {
    if (!pendingRequestFiles.length) {
        return `<div class="request-file-empty">未选择文件。可直接提交文字请求，或附加常见文档、表格、图片和代码文件。</div>`;
    }
    return pendingRequestFiles.map((file, index) => `
        <div class="request-file-item">
            <div class="request-file-meta">
                <div class="request-file-name">${esc(file.name)}</div>
                <div class="request-file-desc">${formatRequestFileSize(file.size)}${file.type ? ` · ${esc(file.type)}` : ''}</div>
            </div>
            <button class="btn ghost sm" onclick="removePendingRequestFile(${index})">移除</button>
        </div>
    `).join('');
}

function ensureRequestFileInput() {
    if (requestFileInput) return requestFileInput;
    requestFileInput = document.createElement('input');
    requestFileInput.type = 'file';
    requestFileInput.accept = REQUEST_FILE_ACCEPT;
    requestFileInput.multiple = true;
    requestFileInput.style.display = 'none';
    requestFileInput.addEventListener('change', (event) => {
        const files = Array.from(event.target.files || []);
        pendingRequestFiles = files;
        const list = document.getElementById('req-file-list');
        if (list) list.innerHTML = renderSelectedRequestFiles();
        if (typeof updateRequestSubmitState === 'function') updateRequestSubmitState();
        event.target.value = '';
    });
    document.body.appendChild(requestFileInput);
    return requestFileInput;
}

function openRequestFilePicker() {
    ensureRequestFileInput().click();
}

function removePendingRequestFile(index) {
    pendingRequestFiles.splice(index, 1);
    const list = document.getElementById('req-file-list');
    if (list) list.innerHTML = renderSelectedRequestFiles();
    if (typeof updateRequestSubmitState === 'function') updateRequestSubmitState();
}

function clearPendingRequestFiles() {
    pendingRequestFiles = [];
    const list = document.getElementById('req-file-list');
    if (list) list.innerHTML = renderSelectedRequestFiles();
    if (typeof updateRequestSubmitState === 'function') updateRequestSubmitState();
}

function toStageId(stage) {
    return typeof stage === 'string' ? stage : stage?.id;
}

function pipelineStageIds(stages) {
    return (stages || []).map(toStageId).filter(Boolean);
}

function taskPipelineStageIds(task) {
    if (task?.pipeline_snapshot?.length) return pipelineStageIds(task.pipeline_snapshot);
    return STAGES;
}

function statusCls(s) { return s || 'pending'; }
function completedCount(task) {
    const pipelineStages = taskPipelineStageIds(task);
    return pipelineStages.filter(stageId => {
        const stageData = task?.stages?.[stageId];
        return stageData && ['passed','completed'].includes(stageData.status);
    }).length;
}
function taskPct(task) {
    if (!task) return 0;
    const pipelineStages = taskPipelineStageIds(task);
    const total = pipelineStages.length || 1;
    return Math.min(100, Math.round(completedCount(task) / total * 100));
}
function getTaskStageCount(task) {
    return taskPipelineStageIds(task).length;
}
function classifyTask(t) {
    const s = (t?.status||'').toLowerCase(), st = (t?.current_stage||'').toLowerCase();
    if (s==='completed'||s==='done') return 'done';
    if (s==='failed'||s==='error') return 'attention';
    if (s==='paused') return 'review';
    if (s==='waiting_human'||st.includes('review')||st==='testing'||st==='delivery') return 'review';
    return 'progress';
}
function fmtTime(ts) {
    if (!ts) return '-';
    try { const d = new Date(ts); return d.toLocaleTimeString('zh-CN',{hour:'2-digit',minute:'2-digit',second:'2-digit'}); } catch(e) { return ts; }
}
function fmtTokens(n) {
    if (!n || n === 0) return '0';
    if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
    if (n >= 1000) return (n / 1000).toFixed(1) + 'K';
    return String(n);
}
function tokenStatusCls(status) {
    if (status === 'exceeded') return 'failed';
    if (status === 'warning') return 'waiting';
    return 'done';
}

/* ── Status Display Helpers ── */
const STAGE_ICONS = {
    intake: '📥', planning: '📋', requirements: '📝', design: '🏗️',
    development: '💻', code_review: '👁️', security_review: '🔒',
    safety_review: '🛡️', testing: '🧪', build_verification: '🔧', delivery: '🚀'
};
function getStageIcon(stage) { return STAGE_ICONS[stage] || '⚙️'; }

function getStatusIcon(status) {
    const s = String(status||'pending').toLowerCase();
    if (['completed','done','passed'].includes(s)) return '✓';
    if (['failed','error'].includes(s)) return '✗';
    if (['running','in_progress'].includes(s)) return '▶';
    if (['waiting_human'].includes(s)) return '⏸';
    return '○';
}

function getStatusText(status) {
    const s = String(status||'').toLowerCase();
    if (!s || s==='pending') return '待处理';
    if (['completed','done'].includes(s)) return '已完成';
    if (s==='passed') return '已通过';
    if (['running','in_progress'].includes(s)) return '进行中';
    if (s==='paused') return '已暂停';
    if (['waiting','waiting_human'].includes(s)) return '等待审批';
    if (['failed','error'].includes(s)) return '失败';
    if (s==='idle') return '空闲';
    return s;
}

function fmtDuration(startStr, endStr) {
    if (!startStr) return '';
    const start = new Date(startStr);
    const end = endStr ? new Date(endStr) : new Date();
    const sec = Math.round((end - start) / 1000);
    if (sec < 60) return `${sec}s`;
    const min = Math.floor(sec / 60);
    const s = sec % 60;
    if (min < 60) return `${min}m${s}s`;
    return `${Math.floor(min/60)}h${min%60}m`;
}

function taskDuration(task) {
    if (!task?.started_at) return '—';
    const start = new Date(task.started_at).getTime();
    let end;
    if (task.completed_at) {
        end = new Date(task.completed_at).getTime();
    } else if (task.status === 'failed' || task.status === 'completed') {
        const stages = task.stages || {};
        let lastEnd = null;
        for (const stage of Object.values(stages)) {
            if (stage.ended_at) {
                const date = new Date(stage.ended_at).getTime();
                if (!lastEnd || date > lastEnd) lastEnd = date;
            }
        }
        end = lastEnd || new Date(task.updated_at || task.started_at).getTime();
    } else {
        end = Date.now();
    }
    const sec = Math.round((end - start) / 1000);
    if (sec < 60) return `${sec}s`;
    if (sec < 3600) return `${Math.floor(sec/60)}m ${sec%60}s`;
    const h = Math.floor(sec/3600), m = Math.floor((sec%3600)/60);
    return `${h}h ${m}m`;
}

function stageDuration(stageData, taskStatus) {
    if (!stageData?.started_at) return '';
    const start = new Date(stageData.started_at).getTime();
    let end;
    if (stageData.completed_at || stageData.ended_at) {
        end = new Date(stageData.completed_at || stageData.ended_at).getTime();
    } else if (stageData.status === 'failed' || stageData.status === 'passed' || 
               taskStatus === 'failed' || taskStatus === 'completed') {
        end = new Date(stageData.started_at).getTime();
    } else {
        end = Date.now();
    }
    const sec = Math.round((end - start) / 1000);
    if (sec < 60) return `${sec}s`;
    if (sec < 3600) return `${Math.floor(sec/60)}m ${sec%60}s`;
    return `${Math.floor(sec/3600)}h ${Math.floor((sec%3600)/60)}m`;
}
