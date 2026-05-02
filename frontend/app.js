// Configuration
const CONFIG = {
    API_BASE_URL: 'http://localhost:8000/api/v1'
};

// Global Chart instance to destroy on re-render
let forecastChartInstance = null;
let currentInventoryData = null; // Store for recalculation

// Tab switching logic
document.querySelectorAll('.nav-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
        document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
        e.currentTarget.classList.add('active');
        
        document.querySelectorAll('.view-section').forEach(v => v.classList.remove('active'));
        const targetId = e.currentTarget.getAttribute('data-target');
        document.getElementById(targetId).classList.add('active');
        
        // Auto-refresh metrics if that tab is clicked
        if (targetId === 'view-metrics') {
            fetchModelMetrics();
        }
        
        document.querySelector('.content-area').scrollTop = 0;
    });
});

function setTodayDate(elementId) {
    const today = new Date().toISOString().split('T')[0];
    document.getElementById(elementId).value = today;
}

function setTomorrowDate(elementId) {
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    const dateStr = tomorrow.toISOString().split('T')[0];
    document.getElementById(elementId).value = dateStr;
}

function setDateConstraints() {
    const today = new Date().toISOString().split('T')[0];
    
    // Planning & Forecasting is for upcoming days only
    document.getElementById('forecast-date').setAttribute('min', today);
    document.getElementById('staff-date').setAttribute('min', today);
    document.getElementById('inventory-date').setAttribute('min', today);
    
    // Feedback is only for actuals (today or past dates)
    document.getElementById('fb-date').setAttribute('max', today);
}

document.addEventListener('DOMContentLoaded', () => {
    setTodayDate('forecast-date');
    setTodayDate('fb-date');
    setTomorrowDate('staff-date');
    setTomorrowDate('inventory-date');
    
    // Apply validation constraints
    setDateConstraints();
    
    // Auto-fetch prediction for today's feedback
    fetchPredictionForFeedback();
});

function setLoadingState(section, isLoading) {
    const btn = document.getElementById(`btn-${section}`);
    const loader = document.getElementById(`loader-${section}`);
    
    if (isLoading) {
        btn.disabled = true;
        loader.style.display = 'inline-block';
        hideError(section);
        hideSuccess(section);
    } else {
        btn.disabled = false;
        loader.style.display = 'none';
    }
}

function showError(section, message) {
    const errorEl = document.getElementById(`error-${section}`);
    if (errorEl) {
        errorEl.textContent = message;
        errorEl.style.display = 'block';
    }
}

function hideError(section) {
    const errorEl = document.getElementById(`error-${section}`);
    if (errorEl) errorEl.style.display = 'none';
}

function showSuccess(section) {
    const el = document.getElementById(`success-${section}`);
    if (el) el.style.display = 'block';
}

function hideSuccess(section) {
    const el = document.getElementById(`success-${section}`);
    if (el) el.style.display = 'none';
}

// 1. Forecast Section
document.getElementById('btn-forecast').addEventListener('click', async () => {
    const dateStr = document.getElementById('forecast-date').value;
    if (!dateStr) return showError('forecast', 'Please select a date.');

    setLoadingState('forecast', true);
    
    try {
        const response = await fetch(`${CONFIG.API_BASE_URL}/forecast?target_date=${dateStr}`);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        
        const data = await response.json();
        let forecastList = Array.isArray(data) ? data : data.hourly_forecast || [];

        if (forecastList.length === 0) {
            showError('forecast', 'No forecast data available for this date.');
            return;
        }

        let totalCovers = 0;
        let peakHour = '';
        let maxCovers = -1;
        
        const labels = [];
        const chartData = [];

        forecastList.forEach(item => {
            const covers = parseInt(item.predicted_covers, 10) || 0;
            const hour = item.hour;
            
            totalCovers += covers;
            labels.push(`${hour}:00`);
            chartData.push(covers);
            
            if (covers > maxCovers) {
                maxCovers = covers;
                peakHour = `${hour}:00`;
            }
        });
        
        document.getElementById('total-covers').textContent = totalCovers;
        document.getElementById('peak-hour').textContent = peakHour;
        
        renderForecastChart(labels, chartData);
        document.getElementById('result-forecast').style.display = 'block';

    } catch (error) {
        showError('forecast', 'Failed to fetch forecast: ' + error.message);
    } finally {
        setLoadingState('forecast', false);
    }
});

