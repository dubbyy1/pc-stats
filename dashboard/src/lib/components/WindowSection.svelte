<script>
    import Chart from 'chart.js/auto';
    let {
        monitors = [],
        windows = [],
        windowSnapshots = [],
    } = $props();

    const colors = [
        '#4493f8',
        '#ff3e00',
        '#f1e05a',
        '#178600'
    ];

    let appNames = $derived.by(() => {
        let res = new Set();
        for (const name of windowSnapshots.map(snap => snap.active)) {
            res.add(name)
        }
        for (const name of windows.map(win => win.name)) {
            res.add(name)
        }
        res = Array.from(res)
        return res
    })
    let windowNames = $derived.by(() => {
        let res = new Set();
        for (const name of windows.map(win => win.name)) {
            res.add(name)
        }
        res = Array.from(res)
        return res
    })

    let frequencyInfo = $derived.by(() => {
        let res = {};
        for (const window of windows) {
            if (res[window.name]) {
                if (!res[window.name].includes(window.ssid)) {
                    res[window.name].push(window.ssid);
                }
            } else {
                res[window.name] = [window.ssid];
            }
        }
        res = Object.entries(res).map(entry => {
            return [entry[0], Math.round((entry[1].length / windowSnapshots.length) * 100_00) / 100];
        })
        res = res.sort(([, a], [, b]) => {
            return b - a;
        });
        res = new Map(res)
        console.log(res)
        return res;
    });
    let focusInfo = $derived.by(() => {
        let res = {};
        for (const snap of windowSnapshots) {
            if (res[snap.active]) {
                res[snap.active] += 1;
            } else {
                res[snap.active] = 1;
            }
        }

        res = Object.entries(res).map(entry => {
            return [entry[0], Math.round((entry[1] / Math.sumPrecise(Object.values(res))) * 100_00) / 100];
        })
        res = res.sort(([, a], [, b]) => {
            return b - a;
        });

        res = new Map(res)
        console.log(res)
        return res;
    });
    let dominanceInfo = $derived.by(() => {
        let res = {}

        for (let app of windowNames) {
            let matches = windows
                .filter(win => win.name == app)
                .filter(win => win.width > 0)
                .filter(win => win.desktop == windowSnapshots[win.ssid - 1].current_desktop)
                .map(win => win.width * win.height)
            const totalSurfaceArea = Math.sumPrecise(matches)
            const totalMonitorSurface = Math.sumPrecise(
                monitors.map(monitor => monitor.width * monitor.height)
            ) * windowSnapshots.length

            let percentage = totalSurfaceArea / totalMonitorSurface
            res[app] = Math.round(percentage * 100_00) / 100;
        }

        res = Object.entries(res).sort(([,a], [,b]) => {
            return b - a;
        });

        res = new Map(res)
        console.log(res)
        return res
    });

    let appInfo = $derived.by(() => {
        let res = [];
        for (const app of appNames) {
          let frequency = frequencyInfo.get(app) ?? -1;
          let focus = focusInfo.get(app) ?? -1;
          let dominance = dominanceInfo.get(app) ?? -1;
          res.push({ name: app, frequency, focus, dominance })
        }
        console.log(res)
        return res;
    });

    function appSort(method, apps, filter=true) {
        if (method == "frequency") {
            return apps
              .sort((a, b) => b.frequency - a.frequency)
              .filter(app => app.frequency !== -1 || !filter)
        } else if (method == "focus") {
            return apps
              .sort((a, b) => b.focus - a.focus)
              .filter(app => app.focus !== -1 || !filter)
        } else if (method == "dominance") {
            return apps
              .sort((a, b) => b.dominance - a.dominance)
              .filter(app => app.dominance !== -1 || !filter)
        } else if (method == "idle") {
            return apps
              .sort((a, b) => (a.focus / a.frequency) - (b.focus / b.frequency))
              .filter(app => app.focus !== -1 && app.frequency !== -1 || !filter)
        }
    }

    function appCount(app) {
        let res = {
            present: 0,
            focused: 0
        };

        res.present = windowSnapshots.filter(snap => {
            return windows
                .filter(win => win.ssid == snap.id)
                .map(win => win.name)
                .includes(app)
        }).length;
        res.focused = windowSnapshots.filter(snap => snap.active === app).length;
        return res;
    }

    let avgWindowsInfo = $derived.by(() => {
        let counts = windowSnapshots.map(snap => windows.filter(win => win.ssid === snap.id).length)
        return {
          average: Math.round((windows.length / windowSnapshots.length) * 10) / 10,
          max: Math.max(...counts),
          min: Math.min(...counts)
        }
    })

    let desktopPie = $state(null);
    let desktopPieChart;

    function countDesktops() {
        let res = {};
        for (const snap of windowSnapshots) {
            if (res[snap.current_desktop]) {
                res[snap.current_desktop] += 1;
            } else {
                res[snap.current_desktop] = 1;
            }
        }
        return res;
    }
    $effect(() => {
        let desktops = countDesktops();
        if (desktopPieChart) {
            desktopPieChart.data.labels = Object.keys(desktops);
            desktopPieChart.data.datasets[0].data = Object.values(desktops);
            desktopPieChart.update('none');
        } else {
            desktopPieChart = new Chart(desktopPie, {
                type: "doughnut",
                data: {
                    labels: Object.keys(desktops),
                    datasets: [{
                        data: Object.values(desktops),
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
    })

    let focusScatter = $state(null);
    let focusScatterChart;

    $effect(() => {
        let eligibleApps = appInfo.filter(app => windowNames.includes(app.name));
        let labels = eligibleApps.map(app => app.name);
        let minDominance = Math.min(...eligibleApps.map(app => app.dominance));
        let maxDominance = Math.max(...eligibleApps.map(app => app.dominance));
        let data = eligibleApps.map(app => {
          console.log(app)
          return {
            x: app.frequency,
            y: app.focus,
            r: 2 + (Math.log(app.dominance) - Math.log(minDominance)) /
                (Math.log(maxDominance) - Math.log(minDominance)) * 8
          }
        });
        if (focusScatterChart) {
            focusScatterChart.data.datasets[0].data = data;
            focusScatterChart.update('none');
        } else {
            focusScatterChart = new Chart(focusScatter, {
                type: 'bubble',
                data: {
                    labels: labels,
                    datasets: [{
                        data: data,
                        backgroundColor: colors[0],
                    }]
                },
                options: {
                    plugins: {
                        legend: {
                            display: false
                        }
                    }
                }
            });
        }
    })
</script>

<div class="page-title">Windows</div>

<div class="row">
    <div class="info-box">
        <span>Most Dominant App</span>
        <span style="font-size: 2.2rem; font-weight: normal">{appSort("dominance", appInfo)[0].name}</span>
        <span style="color: #8b949e; font-weight: normal">{appSort("dominance", appInfo)[0].dominance}% of monitor</span>
    </div>
    <!-- <div class="info-box">
        <span>Largest App</span>
        <span style="font-size: 2.2rem; font-weight: normal">{dominanceInfo[0].name}</span>
        <span style="color: #8b949e; font-weight: normal">{dominanceInfo[0].percentage}% of monitor</span>
    </div> -->
    <div class="info-box">
        <span>Most Idle App</span>
        <span style="font-size: 2.2rem; font-weight: normal">{appSort("idle", appInfo)[0].name}</span>
        <span style="color: #8b949e; font-weight: normal">{appCount(appSort("idle", appInfo)[0].name).present} snapshots, {appCount(appSort("idle", appInfo)[0].name).focused} focused</span>
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
                {#each appSort("frequency", appInfo) as app (app.name)}
                    <span>{app.name}</span>
                {/each}
            </div>
            <div class="progress-column" style="flex: 1;">
                {#each appSort("frequency", appInfo) as app (app.name)}
                    <div class="progress-bar-bg"><div class="progress-bar-fill" style="width: {app.frequency}%"></div></div>
                {/each}
            </div>
            <div class="progress-column">
                {#each appSort("frequency", appInfo) as app (app.name)}
                        <span>{Math.floor(app.frequency)}%</span>
                {/each}
            </div>
        </div>
    </div>
    <div class="info-box">
        <span style="margin-bottom: 1rem">App Focus</span>
        <div class="progress-container">
            <div class="progress-column">
                {#each appSort("focus", appInfo) as app (app.name)}
                    <span>{app.name}</span>
                {/each}
            </div>
            <div class="progress-column" style="flex: 1;">
                {#each appSort("focus", appInfo) as app (app.name)}
                    <div class="progress-bar-bg"><div class="progress-bar-fill" style="width: {app.focus}%"></div></div>
                {/each}
            </div>
            <div class="progress-column">
                {#each appSort("focus", appInfo) as app (app.name)}
                        <span>{Math.floor(app.focus)}%</span>
                {/each}
            </div>
        </div>
    </div>
    <!-- <div class="info-box">
        <span style="margin-bottom: 1rem">App Size</span>
        <div class="progress-container">
            <div class="progress-column">
                {#each appInfo as app (app.name)}
                    <span>{app.name}</span>
                {/each}
            </div>
            <div class="progress-column" style="flex: 1;">
                {#each appInfo as app (app.name)}
                    <div class="progress-bar-bg"><div class="progress-bar-fill" style="width: {(app.dominance / appInfo[0].dominance) * 100}%"></div></div>
                {/each}
            </div>
            <div class="progress-column">
                {#each appInfo as app (app.name)}
                        <span>{Math.round(app.dominance)}%</span>
                {/each}
            </div>
        </div>
    </div> -->
</div>

<div class="row">
    <div class="info-box">
        <span style="margin-bottom: 1rem">Usage</span>
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
        /*flex: 1;*/
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
