/* ── Pipeline Editor V2 ── */
const ALL_STAGES = [
    { id: 'intake', name: 'Request Intake', agent: 'planner', icon: '📥' },
    { id: 'planning', name: 'Sprint Planning', agent: 'planner', icon: '📋' },
    { id: 'software-requirement-orchestrator', name: 'Software Requirement Orchestrator', agent: 'software-requirement-orchestrator', icon: '📑' },
    { id: 'cockpit-middleware-architect', name: 'Cockpit Middleware Architect', agent: 'cockpit-middleware-architect', icon: '🚗' },
    { id: 'development', name: 'Implementation', agent: 'developer', icon: '💻' },
    { id: 'code_review', name: 'Code Review', agent: 'code-reviewer', icon: '👁️' },
    { id: 'security_review', name: 'Security Review', agent: 'security-reviewer', icon: '🔒' },
    { id: 'safety_review', name: 'Safety Review', agent: 'safety-reviewer', icon: '🛡️' },
    { id: 'testing', name: 'QA Testing', agent: 'qa-engineer', icon: '🧪' },
    { id: 'build_verification', name: 'Build Verify', agent: 'build-verifier', icon: '🔧' },
    { id: 'delivery', name: 'Gerrit Delivery', agent: 'delivery-manager', icon: '🚀' },
];

let editorStages = [];
let fallbackRules = {};
let selectedStageId = null;
let editorLoaded = false;
let pipelineIsCustom = false;
let pipelineFetched = false;
let renderThrottleTimer = null;
let pendingAddStage = null;

function initPipelineEditor() {
    if (!editorLoaded) {
        const sourceStages = SAVED_PIPELINE_STAGES?.length ? SAVED_PIPELINE_STAGES : STAGES.map(id => ({ id }));
        editorStages = sourceStages.map(item => {
            const id = toStageId(item);
            const stage = ALL_STAGES.find(s => s.id === id);
            return stage ? { ...stage } : { id, name: item?.name || id, agent: item?.agent || '-', icon: '⚙️' };
        });
        fallbackRules = {};
        editorStages.forEach(s => {
            const saved = sourceStages.find(item => toStageId(item) === s.id)?.fallback;
            fallbackRules[s.id] = saved
                ? { enabled: !!saved.enabled, targetStageId: saved.targetStageId || '', maxRetries: saved.maxRetries || 3 }
                : { enabled: false, targetStageId: '', maxRetries: 3 };
        });
        if (!SAVED_PIPELINE_STAGES?.length && fallbackRules.testing) {
            fallbackRules.testing = { enabled: true, targetStageId: 'development', maxRetries: 3 };
        }
        if (!SAVED_PIPELINE_STAGES?.length && fallbackRules.code_review) {
            fallbackRules.code_review = { enabled: true, targetStageId: 'development', maxRetries: 2 };
        }
        editorLoaded = true;
    }
    const tag = document.getElementById('pipe-mode-tag');
    const btn = document.getElementById('pipe-restore-btn');
    if (tag) tag.textContent = pipelineIsCustom ? '自定义配置' : '系统默认';
    if (btn) btn.style.display = pipelineIsCustom ? '' : 'none';
    renderPipelineEditor();
}