function renderForecastChart(labels, data) {
    const ctx = document.getElementById('forecastChart').getContext('2d');
    
    if (forecastChartInstance) {
        forecastChartInstance.destroy();
    }
    
    const gradient = ctx.createLinearGradient(0, 0, 0, 350);
    gradient.addColorStop(0, 'rgba(139, 92, 246, 0.5)'); // Primary color
    gradient.addColorStop(1, 'rgba(139, 92, 246, 0.0)');

    forecastChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Predicted Covers',
                data: data,
                borderColor: '#8b5cf6',
                backgroundColor: gradient,
                borderWidth: 3,
                pointBackgroundColor: '#fff',
                pointBorderColor: '#8b5cf6',
                pointBorderWidth: 2,
                pointRadius: 4,
                pointHoverRadius: 6,
                fill: true,
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    backgroundColor: 'rgba(15, 23, 42, 0.9)',
                    titleColor: '#94a3b8',
                    bodyColor: '#fff',
                    borderColor: 'rgba(255,255,255,0.1)',
                    borderWidth: 1,
                    padding: 10
                }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(255,255,255,0.05)', drawBorder: false },
                    ticks: { color: '#94a3b8' }
                },
                y: {
                    grid: { color: 'rgba(255,255,255,0.05)', drawBorder: false },
                    ticks: { color: '#94a3b8', beginAtZero: true }
                }
            },
            interaction: {
                mode: 'nearest',
                axis: 'x',
                intersect: false
            }
        }
    });
}

// 2. Staff Plan Section
document.getElementById('btn-staff').addEventListener('click', async () => {
    const dateStr = document.getElementById('staff-date').value;
    if (!dateStr) return showError('staff', 'Please select a date.');

    setLoadingState('staff', true);
    
    try {
        const response = await fetch(`${CONFIG.API_BASE_URL}/staff-plan?target_date=${dateStr}`);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        
        const data = await response.json();
        renderStaffTable(data.hourly_plan || []);
        document.getElementById('result-staff').style.display = 'block';
        
    } catch (error) {
        showError('staff', 'Failed to fetch staff plan: ' + error.message);
    } finally {
        setLoadingState('staff', false);
    }
});

