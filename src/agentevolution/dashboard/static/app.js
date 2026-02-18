/* ══════════════════════════════════════════════════
   AgentEvolution Dashboard v2 — Frontend Logic
   ══════════════════════════════════════════════════ */

const API = '';

// Agent color palette
const AGENT_COLORS = {
    'agent-alpha': { class: 'agent-alpha', bg: '#818cf8', label: 'α' },
    'agent-beta': { class: 'agent-beta', bg: '#34d399', label: 'β' },
    'agent-gamma': { class: 'agent-gamma', bg: '#fbbf24', label: 'γ' },
    'agent-delta': { class: 'agent-delta', bg: '#f472b6', label: 'δ' },
};

function getAgentStyle(agentId) {
    return AGENT_COLORS[agentId] || { class: 'agent-default', bg: '#6b7280', label: '?' };
}

// State
let allTools = [];
let currentSort = 'fitness';
let fitnessChartInstance = null;
let velocityChartInstance = null;
let distributionChartInstance = null;

// ─── Init ───

document.addEventListener('DOMContentLoaded', () => {
    initConstellation();
    loadDashboard();
    setupModal();
    setupSortButtons();
    setupNavTabs();

    // Auto-refresh
    setInterval(loadDashboard, 5000);
});

// ─── Constellation Effect ───

function initConstellation() {
    const canvas = document.getElementById('constellation');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    let width, height;
    let particles = [];

    // Resize
    const resize = () => {
        width = canvas.width = window.innerWidth;
        height = canvas.height = window.innerHeight;
    };
    window.addEventListener('resize', resize);
    resize();

    // Create particles
    for (let i = 0; i < 60; i++) {
        particles.push({
            x: Math.random() * width,
            y: Math.random() * height,
            vx: (Math.random() - 0.5) * 0.5,
            vy: (Math.random() - 0.5) * 0.5,
            size: Math.random() * 2 + 1,
            color: Math.random() > 0.5 ? 'rgba(139, 92, 246, 0.4)' : 'rgba(6, 182, 212, 0.4)'
        });
    }

    // Animation Loop
    function animate() {
        ctx.clearRect(0, 0, width, height);

        // Update and draw particles
        particles.forEach(p => {
            p.x += p.vx;
            p.y += p.vy;

            if (p.x < 0 || p.x > width) p.vx *= -1;
            if (p.y < 0 || p.y > height) p.vy *= -1;

            ctx.beginPath();
            ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
            ctx.fillStyle = p.color;
            ctx.fill();
        });

        // Draw connections
        for (let i = 0; i < particles.length; i++) {
            for (let j = i + 1; j < particles.length; j++) {
                const dx = particles[i].x - particles[j].x;
                const dy = particles[i].y - particles[j].y;
                const dist = Math.sqrt(dx * dx + dy * dy);

                if (dist < 150) {
                    ctx.beginPath();
                    ctx.strokeStyle = `rgba(255, 255, 255, ${0.1 - dist / 1500})`;
                    ctx.lineWidth = 1;
                    ctx.moveTo(particles[i].x, particles[i].y);
                    ctx.lineTo(particles[j].x, particles[j].y);
                    ctx.stroke();
                }
            }
        }
        requestAnimationFrame(animate);
    }
    animate();
}


// ─── Nav Tabs ───

