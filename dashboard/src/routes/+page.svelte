<script>
    import initSqlJs from 'sql.js';
    let fileInput;
    let importTextButton;
    let importIconButton;
    let sectionButtonMouse;
    let fileName = $state("");

    let SCREEN_W = $state(1920);
    let SCREEN_H = $state(1080);

    let canvas;
    let canvasContainer = $state(null);
    let clicks = $state([]);
    let monitors = $state([]);

    async function chooseFile(event) {
        const file = event.target.files[0];
        fileName = file.name;
        importTextButton.style.display = 'none';
        importIconButton.style.display = 'inline';

        const SQL = await initSqlJs({ locateFile: () => '/sql-wasm.wasm' });

        const buf = await file.arrayBuffer();
        const db = new SQL.Database(new Uint8Array(buf));
        parseFile(db);
    }

    async function parseFile(db) {
        const monitors_result = db.exec("SELECT id, x, y, width, height FROM monitors");

        const clicks_result = db.exec("SELECT id, x, y, button FROM clicks");

        const [{ columns: monitors_columns, values: monitors_values }] = monitors_result;

        SCREEN_H = 0;
        SCREEN_W = 0;
        for (let monitor of monitors_values) {
            console.log(monitor);
            SCREEN_W += monitor[3];
            SCREEN_H = Math.max(SCREEN_H, monitor[4]);
        }
        console.log(SCREEN_W, SCREEN_H);

        monitors = monitors_values.map(row =>
            Object.fromEntries(monitors_columns.map((col, i) => [col, row[i]]))
        );

        const [{ columns: clicks_columns, values: clicks_values }] = clicks_result;
        clicks = clicks_values.map(row =>
            Object.fromEntries(clicks_columns.map((col, i) => [col, row[i]]))
        );
    }

    // function drawClicks() {
    //   let clickElements = [];

    //   for (const { x, y } of clicks) {
    //     const click = document.createElement('div');
    //     click.className = "click"
    //     click.style.left = `${x}px`;
    //     click.style.top = `${y}px`;

    //     canvas.appendChild(click);
    //   }
    // }

    // function drawHeatmap() {
    //     const CELL_SIZE = 8;      // how many screen pixels per cell
    //     const SCREEN_W = 1920 + 1600;    // change to your resolution
    //     const SCREEN_H = 1080;

    //     const cols = Math.ceil(SCREEN_W / CELL_SIZE);
    //     const rows = Math.ceil(SCREEN_H / CELL_SIZE);

    //     // 1. Build a grid and count clicks per cell
    //     const grid = Array.from({ length: rows }, () => new Array(cols).fill(0));
    //     for (const { x, y } of clicks) {
    //         const col = Math.floor(x / CELL_SIZE);
    //         const row = Math.floor(y / CELL_SIZE);
    //         if (row >= 0 && row < rows && col >= 0 && col < cols) {
    //             grid[row][col]++;
    //         }
    //     }

    //     // 2. Find the highest count so we can normalise
    //     const max = grid.reduce((m, row) => Math.max(m, ...row), 0);
    //     if (max === 0) return;

    //     // 3. Draw each cell as a coloured rectangle
    //     const ctx = canvas.getContext('2d');
    //     canvas.width = cols;
    //     canvas.height = rows;
    //     ctx.clearRect(0, 0, cols, rows);

    //     for (let row = 0; row < rows; row++) {
    //         for (let col = 0; col < cols; col++) {
    //             const count = grid[row][col];
    //             if (count === 0) continue;

    //             const t = count / max;               // 0 = cold, 1 = hot
    //             const hue = (1 - t) * 240;           // 240 = blue, 0 = red
    //             const alpha = 0.2 + t * 1;
    //             ctx.fillStyle = `hsla(${hue}, 100%, 50%, ${alpha})`;
    //             ctx.fillRect(col, row, 1, 1);
    //         }
    //     }
    // }
</script>

