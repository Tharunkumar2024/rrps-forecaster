// Configuration
const CONFIG = {
    // Set your FastAPI backend URL here
    API_BASE_URL: 'http://localhost:8000/api/v1'
};

// Tab switching logic
document.querySelectorAll('.nav-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
        // Remove active class from all buttons
        document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
        // Add to clicked
        e.currentTarget.classList.add('active');
        
        // Hide all views
        document.querySelectorAll('.view-section').forEach(v => v.classList.remove('active'));
        
        // Show target view
        const targetId = e.currentTarget.getAttribute('data-target');
        document.getElementById(targetId).classList.add('active');
        
        // Reset scroll position
        document.querySelector('.content-area').scrollTop = 0;
    });
});

// Utility function for setting today's date
function setTodayDate(elementId) {
    const today = new Date().toISOString().split('T')[0];
    document.getElementById(elementId).value = today;
}

// Utility function for setting tomorrow's date
function setTomorrowDate(elementId) {
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    const dateStr = tomorrow.toISOString().split('T')[0];
    document.getElementById(elementId).value = dateStr;
}

// Initialize on load
document.addEventListener('DOMContentLoaded', () => {
    setTodayDate('forecast-date');
    setTodayDate('fb-date');
    setTomorrowDate('staff-date');
    setTomorrowDate('inventory-date');
});

// Helper for UI loading states
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
        const tbody = document.getElementById('forecast-table-body');
        tbody.innerHTML = '';
        
        let forecastList = Array.isArray(data) ? data : data.hourly_forecast || data.forecast || Object.entries(data).map(([k, v]) => ({ hour: k, covers: v }));

        if (forecastList.length === 0) {
            showError('forecast', 'No forecast data available for this date.');
            return;
        }

        let totalCovers = 0;
        forecastList.forEach(item => {
            const tr = document.createElement('tr');
            const tdHour = document.createElement('td');
            tdHour.textContent = item.hour ?? item.time ?? item.timestamp ?? '';
            const tdCovers = document.createElement('td');
            
            const covers = parseInt(item.predicted_covers ?? item.covers ?? item.value ?? 0, 10) || 0;
            totalCovers += covers;
            
            tdCovers.textContent = covers;
            tr.appendChild(tdHour);
            tr.appendChild(tdCovers);
            tbody.appendChild(tr);
        });
        
        const totalCoversEl = document.getElementById('total-covers');
        if (totalCoversEl) totalCoversEl.textContent = totalCovers;
        
        document.getElementById('result-forecast').style.display = 'flex';

    } catch (error) {
        showError('forecast', 'Failed to fetch forecast: ' + error.message);
    } finally {
        setLoadingState('forecast', false);
    }
});

// 2. Staff Plan Section
document.getElementById('btn-staff').addEventListener('click', async () => {
    const dateStr = document.getElementById('staff-date').value;
    if (!dateStr) return showError('staff', 'Please select a date.');

    setLoadingState('staff', true);
    
    try {
        const response = await fetch(`${CONFIG.API_BASE_URL}/staff-plan?target_date=${dateStr}`);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        
        const data = await response.json();
        const tbody = document.getElementById('staff-table-body');
        tbody.innerHTML = '';

        let peakWaiters = 0;
        let peakChefs = 0;

        if (data.hourly_plan && Array.isArray(data.hourly_plan)) {
            data.hourly_plan.forEach(hp => {
                let w = 0, c = 0;
                if (hp.roles) {
                    hp.roles.forEach(r => {
                        if (r.role.toLowerCase() === 'waiter') w += r.count;
                        if (r.role.toLowerCase() === 'chef') c += r.count;
                    });
                }
                
                peakWaiters = Math.max(peakWaiters, w);
                peakChefs = Math.max(peakChefs, c);

                const tr = document.createElement('tr');
                const tdHour = document.createElement('td');
                tdHour.textContent = hp.hour ?? '';
                const tdWaiters = document.createElement('td');
                tdWaiters.textContent = w;
                const tdChefs = document.createElement('td');
                tdChefs.textContent = c;
                tr.appendChild(tdHour);
                tr.appendChild(tdWaiters);
                tr.appendChild(tdChefs);
                tbody.appendChild(tr);
            });
        } else {
            showError('staff', 'Unrecognized response format for staff plan.');
        }
        
        document.getElementById('waiters-count').textContent = peakWaiters;
        document.getElementById('chefs-count').textContent = peakChefs;
        document.getElementById('result-staff').style.display = 'block';
        
    } catch (error) {
        showError('staff', 'Failed to fetch staff plan: ' + error.message);
    } finally {
        setLoadingState('staff', false);
    }
});

// 3. Inventory Section
document.getElementById('btn-inventory').addEventListener('click', async () => {
    const dateStr = document.getElementById('inventory-date').value;
    if (!dateStr) return showError('inventory', 'Please select a date.');

    setLoadingState('inventory', true);
    
    try {
        const response = await fetch(`${CONFIG.API_BASE_URL}/inventory-plan?target_date=${dateStr}`);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        
        const data = await response.json();
        const listEl = document.getElementById('inventory-list');
        listEl.innerHTML = '';
        
        let ingredients = Array.isArray(data) ? data : data.inventory || data.ingredients || data.items || [];

        if (ingredients.length === 0) {
            showError('inventory', 'No inventory data available.');
            return;
        }

        ingredients.forEach(item => {
            const li = document.createElement('li');
            li.className = 'inventory-item';
            
            const nameSpan = document.createElement('span');
            nameSpan.className = 'inventory-name';
            nameSpan.textContent = item.ingredient_name ?? item.name ?? item.ingredient ?? item.item ?? 'Unknown';
            
            const qtySpan = document.createElement('span');
            qtySpan.className = 'inventory-qty';
            let qty = item.quantity_kg ?? item.quantity ?? item.amount ?? item.value ?? '';
            qtySpan.textContent = qty;
            
            if (item.unit) {
                qtySpan.textContent += ` ${item.unit}`;
            } else if (item.quantity_kg !== undefined) {
                qtySpan.textContent += ` kg`;
            }

            li.appendChild(nameSpan);
            li.appendChild(qtySpan);
            listEl.appendChild(li);
        });

        document.getElementById('result-inventory').style.display = 'block';

    } catch (error) {
        showError('inventory', 'Failed to fetch inventory plan: ' + error.message);
    } finally {
        setLoadingState('inventory', false);
    }
});

// 4. Feedback Form
document.getElementById('feedback-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    setLoadingState('feedback', true);
    
    const payload = {
        date: document.getElementById('fb-date').value,
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
        
    } catch (error) {
        showError('feedback', 'Failed to submit feedback: ' + error.message);
    } finally {
        setLoadingState('feedback', false);
    }
});