function setupNavTabs() {
    document.querySelectorAll('.nav-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');

            const tabName = tab.dataset.tab;
            const mainGrid = document.querySelector('.main-grid');
            const overviewSections = document.querySelectorAll('.section-overview');
            const chartsGrid = document.querySelector('.charts-grid'); // Explicitly select charts grid
            const registryPanel = document.getElementById('panel-registry');
            // Sidebar panels
            const sidebar = document.querySelector('.sidebar');
            const lbPanel = document.querySelector('.panel-leaderboard');
            const agentPanel = document.querySelector('.panel-agents');
            const actPanel = document.querySelector('.panel-activity');

            // Reset
            mainGrid.classList.remove('single-col');
            sidebar.style.display = 'flex';
            registryPanel.style.display = 'block';
            lbPanel.style.display = 'block';
            agentPanel.style.display = 'block';
            actPanel.style.display = 'block'; // Ensure activity is shown by default

            if (tabName === 'overview') {
                overviewSections.forEach(el => el.style.display = 'grid');
                if (chartsGrid) chartsGrid.style.display = 'grid';
                mainGrid.style.display = 'grid';
            } else if (tabName === 'registry') {
                overviewSections.forEach(el => el.style.display = 'none');
                if (chartsGrid) chartsGrid.style.display = 'none';
                mainGrid.style.display = 'grid';
            } else if (tabName === 'activity') {
                overviewSections.forEach(el => el.style.display = 'none');
                if (chartsGrid) chartsGrid.style.display = 'none';
                mainGrid.classList.add('single-col');
                registryPanel.style.display = 'none';
                lbPanel.style.display = 'none';
                agentPanel.style.display = 'none';
                // Activity panel stays visible and takes full width due to single-col sidebar
            }
        });
    });
}

// ─── Sort Buttons ───

function setupSortButtons() {
    document.querySelectorAll('.sort-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.sort-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentSort = btn.dataset.sort;
            renderTools();
        });
    });
}

// ─── Dashboard Load ───

async function loadDashboard() {
    try {
        await Promise.all([loadStats(), loadTools(), loadLeaderboard(), loadActivity()]);
    } catch (err) {
        // Silent fail on network error to avoid spamming console
    }
}

// ─── Stats & Charts ───

async function loadStats() {
    const res = await fetch(`${API}/api/stats`);
    const data = await res.json();

    // Animate number stats
    setStatValue('stat-tools', data.total_tools);
    setStatValue('stat-uses', data.total_uses);
    setStatValue('stat-agents', data.unique_agents);

    // Update text
    const fitnessText = document.getElementById('stat-fitness-text');
    if (fitnessText) fitnessText.textContent = data.avg_fitness.toFixed(3);

    // Update charts
    updateCharts(data);
}

function updateCharts(stats) {
    // 1. Fitness Doughnut
    const ctxFit = document.getElementById('fitnessChart');
    if (ctxFit) {
        if (fitnessChartInstance) {
            fitnessChartInstance.data.datasets[0].data = [stats.avg_fitness, 1 - stats.avg_fitness];
            fitnessChartInstance.update();
        } else {
            fitnessChartInstance = new Chart(ctxFit, {
                type: 'doughnut',
                data: {
                    labels: ['Fitness', 'Gap'],
                    datasets: [{
                        data: [stats.avg_fitness, 1 - stats.avg_fitness],
                        backgroundColor: ['#8b5cf6', 'rgba(255,255,255,0.05)'],
                        borderWidth: 0,
                        hoverOffset: 4
                    }]
                },
                options: {
                    cutout: '75%',
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false }, tooltip: { enabled: false } },
                    animation: { animateScale: true }
                }
            });
        }
    }

    // 2. Velocity Chart (Mock data for demo, ideally from API)
    const ctxVel = document.getElementById('velocityChart');
    if (ctxVel) {
        if (!velocityChartInstance) {
            velocityChartInstance = new Chart(ctxVel, {
                type: 'line',
                data: {
                    labels: ['1h ago', '45m', '30m', '15m', 'Now'],
                    datasets: [{
                        label: 'New Tools',
                        data: [0, 2, 1, 3, 1], // In real app, fetch historical data
                        borderColor: '#06b6d4',
                        backgroundColor: 'rgba(6, 182, 212, 0.1)',
                        fill: true,
                        tension: 0.4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.05)' } },
                        x: { grid: { display: false } }
                    },
                    plugins: { legend: { display: false } }
                }
            });
        }
    }

    // 3. Distribution Chart
    const ctxDist = document.getElementById('distributionChart');
    if (ctxDist) {
        if (!distributionChartInstance) {
            distributionChartInstance = new Chart(ctxDist, {
                type: 'bar',
                data: {
                    labels: ['Utils', 'Data', 'Web', 'Sys'],
                    datasets: [{
                        label: 'Tools by Tag',
                        data: [4, 7, 2, 5], // Mock
                        backgroundColor: ['#8b5cf6', '#10b981', '#f59e0b', '#ef4444'],
                        borderRadius: 4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: { display: false },
                        x: { grid: { display: false } }
                    },
                    plugins: { legend: { display: false } }
                }
            });
        }
    }
}