function renderStaffTable(hourlyPlan) {
    const thead = document.getElementById('staff-table-head');
    const tbody = document.getElementById('staff-table-body');
    thead.innerHTML = '';
    tbody.innerHTML = '';
    
    if (hourlyPlan.length === 0) return;

    // Extract all unique roles across all hours
    const roleSet = new Set();
    hourlyPlan.forEach(hp => {
        if(hp.roles) {
            hp.roles.forEach(r => roleSet.add(r.role));
        }
    });
    const roles = Array.from(roleSet).sort();
    
    // Find max count for each role for heatmap calculation
    const maxCounts = {};
    roles.forEach(role => maxCounts[role] = 0);
    
    hourlyPlan.forEach(hp => {
        if(hp.roles) {
            hp.roles.forEach(r => {
                if(r.count > maxCounts[r.role]) maxCounts[r.role] = r.count;
            });
        }
    });

    // Create Header Row
    const trHead = document.createElement('tr');
    const thHour = document.createElement('th');
    thHour.textContent = 'Hour';
    trHead.appendChild(thHour);
    
    roles.forEach(role => {
        const th = document.createElement('th');
        th.textContent = role;
        trHead.appendChild(th);
    });
    thead.appendChild(trHead);

    // Create Body Rows
    hourlyPlan.forEach(hp => {
        const tr = document.createElement('tr');
        
        const tdHour = document.createElement('td');
        tdHour.textContent = hp.hour ? `${hp.hour}:00` : '';
        tr.appendChild(tdHour);
        
        // Map roles for this hour
        const hourRolesMap = {};
        if (hp.roles) {
            hp.roles.forEach(r => hourRolesMap[r.role] = r.count);
        }
        
        roles.forEach(role => {
            const td = document.createElement('td');
            const count = hourRolesMap[role] || 0;
            td.textContent = count;
            
            // Apply Heatmap logic
            const max = maxCounts[role] || 1; // prevent div zero
            const intensity = count / max; // 0 to 1
            
            if (count > 0) {
                td.className = 'heatmap-cell';
                // Interpolate color: dark slate to primary purple
                // Slate: 15, 23, 42
                // Purple: 139, 92, 246
                // For simplicity, just apply an rgba background
                td.style.backgroundColor = `rgba(139, 92, 246, ${intensity * 0.8})`;
            } else {
                td.style.color = '#475569'; // dim 0s
            }
            
            tr.appendChild(td);
        });
        
        tbody.appendChild(tr);
    });
}

// 3. Inventory Section
document.getElementById('btn-inventory').addEventListener('click', () => fetchInventoryPlan({}));
document.getElementById('btn-recalculate-inventory').addEventListener('click', () => {
    // Gather current stock from inputs
    const currentStock = {};
    document.querySelectorAll('.stock-input').forEach(input => {
        const name = input.getAttribute('data-name');
        const val = parseFloat(input.value);
        if (!isNaN(val) && val > 0) {
            currentStock[name] = val;
        }
    });
    fetchInventoryPlan(currentStock);
});

