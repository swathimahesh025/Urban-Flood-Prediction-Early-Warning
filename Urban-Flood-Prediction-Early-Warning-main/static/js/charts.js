/**
 * Urban Flood Prediction and Early Warning System
 * Chart.js Analytics for Admin Dashboard
 */

document.addEventListener("DOMContentLoaded", async () => {
    const distCanvas = document.getElementById("riskDistributionChart");
    const trendsCanvas = document.getElementById("predictionTrendsChart");

    if (!distCanvas && !trendsCanvas) return;

    try {
        const response = await fetch("/api/admin/chart-data");
        const data = await response.json();

        // 1. Risk Distribution Doughnut Chart
        if (distCanvas && data.distribution) {
            new Chart(distCanvas, {
                type: "doughnut",
                data: {
                    labels: data.distribution.labels,
                    datasets: [{
                        data: data.distribution.data,
                        backgroundColor: data.distribution.colors,
                        borderColor: "#1e293b",
                        borderWidth: 2,
                        hoverOffset: 6
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: "bottom",
                            labels: {
                                color: "#cbd5e1",
                                font: { family: "Inter", size: 12, weight: "bold" },
                                padding: 16
                            }
                        },
                        tooltip: {
                            backgroundColor: "#0f172a",
                            titleColor: "#f8fafc",
                            bodyColor: "#cbd5e1",
                            padding: 10,
                            borderColor: "rgba(255,255,255,0.1)",
                            borderWidth: 1
                        }
                    },
                    cutout: "68%"
                }
            });
        }

        // 2. Daily Prediction Volume & Rainfall Bar/Line Chart
        if (trendsCanvas && data.trends) {
            new Chart(trendsCanvas, {
                type: "bar",
                data: {
                    labels: data.trends.labels,
                    datasets: [
                        {
                            label: "Assessments Count",
                            data: data.trends.counts,
                            backgroundColor: "rgba(2, 132, 199, 0.75)",
                            borderColor: "#0284c7",
                            borderWidth: 1,
                            borderRadius: 6,
                            yAxisID: "y"
                        },
                        {
                            label: "Avg Rainfall (mm)",
                            data: data.trends.rainfall,
                            type: "line",
                            borderColor: "#38bdf8",
                            backgroundColor: "rgba(56, 189, 248, 0.2)",
                            borderWidth: 2.5,
                            pointBackgroundColor: "#38bdf8",
                            pointRadius: 4,
                            yAxisID: "y1"
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: "top",
                            labels: { color: "#cbd5e1", font: { family: "Inter" } }
                        }
                    },
                    scales: {
                        x: {
                            grid: { color: "rgba(255,255,255,0.05)" },
                            ticks: { color: "#94a3b8" }
                        },
                        y: {
                            type: "linear",
                            position: "left",
                            grid: { color: "rgba(255,255,255,0.05)" },
                            ticks: { color: "#94a3b8", stepSize: 1 },
                            title: { display: true, text: "Assessments", color: "#94a3b8" }
                        },
                        y1: {
                            type: "linear",
                            position: "right",
                            grid: { drawOnChartArea: false },
                            ticks: { color: "#38bdf8" },
                            title: { display: true, text: "Rainfall (mm)", color: "#38bdf8" }
                        }
                    }
                }
            });
        }
    } catch (e) {
        console.error("Failed to load admin analytics chart data:", e);
    }
});
