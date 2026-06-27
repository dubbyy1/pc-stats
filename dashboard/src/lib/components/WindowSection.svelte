<script>
    import Chart from 'chart.js/auto';
    import { onDestroy } from 'svelte';

    let {
        monitors = [],
        windows = [],
        windowSnapshots = []
    } = $props();

    const colors = [
        '#4493f8',
        '#ff3e00',
        '#f1e05a',
        '#178600'
    ];

    let rangeStart = $state(0);
    let rangeEnd = $state(1);
    let timelineEl = $state(null);
    let dragging = null;
    let pendingPointerX = 0;
    let dragFrame = null;

    let sortedSnapshots = $derived.by(() =>
        [...windowSnapshots].sort((a, b) => a.timestamp - b.timestamp)
    );

    let minTimestamp = $derived.by(() => {
        if (sortedSnapshots.length === 0) return 0;
        return sortedSnapshots[0].timestamp;
    });

    let maxTimestamp = $derived.by(() => {
        if (sortedSnapshots.length === 0) return 1;
        return sortedSnapshots[sortedSnapshots.length - 1].timestamp;
    });

    let startTimestamp = $derived(minTimestamp + rangeStart * (maxTimestamp - minTimestamp));
    let endTimestamp = $derived(minTimestamp + rangeEnd * (maxTimestamp - minTimestamp));

    let windowsBySnapshot = $derived.by(() => {
        const bySnapshot = {};

        for (const win of windows) {
            bySnapshot[win.ssid] ??= [];
            bySnapshot[win.ssid].push(win);
        }

        return bySnapshot;
    });

    function lowerBoundByTimestamp(snapshots, timestamp) {
        let low = 0;
        let high = snapshots.length;

        while (low < high) {
            const mid = Math.floor((low + high) / 2);
            if (snapshots[mid].timestamp < timestamp) low = mid + 1;
            else high = mid;
        }

        return low;
    }

    function upperBoundByTimestamp(snapshots, timestamp) {
        let low = 0;
        let high = snapshots.length;

        while (low < high) {
            const mid = Math.floor((low + high) / 2);
            if (snapshots[mid].timestamp <= timestamp) low = mid + 1;
            else high = mid;
        }

        return low;
    }

    let filteredSnapshots = $derived.by(() => {
        const start = lowerBoundByTimestamp(sortedSnapshots, startTimestamp);
        const end = upperBoundByTimestamp(sortedSnapshots, endTimestamp);
        return sortedSnapshots.slice(start, end);
    });



    $effect(() => {
        windowSnapshots;
        rangeStart = 0;
        rangeEnd = 1;
    });

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

        pendingPointerX = e.clientX;
        if (dragFrame) return;

        dragFrame = requestAnimationFrame(() => {
            dragFrame = null;
            if (!dragging || !timelineEl) return;

            const rect = timelineEl.getBoundingClientRect();
            const pos = Math.max(0, Math.min(1, (pendingPointerX - rect.left) / rect.width));

            if (dragging === 'start') rangeStart = Math.min(pos, rangeEnd - 0.005);
            else rangeEnd = Math.max(pos, rangeStart + 0.005);
        });
    }

    function stopDrag() {
        dragging = null;
        if (dragFrame) {
            cancelAnimationFrame(dragFrame);
            dragFrame = null;
        }
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
    }

    let windowStats = $derived.by(() => {
        const totalSnapshots = filteredSnapshots.length;
        const monitorArea = monitors.reduce((sum, monitor) => sum + monitor.width * monitor.height, 0);
        const totalMonitorSurface = monitorArea * totalSnapshots;

        const appSeen = {};
        const windowNameSeen = {};
        const focusCounts = {};
        const presentCounts = {};
        const focusedCounts = {};
        const areaByApp = {};
        const desktopCounts = {};
        const windowCounts = [];
        let totalWindowCount = 0;

        for (const snap of filteredSnapshots) {
            const snapshotWindows = windowsBySnapshot[snap.id] ?? [];
            const namesInSnapshot = {};

            desktopCounts[snap.current_desktop] = (desktopCounts[snap.current_desktop] ?? 0) + 1;
            windowCounts.push(snapshotWindows.length);
            totalWindowCount += snapshotWindows.length;

            if (snap.active) {
                appSeen[snap.active] = true;
                focusCounts[snap.active] = (focusCounts[snap.active] ?? 0) + 1;
                focusedCounts[snap.active] = (focusedCounts[snap.active] ?? 0) + 1;
            }

            for (const win of snapshotWindows) {
                if (!win.name) continue;

                appSeen[win.name] = true;
                windowNameSeen[win.name] = true;
                namesInSnapshot[win.name] = true;

                if (win.width > 0 && win.height > 0 && win.desktop === snap.current_desktop) {
                    areaByApp[win.name] = (areaByApp[win.name] ?? 0) + win.width * win.height;
                }
            }

            for (const name of Object.keys(namesInSnapshot)) {
                presentCounts[name] = (presentCounts[name] ?? 0) + 1;
            }
        }

        const appInfo = Object.keys(appSeen).map(name => {
            const frequency = totalSnapshots > 0 && presentCounts[name] !== undefined
                ? Math.round((presentCounts[name] / totalSnapshots) * 100_00) / 100
                : -1;
            const focus = totalSnapshots > 0 && focusCounts[name] !== undefined
                ? Math.round((focusCounts[name] / totalSnapshots) * 100_00) / 100
                : -1;
            const dominance = totalMonitorSurface > 0 && areaByApp[name] !== undefined
                ? Math.round((areaByApp[name] / totalMonitorSurface) * 100_00) / 100
                : -1;

            return { name, frequency, focus, dominance };
        });

        const avgWindowsInfo = totalSnapshots > 0
            ? {
                average: Math.round((totalWindowCount / totalSnapshots) * 10) / 10,
                max: Math.max(...windowCounts),
                min: Math.min(...windowCounts)
            }
            : { average: 0, max: 0, min: 0 };

        return {
            appInfo,
            windowNames: Object.keys(windowNameSeen),
            desktopCounts,
            appCounts: Object.fromEntries(Object.keys(appSeen).map(name => [name, {
                present: presentCounts[name] ?? 0,
                focused: focusedCounts[name] ?? 0
            }])),
            avgWindowsInfo
        };
    });

    let appInfo = $derived(windowStats.appInfo);
    let windowNames = $derived(windowStats.windowNames);
    let desktopCounts = $derived(windowStats.desktopCounts);
    let avgWindowsInfo = $derived(windowStats.avgWindowsInfo);

    function appSort(method, apps, filter = true) {
        let sorted = [...apps];

        if (method === 'frequency') {
            sorted = sorted.sort((a, b) => b.frequency - a.frequency);
            return sorted.filter(app => app.frequency !== -1 || !filter);
        }

        if (method === 'focus') {
            sorted = sorted.sort((a, b) => b.focus - a.focus);
            return sorted.filter(app => app.focus !== -1 || !filter);
        }

        if (method === 'dominance') {
            sorted = sorted.sort((a, b) => b.dominance - a.dominance);
            return sorted.filter(app => app.dominance !== -1 || !filter);
        }

        if (method === 'idle') {
            sorted = sorted.sort((a, b) => (a.focus / a.frequency) - (b.focus / b.frequency));
            return sorted.filter(app => (app.focus !== -1 && app.frequency > 0) || !filter);
        }

        return sorted;
    }

    let frequencyApps = $derived(appSort('frequency', appInfo));
    let focusApps = $derived(appSort('focus', appInfo));
    let dominantApp = $derived(appSort('dominance', appInfo)[0]);
    let idleApp = $derived(appSort('idle', appInfo)[0]);
    let idleAppCount = $derived(windowStats.appCounts[idleApp?.name] ?? { present: 0, focused: 0 });

    let desktopPie = $state(null);
    let desktopPieChart;

    $effect(() => {
        if (!desktopPie) return;

        const labels = Object.keys(desktopCounts);
        const data = Object.values(desktopCounts);

        if (desktopPieChart) {
            desktopPieChart.data.labels = labels;
            desktopPieChart.data.datasets[0].data = data;
            desktopPieChart.update('none');
        } else {
            desktopPieChart = new Chart(desktopPie, {
                type: 'doughnut',
                data: {
                    labels,
                    datasets: [{
                        data,
                        backgroundColor: colors,
                        borderWidth: 1,
                        borderColor: '#0D1117',
                        borderAlign: 'inner',
                        borderJoinStyle: 'round'
                    }]
                },
                options: {
                    animation: false,
                    cutout: '30%',
                    plugins: {
                        legend: {
                            display: false
                        }
                    }
                }
            });
        }
    });

    let focusScatter = $state(null);
    let focusScatterChart;

    $effect(() => {
        if (!focusScatter) return;

        const eligibleApps = appInfo.filter(app => windowNames.includes(app.name));
        const labels = eligibleApps.map(app => app.name);
        const dominanceValues = eligibleApps
            .map(app => app.dominance)
            .filter(value => Number.isFinite(value) && value > 0);
        const minDominance = dominanceValues.length > 0 ? Math.min(...dominanceValues) : 1;
        const maxDominance = dominanceValues.length > 0 ? Math.max(...dominanceValues) : 1;
        const dominanceRange = Math.log(maxDominance) - Math.log(minDominance);

        const data = eligibleApps.map(app => {
            const dominance = Math.max(app.dominance, minDominance);
            const radius = dominanceRange > 0
                ? 2 + ((Math.log(dominance) - Math.log(minDominance)) / dominanceRange) * 8
                : 5;

            return {
                x: Math.max(app.frequency, 0),
                y: Math.max(app.focus, 0),
                r: radius
            };
        });

        if (focusScatterChart) {
            focusScatterChart.data.labels = labels;
            focusScatterChart.data.datasets[0].data = data;
            focusScatterChart.update('none');
        } else {
            focusScatterChart = new Chart(focusScatter, {
                type: 'bubble',
                data: {
                    labels,
                    datasets: [{
                        data,
                        backgroundColor: colors[0]
                    }]
                },
                options: {
                    animation: false,
                    scales: {
                        x: {
                            min: 0,
                            max: 100,
                            title: {
                                display: true,
                                text: 'Frequency %'
                            }
                        },
                        y: {
                            min: 0,
                            max: 100,
                            title: {
                                display: true,
                                text: 'Focus %'
                            }
                        }
                    },
                    plugins: {
                        legend: {
                            display: false
                        }
                    }
                }
            });
        }
    });

    onDestroy(() => {
        desktopPieChart?.destroy();
        focusScatterChart?.destroy();
    });