<main class="container">
    <div class="sidebar">
        <div class= "import-data">
            <input style="display: none;" aria-hidden="true" type="file" accept=".db" onchange={chooseFile} bind:this={fileInput}/>
            <button class= "import-button" bind:this={importTextButton} onclick={() => fileInput.click()}>Import Data</button>
            <span>{ fileName }</span>
            <button class= "upload-button" style="display: none;" bind:this={importIconButton} onclick={() => fileInput.click()} aria-label="Upload">
                <svg xmlns="http://www.w3.org/2000/svg" height="1.1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-upload-icon lucide-upload"><path d="M12 3v12"/><path d="m17 8-5-5-5 5"/><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/></svg>
            </button>
        </div>
        <div class="sections">
            <button class="section-button" bind:this={sectionButtonMouse} onclick={() => sectionButtonMouse.classList.add('active')}>
                <svg xmlns="http://www.w3.org/2000/svg" width="1.2em" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-mouse-icon lucide-mouse"><rect x="5" y="2" width="14" height="20" rx="7"/><path d="M12 6v4"/></svg>
                Mouse
            </button>
        </div>
    </div>
    <div class="content">
        <div class="page-title">Mouse</div>
        <div class="heatmap">
            <span>Heatmap</span>
            <div class="canvas-container" style="aspect-ratio: {SCREEN_W} / {SCREEN_H};" bind:this={canvasContainer}>
            <div class= "canvas" bind:this={canvas}>
                {#each monitors as {id, x, y, width, height} (id)}
                    <div
                        class="monitor"
                        style="
                        width: calc({(width / SCREEN_W) * 100}%);
                        height: calc({(height / SCREEN_H) * 100}%);
                        left: calc({(x / SCREEN_W) * 100}%);
                        top: calc({(y / SCREEN_H) * 100}%);
                        ">
                    </div>
                    <script>
                        console.log({width}, {height});
                    </script>
                {/each}
                {#each clicks as {id, x, y, button} (id)}
                    {#if button == "LEFT"}
                        <div
                            class="click {button}"
                            id={`click-${id}`}
                            style="left: calc({(x / SCREEN_W) * 100}% - 5px); top: calc({(y / SCREEN_H) * 100}% - 5px);">
                        </div>
                    {/if}
                {/each}
                {#each clicks as {id, x, y, button} (id)}
                    {#if button == "RIGHT"}
                        <div
                            class="click {button}"
                            id={`click-${id}`}
                            style="left: calc({(x / SCREEN_W) * 100}% - 5px); top: calc({(y / SCREEN_H) * 100}% - 5px);">
                        </div>
                    {/if}
                {/each}
                {#each clicks as {id, x, y, button} (id)}
                    {#if button == "MIDDLE"}
                        <div
                            class="click {button}"
                            id={`click-${id}`}
                            style="left: calc({(x / SCREEN_W) * 100}% - 5px); top: calc({(y / SCREEN_H) * 100}% - 5px);">
                        </div>
                    {/if}
                {/each}
            </div>
        </div>
        </div>
    </div>
</main>

<style>
    .sidebar {
        display: flex;
        flex-direction: column;
        background-color: #010409;
        height: 100%;
        width: 300px;
    }

    main {
        overflow: hidden;
        background-color: #0D1117;
        color: #ffffff;

        font-family: sans-serif;

        display: flex;
        flex-direction: row;
        width: 100vw;
        height: 100vh;
    }

    .content {
        display: flex;
        height: 100vh;
        width: 100%;
        flex-direction: column;
        margin: 1rem 2rem;
        gap: 1rem;
        flex: 1;
    }

    .heatmap {
        display: flex;
        flex-direction: column;
        /*gap: 0.1rem;*/
        align-self: center;

        width: 100%;
        padding: 0.75rem 1rem 1rem 1rem;
        border: 1px solid #3d444d;
        border-radius:  0.5rem;

        font-size: 0.9rem;
        font-weight: bold;
        color: #fff;
    }

    .canvas-container {
        margin-top: 0.5rem;
    }

    .canvas {
        position: relative;

        display: flex;
        align-items: end;
        flex-direction: row;

        width:100%;
        height:100%;
    }
    .monitor {
        position: absolute;
        border: 1px solid #3d444d;
        background-color: #151B23;
        border-radius: 0.5rem;
    }

    .click {
        background-color: #ffffff;
        position: absolute;
        border-radius: 100px;
        width: 10px;
        height: 10px;
    }
    .click.LEFT {
        background-color: #4493f8;
        opacity: 0.1;
    }
    .click.RIGHT {
        background-color: #ff3e00;
        opacity: 0.2;
    }
    .click.MIDDLE {
        background-color: #f1e05a;
        opacity: 0.2;
    }

    .import-data {
        display: flex;
        flex-direction: inline-row;
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
        flex-direction: inline-row;
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
        text-align: start;
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

</style>