function renderPipelineEditor() {
    const body = document.getElementById('pipe-editor-body');
    if (!body) return;

    const flowHtml = editorStages.map((s, i) => {
        const hasFallback = fallbackRules[s.id]?.enabled;
        const isSelected = selectedStageId === s.id;
        return `
            ${i > 0 ? `<div class="pipe-connector"><svg viewBox="0 0 32 12"><path d="M0 6 L24 6 M20 2 L26 6 L20 10"/></svg></div>` : ''}
            <div class="pipe-node ${isSelected ? 'selected' : ''} ${hasFallback ? 'has-fallback' : ''}"
                 onclick="selectPipeStage('${s.id}')" data-stage="${s.id}" data-index="${i}">
                <div class="pipe-node-card">
                    <div class="pipe-node-num">${i + 1}</div>
                    <div class="pipe-node-name">${esc(s.name)}</div>
                    <div class="pipe-node-agent">${esc(s.agent)}</div>
                    <div class="pipe-node-actions">
                        <button class="pipe-node-btn settings" onclick="event.stopPropagation();selectPipeStage('${s.id}')" title="配置">⚙</button>
                        <button class="pipe-node-btn delete" onclick="event.stopPropagation();pipeRemove(${i})" title="删除">×</button>
                    </div>
                </div>
            </div>
        `;
    }).join('');

    const fallbackArrows = [];
    editorStages.forEach((s, i) => {
        const rule = fallbackRules[s.id];
        if (rule?.enabled && rule.targetStageId) {
            const targetIdx = editorStages.findIndex(t => t.id === rule.targetStageId);
            if (targetIdx >= 0 && targetIdx < i) {
                fallbackArrows.push({
                    fromIdx: i,
                    toIdx: targetIdx,
                    fromId: s.id,
                    toId: rule.targetStageId,
                    fromName: s.name,
                    toName: editorStages[targetIdx].name,
                    retries: rule.maxRetries,
                });
            }
        }
    });

    const hasAnyFallback = fallbackArrows.length > 0;
    const legendHtml = hasAnyFallback ? `
        <div class="pipe-legend">
            <div class="pipe-legend-item">
                <div class="pipe-legend-line"></div>
                <span>正常流程</span>
            </div>
            <div class="pipe-legend-item">
                <div class="pipe-legend-line fallback"></div>
                <span>失败回退 (点击查看详情)</span>
            </div>
        </div>
    ` : '';

    const configPanelHtml = selectedStageId ? renderStageConfig(selectedStageId) : '';

    body.innerHTML = `
        <div class="pipe-editor-v2">
            <div class="pipe-canvas" id="pipe-canvas">
                <div class="pipe-flow" id="pipe-flow">
                    ${flowHtml}
                    <div class="pipe-connector"><svg viewBox="0 0 32 12"><path d="M0 6 L24 6 M20 2 L26 6 L20 10"/></svg></div>
                    <div class="pipe-add-node" onclick="openAddStageModal()">
                        <div class="pipe-add-btn">+</div>
                        <div class="pipe-add-label">添加</div>
                    </div>
                </div>
                <svg class="pipe-fallback-layer" id="pipe-fallback-svg"></svg>
            </div>
            ${legendHtml}
            ${configPanelHtml}
        </div>
    `;

    if (fallbackArrows.length > 0) {
        requestAnimationFrame(() => drawFallbackArrows(fallbackArrows));
    }

    renderEditorPreview();
}

function renderEditorPreview() {
    const preview = document.getElementById('pipe-preview-content');
    if (!preview) return;

    const stageList = editorStages.map(s => s.id);
    let html = '<div class="pipeline-visual" style="margin:0"><div class="pipeline-stages">';

    stageList.forEach((stage, idx) => {
        const isLast = idx === stageList.length - 1;
        const hasFallback = fallbackRules[stage]?.enabled;
        const rule = fallbackRules[stage];
        const validFallback = hasFallback && stageList.includes(rule?.targetStageId);

        html += `
            <div class="pipeline-stage pending ${validFallback ? 'has-fallback-preview' : ''}">
                <div class="pipeline-stage-node" style="${validFallback ? 'border-color:var(--amber)' : ''}">
                    ${getStageIcon(stage)}
                </div>
                <div class="pipeline-stage-info">
                    <div class="psi-name">${esc(humanStage(stage))}</div>
                    <div class="psi-status pending">待处理</div>
                    ${validFallback ? `<div class="psi-fallback-hint">↩ ${esc(humanStage(rule.targetStageId))}</div>` : ''}
                </div>
            </div>
            ${!isLast ? '<div class="pipeline-stage-connector"><div class="connector-line"></div></div>' : ''}
        `;
    });

    html += '</div></div>';

    const totalStages = stageList.length;
    const fallbackCount = stageList.filter(id => {
        const rule = fallbackRules[id];
        return rule?.enabled && stageList.includes(rule.targetStageId);
    }).length;
    html += `
        <div class="preview-summary">
            <span class="preview-stat"><strong>${totalStages}</strong> 个阶段</span>
            <span class="preview-stat"><strong>${fallbackCount}</strong> 个回退规则</span>
        </div>
    `;

    preview.innerHTML = html;
}

