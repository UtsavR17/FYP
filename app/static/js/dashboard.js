/* =============================================================================
   dashboard.js - Admin dashboard charts and interactions (Task 34)
   Loaded only on /dashboard, after Chart.js 4.x and admin.js.
   ============================================================================= */

(function () {
    'use strict';

    // Fallback colours. The live values are read from the .dash CSS custom
    // properties in admin.css, which mirror the .appt-status-* badge colours.
    var FALLBACK_SERIES = {
        moto:  '#e67e22',
        parts: '#1d4ed8'
    };
    var FALLBACK_STATUS = {
        'Pending':     '#b45309',
        'Confirmed':   '#1d4ed8',
        'In Progress': '#c05621',
        'Completed':   '#15803d',
        'Cancelled':   '#b91c1c',
        'No Show':     '#4b5563'
    };

    // -------------------------------------------------------------------------
    // Helpers
    // -------------------------------------------------------------------------
    function cssVar(el, name, fallback) {
        var value = getComputedStyle(el).getPropertyValue(name).trim();
        return value || fallback;
    }

    function slug(text) {
        return String(text).toLowerCase().replace(/\s+/g, '-');
    }

    function hexToRgba(hex, alpha) {
        var h = hex.replace('#', '');
        if (h.length === 3) {
            h = h.split('').map(function (c) { return c + c; }).join('');
        }
        var n = parseInt(h, 16);
        return 'rgba(' + ((n >> 16) & 255) + ', ' + ((n >> 8) & 255) + ', ' + (n & 255) + ', ' + alpha + ')';
    }

    function formatMUR(value) {
        return 'MUR ' + Number(value || 0).toLocaleString('en-US', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
    }

    function formatCompact(value) {
        var abs = Math.abs(value);
        var units = [[1e6, 'M'], [1e3, 'k']];
        for (var i = 0; i < units.length; i++) {
            if (abs >= units[i][0]) {
                return String(+(value / units[i][0]).toFixed(1)) + units[i][1];
            }
        }
        return String(value);
    }

    // -------------------------------------------------------------------------
    // Clickable table rows: the first-cell <a> is the real, keyboard-focusable
    // link; clicking anywhere else on the row follows it.
    // -------------------------------------------------------------------------
    function initRowLinks() {
        document.querySelectorAll('.dash-row-link').forEach(function (row) {
            row.addEventListener('click', function (event) {
                if (event.target.closest('a, button')) return;
                var anchor = row.querySelector('.dash-row-anchor');
                if (!anchor) return;
                if (event.ctrlKey || event.metaKey) {
                    window.open(anchor.href, '_blank');
                } else {
                    window.location.href = anchor.href;
                }
            });
        });
    }

    // -------------------------------------------------------------------------
    // Module overview collapse: swap the toggle label.
    // -------------------------------------------------------------------------
    function initModuleToggle() {
        var panel = document.getElementById('dashModules');
        var toggle = document.getElementById('dashModulesToggle');
        if (!panel || !toggle) return;
        var label = toggle.querySelector('.dash-modules-toggle-label');

        panel.addEventListener('shown.bs.collapse', function () {
            if (label) label.textContent = 'Hide modules';
        });
        panel.addEventListener('hidden.bs.collapse', function () {
            if (label) label.textContent = 'View all modules';
        });
    }

    // -------------------------------------------------------------------------
    // Chart.js plugins
    // -------------------------------------------------------------------------

    // Vertical dashed line at the hovered month.
    function crosshairPlugin(color) {
        return {
            id: 'dashCrosshair',
            beforeDatasetsDraw: function (chart) {
                var active = chart.tooltip && chart.tooltip.getActiveElements();
                if (!active || !active.length) return;
                var x = active[0].element.x;
                var area = chart.chartArea;
                var ctx = chart.ctx;
                ctx.save();
                ctx.beginPath();
                ctx.setLineDash([4, 4]);
                ctx.moveTo(x, area.top);
                ctx.lineTo(x, area.bottom);
                ctx.lineWidth = 1;
                ctx.strokeStyle = color;
                ctx.stroke();
                ctx.restore();
            }
        };
    }

    // Total and caption drawn in the middle of the donut.
    function centerTextPlugin(total, fontFamily, textColor, mutedColor) {
        return {
            id: 'dashCenterText',
            afterDraw: function (chart) {
                var meta = chart.getDatasetMeta(0);
                if (!meta || !meta.data || !meta.data.length) return;
                var x = meta.data[0].x;
                var y = meta.data[0].y;
                var ctx = chart.ctx;
                ctx.save();
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillStyle = textColor;
                ctx.font = '700 28px ' + fontFamily;
                ctx.fillText(String(total), x, y - 8);
                ctx.fillStyle = mutedColor;
                ctx.font = '400 11px ' + fontFamily;
                ctx.fillText(total === 1 ? 'appointment' : 'appointments', x, y + 16);
                ctx.restore();
            }
        };
    }

    // -------------------------------------------------------------------------
    // Line chart: motorcycle sales vs parts sales
    // -------------------------------------------------------------------------
    function initSalesChart(data, theme) {
        var canvas = document.getElementById('dashSalesChart');
        if (!canvas) return;

        var series = [
            { label: 'Motorcycle sales', values: data.motorcycle, color: theme.moto },
            { label: 'Parts sales',      values: data.parts,      color: theme.parts }
        ];

        var allZero = series.every(function (s) {
            return s.values.every(function (v) { return !v; });
        });
        if (allZero) {
            var note = document.getElementById('dashSalesEmpty');
            if (note) note.hidden = false;
        }

        function gradient(color) {
            return function (context) {
                var chart = context.chart;
                var area = chart.chartArea;
                if (!area) return 'transparent';
                var g = chart.ctx.createLinearGradient(0, area.top, 0, area.bottom);
                g.addColorStop(0, hexToRgba(color, 0.22));
                g.addColorStop(1, hexToRgba(color, 0));
                return g;
            };
        }

        new Chart(canvas, {
            type: 'line',
            data: {
                labels: data.months,
                datasets: series.map(function (s) {
                    return {
                        label: s.label,
                        data: s.values,
                        borderColor: s.color,
                        backgroundColor: gradient(s.color),
                        fill: 'origin',
                        tension: 0.35,
                        borderWidth: 2,
                        pointRadius: 0,
                        pointHoverRadius: 5,
                        pointHoverBorderWidth: 2,
                        pointBackgroundColor: s.color,
                        pointHoverBackgroundColor: s.color,
                        pointHoverBorderColor: theme.cardBg
                    };
                })
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: 'index', intersect: false },
                layout: { padding: { top: 6 } },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: theme.textPrimary,
                        titleColor: '#ffffff',
                        bodyColor: '#ffffff',
                        titleFont: { family: theme.font, weight: '600', size: 12 },
                        bodyFont: { family: theme.font, size: 12 },
                        padding: 10,
                        cornerRadius: 8,
                        usePointStyle: true,
                        boxWidth: 8,
                        boxHeight: 8,
                        boxPadding: 4,
                        callbacks: {
                            label: function (ctx) {
                                return ctx.dataset.label + ': ' + formatMUR(ctx.parsed.y);
                            },
                            labelColor: function (ctx) {
                                var c = ctx.dataset.borderColor;
                                return { borderColor: c, backgroundColor: c };
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: { display: false },
                        border: { display: false },
                        ticks: {
                            color: theme.textMuted,
                            font: { family: theme.font, size: 11 }
                        }
                    },
                    y: {
                        beginAtZero: true,
                        suggestedMax: allZero ? 100000 : undefined,
                        border: { display: false },
                        grid: { color: theme.border, drawTicks: false },
                        ticks: {
                            color: theme.textMuted,
                            font: { family: theme.font, size: 11 },
                            padding: 8,
                            maxTicksLimit: 6,
                            callback: function (value) { return formatCompact(value); }
                        }
                    }
                }
            },
            plugins: [crosshairPlugin(theme.textMuted)]
        });
    }

    // -------------------------------------------------------------------------
    // Donut chart: appointments by status
    // -------------------------------------------------------------------------
    function initStatusChart(data, theme) {
        var canvas = document.getElementById('dashStatusChart');
        if (!canvas) return;

        var total = data.statusCounts.reduce(function (a, b) { return a + b; }, 0);

        // Zero-count statuses stay in the HTML legend but are not drawn.
        var labels = [];
        var values = [];
        var colors = [];
        data.statuses.forEach(function (status, i) {
            if (data.statusCounts[i] > 0) {
                labels.push(status);
                values.push(data.statusCounts[i]);
                colors.push(theme.status[status]);
            }
        });

        var dataset = total > 0
            ? {
                data: values,
                backgroundColor: colors,
                borderColor: theme.cardBg,
                // A lone slice needs no gap; a border would leave a seam at the top.
                borderWidth: values.length > 1 ? 3 : 0,
                borderRadius: values.length > 1 ? 4 : 0,
                hoverOffset: 4
            }
            : {
                // Empty state: one light grey ring.
                data: [1],
                backgroundColor: [theme.border],
                borderWidth: 0
            };

        new Chart(canvas, {
            type: 'doughnut',
            data: {
                labels: total > 0 ? labels : ['No appointments'],
                datasets: [dataset]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '70%',
                layout: { padding: 4 },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        enabled: total > 0,
                        backgroundColor: theme.textPrimary,
                        bodyFont: { family: theme.font, size: 12 },
                        padding: 10,
                        cornerRadius: 8,
                        usePointStyle: true,
                        boxWidth: 8,
                        boxHeight: 8,
                        boxPadding: 4,
                        callbacks: {
                            label: function (ctx) {
                                var pct = total ? (ctx.parsed / total) * 100 : 0;
                                return ctx.label + ': ' + ctx.parsed + ' (' + pct.toFixed(1) + '%)';
                            }
                        }
                    }
                }
            },
            plugins: [centerTextPlugin(total, theme.font, theme.textPrimary, theme.textMuted)]
        });
    }

    // -------------------------------------------------------------------------
    // Boot
    // -------------------------------------------------------------------------
    document.addEventListener('DOMContentLoaded', function () {
        initRowLinks();
        initModuleToggle();

        var dataEl = document.getElementById('dash-data');
        var root = document.querySelector('.dash');
        if (!dataEl || !root) return;

        if (typeof Chart === 'undefined') {
            console.warn('[MotoAdmin] Chart.js not loaded; dashboard charts skipped.');
            return;
        }

        var data;
        try {
            data = JSON.parse(dataEl.dataset.chart);
        } catch (e) {
            console.warn('[MotoAdmin] Could not parse dashboard chart data.', e);
            return;
        }

        var status = {};
        Object.keys(FALLBACK_STATUS).forEach(function (name) {
            status[name] = cssVar(root, '--dash-status-' + slug(name), FALLBACK_STATUS[name]);
        });

        var theme = {
            moto:        cssVar(root, '--dash-series-moto', FALLBACK_SERIES.moto),
            parts:       cssVar(root, '--dash-series-parts', FALLBACK_SERIES.parts),
            status:      status,
            cardBg:      cssVar(root, '--card-bg', '#ffffff'),
            border:      cssVar(root, '--border-color', '#e5e7eb'),
            textPrimary: cssVar(root, '--text-primary', '#1a2332'),
            textMuted:   cssVar(root, '--text-muted', '#9ca3af'),
            font:        cssVar(root, '--font-family', 'Inter, sans-serif')
        };

        Chart.defaults.font.family = theme.font;
        if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
            Chart.defaults.animation = false;
        }

        initSalesChart(data, theme);
        initStatusChart(data, theme);
    });
})();