</script>

<svelte:window
    onpointermove={onPointerMove}
    onpointerup={stopDrag}
/>

<div class="page-title">Windows</div>

<div class="timeline-card">
    Timline
    <div class="timeline" bind:this={timelineEl}>
        <div class="timeline-track"></div>
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
        <span>{filteredSnapshots.length.toLocaleString()} snapshots</span>
        <span>{formatDate(endTimestamp)}</span>
    </div>
</div>

<div class="row">
    <div class="info-box">
        <span>Most Dominant App</span>
        <span style="font-size: 2.2rem; font-weight: normal">{dominantApp?.name ?? 'No data'}</span>
        <span style="color: #8b949e; font-weight: normal">{dominantApp?.dominance ?? 0}% of monitor</span>
    </div>
    <div class="info-box">
        <span>Most Idle App</span>
        <span style="font-size: 2.2rem; font-weight: normal">{idleApp?.name ?? 'No data'}</span>
        <span style="color: #8b949e; font-weight: normal">{idleAppCount.present} snapshots, {idleAppCount.focused} focused</span>
    </div>
    <div class="info-box">
        <span>Average Open Windows</span>
        <span style="font-size: 2.2rem; font-weight: normal">{avgWindowsInfo.average}</span>
        <span style="color: #8b949e; font-weight: normal">{avgWindowsInfo.max} max, {avgWindowsInfo.min} min</span>
    </div>