function drawFallbackArrows(arrows) {
    const svg = document.getElementById('pipe-fallback-svg');
    const canvas = document.getElementById('pipe-canvas');
    const flow = document.getElementById('pipe-flow');
    if (!svg || !canvas || !flow) return;

    const flowOffsetTop = flow.offsetTop;
    const flowOffsetLeft = flow.offsetLeft;

    const svgHeight = flow.offsetHeight + 100;
    svg.style.width = canvas.scrollWidth + 'px';
    svg.style.height = svgHeight + 'px';

    let svgContent = '';

    arrows.forEach((arrow, arrowIdx) => {
        const fromNode = document.querySelector(`[data-index="${arrow.fromIdx}"]`);
        const toNode = document.querySelector(`[data-index="${arrow.toIdx}"]`);
        if (!fromNode || !toNode) return;

        const fromCard = fromNode.querySelector('.pipe-node-card');
        const toCard = toNode.querySelector('.pipe-node-card');
        if (!fromCard || !toCard) return;

        const fromX = fromNode.offsetLeft + fromNode.offsetWidth / 2 + flowOffsetLeft;
        const fromY = flowOffsetTop + fromNode.offsetTop + fromCard.offsetHeight + 15;
        const toX = toNode.offsetLeft + toNode.offsetWidth / 2 + flowOffsetLeft;
        const toY = flowOffsetTop + toNode.offsetTop + toCard.offsetHeight + 15;

        const baseY = Math.max(fromY, toY);
        const midY = baseY + 25 + (arrowIdx * 18);

        const path = `M ${fromX} ${fromY}
                      L ${fromX} ${midY - 8}
                      Q ${fromX} ${midY}, ${fromX - 12} ${midY}
                      L ${toX + 12} ${midY}
                      Q ${toX} ${midY}, ${toX} ${midY - 8}
                      L ${toX} ${toY + 6}`;

        const arrowHead = `M ${toX - 4} ${toY + 10} L ${toX} ${toY + 3} L ${toX + 4} ${toY + 10}`;

        svgContent += `
            <g class="pipe-fallback-arrow-group" onclick="selectPipeStage('${arrow.fromId}')" style="cursor:pointer">
                <path d="${path}" style="stroke:var(--amber);stroke-width:2;fill:none;stroke-dasharray:6 4;animation:dash-flow 1s linear infinite"/>
                <path d="${arrowHead}" style="stroke:var(--amber);stroke-width:2;fill:var(--amber)"/>
                <title>失败回退: ${arrow.fromName} → ${arrow.toName} (最多重试 ${arrow.retries} 次)</title>
            </g>
        `;

        const labelX = (fromX + toX) / 2;
        const labelY = midY + 3;
        svgContent += `
            <foreignObject x="${labelX - 45}" y="${labelY - 8}" width="90" height="22">
                <div xmlns="http://www.w3.org/1999/xhtml" style="
                    background:var(--amber);
                    color:#fff;
                    font-size:9px;
                    font-weight:700;
                    padding:3px 8px;
                    border-radius:99px;
                    text-align:center;
                    white-space:nowrap;
                    box-shadow:0 2px 6px rgba(245,158,11,0.35);
                ">↩ ${arrow.retries}次重试</div>
            </foreignObject>
        `;
    });

    svg.innerHTML = svgContent;
}