async function fetchInventoryPlan(currentStock = {}) {
    const dateStr = document.getElementById('inventory-date').value;
    if (!dateStr) return showError('inventory', 'Please select a date.');

    setLoadingState('inventory', true);
    
    try {
        const payload = { target_date: dateStr, current_stock: currentStock };
        const response = await fetch(`${CONFIG.API_BASE_URL}/inventory-plan`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        
        const data = await response.json();
        currentInventoryData = data.ingredients || [];
        renderInventoryCards(currentInventoryData, currentStock);
        document.getElementById('result-inventory').style.display = 'block';

    } catch (error) {
        showError('inventory', 'Failed to fetch inventory plan: ' + error.message);
    } finally {
        setLoadingState('inventory', false);
    }
}

function renderInventoryCards(ingredients, currentStock) {
    const listEl = document.getElementById('inventory-list');
    listEl.innerHTML = '';

    if (ingredients.length === 0) {
        listEl.innerHTML = '<p class="text-muted">No procurement needed for this date.</p>';
        return;
    }

    ingredients.forEach(item => {
        const card = document.createElement('div');
        card.className = 'inventory-card';
        
        const isPerishable = item.shelf_life_days < 3;
        const shelfLifeClass = isPerishable ? 'badge warning' : 'badge';
        
        const stockValue = currentStock[item.ingredient_name] || 0;

        card.innerHTML = `
            <div class="inventory-header">
                <span class="inventory-name">${item.ingredient_name}</span>
                <div style="text-align: right;">
                    <span style="font-size: 0.8rem; color: var(--text-muted); display: block; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.2rem;">To Order</span>
                    <span class="inventory-qty">${item.quantity_kg.toFixed(2)} kg</span>
                </div>
            </div>
            <div class="inventory-meta">
                <span class="${shelfLifeClass}">Shelf Life: ${item.shelf_life_days}d</span>
                <span class="badge">Lead Time: ${item.lead_time_days}d</span>
            </div>
            <div class="inventory-input-group mt-2">
                <label>Current Stock (kg)</label>
                <input type="number" class="dark-input stock-input" data-name="${item.ingredient_name}" value="${stockValue}" min="0" step="0.1" placeholder="0.0">
            </div>
        `;
        listEl.appendChild(card);
    });
}

// 4. Feedback Form

// Auto-fetch prediction when date changes
document.getElementById('fb-date').addEventListener('change', fetchPredictionForFeedback);

async function fetchPredictionForFeedback() {
    const dateStr = document.getElementById('fb-date').value;
    if (!dateStr) return;

    const predInput = document.getElementById('fb-predicted');
    const submitBtn = document.getElementById('btn-feedback');
    const loader = document.getElementById('fb-pred-loader');
    
    predInput.value = '';
    predInput.placeholder = 'Loading...';
    submitBtn.disabled = true;
    loader.style.display = 'inline-block';
    hideError('feedback');

    try {
        const response = await fetch(`${CONFIG.API_BASE_URL}/forecast?target_date=${dateStr}`);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        
        const data = await response.json();
        let forecastList = Array.isArray(data) ? data : data.hourly_forecast || [];
        
        let totalCovers = 0;
        forecastList.forEach(item => {
            totalCovers += (parseInt(item.predicted_covers, 10) || 0);
        });
        
        predInput.value = totalCovers;
        submitBtn.disabled = false;
    } catch (error) {
        predInput.placeholder = 'Error';
        showError('feedback', 'Could not load prediction for this date. Generate forecast first.');
    } finally {
        loader.style.display = 'none';
    }
}

document.getElementById('feedback-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    setLoadingState('feedback', true);
    
    const payload = {
        target_date: document.getElementById('fb-date').value,
        predicted_covers: parseInt(document.getElementById('fb-predicted').value, 10),
        actual_covers: parseInt(document.getElementById('fb-actual').value, 10),
        reason: document.getElementById('fb-reason').value,
        notes: document.getElementById('fb-notes').value
    };

    try {
        const response = await fetch(`${CONFIG.API_BASE_URL}/feedback`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        
        showSuccess('feedback');
        document.getElementById('feedback-form').reset();
        setTodayDate('fb-date');
        fetchPredictionForFeedback();
        
    } catch (error) {
        showError('feedback', 'Failed to submit feedback: ' + error.message);
    } finally {
        setLoadingState('feedback', false);
    }
});

// 5. Metrics View
document.getElementById('btn-metrics').addEventListener('click', fetchModelMetrics);

async function fetchModelMetrics() {
    setLoadingState('metrics', true);
    
    try {
        const response = await fetch(`${CONFIG.API_BASE_URL}/model-info`);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        
        const data = await response.json();
        
        const engineEl = document.getElementById('metric-engine');
        const mapeEl = document.getElementById('metric-mape');
        const featEl = document.getElementById('metric-features');
        
        if (data.is_model_loaded) {
            engineEl.textContent = 'XGBoost AI Model';
            engineEl.style.color = 'var(--success)';
            
            const mapePercent = (data.model_mape * 100).toFixed(2);
            mapeEl.textContent = `${mapePercent}%`;
            
            if (data.model_mape > 0.2) {
                mapeEl.style.color = 'var(--warning)'; // warn if WMAPE > 20%
            } else {
                mapeEl.style.color = 'var(--success)';
            }
            
            featEl.textContent = data.feature_count || '--';
        } else {
            engineEl.textContent = 'Rule-Based Fallback';
            engineEl.style.color = 'var(--warning)';
            mapeEl.textContent = 'N/A';
            mapeEl.style.color = 'var(--text-muted)';
            featEl.textContent = '0 (Heuristics)';
        }
        
    } catch (error) {
        console.error("Failed to fetch model metrics", error);
        document.getElementById('metric-engine').textContent = 'Error Fetching API';
    } finally {
        setLoadingState('metrics', false);
    }
}
