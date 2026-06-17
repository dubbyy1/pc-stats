<script>
    import initSqlJs from 'sql.js';
    import Chart from 'chart.js/auto'
    import { tick } from 'svelte';
    import { page } from '$app/state';

    let fileInput;
    let importTextButton;
    let importIconButton;
    let sectionButtonMouse;
    let fileName = $state("");

    let SCREEN_W = $state(0);
    let SCREEN_H = $state(0);

    let heatmapCanvas;

    let monitors = $state([]);

    let allClicks = $state([]);

    let minTimestamp = $state(0);
    let maxTimestamp = $state(1);
    let rangeStart = $state(0); // 0–1 normalised
    let rangeEnd   = $state(1);
    let selectedButtons = $state({
        LEFT: true,
        RIGHT: true,
        MIDDLE: true
    });

    let timelineEl = $state(null);
    let dragging = null; // 'start' | 'end' | null

    let timelineWidth = $state(0);
    let BUCKETS = $derived(Math.floor((timelineWidth * 0.75) / 5));

    const buttonTypes = [
        { key: "LEFT", label: "Left Click" },
        { key: "RIGHT", label: "Right Click" },
        { key: "MIDDLE", label: "Middle Click" }
    ];

    let buttonFilteredClicks = $derived(
        allClicks.filter(c => selectedButtons[c.button])
    );

    let densityData = $derived.by(() => {
        const counts = new Array(BUCKETS).fill(0);

        if (BUCKETS <= 0 || buttonFilteredClicks.length === 0 || maxTimestamp === minTimestamp) {
            return { buckets: counts, max: 0 };
        }

        const range = maxTimestamp - minTimestamp;
        for (const { timestamp } of buttonFilteredClicks) {
            const i = Math.min(BUCKETS - 1, Math.floor((timestamp - minTimestamp) / range * BUCKETS));
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

    let startTimestamp = $derived(minTimestamp + rangeStart * (maxTimestamp - minTimestamp));
    let endTimestamp   = $derived(minTimestamp + rangeEnd   * (maxTimestamp - minTimestamp));

    let timeFilteredClicks = $derived(
        allClicks.filter(c => c.timestamp >= startTimestamp && c.timestamp <= endTimestamp)
    );

    let filteredClicks = $derived(
        timeFilteredClicks.filter(c => selectedButtons[c.button])
    );

    $effect(() => {
        if (heatmapCanvas && SCREEN_W > 0) drawClicks();
    });
    let buttonCounts = $derived(new Map([
        ["LEFT", filteredClicks.filter(c => c.button === "LEFT").length],
        ["RIGHT", filteredClicks.filter(c => c.button === "RIGHT").length],
        ["MIDDLE", filteredClicks.filter(c => c.button === "MIDDLE").length]
    ]));
    $effect(() => {
        if (buttonPie && monitorPie && hourChartEl && dayChartEl) {
            drawButtonPie()
            drawMonitorPie()
            drawHourChart()
            drawDayChart()
        }
    });

    const colors = [
        "#4493f8",
        "#ff3e00",
        "#f1e05a"
    ]

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
        else                      rangeEnd   = Math.max(pos, rangeStart + 0.005);
    }

    function stopDrag() {
        dragging = null;
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
    }

    $effect(() => {
	const dbUrl = page.url.searchParams.get('db');

	if (dbUrl) {
		loadDbFromUrl(dbUrl);
	}
    });

    async function loadDbFromUrl(dbUrl) {
     	fileName = dbUrl.split('/').pop() ?? 'remote.db';
     	importTextButton.style.display = 'none';
        importIconButton.style.display = 'inline';

     	const SQL = await initSqlJs({ locateFile: () => '/sql-wasm.wasm' });
     	const response = await fetch(dbUrl);

     	if (!response.ok) {
      		throw new Error(`Failed to load DB: ${response.status}`);
     	}

     	const buf = await response.arrayBuffer();
     	const db = new SQL.Database(new Uint8Array(buf));

     	parseFile(db);
    }


    $effect(() => {
	loadCachedDbOnStartup();
    });

    const DB_CACHE_NAME = 'pc-stats-cache';
    const DB_STORE_NAME = 'files';
    const DB_KEY = 'latest-db';

    let loadedCache = false;

    function openCacheDb() {
     	return new Promise((resolve, reject) => {
      		const request = indexedDB.open(DB_CACHE_NAME, 1);

      		request.onupgradeneeded = () => {
     			request.result.createObjectStore(DB_STORE_NAME);
      		};

      		request.onsuccess = () => resolve(request.result);
      		request.onerror = () => reject(request.error);
     	});
    }

    async function loadDbFromCache() {
     	const cacheDb = await openCacheDb();

     	return new Promise((resolve, reject) => {
      		const tx = cacheDb.transaction(DB_STORE_NAME, 'readonly');
      		const request = tx.objectStore(DB_STORE_NAME).get(DB_KEY);

      		request.onsuccess = () => resolve(request.result);
      		request.onerror = () => reject(request.error);
     	});
    }

    async function loadCachedDbOnStartup() {
     	if (loadedCache) return;
     	loadedCache = true;

     	const buf = await loadDbFromCache();

     	if (!buf) return;

     	fileName = 'cache';
     	importTextButton.style.display = 'none';
     	importIconButton.style.display = 'inline';

     	const SQL = await initSqlJs({ locateFile: () => '/sql-wasm.wasm' });
     	const db = new SQL.Database(new Uint8Array(buf));

     	parseFile(db);
    }

    async function saveDbToCache(buffer) {
     	const cacheDb = await openCacheDb();

     	return new Promise((resolve, reject) => {
      		const tx = cacheDb.transaction(DB_STORE_NAME, 'readwrite');
      		tx.objectStore(DB_STORE_NAME).put(buffer, DB_KEY);
      		tx.oncomplete = resolve;
      		tx.onerror = () => reject(tx.error);
     	});
    }

    async function chooseFile(event) {
        const file = event.target.files[0];
        fileName = file.name;
        importTextButton.style.display = 'none';
        importIconButton.style.display = 'inline';

        const SQL = await initSqlJs({ locateFile: () => '/sql-wasm.wasm' });
        const buf = await file.arrayBuffer();

        await saveDbToCache(buf);

        const db = new SQL.Database(new Uint8Array(buf));
        parseFile(db);
    }

    async function parseFile(db) {
        const monitors_result = db.exec("SELECT id, name, x, y, width, height FROM monitors");
        const [{ columns: monitors_columns, values: monitors_values }] = monitors_result;

        monitors = monitors_values.map(row =>
            Object.fromEntries(monitors_columns.map((col, i) => [col, row[i]]))
        );

        SCREEN_H = 0;
        SCREEN_W = 0;
        for (const monitor of monitors) {
            SCREEN_W += monitor.width;
            SCREEN_H = Math.max(SCREEN_H, monitor.height);
        }

        const clicks_result = db.exec("SELECT id, timestamp, x, y, button FROM clicks");
        const [{ columns: clicks_columns, values: clicks_values }] = clicks_result;

        const clicks = clicks_values.map(row =>
            Object.fromEntries(clicks_columns.map((col, i) => [col, row[i]]))
        );

        if (clicks.length > 0) {
            minTimestamp = clicks.reduce((m, c) => Math.min(m, c.timestamp), Infinity);
            maxTimestamp = clicks.reduce((m, c) => Math.max(m, c.timestamp), -Infinity);
        }

        rangeStart = 0;
        rangeEnd   = 1;

        await tick();
        allClicks = clicks;
        timelineWidth = timelineEl.getBoundingClientRect().width;
    }

    let buttonPie;
    let buttonChart;
    let monitorPie;
    let monitorChart;
    let hourChartEl;
    let hourChart;
    let dayChartEl;
    let dayChart;

    function drawButtonPie() {
        if (buttonChart) buttonChart.destroy();
        buttonChart = new Chart(buttonPie, {
            type: "doughnut",
            data: {
                labels: ["Left", "Right", "Middle"],
                datasets: [{
                    data: [
                        buttonCounts.get("LEFT"),
                        buttonCounts.get("RIGHT"),
                        buttonCounts.get("MIDDLE")
                    ],

                    backgroundColor: ["#4493f8", "#ff3e00", "#f1e05a"],
                    borderWidth: 1,
                    borderColor: "#0D1117",
                    borderAlign: "inner",
                    borderJoinStyle: "round",
                }],
            },
            options: {
                cutout: "30%",
                plugins: {
            		legend: {
           			display: false
              		}
               	}
            }
        })
    }

    function drawMonitorPie() {
        if (monitorChart) monitorChart.destroy();
        monitorChart = new Chart(monitorPie, {
            type: "doughnut",
            data: {
                labels: monitors.map(m => m.name),
                datasets: [{
                    data: monitors.map(m =>
                        filteredClicks.filter(c =>
                            (c.x >= m.x) && c.x < (m.x + m.width)
                        ).length
                    ),

                    backgroundColor: ["#4493f8", "#ff3e00", "#f1e05a"],
                    borderWidth: 1,
                    borderColor: "#0D1117",
                    borderAlign: "inner",
                    borderJoinStyle: "round",
                }],
            },
            options: {
                cutout: "30%",
                plugins: {
            		legend: {
           			display: false
              		}
               	}
            }
        })
    }

    function getClicksHourly() {
        var hours = Array.from({length: 24}, () => 0);

        for (const {timestamp} of filteredClicks) {
            const hour = new Date(Math.round(timestamp * 1000)).getHours();
            hours[hour]++;
        }
        console.log(hours);
        return hours;
    }
    function drawHourChart() {
        if (hourChart) hourChart.destroy()
        hourChart = new Chart(hourChartEl, {
            type: "bar",
            data: {
                labels: Array.from({length: 24}, (x, i) => i.toString().padStart(2, "0") + ":00"),
                datasets: [{
                    data: getClicksHourly(),

                    backgroundColor: "#4493f8",
                    borderWidth: 0,
                    // borderColor: "#fff",
                    // borderAlign: "inner",
                    // borderJoinStyle: "round",
                }]
            },
            options: {
                cutout: "30%",
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
            		legend: {
           			display: false
              		}
               	}
            }
        })
        // hourChart.resize(
        //   hourChartEl.getBoundingClientRect().width,
        //   hourChartEl.getBoundingClientRect().height
        // )
    }

    function getClicksDaily() {
        var days = Array.from({length: 7}, () => 0);

        for (const {timestamp} of filteredClicks) {
            const day = (new Date(Math.round(timestamp * 1000)).getDay() + 1) % 7;
            days[day]++;
        }
        console.log(days);
        return days;
    }
    function drawDayChart() {
        if (dayChart) dayChart.destroy()
        dayChart = new Chart(dayChartEl, {
            type: "bar",
            data: {
                labels: [
                  "Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"
                ],
                datasets: [{
                    data: getClicksDaily(),

                    backgroundColor: "#4493f8",
                    borderWidth: 0,
                    // borderColor: "#fff",
                    // borderAlign: "inner",
                    // borderJoinStyle: "round",
                }]
            },
            options: {
                cutout: "30%",
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
            		legend: {
           			display: false
              		}
               	}
            }
        })
        // hourChart.resize(
        //   hourChartEl.getBoundingClientRect().width,
        //   hourChartEl.getBoundingClientRect().height
        // )
    }

    function drawMonitors() {
        const rem = parseFloat(getComputedStyle(document.documentElement).fontSize);
        const scale = SCREEN_W / heatmapCanvas.getBoundingClientRect().width;
        const ctx = heatmapCanvas.getContext('2d');
        ctx.fillStyle = "#151B23";
        ctx.strokeStyle = "#3d444d";
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
            ['LEFT',   colors[0] + '1a'],
            ['RIGHT',  colors[1] + '33'],
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

<main class="container">
    <div class="sidebar">
        <div class="import-data">
            <input style="display: none;" aria-hidden="true" type="file" accept=".db" onchange={chooseFile} bind:this={fileInput}/>
            <button class="import-button" bind:this={importTextButton} onclick={() => fileInput.click()}>Import Data</button>
            <span>{ fileName }</span>
            <button class="upload-button" style="display: none;" bind:this={importIconButton} onclick={() => fileInput.click()} aria-label="Upload">
                <svg xmlns="http://www.w3.org/2000/svg" height="1.1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12"/><path d="m17 8-5-5-5 5"/><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/></svg>
            </button>
        </div>
        <div class="sections">
            <button class="section-button" bind:this={sectionButtonMouse} onclick={() => sectionButtonMouse.classList.add('active')}>
                <svg xmlns="http://www.w3.org/2000/svg" width="1.2em" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="2" width="14" height="20" rx="7"/><path d="M12 6v4"/></svg>
                Mouse
            </button>
        </div>
    </div>

    <div class="content">
        <div class="inner">
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
                    <span class="click-count">{buttonCounts.get("LEFT").toLocaleString()} left clicks</span>
                    <span class="click-count">{buttonCounts.get("RIGHT").toLocaleString()} right clicks</span>
                    <span class="click-count">{buttonCounts.get("MIDDLE").toLocaleString()} middle clicks</span>
                    <span class="click-count" style="margin-left: 2rem;">{filteredClicks.length.toLocaleString()} clicks</span>
                </div>

                <!-- Timeline scrubber -->
                <div class="timeline" bind:this={timelineEl}>
                    <!-- density histogram -->
                    <div class="timeline-track">
                        {#each densityBuckets as h, i (i)}
                            <div class="density-bar" title="{Math.round((h / 100) * bucketMax)}" style="height: {Math.max(h, 3)}%"></div>
                        {/each}
                    </div>

                    <!-- dim unselected regions -->
                    <div class="timeline-dim" style="left: 0; width: {rangeStart * 100}%"></div>
                    <div class="timeline-dim" style="left: {rangeEnd * 100}%; right: 0"></div>

                    <!-- handles -->
                    <div class="timeline-handle"
                        style="left: {rangeStart * 100}%"
                        onpointerdown={e => startDragHandle(e, 'start')}>
                    </div>
                    <div class="timeline-handle"
                        style="left: {rangeEnd * 100}%"
                        onpointerdown={e => startDragHandle(e, 'end')}>
                    </div>
                </div>

                <div class="timeline-labels">
                    <span>{formatDate(startTimestamp)}</span>
                    <span>{formatDate(endTimestamp)}</span>
                </div>

                <div class="canvas-container">
                    <canvas class= "heatmap-canvas" style="aspect-ratio: {SCREEN_W} / {SCREEN_H};" width={SCREEN_W} height={SCREEN_H} bind:this={heatmapCanvas}></canvas>
                </div>
            </div>
            <div style="display: flex; gap: 1rem;">
                <div class="pie-container">
                    <span>Buttons</span>
                    <div style="flex: 1; display: flex; flex-direction: column; justify-content: center; align-items: center; gap: 1rem;">
                        <canvas class="pie" bind:this={buttonPie}></canvas>
                    </div>
                </div>

                <div class="pie-container">
                    <span>Monitors</span>
                    <canvas class="pie" bind:this={monitorPie}></canvas>

                    {#each monitors as m (m.id)}
                        <div class="key-item">
                            <div class="key-color" style="background-color: {colors[m.id]}"></div>
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

        </div>
    </div>
</main>

<style>
    main {
        background-color: #0D1117;
        color: #ffffff;
        font-family: sans-serif;
        display: flex;
        flex-direction: row;
        width: 100vw;
        height: 100vh;
        overflow: hidden;
    }

    .sidebar {
        display: flex;
        flex-direction: column;
        background-color: #010409;
        height: 100%;
        width: 18rem;
        overflow: hidden;
    }

    .content {
        flex: 1;
        display: flex;
        flex-direction: column;
        align-items: center;
    }

    .inner {
        display: flex;
        flex-direction: column;
        margin: 1rem 2rem;
        width: 78rem;
        gap: 1rem;
        overflow-y: scroll;
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

    /* ── Timeline ── */

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

    /* wider invisible hit area */
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

    /* ── Canvas ── */

    .canvas-container {
        margin-top: 0.5rem;
    }

    .heatmap-canvas {
        position: relative;
        max-width: 100%;
        max-height: 100%;
    }

    /* ── Sidebar ── */

    .import-data {
        display: flex;
        flex-direction: row;
        justify-content: start;
        font-weight: bold;
        align-items: center;
        gap: 0.4em;
        padding: 1rem;
    }

    .import-button {
        cursor: pointer;
        color: #4493f8;
        font-family: sans-serif;
        font-size: 1rem;
        font-weight: bold;
        border: 0px;
        border-radius: 2em;
        background-color: #010409;
        transition: 0.1s;
    }
    .import-button:hover {
        text-decoration: underline;
    }

    .upload-button {
        cursor: pointer;
        margin-top: 0.35em;
        border: 0px;
        background-color: #010409;
        color: #4493f8;
    }

    .sections {
        display: flex;
        flex-direction: column;
        padding: 0.5rem 0.5rem;
    }

    .section-button {
        display: flex;
        flex-direction: row;
        align-items: center;
        gap: 0.6em;
        background-color: #010409;
        font-size: 1rem;
        color: #ffffff;
        padding: 0.5em;
        border-radius: 0.5em;
        border: 0px;
        cursor: pointer;
        transition: 0s;
        text-align: start;
    }
    .section-button:hover {
        background-color: #13181E;
        transition: 0.1s;
    }
    .section-button.active {
        background-color: #1E242A;
    }

    .page-title {
        font-size: 2rem;
        font-weight: bold;
        color: #ffffff;
        text-align: start;
        margin: 0.5rem 0;
    }

    .pie-container {
        display: flex;
        flex-direction: column;
        align-self: left;
        gap: 0.5rem;
        flex: 1;
        /*width: 20%;*/
        padding: 0.75rem 1rem 1rem 1rem;
        border: 1px solid #3d444d;
        border-radius: 0.5rem;
        font-size: 0.9rem;
        font-weight: bold;
        color: #fff;
    }

    .pie {
        margin-top: 0.5rem;
        /*aspect-ratio: 1;*/
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
</style>