function renderStageConfig(stageId) {
    const stage = editorStages.find(s => s.id === stageId);
    if (!stage) return '';

    const idx = editorStages.findIndex(s => s.id === stageId);
    const rule = fallbackRules[stageId] || { enabled: false, targetStageId: '', maxRetries: 3 };
    const possibleTargets = editorStages.slice(0, idx);

    return `
        <div class="pipe-config-panel fade-in">
            <div class="pipe-config-header">
                <div class="pipe-config-title">${STAGE_ICONS[stageId] || '⚙️'} ${esc(stage.name)} 配置</div>
                <button class="pipe-config-close" onclick="closePipeConfig()">×</button>
            </div>
            <div class="pipe-config-body">
                <div class="pipe-config-section">
                    <div class="pipe-config-label">基本信息</div>
                    <div style="display:grid;gap:10px">
                        <div class="fallback-rule" style="border-color:var(--accent-soft)">
                            <div class="fallback-icon" style="background:var(--accent-soft);color:var(--accent)">⚙️</div>
                            <div class="fallback-content">
                                <div class="fallback-desc" style="color:var(--text-primary);font-weight:600">执行 Agent</div>
                                <div style="font-size:12px;color:var(--text-secondary)">${esc(stage.agent)}</div>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="pipe-config-section">
                    <div class="pipe-config-label">失败回退规则</div>
                    <div class="fallback-rules">
                        <div class="fallback-rule ${rule.enabled ? 'active' : ''}">
                            <div class="fallback-icon">↩</div>
                            <div class="fallback-content">
                                <div class="fallback-desc">当此阶段失败时，自动回退到指定阶段重试</div>
                                <div class="fallback-target">
                                    <span style="font-size:12px;color:var(--text-muted)">回退到：</span>
                                    <select class="fallback-select" onchange="updateFallbackTarget('${stageId}', this.value)" ${!possibleTargets.length ? 'disabled' : ''}>
                                        <option value="">不回退（直接失败）</option>
                                        ${possibleTargets.map(t => `
                                            <option value="${t.id}" ${rule.targetStageId === t.id ? 'selected' : ''}>${esc(t.name)}</option>
                                        `).join('')}
                                    </select>
                                </div>
                            </div>
                            <div class="fallback-toggle ${rule.enabled ? 'on' : ''}" onclick="toggleFallback('${stageId}')"></div>
                        </div>

                        ${rule.enabled ? `
                        <div class="fallback-rule" style="padding:14px 16px">
                            <div class="retry-config">
                                <span class="retry-label">最大重试次数：</span>
                                <input type="number" class="retry-input" value="${rule.maxRetries}" min="1" max="10"
                                       onchange="updateFallbackRetries('${stageId}', this.value)">
                                <span class="retry-label" style="color:var(--text-muted)">次后彻底失败</span>
                            </div>
                        </div>
                        ` : ''}
                    </div>
                </div>

                ${idx > 0 ? `
                <div class="pipe-config-section">
                    <div class="pipe-config-label">位置调整</div>
                    <div style="display:flex;gap:8px">
                        <button class="btn ghost sm" onclick="moveStage('${stageId}', -1)" ${idx === 0 ? 'disabled' : ''}>← 前移</button>
                        <button class="btn ghost sm" onclick="moveStage('${stageId}', 1)" ${idx === editorStages.length - 1 ? 'disabled' : ''}>后移 →</button>
                    </div>
                </div>
                ` : ''}
            </div>
        </div>
    `;
}

function selectPipeStage(stageId) {
    selectedStageId = stageId;
    renderPipelineEditor();
}

function closePipeConfig() {
    selectedStageId = null;
    renderPipelineEditor();
}

function toggleFallback(stageId) {
    if (!fallbackRules[stageId]) {
        fallbackRules[stageId] = { enabled: false, targetStageId: '', maxRetries: 3 };
    }
    fallbackRules[stageId].enabled = !fallbackRules[stageId].enabled;

    if (fallbackRules[stageId].enabled && !fallbackRules[stageId].targetStageId) {
        const idx = editorStages.findIndex(s => s.id === stageId);
        if (idx > 0) {
            fallbackRules[stageId].targetStageId = editorStages[idx - 1].id;
        }
    }
    renderPipelineEditor();
}

function updateFallbackTarget(stageId, targetId) {
    if (!fallbackRules[stageId]) {
        fallbackRules[stageId] = { enabled: false, targetStageId: '', maxRetries: 3 };
    }
    fallbackRules[stageId].targetStageId = targetId;
    fallbackRules[stageId].enabled = !!targetId;
    renderPipelineEditor();
}

function updateFallbackRetries(stageId, retries) {
    if (!fallbackRules[stageId]) return;
    fallbackRules[stageId].maxRetries = Math.max(1, Math.min(10, parseInt(retries) || 3));
}

function moveStage(stageId, direction) {
    const idx = editorStages.findIndex(s => s.id === stageId);
    const newIdx = idx + direction;
    if (newIdx < 0 || newIdx >= editorStages.length) return;

    const stage = editorStages.splice(idx, 1)[0];
    editorStages.splice(newIdx, 0, stage);

    Object.keys(fallbackRules).forEach(sid => {
        const rule = fallbackRules[sid];
        if (rule.enabled && rule.targetStageId) {
            const stageIdx = editorStages.findIndex(s => s.id === sid);
            const targetIdx = editorStages.findIndex(s => s.id === rule.targetStageId);
            if (targetIdx >= stageIdx) {
                rule.enabled = false;
                rule.targetStageId = '';
            }
        }
    });

    renderPipelineEditor();
}

