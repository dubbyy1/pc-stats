<script>
    import Chart from 'chart.js/auto';
    import { onDestroy, tick } from 'svelte';
	import { SvelteSet } from 'svelte/reactivity';

    let {
        allClicks = [],
        monitors = [],
        screenW = 0,
        screenH = 0
    } = $props();

    let heatmapCanvas = $state(null);

    let rangeStart = $state(0);
    let rangeEnd = $state(1);
    let selectedButtons = $state({
        LEFT: true,
        RIGHT: true,
        MIDDLE: true
    });

    let timelineEl = $state(null);
    let dragging = null; // 'start' | 'end' | null
    let timelineWidth = $state(0);
    let BUCKETS = $derived(Math.floor((timelineWidth * 0.75) / 5));

    let buttonPie = $state(null);
    let buttonChart;
    let monitorPie = $state(null);
    let monitorChart;
    let hourChartEl = $state(null);
    let hourChart;
    let dayChartEl = $state(null);
    let dayChart;

    const colors = [
        '#4493f8',
        '#ff3e00',
        '#f1e05a'
    ];

    const buttonTypes = [
        { key: 'LEFT', label: 'Left Click' },
        { key: 'RIGHT', label: 'Right Click' },
        { key: 'MIDDLE', label: 'Middle Click' }
    ];

    let minTimestamp = $derived.by(() => {
        if (allClicks.length === 0) return 0;
        return allClicks.reduce((m, c) => Math.min(m, c.timestamp), Infinity);
    });

    let maxTimestamp = $derived.by(() => {
        if (allClicks.length === 0) return 1;
        return allClicks.reduce((m, c) => Math.max(m, c.timestamp), -Infinity);
    });

    let startTimestamp = $derived(minTimestamp + rangeStart * (maxTimestamp - minTimestamp));
    let endTimestamp = $derived(minTimestamp + rangeEnd * (maxTimestamp - minTimestamp));

    let buttonFilteredClicks = $derived(
        allClicks.filter(c => selectedButtons[c.button])
    );

    let timeFilteredClicks = $derived(
        allClicks.filter(c => c.timestamp >= startTimestamp && c.timestamp <= endTimestamp)
    );

    let filteredClicks = $derived(
        timeFilteredClicks.filter(c => selectedButtons[c.button])
    );

    let buttonCounts = $derived(new Map([
        ['LEFT', filteredClicks.filter(c => c.button === 'LEFT').length],
        ['RIGHT', filteredClicks.filter(c => c.button === 'RIGHT').length],
        ['MIDDLE', filteredClicks.filter(c => c.button === 'MIDDLE').length]
    ]));

    let densityData = $derived.by(() => {
        const counts = new Array(BUCKETS).fill(0);

        if (BUCKETS <= 0 || buttonFilteredClicks.length === 0 || maxTimestamp === minTimestamp) {
            return { buckets: counts, max: 0 };
        }

        const range = maxTimestamp - minTimestamp;
        for (const { timestamp } of buttonFilteredClicks) {
            const i = Math.min(BUCKETS - 1, Math.floor(((timestamp - minTimestamp) / range) * BUCKETS));
            counts[i]++;
        }

        const max = Math.max(...counts);
        return {
            buckets: max > 0 ? counts.map(c => (c / max) * 100) : counts,
            max
        };
    });

    let densityBuckets = $derived(densityData.buckets);
    let bucketMax = $derived(densityData.max);

    $effect(() => {
        allClicks;
        rangeStart = 0;
        rangeEnd = 1;
    });

    $effect(() => {
        if (timelineEl) {
            tick().then(() => {
                if (timelineEl) timelineWidth = timelineEl.getBoundingClientRect().width;
            });
        }
    });

    $effect(() => {
        if (heatmapCanvas && screenW > 0 && screenH > 0) drawClicks();
    });

    $effect(() => {
        if (buttonPie && monitorPie && hourChartEl && dayChartEl) {
            drawButtonPie();
            drawMonitorPie();
            drawHourChart();
            drawDayChart();
        }
    });

    onDestroy(() => {
        buttonChart?.destroy();
        monitorChart?.destroy();
        hourChart?.destroy();
        dayChart?.destroy();
    });

    function toggleButtonFilter(button) {
        selectedButtons[button] = !selectedButtons[button];
    }

    function formatDate(ts) {
        if (!ts) return '';
        return new Date(ts * 1000).toLocaleString(undefined, {
            month: 'short',
            day: 'numeric',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    }

    function startDragHandle(e, handle) {
        dragging = handle;
        document.body.style.cursor = 'ew-resize';
        document.body.style.userSelect = 'none';
        e.preventDefault();
    }

    function onPointerMove(e) {
        if (!dragging || !timelineEl) return;
        const rect = timelineEl.getBoundingClientRect();
        const pos = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
        if (dragging === 'start') rangeStart = Math.min(pos, rangeEnd - 0.005);
        else rangeEnd = Math.max(pos, rangeStart + 0.005);
    }

    function stopDrag() {
        dragging = null;
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
    }

    let clickInfo = $derived.by(() => {
        let uniqueDates = new SvelteSet();
        let uniqueHours = new SvelteSet();

        for (const {timestamp} of allClicks) {
            let time = new Date(timestamp * 1000);
            uniqueDates.add(time.toDateString());
            uniqueHours.add(time.toDateString() + " " + time.getHours());
        }

        return {
            clicksPerDay: Math.round(allClicks.length / uniqueDates.size),
            clicksPerHour: Math.round(allClicks.length / uniqueHours.size),
            daysCounted: uniqueDates.size,
            hoursCounted: uniqueHours.size
        };
    })

    function drawButtonPie() {
        if (buttonChart) buttonChart.destroy();
        buttonChart = new Chart(buttonPie, {
            type: 'doughnut',
            data: {
                labels: ['Left', 'Right', 'Middle'],
                datasets: [{
                    data: [
                        buttonCounts.get('LEFT'),
                        buttonCounts.get('RIGHT'),
                        buttonCounts.get('MIDDLE')
                    ],
                    backgroundColor: colors,
                    borderWidth: 1,
                    borderColor: '#0D1117',
                    borderAlign: 'inner',
                    borderJoinStyle: 'round'
                }]
            },
            options: {
                cutout: '30%',
                plugins: {
                    legend: {
                        display: false
                    }
                }
            }
        });
    }

    function drawMonitorPie() {
        if (monitorChart) monitorChart.destroy();
        monitorChart = new Chart(monitorPie, {
            type: 'doughnut',
            data: {
                labels: monitors.map(m => m.name),
                datasets: [{
                    data: monitors.map(m =>
                        filteredClicks.filter(c =>
                            c.x >= m.x && c.x < m.x + m.width
                        ).length
                    ),
                    backgroundColor: colors,
                    borderWidth: 1,
                    borderColor: '#0D1117',
                    borderAlign: 'inner',
                    borderJoinStyle: 'round'
                }]
            },
            options: {
                cutout: '30%',
                plugins: {
                    legend: {
                        display: false
                    }
                }
            }
        });
    }

    function getClicksHourly() {
        const hours = Array.from({ length: 24 }, () => 0);

        for (const { timestamp } of filteredClicks) {
            const hour = new Date(Math.round(timestamp * 1000)).getHours();
            hours[hour]++;
        }

        return hours;
    }

    function drawHourChart() {
        if (hourChart) hourChart.destroy();
        hourChart = new Chart(hourChartEl, {
            type: 'bar',
            data: {
                labels: Array.from({ length: 24 }, (_x, i) => i.toString().padStart(2, '0') + ':00'),
                datasets: [{
                    data: getClicksHourly(),
                    backgroundColor: '#4493f8',
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    }
                }
            }
        });
    }

    function getClicksDaily() {
        const days = Array.from({ length: 7 }, () => 0);

        for (const { timestamp } of filteredClicks) {
            const day = (new Date(Math.round(timestamp * 1000)).getDay() + 1) % 7;
            days[day]++;
        }

        return days;
    }

    function drawDayChart() {
        if (dayChart) dayChart.destroy();
        dayChart = new Chart(dayChartEl, {
            type: 'bar',
            data: {
                labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
                datasets: [{
                    data: getClicksDaily(),
                    backgroundColor: '#4493f8',
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    }
                }
            }
        });
    }

    function drawMonitors() {
        const rem = parseFloat(getComputedStyle(document.documentElement).fontSize);
        const scale = screenW / heatmapCanvas.getBoundingClientRect().width;
        const ctx = heatmapCanvas.getContext('2d');
        ctx.fillStyle = '#151B23';
        ctx.strokeStyle = '#3d444d';
        ctx.lineWidth = 5;

        for (const { x, y, width, height } of monitors) {
            ctx.beginPath();
            ctx.roundRect(x, y, width, height, 0.5 * rem * scale);
            ctx.fill();
            ctx.stroke();
            ctx.closePath();
        }
    }

    function drawClicks() {
        const ctx = heatmapCanvas.getContext('2d');
        ctx.clearRect(0, 0, heatmapCanvas.width, heatmapCanvas.height);
        drawMonitors();

        const buttons = new Map([
            ['LEFT', colors[0] + '1a'],
            ['RIGHT', colors[1] + '33'],
            ['MIDDLE', colors[2] + '33']
        ]);

        for (const { x, y, button } of filteredClicks) {
            ctx.fillStyle = buttons.get(button);
            ctx.beginPath();
            ctx.arc(x, y, 10, 0, 2 * Math.PI);
            ctx.fill();
            ctx.closePath();
        }
    }
</script>

<svelte:window
    onpointermove={onPointerMove}
    onpointerup={stopDrag}
    onresize={() => {
        if (timelineEl) timelineWidth = timelineEl.getBoundingClientRect().width;
    }}
/>

<div class="page-title">Mouse</div>

<div class="click-filter" aria-label="Click filters">
    {#each buttonTypes as button, i (button.key)}
        <button
            class:active={selectedButtons[button.key]}
            type="button"
            aria-pressed={selectedButtons[button.key]}
            onclick={() => toggleButtonFilter(button.key)}
        >
            <span class="key-color" style="background-color: {colors[i]}"></span>
            {button.label}
        </button>
    {/each}
</div>

<div class="heatmap">
    <div class="heatmap-header">
        <span style="flex: 1;">Heatmap</span>
        <span class="click-count">{buttonCounts.get('LEFT').toLocaleString()} left clicks</span>
        <span class="click-count">{buttonCounts.get('RIGHT').toLocaleString()} right clicks</span>
        <span class="click-count">{buttonCounts.get('MIDDLE').toLocaleString()} middle clicks</span>
        <span class="click-count" style="margin-left: 2rem;">{filteredClicks.length.toLocaleString()} clicks</span>
    </div>

    <div class="timeline" bind:this={timelineEl}>
        <div class="timeline-track">
            {#each densityBuckets as h, i (i)}
                <div class="density-bar" title="{Math.round((h / 100) * bucketMax)}" style="height: {Math.max(h, 3)}%"></div>
            {/each}
        </div>

        <div class="timeline-dim" style="left: 0; width: {rangeStart * 100}%"></div>
        <div class="timeline-dim" style="left: {rangeEnd * 100}%; right: 0"></div>

        <div
            class="timeline-handle"
            role="slider"
            tabindex="0"
            aria-label="Start time"
            aria-valuemin="0"
            aria-valuemax="100"
            aria-valuenow={Math.round(rangeStart * 100)}
            style="left: {rangeStart * 100}%"
            onpointerdown={e => startDragHandle(e, 'start')}
        ></div>
        <div
            class="timeline-handle"
            role="slider"
            tabindex="0"
            aria-label="End time"
            aria-valuemin="0"
            aria-valuemax="100"
            aria-valuenow={Math.round(rangeEnd * 100)}
            style="left: {rangeEnd * 100}%"
            onpointerdown={e => startDragHandle(e, 'end')}
        ></div>
    </div>

    <div class="timeline-labels">
        <span>{formatDate(startTimestamp)}</span>
        <span>{formatDate(endTimestamp)}</span>
    </div>

    <div class="canvas-container">
        <canvas class="heatmap-canvas" style="aspect-ratio: {screenW} / {screenH};" width={screenW} height={screenH} bind:this={heatmapCanvas}></canvas>
    </div>
</div>

<div class="row">
    <div class="info-box">
        <span>Clicks Per Day</span>
        <span style="font-size: 2.2rem; font-weight: normal">{clickInfo.clicksPerDay}</span>
        <span style="color: #8b949e; font-weight: normal">{clickInfo.daysCounted} active days</span>
    </div>
    <div class="info-box">
        <span>Clicks Per Hour</span>
        <span style="font-size: 2.2rem; font-weight: normal">{clickInfo.clicksPerHour}</span>
        <span style="color: #8b949e; font-weight: normal">{clickInfo.hoursCounted} active hours</span>
    </div>
</div>

<div class="row">
    <div class="pie-container">
        <span>Buttons</span>
        <div class="pie-wrapper">
            <canvas class="pie" bind:this={buttonPie}></canvas>
        </div>
    </div>

    <div class="pie-container">
        <span>Monitors</span>
        <canvas class="pie" bind:this={monitorPie}></canvas>

        {#each monitors as m (m.id)}
            <div class="key-item">
                <div class="key-color" style="background-color: {colors[m.id % colors.length]}"></div>
                <div>{m.name}</div>
            </div>
        {/each}
    </div>

    <div class="hours-container">
        <span>Hourly Activity</span>
        <div class="bar-container">
            <canvas class="bar-chart" bind:this={hourChartEl}></canvas>
        </div>
    </div>
</div>

<div class="days-container">
    <span>Daily Activity</span>
    <div class="bar-container">
        <canvas class="bar-chart" bind:this={dayChartEl}></canvas>
    </div>
</div>

<style>
    .page-title {
        font-size: 2rem;
        font-weight: bold;
        color: #ffffff;
        text-align: start;
        margin: 0.5rem 0;
    }

    .click-count {
        font-size: 0.8rem;
        font-weight: normal;
        color: #8b949e;
    }

    .click-filter {
        display: flex;
        flex-direction: row;
        align-items: center;
        gap: 0.5rem;
    }

    .click-filter button {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.45rem 0.7rem;
        border: 1px solid #3d444d;
        border-radius: 0.4rem;
        background-color: #151B23;
        color: #8b949e;
        font: inherit;
        font-size: 0.8rem;
        cursor: pointer;
    }

    .click-filter button.active {
        background-color: #1E242A;
        color: #ffffff;
        border-color: #4493f8;
    }

    .key-item {
        display: flex;
        flex-direction: row;
        align-items: center;
        gap: 0.5rem;
    }

    .key-color {
        width: 1rem;
        height: 1rem;
        border-radius: 0.2rem;
    }

    .heatmap {
        display: flex;
        flex-direction: column;
        align-self: center;
        width: calc(100% - 2rem - 2px);
        padding: 0.75rem 1rem 1rem 1rem;
        border: 1px solid #3d444d;
        border-radius: 0.5rem;
        font-size: 0.9rem;
        font-weight: bold;
        color: #fff;
    }

    .heatmap-header {
        display: flex;
        flex-direction: row;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 0.5rem;
        gap: 1rem;
    }

    .timeline {
        position: relative;
        height: 52px;
        user-select: none;
    }

    .timeline-track {
        position: absolute;
        inset: 0;
        background-color: #151B23;
        border-radius: 0.4rem;
        overflow: hidden;
        display: flex;
        align-items: flex-end;
        gap: 1px;
        padding: 4px 2px 0;
    }

    .density-bar {
        flex: 1;
        background-color: #4493f855;
        border-radius: 1px 1px 0 0;
    }

    .timeline-dim {
        position: absolute;
        top: 0;
        bottom: 0;
        background-color: rgba(0, 0, 0, 0.6);
        pointer-events: none;
        border-radius: 0.4rem;
    }

    .timeline-handle {
        position: absolute;
        top: -3px;
        bottom: -3px;
        width: 0.2rem;
        background-color: #4493f8;
        border-radius: 3px;
        transform: translateX(-50%);
        cursor: ew-resize;
        z-index: 10;
    }

    .timeline-handle::before {
        content: '';
        position: absolute;
        inset: 0 -2px;
    }

    .timeline-labels {
        display: flex;
        justify-content: space-between;
        font-size: 0.75rem;
        font-weight: normal;
        color: #8b949e;
        margin-top: 0.3rem;
        margin-bottom: 0.5rem;
    }

    .canvas-container {
        margin-top: 0.5rem;
    }

    .heatmap-canvas {
        position: relative;
        max-width: 100%;
        max-height: 100%;
    }

    .row {
        display: flex;
        gap: 1rem;
    }

    .pie-container {
        display: flex;
        flex-direction: column;
        align-self: left;
        gap: 0.5rem;
        flex: 1;
        padding: 0.75rem 1rem 1rem 1rem;
        border: 1px solid #3d444d;
        border-radius: 0.5rem;
        font-size: 0.9rem;
        font-weight: bold;
        color: #fff;
    }

    .pie-wrapper {
        flex: 1;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        gap: 1rem;
    }

    .pie {
        margin-top: 0.5rem;
    }

    .bar-container {
        flex: 1;
    }

    .hours-container {
        display: flex;
        flex-direction: column;
        align-self: left;
        gap: 1rem;
        flex: 3;
        width: 20%;
        padding: 0.75rem 1rem 1rem 1rem;
        border: 1px solid #3d444d;
        border-radius: 0.5rem;
        font-size: 0.9rem;
        font-weight: bold;
        color: #fff;
    }

    .days-container {
        display: flex;
        flex-direction: column;
        align-self: left;
        gap: 0.5rem;
        flex: 1;
        padding: 0.75rem 1rem 1rem 1rem;
        border: 1px solid #3d444d;
        border-radius: 0.5rem;
        font-size: 0.9rem;
        font-weight: bold;
        color: #fff;
    }

    .info-box {
        display: flex;
        flex-direction: column;
        align-self: left;
        flex: 1;
        padding: 0.75rem 1rem 1rem 1rem;
        border: 1px solid #3d444d;
        border-radius: 0.5rem;
        font-size: 0.9rem;
        font-weight: bold;
        color: #fff;
    }
</style>
