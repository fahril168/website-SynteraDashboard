/**
 * SYNTERA - Enterprise AI-IoT Dehumidification Dryer System
 * Centered Digital Clock Metric Card & Simulation Engine
 */

document.addEventListener('DOMContentLoaded', () => {
  // ===== DEVICE ID FROM URL =====
  const urlParams = new URLSearchParams(window.location.search);
  const currentDeviceId = urlParams.get('device');

  // Redirect to device selector if no device specified
  if (!currentDeviceId) {
    window.location.href = '/devices.html';
    return;
  }

  // Operational State Variables
  let isAiMode = true;
  let isBatchRunning = true;

  // Real-time sensor states
  let currentTemp = null;
  let currentHumidity = null;
  let currentWeight = null;
  let currentDryingRate = null;
  let heaterTemp = null;
  let batchDurationSeconds = 0;
  let totalBatchSeconds = 18000; // 5 jam estimasi siklus penuh

  // Actuator States
  let heaterState = false;
  let fanState = false;
  let exhaustState = false;

  // Chart Instances & Data
  let telemetryChart;
  let actuatorDonutChart;
  const maxDataPoints = 20;
  const chartLabels = [];
  const tempDataHistory = [];
  const humidityDataHistory = [];

  // DOM Elements - Status Badge & Controls
  const systemStatusBadge = document.getElementById('systemStatusBadge');
  const systemStatusText = document.getElementById('systemStatusText');

  // DOM Elements - Metrics & Gauges
  const valHumidity = document.getElementById('valHumidity');
  const valMoisture = document.getElementById('valMoisture');
  const valDryingRate = document.getElementById('valDryingRate');
  const valSubMoisture = document.getElementById('valSubMoisture');
  const valEstTimeDigits = document.getElementById('valEstTimeDigits');
  const valActuatorCount = document.getElementById('valActuatorCount');
  const gaugeStatusTag = document.getElementById('gaugeStatusTag');
  const gaugeSubtext = document.getElementById('gaugeSubtext');
  const telemetrySubtitle = document.getElementById('telemetrySubtitle');

  // DOM Elements - Donut Card
  const donutValText = document.getElementById('donutValText');
  const donutLblText = document.getElementById('donutLblText');
  const donutPctHeater = document.getElementById('donutPctHeater');
  const donutPctFan = document.getElementById('donutPctFan');
  const donutPctPeltier = document.getElementById('donutPctPeltier');

  // DOM Elements - Actuators
  const controlModeTag = document.getElementById('controlModeTag');
  const toggleHeater = document.getElementById('toggleHeater');
  const toggleFan = document.getElementById('toggleFan');
  const togglePeltier = document.getElementById('togglePeltier');
  const chipHeater = document.getElementById('chipHeater');
  const chipFan = document.getElementById('chipFan');
  const chipPeltier = document.getElementById('chipPeltier');

  const statusHeaterText = document.getElementById('statusHeaterText');
  const statusFanText = document.getElementById('statusFanText');
  const statusPeltierText = document.getElementById('statusPeltierText');

  // DOM Elements - Buttons & Tables
  const btnToggleMode = document.getElementById('btnToggleMode');
  const btnBatchAction = document.getElementById('btnBatchAction');
  const logTableBody = document.getElementById('logTableBody');
  const btnClearLogs = document.getElementById('btnClearLogs');
  const btnExportCSV = document.getElementById('btnExportCSV');

  // Initialize Line Chart, Donut Chart, and Speedometer Gauge
  initLineChart();
  initDonutChart();
  drawTemperatureGauge('tempGaugeCanvas', 0, 0, 60, false);

  // Set device tag in header
  const deviceTag = document.getElementById('deviceTag');
  if (deviceTag) deviceTag.textContent = currentDeviceId;

  // Event Listeners for Operational Controls
  btnToggleMode.addEventListener('click', toggleSystemMode);
  btnBatchAction.addEventListener('click', toggleBatchState);

  if (btnClearLogs) {
    btnClearLogs.addEventListener('click', () => {
      if (logTableBody) logTableBody.innerHTML = '';
    });
  }

  if (btnExportCSV) {
    btnExportCSV.addEventListener('click', exportDataCSV);
  }

  // Redraw gauge on window resize for responsive rendering
  window.addEventListener('resize', () => {
    drawTemperatureGauge('tempGaugeCanvas', currentTemp !== null ? currentTemp : 0, 0, 60, currentTemp !== null);
  });

  // Manual Toggle Listeners
  if (toggleHeater) {
    toggleHeater.addEventListener('change', (e) => {
      if (!isAiMode) {
        sendControlUpdate({ heater: e.target.checked });
      }
    });
  }

  if (toggleFan) {
    toggleFan.addEventListener('change', (e) => {
      if (!isAiMode) {
        sendControlUpdate({ fan: e.target.checked });
      }
    });
  }

  if (togglePeltier) {
    togglePeltier.addEventListener('change', (e) => {
      if (!isAiMode) {
        sendControlUpdate({ exhaust: e.target.checked });
      }
    });
  }

  // Real-Time Polling Loop from Flask Backend (setiap 5 detik sesuai laporan)
  setInterval(fetchDashboardState, 5000);
  fetchDashboardState(); // Initial fetch on load

  // Backend Communication Handlers
  async function fetchDashboardState() {
    try {
      const res = await fetch(`/api/dashboard/state/${currentDeviceId}`);
      if (res.status === 401) {
        window.location.href = '/login.html';
        return;
      }
      if (!res.ok) return;
      const data = await res.json();
      applyServerState(data.system_state, data.logs);
    } catch (err) {
      console.warn('Gagal menghubungi backend Flask:', err);
    }
  }

  async function sendControlUpdate(payload) {
    try {
      const res = await fetch(`/api/dashboard/control/${currentDeviceId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        const data = await res.json();
        if (data.system_state) {
          applyServerState(data.system_state);
        }
      }
    } catch (err) {
      console.error('Gagal mengirim kontrol ke Flask:', err);
    }
  }

  function applyServerState(state, logs = null) {
    if (!state) return;

    isAiMode = state.is_ai_mode !== undefined ? state.is_ai_mode : true;
    currentTemp = typeof state.current_temp === 'number' ? state.current_temp : null;
    currentHumidity = typeof state.current_humidity === 'number' ? state.current_humidity : null;
    currentWeight = typeof state.current_weight === 'number' ? state.current_weight : null;
    currentDryingRate = typeof state.current_drying_rate === 'number' ? state.current_drying_rate : null;
    heaterTemp = typeof state.heater_temp === 'number' ? state.heater_temp : null;

    heaterState = !!state.heater_state;
    fanState = !!state.fan_state;
    exhaustState = !!(state.exhaust_state || state.peltier_state);

    const isConnected = state.connection === 'ONLINE';
    if (systemStatusBadge) {
      systemStatusBadge.classList.toggle('online', isConnected);
      systemStatusBadge.classList.toggle('offline', !isConnected);
    }
    if (systemStatusText) {
      systemStatusText.textContent = isConnected ? 'ESP32 Connected (5s)' : 'ESP32 Offline / Menunggu...';
    }

    if (controlModeTag) {
      controlModeTag.className = 'control-mode-tag';
      controlModeTag.textContent = isAiMode ? 'AI Auto Control' : 'Manual Override';
      controlModeTag.style.background = isAiMode ? 'var(--purple-light)' : 'var(--amber-light)';
      controlModeTag.style.color = isAiMode ? 'var(--purple-ai)' : 'var(--amber-warning)';
    }

    if (btnToggleMode) {
      btnToggleMode.textContent = isAiMode ? 'Moda AI Adaptif' : 'Moda Kendali Manual';
    }

    updateActuatorUI();

    const hasSensorData = currentTemp !== null && currentHumidity !== null;

    if (hasSensorData) {
      if (valHumidity) valHumidity.innerHTML = `${currentHumidity.toFixed(1)} <span class="unit">%</span>`;

      // Render Bobot HX711 & Drying Rate
      if (valMoisture) {
        valMoisture.innerHTML = `${currentWeight !== null ? currentWeight.toFixed(2) : '--'} <span class="unit">kg</span>`;
      }
      if (valDryingRate) {
        valDryingRate.textContent = currentDryingRate !== null ? `Rate: ${currentDryingRate.toFixed(2)} g/m` : 'Rate: -- g/m';
      }

      drawTemperatureGauge('tempGaugeCanvas', currentTemp, 0, 60, true);

      // Push ke Telemetry Chart
      const timeNow = new Date().toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
      if (chartLabels.length >= maxDataPoints) {
        chartLabels.shift();
        tempDataHistory.shift();
        humidityDataHistory.shift();
      }
      chartLabels.push(timeNow);
      tempDataHistory.push(parseFloat(currentTemp.toFixed(1)));
      humidityDataHistory.push(parseFloat(currentHumidity.toFixed(1)));
      if (telemetryChart) telemetryChart.update();
    } else {
      if (valHumidity) valHumidity.innerHTML = '-- <span class="unit">%</span>';
      if (valMoisture) valMoisture.innerHTML = '-- <span class="unit">kg</span>';
      if (valDryingRate) valDryingRate.textContent = 'Rate: -- g/m';
      drawTemperatureGauge('tempGaugeCanvas', 0, 0, 60, false);
    }

    // AI Diagnosis update
    if (state.ai_diagnosis) {
      if (gaugeStatusTag) {
        const isOptimal = state.ai_diagnosis.status_class === 'OPTIMAL';
        const isStandby = state.ai_diagnosis.status_class === 'STANDBY';
        const isEmergency = state.ai_diagnosis.status_class === 'EMERGENCY';
        const badgeColor = isEmergency ? 'red' : (isStandby ? 'gray' : (isOptimal ? 'green' : 'amber'));
        gaugeStatusTag.className = `gauge-status-tag ${badgeColor}`;
        gaugeStatusTag.textContent = state.ai_diagnosis.status_title || 'Monitoring';
      }
      if (gaugeSubtext) {
        gaugeSubtext.textContent = state.ai_diagnosis.status_desc || '';
      }
    }

    // Donut Chart
    const actCount = (heaterState ? 1 : 0) + (fanState ? 1 : 0) + (exhaustState ? 1 : 0);
    if (donutValText) donutValText.textContent = actCount > 0 ? `${Math.round((actCount / 3) * 100)}%` : '0%';
    if (donutLblText) donutLblText.textContent = actCount > 0 ? 'Aktif' : 'Idle';

    if (actuatorDonutChart) {
      if (actCount > 0) {
        const hVal = heaterState ? 40 : 5;
        const fVal = fanState ? 35 : 5;
        const pVal = exhaustState ? 25 : 5;
        actuatorDonutChart.data.datasets[0].data = [hVal, fVal, pVal];
        actuatorDonutChart.data.datasets[0].backgroundColor = ['#e11d48', '#0284c7', '#7c3aed'];
      } else {
        actuatorDonutChart.data.datasets[0].data = [1];
        actuatorDonutChart.data.datasets[0].backgroundColor = ['#e2e8f0'];
      }
      actuatorDonutChart.update();
    }

    if (logs && Array.isArray(logs) && logs.length > 0) {
      renderLogsTable(logs);
    }
  }

  function renderLogsTable(logs) {
    if (!logTableBody) return;
    logTableBody.innerHTML = '';
    logs.forEach(item => {
      const tr = document.createElement('tr');
      const badgeClass = (item.status_class || 'OPTIMAL').toLowerCase();
      tr.innerHTML = `
        <td>${item.timestamp || '--:--:--'}</td>
        <td><strong>${item.source || 'ESP32_AI'}</strong></td>
        <td>${item.temp !== undefined ? Number(item.temp).toFixed(1) + '°C' : '-- °C'}</td>
        <td>${item.humidity !== undefined ? Number(item.humidity).toFixed(1) + '%' : '-- %'}</td>
        <td><span class="badge-tag ${badgeClass}">${item.status_class || 'INFO'}</span></td>
        <td>${item.action || '-'}</td>
      `;
      logTableBody.appendChild(tr);
    });
  }



  /**
   * Speedometer Gauge Renderer
   * @param {string} canvasId
   * @param {number} value
   * @param {number} minVal
   * @param {number} maxVal
   * @param {boolean} isPowered
   */
  function drawTemperatureGauge(canvasId, value, minVal = 0, maxVal = 60, isPowered = true) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;
    const cx = width / 2;
    const cy = height / 2 + 14;
    const radius = Math.min(width, height) / 2 - 18;

    ctx.clearRect(0, 0, width, height);

    const startAngle = 0.75 * Math.PI;
    const endAngle = 2.25 * Math.PI;
    const totalAngle = endAngle - startAngle;

    const segments = isPowered ? [
      { from: 0, to: 30, color: '#38bdf8' },     // Blue / Dingin (< 30°C)
      { from: 30, to: 45, color: '#22c55e' },    // Hijau (30 - 45°C Rentang Target Optimal Presisi)
      { from: 45, to: 55, color: '#f59e0b' },    // Kuning / Oranye (45 - 55°C Ambang Atas)
      { from: 55, to: 65, color: '#ef4444' }     // Merah (> 55°C s/d Cut-Off Proteksi 65°C)
    ] : [
      { from: 0, to: 65, color: '#e2e8f0' }      // Standby Neutral Track
    ];

    const lineWidth = 24;

    segments.forEach(seg => {
      const a1 = startAngle + ((seg.from - minVal) / (maxVal - minVal)) * totalAngle;
      const a2 = startAngle + ((seg.to - minVal) / (maxVal - minVal)) * totalAngle;

      ctx.beginPath();
      ctx.arc(cx, cy, radius, a1, a2, false);
      ctx.lineWidth = lineWidth;
      ctx.strokeStyle = seg.color;
      ctx.lineCap = 'butt';
      ctx.stroke();
    });

    ctx.beginPath();
    ctx.arc(cx, cy, radius - lineWidth / 2 - 2, 0, 2 * Math.PI);
    ctx.fillStyle = '#ffffff';
    ctx.fill();

    const clampedVal = Math.max(minVal, Math.min(maxVal, value));
    const valAngle = isPowered ? (startAngle + ((clampedVal - minVal) / (maxVal - minVal)) * totalAngle) : startAngle;
    const needleLen = radius - 22;

    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(valAngle);

    ctx.beginPath();
    ctx.moveTo(0, -5);
    ctx.lineTo(needleLen, 0);
    ctx.lineTo(0, 5);
    ctx.fillStyle = isPowered ? '#1e293b' : '#94a3b8';
    ctx.fill();

    ctx.beginPath();
    ctx.arc(0, 0, 7.5, 0, 2 * Math.PI);
    ctx.fillStyle = isPowered ? '#0f172a' : '#64748b';
    ctx.fill();
    ctx.restore();

    ctx.fillStyle = isPowered ? '#0f172a' : '#94a3b8';
    ctx.font = '800 28px Outfit, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(isPowered ? value.toFixed(1) : '--.-', cx, cy + radius - 18);

    ctx.fillStyle = '#64748b';
    ctx.font = '600 13px Inter, sans-serif';
    ctx.fillText('°C', cx, cy + radius + 2);

    ctx.fillStyle = '#94a3b8';
    ctx.font = '500 12px Inter, sans-serif';
    ctx.fillText(`${minVal}`, cx - radius + 8, cy + radius / 2 + 22);
    ctx.fillText(`${maxVal}`, cx + radius - 8, cy + radius / 2 + 22);
  }

  function evaluateAiModel(temp, rh) {
    let statusClass = 'OPTIMAL';
    let recHeater = true;
    let recFan = true;
    let recPeltier = true;
    let actionSummary = 'Mempertahankan kestabilan suhu & RH';

    if (rh > 45.0) {
      statusClass = 'DEHUMIDIFYING';
      recPeltier = true;
      recFan = true;
      recHeater = (temp < 40.0);
      actionSummary = 'Aktivasi Maksimal Dehumidifier & Fan';
    } else if (temp < 38.0) {
      statusClass = 'HEATING';
      recHeater = true;
      recFan = true;
      recPeltier = true;
      actionSummary = 'Boost Pemanas (Relay 1 ON)';
    } else if (temp > 43.0) {
      statusClass = 'HEATING';
      recHeater = false;
      recFan = true;
      recPeltier = true;
      actionSummary = 'Proteksi Suhu: Pemanas OFF';
    }

    return {
      statusClass: statusClass,
      recommendedHeater: recHeater,
      recommendedFan: recFan,
      recommendedPeltier: recPeltier,
      actionSummary: actionSummary
    };
  }

  function updateMetricsUI(remainingSeconds) {
    if (valHumidity) valHumidity.innerHTML = `${currentHumidity.toFixed(1)} <span class="unit">%</span>`;
    if (valMoisture) valMoisture.innerHTML = `${currentMoisture.toFixed(1)} <span class="unit">%</span>`;

    let hrs = Math.floor(remainingSeconds / 3600);
    let mins = Math.floor((remainingSeconds % 3600) / 60);
    let hrsStr = hrs < 10 ? '0' + hrs : hrs;
    let minsStr = mins < 10 ? '0' + mins : mins;

    if (valEstTimeDigits) valEstTimeDigits.textContent = `${hrsStr}:${minsStr}`;
  }

  function updateActuatorUI() {
    if (toggleHeater) {
      toggleHeater.checked = heaterState;
      toggleHeater.disabled = isAiMode;
    }
    if (toggleFan) {
      toggleFan.checked = fanState;
      toggleFan.disabled = isAiMode;
    }
    if (togglePeltier) {
      togglePeltier.checked = exhaustState;
      togglePeltier.disabled = isAiMode;
    }

    if (statusHeaterText) {
      statusHeaterText.textContent = heaterState ? 'AKTIF (300W)' : 'NON-AKTIF';
      statusHeaterText.className = `status-indicator ${heaterState ? 'active' : 'inactive'}`;
    }

    if (statusFanText) {
      statusFanText.textContent = fanState ? 'AKTIF (Sirkulasi)' : 'NON-AKTIF';
      statusFanText.className = `status-indicator ${fanState ? 'active' : 'inactive'}`;
    }

    if (statusPeltierText) {
      statusPeltierText.textContent = exhaustState ? 'AKTIF (Evakuasi)' : 'NON-AKTIF';
      statusPeltierText.className = `status-indicator ${exhaustState ? 'active' : 'inactive'}`;
    }

    // Dynamic Active Tools List Update
    const activeCount = (heaterState ? 1 : 0) + (fanState ? 1 : 0) + (exhaustState ? 1 : 0);

    if (valActuatorCount) valActuatorCount.textContent = `${activeCount} / 3 Aktif`;

    if (chipHeater) {
      chipHeater.textContent = heaterState ? '● AKTIF' : '○ OFF';
      chipHeater.className = `act-badge ${heaterState ? 'active' : 'inactive'}`;
    }

    if (chipFan) {
      chipFan.textContent = fanState ? '● AKTIF' : '○ OFF';
      chipFan.className = `act-badge ${fanState ? 'active' : 'inactive'}`;
    }

    if (chipPeltier) {
      chipPeltier.textContent = exhaustState ? '● AKTIF' : '○ OFF';
      chipPeltier.className = `act-badge ${exhaustState ? 'active' : 'inactive'}`;
    }
  }

  function toggleSystemMode() {
    sendControlUpdate({ is_ai_mode: !isAiMode });
  }

  function toggleBatchState() {
    isBatchRunning = !isBatchRunning;
    if (isBatchRunning) {
      if (btnBatchAction) btnBatchAction.textContent = 'Jeda Batch';
      addLogEntry('SYSTEM', 'Proses pengeringan dilanjutkan');
    } else {
      if (btnBatchAction) btnBatchAction.textContent = 'Lanjutkan Batch';
      addLogEntry('SYSTEM', 'Proses pengeringan dijeda oleh pengguna');
    }
  }

  function addLogEntry(source, actionMsg, aiClass = 'OPTIMAL') {
    const timeStr = new Date().toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit', second: '2-digit' });

    let badgeCss = 'optimal';
    if (aiClass === 'HEATING') badgeCss = 'heating';
    if (aiClass === 'DEHUMIDIFYING') badgeCss = 'dehumidifying';
    if (aiClass === 'STANDBY') badgeCss = 'standby';

    let actuatorStatusStr = `H:${heaterState ? 'ON' : 'OFF'} | F:${fanState ? 'ON' : 'OFF'} | P:${peltierState ? 'ON' : 'OFF'}`;

    const tempStr = currentTemp !== null ? `${currentTemp.toFixed(1)}°C` : '-- °C';
    const humStr = currentHumidity !== null ? `${currentHumidity.toFixed(1)}%` : '-- %';

    const rowHtml = `
      <td>${timeStr}</td>
      <td><strong>${source}</strong></td>
      <td>${tempStr}</td>
      <td>${humStr}</td>
      <td><span class="badge-tag ${badgeCss}">${aiClass}</span></td>
      <td>${actionMsg} (${actuatorStatusStr})</td>
    `;

    if (logTableBody) {
      const tr = document.createElement('tr');
      tr.innerHTML = rowHtml;
      logTableBody.insertBefore(tr, logTableBody.firstChild);
      if (logTableBody.children.length > 25) logTableBody.removeChild(logTableBody.lastChild);
    }
  }

  function exportDataCSV() {
    if (tempDataHistory.length === 0) return;

    let csvContent = "data:text/csv;charset=utf-8,Timestamp,Suhu_C,RH_Percent,KadarAir_Percent,Heater_State,Fan_State,Peltier_State\n";
    const now = new Date();

    for (let i = 0; i < tempDataHistory.length; i++) {
      let timeStr = chartLabels[i] || now.toLocaleTimeString();
      csvContent += `${timeStr},${tempDataHistory[i]},${humidityDataHistory[i]},${currentMoisture.toFixed(1)},${heaterState ? 1 : 0},${fanState ? 1 : 0},${peltierState ? 1 : 0}\n`;
    }

    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `syntera_nilam_telemetry_${Date.now()}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    addLogEntry('USER_ACTION', 'Mengekspor log telemetry dalam format CSV');
  }

  function initLineChart() {
    const ctx = document.getElementById('telemetryChart').getContext('2d');

    const gradientTemp = ctx.createLinearGradient(0, 0, 0, 290);
    gradientTemp.addColorStop(0, 'rgba(225, 29, 72, 0.15)');
    gradientTemp.addColorStop(1, 'rgba(225, 29, 72, 0.0)');

    const gradientHumidity = ctx.createLinearGradient(0, 0, 0, 290);
    gradientHumidity.addColorStop(0, 'rgba(2, 132, 199, 0.15)');
    gradientHumidity.addColorStop(1, 'rgba(2, 132, 199, 0.0)');

    telemetryChart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: chartLabels,
        datasets: [
          {
            label: 'Suhu (°C)',
            data: tempDataHistory,
            borderColor: '#e11d48',
            backgroundColor: gradientTemp,
            borderWidth: 2.5,
            fill: true,
            tension: 0.3,
            pointRadius: 3,
            yAxisID: 'yTemp'
          },
          {
            label: 'Kelembapan RH (%)',
            data: humidityDataHistory,
            borderColor: '#0284c7',
            backgroundColor: gradientHumidity,
            borderWidth: 2.5,
            fill: true,
            tension: 0.3,
            pointRadius: 3,
            yAxisID: 'yRH'
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: true,
            position: 'top',
            labels: { color: '#475569', font: { family: 'Inter', size: 12, weight: '600' }, usePointStyle: true }
          }
        },
        scales: {
          x: { grid: { color: 'rgba(0, 0, 0, 0.04)' }, ticks: { color: '#64748b', font: { size: 11 } } },
          yTemp: {
            type: 'linear', position: 'left', min: 20, max: 60,
            grid: { color: 'rgba(0, 0, 0, 0.04)' },
            ticks: { color: '#e11d48', font: { size: 11 } }
          },
          yRH: {
            type: 'linear', position: 'right', min: 10, max: 90,
            grid: { drawOnChartArea: false },
            ticks: { color: '#0284c7', font: { size: 11 } }
          }
        }
      }
    });
  }

  function initDonutChart() {
    const ctx = document.getElementById('actuatorDonutChart').getContext('2d');
    actuatorDonutChart = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: ['Air Heater 300W', 'Inline Duct Fan', 'Exhaust Fan'],
        datasets: [{
          data: [1], // Neutral standby ring
          backgroundColor: ['#e2e8f0'],
          borderWidth: 0,
          hoverOffset: 5
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '72%',
        plugins: {
          legend: { display: false }
        }
      }
    });
  }
});