function openAddStageModal() {
    const modal = document.getElementById('add-stage-modal');
    const body = document.getElementById('stage-options-body');
    const usedIds = new Set(editorStages.map(s => s.id));
    const available = ALL_STAGES.filter(s => !usedIds.has(s.id));

    if (!available.length) {
        alert('所有可用的 Stage 都已添加');
        return;
    }

    pendingAddStage = null;
    body.innerHTML = available.map(s => `
        <div class="stage-option" onclick="selectStageToAdd('${s.id}')">
            <div class="stage-option-icon">${s.icon || '⚙️'}</div>
            <div class="stage-option-info">
                <div class="stage-option-name">${esc(s.name)}</div>
                <div class="stage-option-agent">执行者: ${esc(s.agent)}</div>
            </div>
            <div class="stage-option-check">✓</div>
        </div>
    `).join('');

    modal.classList.add('open');
}

function selectStageToAdd(stageId) {
    pendingAddStage = stageId;
    document.querySelectorAll('.stage-option').forEach(el => el.classList.remove('selected'));
    document.querySelector(`.stage-option[onclick*="${stageId}"]`)?.classList.add('selected');
}

function closeAddStageModal() {
    const modal = document.getElementById('add-stage-modal');
    modal.classList.remove('open');
    pendingAddStage = null;
}

function confirmAddStage() {
    if (!pendingAddStage) {
        alert('请选择一个 Stage');
        return;
    }
    const stage = ALL_STAGES.find(s => s.id === pendingAddStage);
    if (stage) {
        editorStages.push({ ...stage });
        fallbackRules[stage.id] = { enabled: false, targetStageId: '', maxRetries: 3 };
    }
    closeAddStageModal();
    renderPipelineEditor();
}

function pipeRemove(idx) {
    const stageId = editorStages[idx]?.id;
    editorStages.splice(idx, 1);
    if (stageId) {
        delete fallbackRules[stageId];
        Object.values(fallbackRules).forEach(rule => {
            if (rule.targetStageId === stageId) {
                rule.enabled = false;
                rule.targetStageId = '';
            }
        });
    }
    if (selectedStageId === stageId) selectedStageId = null;
    renderPipelineEditor();
}

function resetPipelineEditor() {
    const sourceStages = SAVED_PIPELINE_STAGES?.length ? SAVED_PIPELINE_STAGES : STAGES.map(id => ({ id }));
    editorStages = sourceStages.map(item => {
        const id = toStageId(item);
        const stage = ALL_STAGES.find(s => s.id === id);
        return stage ? { ...stage } : { id, name: item?.name || id, agent: item?.agent || '-', icon: '⚙️' };
    });
    fallbackRules = {};
    editorStages.forEach(s => {
        const saved = sourceStages.find(item => toStageId(item) === s.id)?.fallback;
        fallbackRules[s.id] = saved
            ? { enabled: !!saved.enabled, targetStageId: saved.targetStageId || '', maxRetries: saved.maxRetries || 3 }
            : { enabled: false, targetStageId: '', maxRetries: 3 };
    });
    if (!SAVED_PIPELINE_STAGES?.length && fallbackRules.testing) {
        fallbackRules.testing = { enabled: true, targetStageId: 'development', maxRetries: 3 };
    }
    if (!SAVED_PIPELINE_STAGES?.length && fallbackRules.code_review) {
        fallbackRules.code_review = { enabled: true, targetStageId: 'development', maxRetries: 2 };
    }
    selectedStageId = null;
    renderPipelineEditor();
}

async function saveAsTemplate() {
    const name = prompt('请输入模板名称：', '我的流程');
    if (!name || !name.trim()) return;

    const description = prompt('请输入模板描述（可选）：', '');

    const stages = editorStages.map(s => ({
        id: s.id,
        name: s.name,
        agent: s.agent,
    }));

    try {
        const r = await fetch('/api/pipeline-templates', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name: name.trim(),
                description: description || '',
                stages,
            }),
        });
        const data = await r.json();
        if (!r.ok) {
            throw new Error(data.error || '保存失败');
        }
        showToast(`模板 "${name.trim()}" 已保存`);
        await fetchPipelineTemplates();
    } catch (e) {
        showToast('保存模板失败: ' + e.message, true);
    }
}