</div>

<div class="row">
    <div class="info-box">
        <span style="margin-bottom: 1rem">App frequency</span>
        <div class="progress-container">
            <div class="progress-column">
                {#each frequencyApps as app (app.name)}
                    <span>{app.name}</span>
                {/each}
            </div>
            <div class="progress-column" style="flex: 1;">
                {#each frequencyApps as app (app.name)}
                    <div class="progress-bar-bg"><div class="progress-bar-fill" style="width: {app.frequency}%"></div></div>
                {/each}
            </div>
            <div class="progress-column">
                {#each frequencyApps as app (app.name)}
                    <span>{Math.floor(app.frequency)}%</span>
                {/each}
            </div>
        </div>
    </div>
    <div class="info-box">
        <span style="margin-bottom: 1rem">App Focus</span>
        <div class="progress-container">
            <div class="progress-column">
                {#each focusApps as app (app.name)}
                    <span>{app.name}</span>
                {/each}
            </div>
            <div class="progress-column" style="flex: 1;">
                {#each focusApps as app (app.name)}
                    <div class="progress-bar-bg"><div class="progress-bar-fill" style="width: {app.focus}%"></div></div>
                {/each}
            </div>
            <div class="progress-column">
                {#each focusApps as app (app.name)}
                    <span>{Math.floor(app.focus)}%</span>
                {/each}
            </div>
        </div>
    </div>
</div>

<div class="row">
    <div class="info-box">
        <span style="margin-bottom: 1rem">Usage <span style="color: #8b949e; font-weight: normal; font-style: italic;">— size = dominance</span></span>
        <canvas class="scatter" bind:this={focusScatter}></canvas>
    </div>
    <div class="pie-box">
        <span>Desktops</span>
        <div class="pie-wrapper">
            <canvas class="pie" bind:this={desktopPie}></canvas>
        </div>
    </div>
</div>

<style>
    .row {
        display: flex;
        gap: 1rem;
    }

    .page-title {
        font-size: 2rem;
        font-weight: bold;
        color: #ffffff;
        text-align: start;
        margin: 0.5rem 0;
    }

    .info-box,
    .timeline-card {
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

    .timeline-card {
        gap: 0.5rem;
    }

    .timeline {
        position: relative;
        height: 42px;
        user-select: none;
    }

    .timeline-track {
        position: absolute;
        inset: 0;
        background-color: #151B23;
        border-radius: 0.4rem;
        overflow: hidden;
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
    }

    .progress-container {
        display: flex;
        flex-direction: row;
        align-self: left;
        font-weight: normal;
        gap: 0.5rem;
    }

    .progress-column {
        display: flex;
        flex-direction: column;
        gap: 1rem;
    }

    .progress-bar-bg {
        flex: 1;
        height: 0.25rem;
        margin: 0.375rem;
        background-color: #3d444d;
        border-radius: 0.25rem;
    }

    .progress-bar-fill {
        max-width: 100%;
        height: 100%;
        background-color: #4493F8;
        border-radius: 0.25rem;
    }

    .pie-box {
        display: flex;
        flex-direction: column;
        align-self: left;
        gap: 0.5rem;
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
</style>