function setStatValue(id, value) {
    const el = document.querySelector(`#${id} .stat-value`);
    if (!el) return;
    const current = parseInt(el.textContent) || 0;
    if (current !== value) {
        el.textContent = value;
        el.style.transition = 'transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1)';
        el.style.transform = 'scale(1.15)';
        setTimeout(() => { el.style.transform = 'scale(1)'; }, 300);
    }
}

// ─── Tools ───

async function loadTools() {
    const res = await fetch(`${API}/api/tools`);
    const data = await res.json();
    allTools = data.tools;
    document.querySelector('.panel-count').textContent = data.total;
    renderTools();
    renderAgents();

    // Update charts with real data if possible
    if (velocityChartInstance) {
        // Simple real-time update logic could go here
    }
}

function renderTools() {
    const container = document.getElementById('tool-list');
    if (!allTools.length) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">🔨</div>
                <div class="empty-text">No tools in the ecosystem yet</div>
                <div class="empty-hint">python examples/multi_agent_demo.py</div>
            </div>`;
        return;
    }

    // Sort tools
    const sorted = [...allTools].sort((a, b) => {
        if (currentSort === 'fitness') return b.fitness_score - a.fitness_score;
        if (currentSort === 'uses') return b.total_uses - a.total_uses;
        return new Date(b.created_at) - new Date(a.created_at);
    });

    container.innerHTML = sorted.map(tool => {
        const agent = getAgentStyle(tool.author_agent_id);
        const fitnessClass = tool.fitness_score >= 0.7 ? 'fitness-high' : tool.fitness_score >= 0.4 ? 'fitness-mid' : 'fitness-low';
        const fitnessColor = tool.fitness_score >= 0.7 ? '#10b981' : tool.fitness_score >= 0.4 ? '#f59e0b' : '#ef4444';
        const isFork = tool.parent_tool_id && tool.parent_tool_id !== '';

        return `
        <div class="tool-card" onclick="showToolDetail('${tool.id}')">
            <div class="tool-card-top">
                <div class="tool-name-group">
                    <span class="tool-name">${esc(tool.name)}</span>
                    <span class="tool-version-badge">v${tool.version}</span>
                    ${isFork ? '<span class="tool-fork-badge">⑂ fork</span>' : ''}
                </div>
                <div class="tool-fitness-chip ${fitnessClass}">
                    ${tool.fitness_score.toFixed(2)}
                </div>
            </div>
            <div class="tool-desc">${esc(tool.description)}</div>
            <div class="tool-footer">
                <span class="tool-meta-chip">⚡ ${tool.total_uses} uses</span>
                <span class="tool-meta-chip">${trustIcon(tool.trust_level)} ${trustLabel(tool.trust_level)}</span>
                ${tool.tags.slice(0, 3).map(t => `<span class="tool-tag">${esc(t)}</span>`).join('')}
                <div class="fitness-bar-track">
                    <div class="fitness-bar-fill" style="width:${tool.fitness_score * 100}%;background:${fitnessColor}"></div>
                </div>
                <span class="tool-agent ${agent.class}">${esc(tool.author_agent_id)}</span>
            </div>
        </div>`;
    }).join('');
}

// ─── Agents ───

function renderAgents() {
    const container = document.getElementById('agent-grid');
    // Group tools by agent
    const agents = {};
    allTools.forEach(tool => {
        if (!agents[tool.author_agent_id]) {
            agents[tool.author_agent_id] = { tools: 0, totalFitness: 0 };
        }
        agents[tool.author_agent_id].tools++;
        agents[tool.author_agent_id].totalFitness += tool.fitness_score;
    });

    if (!Object.keys(agents).length) {
        container.innerHTML = '<div class="empty-state"><div class="empty-icon">🤖</div><div class="empty-text">No agents yet</div></div>';
        return;
    }

    container.innerHTML = Object.entries(agents).map(([agentId, data]) => {
        const style = getAgentStyle(agentId);
        const avgFitness = (data.totalFitness / data.tools).toFixed(2);
        return `
        <div class="agent-row">
            <div class="agent-avatar" style="background:${style.bg}">${style.label}</div>
            <div class="agent-details">
                <div class="agent-name">${esc(agentId)}</div>
                <div class="agent-meta">${data.tools} tools • avg fitness ${avgFitness}</div>
            </div>
            <div class="agent-tools-count">${data.tools}</div>
        </div>`;
    }).join('');
}

// ─── Leaderboard ───

async function loadLeaderboard() {
    const res = await fetch(`${API}/api/leaderboard?limit=8`);
    const data = await res.json();
    const container = document.getElementById('leaderboard');

    if (!data.leaderboard.length) {
        container.innerHTML = '<div class="empty-state"><div class="empty-icon">🏆</div><div class="empty-text">No tools yet</div></div>';
        return;
    }

    container.innerHTML = data.leaderboard.map((item, i) => {
        const rankClass = i === 0 ? 'lb-rank-gold' : i === 1 ? 'lb-rank-silver' : i === 2 ? 'lb-rank-bronze' : 'lb-rank-normal';
        const rankText = i === 0 ? '👑' : i === 1 ? '🥈' : i === 2 ? '🥉' : `#${i + 1}`;
        const fitnessColor = item.fitness_score >= 0.7 ? '#10b981' : item.fitness_score >= 0.4 ? '#f59e0b' : '#ef4444';
        const barWidth = item.fitness_score * 100;

        return `
        <div class="lb-row">
            <span class="lb-rank ${rankClass}">${rankText}</span>
            <div class="lb-info">
                <div class="lb-name">${esc(item.name)}</div>
                <div class="lb-author">${esc(item.author)}</div>
            </div>
            <div class="lb-fitness-bar">
                <div class="lb-fitness-fill" style="width:${barWidth}%;background:${fitnessColor}"></div>
            </div>
            <span class="lb-score">${item.fitness_score.toFixed(2)}</span>
        </div>`;
    }).join('');
}