async function savePipeline() {
    const stages = editorStages.map(s => ({
        id: s.id,
        name: s.name,
        agent: s.agent,
        fallback: fallbackRules[s.id] || { enabled: false, targetStageId: '', maxRetries: 3 },
    }));
    const r = await fetch('/api/pipeline', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ stages }),
    });
    const data = await r.json();
    pipelineIsCustom = data.is_custom ?? true;
    pipelineFetched = true;
    SAVED_PIPELINE_STAGES = stages;
    STAGES = editorStages.map(s => s.id);
    editorLoaded = true;

    await fetchRuntime();
    renderPipelineEditor();
    showToast('Pipeline 配置已保存并生效');
}

function showToast(message, isError = false) {
    let toast = document.getElementById('toast-msg');
    if (!toast) {
        toast = document.createElement('div');
        toast.id = 'toast-msg';
        toast.style.cssText = 'position:fixed;bottom:24px;left:50%;transform:translateX(-50%);padding:12px 24px;border-radius:var(--radius-md);font-size:13px;font-weight:600;z-index:9999;opacity:0;transition:opacity 0.3s';
        document.body.appendChild(toast);
    }
    toast.textContent = message;
    toast.style.background = isError ? 'var(--rose)' : 'var(--green)';
    toast.style.color = '#fff';
    toast.style.opacity = '1';
    setTimeout(() => { toast.style.opacity = '0'; }, 2500);
}

async function restoreDefaultPipeline() {
    if (!confirm('确定要恢复系统默认 Pipeline 配置吗？')) return;
    await fetch('/api/pipeline/reset', { method: 'POST' });
    pipelineIsCustom = false;
    pipelineFetched = true;
    SAVED_PIPELINE_STAGES = null;
    STAGES = [...DEFAULT_STAGES];
    editorLoaded = false;

    await fetchRuntime();
    initPipelineEditor();
    showToast('已恢复默认 Pipeline 配置');
}

/* ── SSE ── */
function connectStream() {
    if (eventSource) eventSource.close();
    const lastSeq = latestEvents.length ? latestEvents[latestEvents.length - 1].seq : 0;
    eventSource = new EventSource(`/api/stream?since=${lastSeq}`);
    eventSource.onmessage = (msg) => {
        const ev = JSON.parse(msg.data);
        latestEvents = mergeEvents(latestEvents, [ev]);
        if (document.hidden) {
            needsVisibilitySync = true;
            return;
        }
        if (!renderThrottleTimer) {
            renderThrottleTimer = setTimeout(async () => {
                renderThrottleTimer = null;
                await fetchRuntime({ animate: false });
            }, 2000);
        }
    };
    eventSource.onerror = () => {
        if (eventSource) eventSource.close();
        setTimeout(connectStream, 3000);
    };
}

/* ── Boot ── */
(function init() {
    const savedCollapsed = localStorage.getItem('sidebarCollapsed');
    sidebarCollapsed = savedCollapsed === 'true';

    if (sidebarCollapsed) {
        document.getElementById('app')?.classList.add('sidebar-collapsed');
    }

    document.addEventListener('visibilitychange', () => {
        if (!document.hidden) {
            const shouldSync = needsVisibilitySync;
            needsVisibilitySync = false;
            if (shouldSync) {
                fetchRuntime({ animate: false }).catch(err => {
                    console.error('[HARNESS] Visibility sync failed:', err);
                });
            }
        }
    });

    Promise.all([
        fetchRuntime({ forceFullRender: true, partial: false }),
        fetchPipelineTemplates(),
    ]).then(() => {
        connectStream();
    }).catch(err => {
        console.error('[HARNESS] Error during init:', err);
    });
    setInterval(() => {
        if (!document.hidden) {
            fetchRuntime({ animate: false }).catch(err => {
                console.error('[HARNESS] Poll refresh failed:', err);
            });
        } else {
            needsVisibilitySync = true;
        }
    }, RUNTIME_POLL_INTERVAL_MS);
})();
