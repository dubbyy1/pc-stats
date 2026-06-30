<script>
    import initSqlJs from 'sql.js';
    import { page } from '$app/state';
    import MouseSection from '$lib/components/MouseSection.svelte';
    import WindowSection from '$lib/components/WindowSection.svelte';

    let fileInput;
    let activeSection = $state('mouse');
    let fileName = $state('');
    let hasFile = $state(false);

    let screenW = $state(0);
    let screenH = $state(0);
    let monitors = $state([]);
    let allClicks = $state([]);
    let windows = $state([]);
    let windowSnapshots = $state([]);

    const DB_CACHE_NAME = 'pc-stats-cache';
    const DB_STORE_NAME = 'files';
    const DB_KEY = 'latest-db';

    let loadedStartupDb = false;

    $effect(() => {
        if (loadedStartupDb) return;
        loadedStartupDb = true;

        const dbUrl = page.url.searchParams.get('db');
        if (dbUrl) loadDbFromUrl(dbUrl);
        else loadCachedDbOnStartup();
    });

    async function chooseFile(event) {
        const file = event.target.files[0];
        if (!file) return;

        fileName = file.name;
        hasFile = true;

        const SQL = await initSqlJs({ locateFile: () => '/sql-wasm.wasm' });
        const buf = await file.arrayBuffer();

        await saveDbToCache(buf);

        const db = new SQL.Database(new Uint8Array(buf));
        parseFile(db);
    }

    async function loadDbFromUrl(dbUrl) {
        fileName = dbUrl.split('/').pop() ?? 'remote.db';
        hasFile = true;

        const SQL = await initSqlJs({ locateFile: () => '/sql-wasm.wasm' });
        const response = await fetch(dbUrl);

        if (!response.ok) {
            throw new Error(`Failed to load DB: ${response.status}`);
        }

        const buf = await response.arrayBuffer();
        const db = new SQL.Database(new Uint8Array(buf));

        parseFile(db);
    }

    async function loadCachedDbOnStartup() {
        const buf = await loadDbFromCache();
        if (!buf) return;

        fileName = 'cache';
        hasFile = true;

        const SQL = await initSqlJs({ locateFile: () => '/sql-wasm.wasm' });
        const db = new SQL.Database(new Uint8Array(buf));

        parseFile(db);
    }

    function parseFile(db) {
        monitors = getRows(db, 'SELECT id, name, x, y, width, height FROM monitors');
        allClicks = getRows(db, 'SELECT id, timestamp, x, y, button FROM clicks');

        windows = getRows(db, 'SELECT ssid, name, pid, desktop, x, y, width, height FROM windows');
        windowSnapshots = getRows(db, 'SELECT id, timestamp, active, current_desktop FROM window_snapshots');

        screenW = 0;
        screenH = 0;

        for (const monitor of monitors) {
            screenW += monitor.width;
            screenH = Math.max(screenH, monitor.height);
        }
    }

    function getRows(db, query) {
        const result = db.exec(query);
        if (result.length === 0) return [];

        const [{ columns, values }] = result;
        return values.map(row =>
            Object.fromEntries(columns.map((col, i) => [col, row[i]]))
        );
    }

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

    async function saveDbToCache(buffer) {
        const cacheDb = await openCacheDb();

        return new Promise((resolve, reject) => {
            const tx = cacheDb.transaction(DB_STORE_NAME, 'readwrite');
            tx.objectStore(DB_STORE_NAME).put(buffer, DB_KEY);
            tx.oncomplete = resolve;
            tx.onerror = () => reject(tx.error);
        });
    }
</script>

<main class="container">
    <div class="sidebar">
        <div class="import-data">
            <input
                style="display: none;"
                aria-hidden="true"
                type="file"
                accept=".db"
                onchange={chooseFile}
                bind:this={fileInput}
            />

            {#if hasFile}
                <button class="upload-button" onclick={() => fileInput.click()} aria-label="Upload">
                    <svg xmlns="http://www.w3.org/2000/svg" height="1.1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12"/><path d="m17 8-5-5-5 5"/><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/></svg>
                </button>
                <span>{fileName}</span>
            {:else}
                <button class="import-button" onclick={() => fileInput.click()}>Import Data</button>
            {/if}
        </div>

        <div class="sections">
            <button class="section-button" class:active={activeSection === 'mouse'} onclick={() => activeSection = 'mouse'}>
                <svg xmlns="http://www.w3.org/2000/svg" width="1.2em" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="2" width="14" height="20" rx="7"/><path d="M12 6v4"/></svg>
                Mouse
            </button>

            <button class="section-button" class:active={activeSection === 'window'} onclick={() => activeSection = 'window'}>
                <svg xmlns="http://www.w3.org/2000/svg" width="1.2em" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 9h18"/></svg>
                Windows
            </button>
        </div>

        <a class="company-mark" href="https://dubbyy.com" aria-label="dubbyy">
            <span class="company-logo" aria-hidden="true"></span>
        </a>
    </div>

    <div class="content">
        <div class="inner">
            {#if activeSection === 'mouse'}
                <MouseSection
                    {allClicks}
                    {monitors}
                    screenW={screenW}
                    screenH={screenH}
                />
            {:else if activeSection === 'window'}
                <WindowSection
                    {monitors}
                    {windows}
                    {windowSnapshots}
                />
            {/if}
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

    .company-mark {
        display: flex;
        align-items: center;
        margin-top: auto;
        padding: 1rem;
        width: fit-content;
    }

    .company-logo {
        width: 3rem;
        height: 3rem;
        background-color: #ffffff;
        -webkit-mask: url('/company-logo.svg') center / contain no-repeat;
        mask: url('/company-logo.svg') center / contain no-repeat;
        opacity: 0.76;
        transition: background-color 0.16s, opacity 0.16s;
    }

    .company-mark:hover .company-logo {
        background-color: #ff8000;
        opacity: 0.92;
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
</style>