// ─── Activity Feed ───

async function loadActivity() {
    const res = await fetch(`${API}/api/activity?limit=12`);
    const data = await res.json();
    const container = document.getElementById('activity-feed');

    if (!data.activities.length) {
        container.innerHTML = '<div class="empty-state"><div class="empty-icon">📡</div><div class="empty-text">No activity</div></div>';
        return;
    }

    container.innerHTML = data.activities.map(act => {
        const agent = getAgentStyle(act.agent_id);
        return `
        <div class="activity-item">
            <div class="activity-dot" style="background:${agent.bg}"></div>
            <div class="activity-text">
                <strong>${esc(act.agent_id)}</strong> published
                <strong>${esc(act.tool_name)}</strong>
                <span class="activity-time">${timeAgo(act.timestamp)}</span>
            </div>
        </div>`;
    }).join('');
}

// ─── Tool Detail Modal ───

function setupModal() {
    document.getElementById('modal-close').addEventListener('click', closeModal);
    document.getElementById('modal-overlay').addEventListener('click', e => {
        if (e.target.id === 'modal-overlay') closeModal();
    });
    document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });
}

async function showToolDetail(toolId) {
    const overlay = document.getElementById('modal-overlay');
    const content = document.getElementById('modal-content');
    overlay.classList.add('active');

    const [toolRes, provRes] = await Promise.all([
        fetch(`${API}/api/tools/${toolId}`),
        fetch(`${API}/api/tools/${toolId}/provenance`),
    ]);
    const tool = await toolRes.json();
    const prov = await provRes.json();
    const agent = getAgentStyle(tool.author_agent_id);
    const successRate = tool.total_uses > 0 ? ((tool.successful_uses / tool.total_uses) * 100).toFixed(0) : '—';
    const fitnessClass = tool.fitness_score >= 0.7 ? 'fitness-high' : tool.fitness_score >= 0.4 ? 'fitness-mid' : 'fitness-low';
    const isFork = tool.parent_tool_id && tool.parent_tool_id !== '';

    content.innerHTML = `
        <div class="modal-header">
            <div class="modal-name">${esc(tool.name)}</div>
            <div class="modal-desc">${esc(tool.description)}</div>
            <div class="modal-badges">
                <span class="tool-fitness-chip ${fitnessClass}">🧬 ${tool.fitness_score.toFixed(4)}</span>
                <span class="tool-meta-chip">${trustIcon(tool.trust_level)} ${trustLabel(tool.trust_level)}</span>
                <span class="tool-meta-chip">⚡ ${tool.total_uses} uses</span>
                <span class="tool-agent ${agent.class}">${esc(tool.author_agent_id)}</span>
                ${isFork ? '<span class="tool-fork-badge">⑂ Fork</span>' : ''}
                <span class="tool-meta-chip" style="font-family:var(--mono);font-size:10px">🔗 ${tool.content_hash ? tool.content_hash.slice(0, 16) : ''}...</span>
            </div>
        </div>

        <div class="modal-section">
            <div class="modal-section-title">Performance</div>
            <div class="modal-stats-grid">
                <div class="modal-stat">
                    <div class="modal-stat-value">${successRate}%</div>
                    <div class="modal-stat-label">Success Rate</div>
                </div>
                <div class="modal-stat">
                    <div class="modal-stat-value">${tool.unique_agents}</div>
                    <div class="modal-stat-label">Unique Agents</div>
                </div>
                <div class="modal-stat">
                    <div class="modal-stat-value">${tool.avg_execution_time_ms > 0 ? tool.avg_execution_time_ms.toFixed(0) + 'ms' : '—'}</div>
                    <div class="modal-stat-label">Avg Latency</div>
                </div>
            </div>
        </div>

        <div class="modal-section">
            <div class="modal-section-title">Source Code</div>
            <div class="modal-code">${esc(tool.code)}</div>
        </div>

        <div class="modal-section">
            <div class="modal-section-title">Test Case</div>
            <div class="modal-code">${esc(tool.test_case)}</div>
        </div>

        ${prov.chain.length ? `
        <div class="modal-section">
            <div class="modal-section-title">Provenance Chain</div>
            <div class="prov-chain">
                ${prov.chain.map(p => `
                    <div class="prov-node">
                        <div class="prov-dot"></div>
                        <div class="prov-info">
                            <div class="prov-hash">${p.content_hash}</div>
                            <div class="prov-detail">v${p.version} • Security: ${p.security_scan} • ${p.execution_time_ms.toFixed(0)}ms • Sig: ${p.signature}</div>
                        </div>
                    </div>
                `).join('')}
            </div>
        </div>` : ''}

        ${tool.input_schema ? `
        <div class="modal-section">
            <div class="modal-section-title">Input Schema (MCP)</div>
            <div class="modal-code">${esc(JSON.stringify(tool.input_schema, null, 2))}</div>
        </div>` : ''}
    `;
}

function closeModal() {
    document.getElementById('modal-overlay').classList.remove('active');
}

// ─── Helpers ───

function trustLabel(level) {
    const labels = { 0: 'Submitted', 1: 'Verified', 2: 'Battle-Tested', 3: 'Community' };
    return labels[level] || `Level ${level}`;
}

function trustIcon(level) {
    const icons = { 0: '📝', 1: '✅', 2: '🏆', 3: '⭐' };
    return icons[level] || '📝';
}

function timeAgo(iso) {
    if (!iso) return '';
    const s = Math.floor((Date.now() - new Date(iso)) / 1000);
    if (s < 60) return 'just now';
    if (s < 3600) return `${Math.floor(s / 60)}m ago`;
    if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
    return `${Math.floor(s / 86400)}d ago`;
}

function esc(str) {
    if (!str) return '';
    const d = document.createElement('div');
    d.textContent = str;
    return d.innerHTML;
}
