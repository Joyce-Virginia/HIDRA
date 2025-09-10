class HidraDashboard {
    constructor(initialData) {
        this.updateInterval = 10000;
        this.chart = null; // Gráfico principal de tendência
        this.historicalChart = null; // Gráfico do modal
        this.map = null;
        this.initialData = initialData;
        this.modalInstance = null;

        this.init();
    }

    init() {
        document.addEventListener('DOMContentLoaded', () => {
            this.initMap();
            this.initTrendChart(); // Renomeado para maior clareza
            this.startAutoUpdate();
            this.bindEvents();
            this.animateCards();

            // Inicializa o modal do Bootstrap
            const modalEl = document.getElementById('historicalChartModal');
            if (modalEl) {
                this.modalInstance = new bootstrap.Modal(modalEl);
            }
        });
    }

    bindSensorCardClicks() {
        const sensorCards = document.querySelectorAll('.sensor-card');
        sensorCards.forEach(card => {
            card.addEventListener('click', () => {
                const sensorParam = card.dataset.sensorCard;
                const sensorName = card.dataset.sensorName;
                const sensorUnit = card.dataset.sensorUnit;
                if (sensorParam) {
                    this.openHistoricalChart(sensorParam, sensorName, sensorUnit);
                }
            });
        });
    }

    async openHistoricalChart(sensorParam, sensorName, sensorUnit) {
        if (!this.modalInstance) return;

        // Mostra o modal e o indicador de loading
        const modalTitle = document.getElementById('historicalChartModalLabel');
        const loadingIndicator = document.getElementById('chart-loading-indicator');
        const chartContainer = document.querySelector('#historicalChartModal .chart-container');
        
        modalTitle.textContent = `Histórico de ${sensorName}`;
        loadingIndicator.style.display = 'block';
        chartContainer.style.display = 'none';
        this.modalInstance.show();

        try {
            // Faz a chamada à nova API
            const response = await fetch(`/api/historical_data/${sensorParam}/`);
            const result = await response.json();

            if (result.success) {
                this.renderHistoricalChart(result.labels, result.data, sensorName, sensorUnit);
                loadingIndicator.style.display = 'none';
                chartContainer.style.display = 'block';
            } else {
                loadingIndicator.innerHTML = `<p class="text-danger">Erro ao carregar dados: ${result.error || 'Tente novamente.'}</p>`;
            }
        } catch (error) {
            console.error('Fetch error for historical data:', error);
            loadingIndicator.innerHTML = '<p class="text-danger">Erro de conexão ao buscar o histórico.</p>';
        }
    }

    renderHistoricalChart(labels, data, sensorName, sensorUnit) {
        const ctx = document.getElementById('historicalChart').getContext('2d');

        // Destrói o gráfico anterior, se existir
        if (this.historicalChart) {
            this.historicalChart.destroy();
        }

        this.historicalChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: `${sensorName} (${sensorUnit})`,
                    data: data,
                    borderColor: '#007bff',
                    backgroundColor: 'rgba(0, 123, 255, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.1,
                    pointRadius: 3,
                    pointBackgroundColor: '#007bff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        title: { display: true, text: 'Horário da Leitura' }
                    },
                    y: {
                        title: { display: true, text: `Valor (${sensorUnit})` },
                        beginAtZero: false
                    }
                },
                plugins: {
                    tooltip: {
                        mode: 'index',
                        intersect: false
                    }
                }
            }
        });
    }

    initMap() {
        this.map = L.map('map').setView([-8.294582306335398, -35.03037438742963], 20);

        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors'
        }).addTo(this.map);

        const sensorMarker = L.marker([-8.294582306335398, -35.03037438742963]).addTo(this.map);
        sensorMarker.bindPopup(`
            <div class="sensor-popup">
                <h5><b>Sensor de Qualidade da Água</b></h5>
                <p><strong>Localização:</strong> Canal da Cohab</p>
                <p><strong>Status:</strong> <span class="status-online">Ativo</span></p>
                <p><strong>Última atualização:</strong> <span id="map-popup-time">${new Date().toLocaleTimeString('pt-BR')}</span></p>
            </div>
        `).openPopup();
    }

    initTrendChart() {
        const ctx = document.getElementById('trendChart').getContext('2d');
        const labels = ['-50s', '-40s', '-30s', '-20s', '-10s', 'Agora'];

        this.chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Temperatura (°C)',
                    data: [this.initialData.temperatura, this.initialData.temperatura, this.initialData.temperatura, this.initialData.temperatura, this.initialData.temperatura, this.initialData.temperatura],
                    borderColor: '#ff6384',
                    backgroundColor: 'rgba(255, 99, 132, 0.2)',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.4,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: false,
                        ticks: { color: '#666' },
                        title: { display: true, text: 'Valores', color: '#333' }
                    },
                    x: {
                        ticks: { color: '#666' },
                        title: { display: true, text: 'Tempo', color: '#333' }
                    }
                }
            }
        });
    }

    updateTrendChart(parameter) {
        // Esta função pode ser expandida para buscar dados históricos
        // Por agora, ela apenas troca o tipo de dado exibido como antes
        const chartConfigs = {
            temperature: { label: 'Temperatura (°C)', color: '#ff6384', data: this.chart.data.datasets[0].data.map(() => this.initialData.temperatura) },
            ph: { label: 'pH', color: '#36a2eb', data: this.chart.data.datasets[0].data.map(() => this.initialData.ph) },
            oxygen: { label: 'Oxigênio (mg/L)', color: '#4bc0c0', data: this.chart.data.datasets[0].data.map(() => this.initialData.oxigenio) },
            turbidity: { label: 'Turbidez (NTU)', color: '#9966ff', data: this.chart.data.datasets[0].data.map(() => this.initialData.turbidez) }
        };

        const config = chartConfigs[parameter];
        if (config) {
            const dataset = this.chart.data.datasets[0];
            dataset.label = config.label;
            dataset.borderColor = config.color;
            dataset.backgroundColor = config.color + '20';
            // dataset.data = config.data; // Idealmente, buscaria dados históricos aqui
            this.chart.update();
        }

        document.querySelectorAll('.chart-btn').forEach(btn => btn.classList.remove('active'));
        document.querySelector(`.chart-btn[onclick*="'${parameter}'"]`).classList.add('active');
    }

    async updateDashboardData() {
        try {
            const response = await fetch('/dashboard_api/');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();

            if (data.success) {
                this.updateSensorCards(data.sensor_data);
                this.updateStatusCards(data.iqa, data.flood_risk);
                this.updatePhotoCard(data.latest_image_url);
                this.updateLastUpdateTime(data.timestamp);
                this.updateMapPopup();
                console.log('Dashboard data updated successfully.');
            } else {
                console.error('API Error:', data.error);
            }
        } catch (error) {
            console.error('Failed to fetch dashboard data:', error);
        }
    }
    
    
    updateSensorCards(sensorData) {
        Object.keys(sensorData).forEach(key => {
            const valueElement = document.querySelector(`[data-sensor-value="${key.toLowerCase()}"]`);
            
            // Verifica se o elemento HTML existe
            if (valueElement) {
                // --- CORREÇÃO FINAL ---
                // Agora, sensorData[key] é apenas o número (ex: 25.5), não mais um objeto.
                // Esta linha agora funciona corretamente.
                const value = sensorData[key];

                // Garante que o valor é um número antes de formatar
                if (typeof value === 'number') {
                    valueElement.textContent = this.formatSensorValue(key, value);
                    
                    const cardElement = document.querySelector(`[data-sensor-card="${key.toLowerCase()}"]`);
                    this.updateSensorAlert(cardElement, key, value);
                }
            }
        });
    }

    updateSensorAlert(cardElement, sensor, value) {
        if (!cardElement) return;

        cardElement.classList.remove('alert', 'danger');
        const limits = {
            temperatura: { warning: 30, critical: 35 },
            ph: { warning_low: 6.5, warning_high: 8.5, critical_low: 6, critical_high: 9 },
            oxigenio: { warning: 6, critical: 4 },
            dbo: { warning: 5, critical: 10 },
            coliformes: { warning: 100, critical: 1000 },
            nitrogenio: { warning: 2.18, critical: 3.7 },
            fosforo: { warning: 0.1, critical: 0.15 },
            turbidez: { warning: 40, critical: 100 },
            solidos: { warning: 300, critical: 500 }
        };

        const limit = limits[sensor.toLowerCase()];
        if (!limit) return;
        
        let alertClass = '';
        if (sensor.toLowerCase() === 'ph') {
            if (value < limit.critical_low || value > limit.critical_high) alertClass = 'danger';
            else if (value < limit.warning_low || value > limit.warning_high) alertClass = 'alert';
        } else if (sensor.toLowerCase() === 'oxigenio') {
            if (value < limit.critical) alertClass = 'danger';
            else if (value < limit.warning) alertClass = 'alert';
        } else {
            if (limit.critical && value > limit.critical) alertClass = 'danger';
            else if (limit.warning && value > limit.warning) alertClass = 'alert';
        }

        if (alertClass) cardElement.classList.add(alertClass);
    }

    updateStatusCards(iqaData, floodData) {
        // Update IQA Card
        const iqaValueEl = document.querySelector('[data-iqa="value"]');
        const iqaClassEl = document.querySelector('[data-iqa="classification"]');
        const qualityCard = document.getElementById('quality-status-card');

        if(iqaValueEl) iqaValueEl.textContent = iqaData.valor;
        if(iqaClassEl) iqaClassEl.textContent = iqaData.classificacao;
        if(qualityCard) {
            const indicator = qualityCard.querySelector('.status-indicator');
            if(indicator) indicator.className = `status-indicator ${iqaData.css_class}`;
        }

        // Update Flood Risk Card
        const floodRiskEl = document.querySelector('[data-flood-risk="level"]');
        const floodCard = document.getElementById('flood-status-card');
        if (floodRiskEl) {
             floodRiskEl.innerHTML = `
                <span class="status-indicator ${floodData.css_class}"></span>
                ${floodData.level}
            `;
        }
    }

    updateLastUpdateTime(timestamp) {
        const timeElement = document.getElementById('last-update-time');
        if (timeElement) {
            timeElement.textContent = new Date(timestamp).toLocaleString('pt-BR');
        }
    }
    
    updateMapPopup() {
        const timeElement = document.getElementById('map-popup-time');
        if (timeElement) {
            timeElement.textContent = new Date().toLocaleTimeString('pt-BR');
        }
    }

    formatSensorValue(sensor, value) {
        const key = sensor.toLowerCase();
        const formats = {
            default: (val) => val.toFixed(1),
            coliformes: (val) => Math.round(val),
            nitrogenio: (val) => val.toFixed(2),
            fosforo: (val) => val.toFixed(3),
            solidos: (val) => Math.round(val),
        };
        return (formats[key] || formats.default)(value);
    }
    
    startAutoUpdate() {
        // Primeira atualização imediata
        this.updateDashboardData();
        
        // Atualizações periódicas
        setInterval(() => {
            this.updateDashboardData();
        }, this.updateInterval);
    }
    
    animateCards() {
        const cards = document.querySelectorAll('.card, .sensor-card');
        cards.forEach((card, index) => {
            card.style.opacity = '0';
            card.style.transform = 'translateY(20px)';
            setTimeout(() => {
                card.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
                card.style.opacity = '1';
                card.style.transform = 'translateY(0)';
            }, index * 50);
        });
    }

    bindEvents() {
        // Bind para os botões do gráfico de tendência
        document.querySelectorAll('.chart-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const parameter = e.target.getAttribute('onclick').match(/'([^']+)'/)[1];
                this.updateTrendChart(parameter);
            });
        });

        // Bind para os cards de sensores
        this.bindSensorCardClicks();
    }
}

// Inicializar o dashboard
const hidraDashboard = new HidraDashboard(initialSensorData);

// Função global para compatibilidade com o `onclick` do template
function updateChart(parameter) {
    hidraDashboard.updateTrendChart(parameter);
}