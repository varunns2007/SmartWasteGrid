document.addEventListener('DOMContentLoaded', () => {
    console.log('[*] SmartWasteGrid Client Initialized');

    // DOM Elements
    const btnRunDetection = document.getElementById('btn-run-detection');
    const btnUpload = document.getElementById('btn-upload');
    const fileInput = document.getElementById('file-input');
    const viewportImg = document.getElementById('viewport-img');
    const gridMatrixContainer = document.getElementById('grid-matrix-container');
    const categoryBreakdownContainer = document.getElementById('category-breakdown');
    const iotBinListContainer = document.getElementById('iot-bin-list');
    
    // Metric Elements
    const statTotalWaste = document.getElementById('stat-total-waste');
    const statPeakSector = document.getElementById('stat-peak-sector');
    const statPeakFill = document.getElementById('stat-peak-fill');
    const statMapAccuracy = document.getElementById('stat-map-accuracy');

    // Default API calls
    fetchBinTelemetry();
    setInterval(fetchBinTelemetry, 8000); // Live poll every 8 seconds

    // Initial Detection Run
    triggerDetection();

    // Event Handlers
    if (btnRunDetection) {
        btnRunDetection.addEventListener('click', () => {
            triggerDetection();
        });
    }

    if (btnUpload) {
        btnUpload.addEventListener('click', () => {
            fileInput.click();
        });
    }

    if (fileInput) {
        fileInput.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (!file) return;

            const formData = new FormData();
            formData.append('file', file);

            btnUpload.disabled = true;
            btnUpload.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Processing...';

            fetch('/api/detect', {
                method: 'POST',
                body: formData
            })
            .then(res => res.json())
            .then(data => {
                btnUpload.disabled = false;
                btnUpload.innerHTML = '📁 Upload File';
                if (data.success) {
                    renderDetectionResults(data);
                } else {
                    alert('Detection Error: ' + data.error);
                }
            })
            .catch(err => {
                btnUpload.disabled = false;
                btnUpload.innerHTML = '📁 Upload File';
                console.error(err);
            });
        });
    }

    function triggerDetection() {
        if (btnRunDetection) {
            btnRunDetection.disabled = true;
            btnRunDetection.innerHTML = '⚡ Scanning...';
        }

        fetch('/api/detect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
        })
        .then(res => res.json())
        .then(data => {
            if (btnRunDetection) {
                btnRunDetection.disabled = false;
                btnRunDetection.innerHTML = '⚡ Run Waste Analysis';
            }
            if (data.success) {
                renderDetectionResults(data);
            }
        })
        .catch(err => {
            if (btnRunDetection) {
                btnRunDetection.disabled = false;
                btnRunDetection.innerHTML = '⚡ Run Waste Analysis';
            }
            console.error('API Error:', err);
        });
    }

    function renderDetectionResults(data) {
        // Update Canvas Annotated Image
        if (viewportImg && data.annotated_image) {
            viewportImg.src = data.annotated_image;
        }

        // Update Stats
        if (statTotalWaste) statTotalWaste.innerText = data.total_waste_detected;
        if (statPeakSector) statPeakSector.innerText = data.highest_risk_sector;
        if (statPeakFill) statPeakFill.innerText = `${data.highest_sector_fill_percent}%`;

        // Render Spatial 3x3 Grid Cards
        if (gridMatrixContainer && data.grid_matrix) {
            gridMatrixContainer.innerHTML = '';
            Object.keys(data.grid_matrix).forEach(sectorKey => {
                const cell = data.grid_matrix[sectorKey];
                const card = document.createElement('div');
                
                let fillClass = 'clean';
                let barColor = '#10b981';
                if (cell.fill_percent > 80) {
                    fillClass = 'critical';
                    barColor = '#ef4444';
                } else if (cell.fill_percent > 50) {
                    fillClass = 'moderate';
                    barColor = '#f59e0b';
                }

                card.className = `grid-cell-card ${fillClass}`;
                card.innerHTML = `
                    <div class="cell-name">SECTOR ${cell.sector}</div>
                    <div class="cell-val" style="color: ${barColor}">${cell.fill_percent}%</div>
                    <div class="cell-status">${cell.item_count} items detected</div>
                    <div class="progress-bar-bg">
                        <div class="progress-bar-fill" style="width: ${cell.fill_percent}%; background-color: ${barColor};"></div>
                    </div>
                `;
                gridMatrixContainer.appendChild(card);
            });
        }

        // Render Category Breakdown
        if (categoryBreakdownContainer && data.category_breakdown) {
            categoryBreakdownContainer.innerHTML = '';
            const categoryColors = {
                'plastic': '#3b82f6',
                'organic': '#10b981',
                'paper': '#f59e0b',
                'metal': '#8b5cf6',
                'glass': '#06b6d4',
                'hazard': '#ef4444'
            };

            Object.entries(data.category_breakdown).forEach(([cls, count]) => {
                const col = categoryColors[cls] || '#3b82f6';
                const item = document.createElement('div');
                item.className = 'category-item';
                item.style.borderLeftColor = col;
                item.innerHTML = `
                    <span class="category-name">${cls}</span>
                    <span class="category-count" style="color: ${col}">${count}</span>
                `;
                categoryBreakdownContainer.appendChild(item);
            });
        }
    }

    function fetchBinTelemetry() {
        fetch('/api/bins')
            .then(res => res.json())
            .then(data => {
                if (iotBinListContainer && data.bins) {
                    iotBinListContainer.innerHTML = '';
                    data.bins.forEach(bin => {
                        let badgeBg = 'rgba(16, 185, 129, 0.15)';
                        let badgeColor = '#34d399';

                        if (bin.status === 'Critical') {
                            badgeBg = 'rgba(239, 68, 68, 0.2)';
                            badgeColor = '#f87171';
                        } else if (bin.status === 'Overflow Risk') {
                            badgeBg = 'rgba(245, 158, 11, 0.2)';
                            badgeColor = '#fbbf24';
                        }

                        const binDiv = document.createElement('div');
                        binDiv.className = 'bin-card';
                        binDiv.innerHTML = `
                            <div class="bin-info">
                                <h4>${bin.bin_id} (${bin.sector})</h4>
                                <p>${bin.location}</p>
                            </div>
                            <div class="fill-badge" style="background: ${badgeBg}; color: ${badgeColor};">
                                ${bin.fill_percent}% Filled
                            </div>
                        `;
                        iotBinListContainer.appendChild(binDiv);
                    });
                }
            })
            .catch(err => console.error('Bin Telemetry Error:', err));
    }
});
