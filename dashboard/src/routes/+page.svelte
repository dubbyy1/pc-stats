<script>
    import initSqlJs from 'sql.js';
    let fileInput;
    let fileName = $state("");

    let canvas;
    let clicks = [];

    const CELL_SIZE = 16;      // how many screen pixels per cell
    const SCREEN_W = 1920 + 1600;    // change to your resolution
    const SCREEN_H = 1080;

    async function chooseFile(event) {
        const file = event.target.files[0];
        fileName = file.name;

        const SQL = await initSqlJs({ locateFile: () => '/sql-wasm.wasm' });

        const buf = await file.arrayBuffer();
        const db = new SQL.Database(new Uint8Array(buf));

        const result = db.exec("SELECT x, y FROM clicks");
        console.log(result)

        const [{ columns, values }] = result;
        clicks = values.map(row =>
            Object.fromEntries(columns.map((col, i) => [col, row[i]]))
        );
        drawHeatmap();
        console.log(fileName);
    }

    function drawHeatmap() {
        const cols = Math.ceil(SCREEN_W / CELL_SIZE);
        const rows = Math.ceil(SCREEN_H / CELL_SIZE);

        // 1. Build a grid and count clicks per cell
        const grid = Array.from({ length: rows }, () => new Array(cols).fill(0));
        for (const { x, y } of clicks) {
            const col = Math.floor(x / CELL_SIZE);
            const row = Math.floor(y / CELL_SIZE);
            if (row >= 0 && row < rows && col >= 0 && col < cols) {
                grid[row][col]++;
            }
        }

        // 2. Find the highest count so we can normalise
        const max = grid.reduce((m, row) => Math.max(m, ...row), 0);
        if (max === 0) return;

        // 3. Draw each cell as a coloured rectangle
        const ctx = canvas.getContext('2d');
        canvas.width = cols;
        canvas.height = rows;
        ctx.clearRect(0, 0, cols, rows);

        for (let row = 0; row < rows; row++) {
            for (let col = 0; col < cols; col++) {
                const count = grid[row][col];
                if (count === 0) continue;

                const t = count / max;               // 0 = cold, 1 = hot
                const hue = (1 - t) * 240;           // 240 = blue, 0 = red
                const alpha = 0.2 + t * 1;
                ctx.fillStyle = `hsla(${hue}, 100%, 50%, ${alpha})`;
                ctx.fillRect(col, row, 1, 1);
            }
        }
    }

    async function parseFile(event) {

    }
</script>

<main class="container">
    <div class="sidebar">
        <div class= "import-data">
            <input style="display: none;" aria-hidden="true" type="file" accept=".db" onchange={chooseFile} bind:this={fileInput}/>
            <button class= "choose-file" onclick={() => fileInput.click()}>Import Data</button>
            <span>{ fileName }</span>
        </div>
    </div>
    <div class="content">
        <canvas bind:this={canvas} style="width: 100%; image-rendering: pixelated;"></canvas>
    </div>
</main>

<style>
    .import-data {
        display: flex;
        flex-direction: inline-row;
        align-items: center;
        gap: 1rem;
    }

    .sidebar {
        background-color: #010409;
        padding: 1rem;
        height: 100%;
        width: 300px;
    }

    main {
        margin: 0px;
        height: 100vh;
        display: flex;
        flex-direction: row;
    }

    :root {
        overflow: hidden;
        margin: 0px;
        background-color: #0D1117;
        color: #ffffff;
    }

    .content {
        display: flex;
        height: 100vh;
        width: 100%;
        flex-direction: column;
        align-items: center;
        gap: 1rem;
    }

    canvas {
        padding: 1rem;
        background: #ffffff;
        transform: scale(0.7);
        /*width: 20%;*/
        /*height: 20%;*/
        /*width: 704px;
        height: 216px;*/
    }

    .choose-file {
        cursor: pointer;
        color: #ffffff;
        border: 0px;
        border-radius: 1em;
        padding: 0.75em;
        background-color: #212830;
        transition: 0.1s;
    }
    .choose-file:hover {
        background-color: #262C36;
    }
    .choose-file:active {
        background-color: #2A313C;
    }
</style>
