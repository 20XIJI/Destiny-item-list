// ==UserScript==
// @name         Destiny2_Term_replace
// @namespace    your-namespace
// @version      5.0
// @description  替换网页中出现的命运2术语 - 支持三语言切换 (EN/简中/繁中)
// @match        *://*/*
// @exclude      *://*.light.gg/*
// @exclude      *://light.gg/*
// @grant        GM_addStyle
// @grant        GM_setValue
// @grant        GM_getValue
// @grant        GM_deleteValue
// @grant        GM_xmlhttpRequest
// @grant        GM_registerMenuCommand
// @connect      20xiji.github.io
// @license      MIT
// @downloadURL https://update.greasyfork.org/scripts/524822/Destiny2_Term_replace.user.js
// @updateURL https://update.greasyfork.org/scripts/524822/Destiny2_Term_replace.meta.js
// ==/UserScript==

(function() {
    'use strict';

    /* === 全局配置 === */
    const CACHE_DAYS = 1;
    const HISTORY_LIMIT = 20;
    const USER_TERMS_KEY = 'userDefinedTerms';
    const ITEMS_PER_PAGE_KEY = 'itemsPerPageSetting';
    const LANG_SOURCE_KEY = 'langSource';
    const LANG_TARGET_KEY = 'langTarget';
    const PAUSED_KEY = 'd2tr_paused';
    const WELCOME_KEY = 'hasShownWelcome_v5_panel';
    const PANEL_OPEN_KEY = 'd2tr_panel_open';

    const LANGUAGES = {
        'en': 'English',
        'zh-chs': '简体中文',
        'zh-cht': '繁體中文'
    };

    const ITEM_LIST_URL = 'https://20xiji.github.io/Destiny-item-list/term-map.json';

    /* === 状态变量 === */
    let replacementHistory = [];
    let termMap = new Map();
    let userTerms = {};
    let currentMode = 1;
    let langSource = GM_getValue(LANG_SOURCE_KEY, 'en');
    let langTarget = GM_getValue(LANG_TARGET_KEY, 'zh-chs');
    let isPaused = GM_getValue(PAUSED_KEY, false);
    let panelOpen = false;
    let currentPage = 1;
    let itemsPerPage = GM_getValue(ITEMS_PER_PAGE_KEY, 20);
    let searchTerm = '';
    let processedNodes = new WeakSet();
    let dataStatus = 'loading'; // loading | ready | error

    function throttle(func, limit) {
        let inThrottle;
        return function(...args) {
            if (!inThrottle) {
                func.apply(this, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    }

    function clearElement(el) {
        while (el.firstChild) el.removeChild(el.firstChild);
    }

    function createSectionHeader(title) {
        const header = document.createElement('div');
        header.className = 'd2tr-section-header';

        const titleSpan = document.createElement('span');
        titleSpan.className = 'd2tr-section-title';
        titleSpan.textContent = title;

        const arrowSpan = document.createElement('span');
        arrowSpan.className = 'd2tr-section-arrow';
        arrowSpan.textContent = '▼';

        header.appendChild(titleSpan);
        header.appendChild(arrowSpan);
        return header;
    }

    /* === 变体生成 === */
    function addVariants(map, source, target) {
        map.set(source, target);
        if (langSource === 'en' && source.includes("'")) {
            map.set(source.replace(/'/g, '’'), target);
        }
        if (langSource === 'en' && source.startsWith('The ')) {
            map.set(source.slice(4), target);
        }
    }

    function buildTermMapFromData(termMapData, sourceLang, targetLang) {
        const map = new Map();
        const buckets = termMapData.data || termMapData;
        for (const bucketName of Object.keys(buckets)) {
            const bucket = buckets[bucketName];
            for (const hashKey of Object.keys(bucket)) {
                const entry = bucket[hashKey];
                const sourceText = entry[sourceLang];
                const targetText = entry[targetLang];
                if (sourceText && targetText && sourceText !== targetText) {
                    addVariants(map, sourceText, targetText);
                }
            }
        }
        return map;
    }

    /* === 样式 === */
    GM_addStyle(`
        :root {
            --destiny-bg: #0a0e14;
            --destiny-panel: #1a1f2e;
            --destiny-accent: #f0b232;
            --destiny-tech: #00d4ff;
            --destiny-success: #4caf50;
            --destiny-danger: #e74c3c;
            --destiny-text: #ffffff;
            --destiny-text-muted: #a0a8b8;
            --destiny-border: rgba(255, 255, 255, 0.1);
            --destiny-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
            --destiny-radius: 12px;
            --destiny-radius-sm: 8px;
        }

        @keyframes d2tr-fadein {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        @keyframes d2tr-fadeout {
            from { opacity: 1; transform: translateY(0); }
            to { opacity: 0; transform: translateY(10px); }
        }
        @keyframes d2tr-pulse {
            0%, 100% { box-shadow: 0 4px 12px rgba(0,0,0,0.3), 0 0 0 0 rgba(240, 178, 50, 0.5); }
            50% { box-shadow: 0 4px 12px rgba(0,0,0,0.3), 0 0 0 10px rgba(240, 178, 50, 0); }
        }

        /* 悬浮按钮 */
        .d2tr-fab {
            position: fixed;
            bottom: 20px;
            right: 20px;
            width: 48px;
            height: 48px;
            border-radius: 50%;
            border: none;
            background: linear-gradient(135deg, var(--destiny-accent), #e6a020);
            color: var(--destiny-bg);
            font-size: 14px;
            font-weight: 800;
            cursor: pointer;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 9998;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            user-select: none;
        }
        .d2tr-fab:hover {
            transform: scale(1.1);
            box-shadow: 0 6px 20px rgba(240, 178, 50, 0.4);
        }
        .d2tr-fab.paused {
            background: rgba(255, 255, 255, 0.15);
            color: var(--destiny-text-muted);
        }
        .d2tr-fab.paused:hover {
            background: rgba(255, 255, 255, 0.25);
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        }
        .d2tr-fab.pulse {
            animation: d2tr-pulse 1.5s ease-in-out 4;
        }

        /* 状态指示灯 */
        .d2tr-status-dot {
            position: absolute;
            top: -2px;
            right: -2px;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            border: 2px solid var(--destiny-panel);
            transition: background 0.3s ease;
        }
        .d2tr-status-dot.loading { background: var(--destiny-accent); }
        .d2tr-status-dot.ready { background: var(--destiny-success); }
        .d2tr-status-dot.error { background: var(--destiny-danger); }

        /* 面板 */
        .d2tr-panel {
            position: fixed;
            bottom: 76px;
            right: 20px;
            width: 300px;
            background: var(--destiny-panel);
            border-radius: var(--destiny-radius);
            box-shadow: var(--destiny-shadow);
            border: 1px solid var(--destiny-border);
            z-index: 9999;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            color: var(--destiny-text);
            overflow: hidden;
            backdrop-filter: blur(10px);
            display: none;
        }
        .d2tr-panel.open {
            display: block;
            animation: d2tr-fadein 0.25s ease-out;
        }
        .d2tr-panel.closing {
            animation: d2tr-fadeout 0.2s ease-in forwards;
        }

        /* 面板头部 */
        .d2tr-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 14px 16px;
            border-bottom: 1px solid var(--destiny-border);
            cursor: grab;
        }
        .d2tr-header:active { cursor: grabbing; }
        .d2tr-header-title {
            font-weight: 600;
            font-size: 14px;
            background: linear-gradient(135deg, var(--destiny-accent), var(--destiny-tech));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .d2tr-header-meta {
            font-size: 11px;
            color: var(--destiny-tech);
            padding: 2px 8px;
            background: rgba(0, 212, 255, 0.1);
            border-radius: 10px;
        }

        /* 分组 */
        .d2tr-section {
            border-bottom: 1px solid var(--destiny-border);
        }
        .d2tr-section:last-child { border-bottom: none; }
        .d2tr-section-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 10px 16px;
            cursor: pointer;
            transition: background 0.2s ease;
            user-select: none;
        }
        .d2tr-section-header:hover {
            background: rgba(255, 255, 255, 0.03);
        }
        .d2tr-section-title {
            font-size: 12px;
            font-weight: 600;
            color: var(--destiny-text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .d2tr-section-arrow {
            font-size: 10px;
            color: var(--destiny-text-muted);
            transition: transform 0.2s ease;
        }
        .d2tr-section.open .d2tr-section-arrow {
            transform: rotate(180deg);
        }
        .d2tr-section-body {
            padding: 0 16px 12px;
            display: none;
        }
        .d2tr-section.open .d2tr-section-body {
            display: block;
        }

        /* 语言选择器 */
        .d2tr-lang-row {
            display: flex;
            align-items: center;
            gap: 6px;
            margin-bottom: 8px;
        }
        .d2tr-lang-row label {
            font-size: 11px;
            color: var(--destiny-text-muted);
            white-space: nowrap;
            min-width: 24px;
        }
        .d2tr-lang-row select {
            flex: 1;
            background: rgba(0, 0, 0, 0.3);
            color: var(--destiny-text);
            border: 1px solid var(--destiny-border);
            border-radius: 6px;
            padding: 6px 8px;
            font-size: 12px;
            cursor: pointer;
            transition: border-color 0.2s ease;
        }
        .d2tr-lang-row select:focus {
            outline: none;
            border-color: var(--destiny-accent);
        }
        .d2tr-swap-btn {
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid var(--destiny-border);
            color: var(--destiny-accent);
            width: 26px;
            height: 26px;
            border-radius: 50%;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 13px;
            transition: all 0.2s ease;
            padding: 0;
            flex-shrink: 0;
        }
        .d2tr-swap-btn:hover {
            background: rgba(240, 178, 50, 0.2);
            transform: rotate(180deg);
        }

        /* 模式按钮 */
        .d2tr-mode-row {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 6px;
        }
        .d2tr-mode-btn {
            padding: 8px 4px;
            border: 1px solid var(--destiny-border);
            border-radius: var(--destiny-radius-sm);
            background: rgba(255, 255, 255, 0.05);
            color: var(--destiny-text-muted);
            cursor: pointer;
            transition: all 0.2s ease;
            font-size: 11px;
            font-weight: 500;
            text-align: center;
        }
        .d2tr-mode-btn:hover {
            background: rgba(255, 255, 255, 0.1);
            color: var(--destiny-text);
            border-color: var(--destiny-accent);
        }
        .d2tr-mode-btn.active {
            background: linear-gradient(135deg, var(--destiny-accent), #e6a020);
            color: var(--destiny-bg);
            border-color: var(--destiny-accent);
            font-weight: 600;
        }

        /* 操作按钮 */
        .d2tr-action-row {
            display: flex;
            gap: 6px;
            margin-top: 8px;
        }
        .d2tr-action-btn {
            flex: 1;
            padding: 8px 6px;
            border: none;
            border-radius: var(--destiny-radius-sm);
            background: linear-gradient(135deg, var(--destiny-accent), #e6a020);
            color: var(--destiny-bg);
            cursor: pointer;
            font-weight: 600;
            font-size: 11px;
            transition: all 0.2s ease;
        }
        .d2tr-action-btn:hover {
            transform: translateY(-1px);
            box-shadow: 0 3px 8px rgba(240, 178, 50, 0.3);
        }
        .d2tr-action-btn:disabled {
            background: rgba(255, 255, 255, 0.1);
            color: var(--destiny-text-muted);
            cursor: not-allowed;
            transform: none;
            box-shadow: none;
        }
        .d2tr-action-btn.danger {
            background: linear-gradient(135deg, var(--destiny-danger), #c0392b);
        }
        .d2tr-action-btn.danger:hover {
            box-shadow: 0 3px 8px rgba(231, 76, 60, 0.3);
        }

        /* 术语管理 */
        .d2tr-term-search {
            width: 100%;
            background: rgba(0, 0, 0, 0.3);
            border: 1px solid var(--destiny-border);
            color: var(--destiny-text);
            border-radius: var(--destiny-radius-sm);
            padding: 7px 10px;
            font-size: 12px;
            box-sizing: border-box;
            transition: border-color 0.2s ease;
            margin-bottom: 8px;
        }
        .d2tr-term-search:focus {
            outline: none;
            border-color: var(--destiny-accent);
        }
        .d2tr-term-list {
            max-height: 160px;
            overflow-y: auto;
            background: rgba(0, 0, 0, 0.2);
            border: 1px solid var(--destiny-border);
            border-radius: var(--destiny-radius-sm);
            padding: 4px;
        }
        .d2tr-term-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 6px 8px;
            margin: 2px 0;
            background: rgba(255, 255, 255, 0.02);
            border-radius: 4px;
            transition: background 0.15s ease;
        }
        .d2tr-term-item:hover {
            background: rgba(255, 255, 255, 0.06);
        }
        .d2tr-term-text {
            font-family: 'JetBrains Mono', 'Fira Code', monospace;
            font-size: 11px;
        }
        .d2tr-term-del {
            background: transparent;
            border: 1px solid transparent;
            border-radius: 4px;
            color: var(--destiny-text-muted);
            cursor: pointer;
            font-size: 13px;
            width: 22px;
            height: 22px;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.15s ease;
            padding: 0;
        }
        .d2tr-term-del:hover {
            border-color: var(--destiny-danger);
            color: var(--destiny-danger);
            background: rgba(231, 76, 60, 0.1);
        }
        .d2tr-pagination {
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 8px;
            margin-top: 8px;
            font-size: 11px;
            color: var(--destiny-text-muted);
        }
        .d2tr-pagination button {
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid var(--destiny-border);
            color: var(--destiny-text-muted);
            border-radius: 4px;
            padding: 4px 10px;
            cursor: pointer;
            font-size: 11px;
            transition: all 0.15s ease;
        }
        .d2tr-pagination button:hover:not(:disabled) {
            background: rgba(255, 255, 255, 0.15);
            color: var(--destiny-text);
        }
        .d2tr-pagination button:disabled {
            opacity: 0.4;
            cursor: not-allowed;
        }

        /* 批量添加面板 */
        .d2tr-batch-area {
            width: 100%;
            height: 80px;
            background: rgba(0, 0, 0, 0.3);
            color: var(--destiny-text);
            border: 1px solid var(--destiny-border);
            border-radius: var(--destiny-radius-sm);
            padding: 8px;
            resize: vertical;
            box-sizing: border-box;
            font-family: 'JetBrains Mono', 'Fira Code', monospace;
            font-size: 11px;
            transition: border-color 0.2s ease;
            margin-top: 6px;
        }
        .d2tr-batch-area:focus {
            outline: none;
            border-color: var(--destiny-accent);
        }
        .d2tr-batch-actions {
            display: flex;
            gap: 6px;
            justify-content: flex-end;
            margin-top: 6px;
        }
        .d2tr-batch-actions button {
            padding: 6px 14px;
            border: none;
            border-radius: var(--destiny-radius-sm);
            cursor: pointer;
            font-weight: 600;
            font-size: 11px;
            transition: all 0.15s ease;
        }
        .d2tr-btn-save {
            background: linear-gradient(135deg, var(--destiny-success), #45a049);
            color: white;
        }
        .d2tr-btn-save:hover {
            transform: translateY(-1px);
            box-shadow: 0 3px 8px rgba(76, 175, 80, 0.3);
        }
        .d2tr-btn-cancel {
            background: rgba(255, 255, 255, 0.1);
            color: var(--destiny-text-muted);
        }
        .d2tr-btn-cancel:hover {
            background: rgba(255, 255, 255, 0.15);
            color: var(--destiny-text);
        }

        /* 高级操作行 */
        .d2tr-adv-row {
            display: flex;
            gap: 6px;
            flex-wrap: wrap;
        }
        .d2tr-adv-btn {
            flex: 1;
            min-width: 60px;
            padding: 7px 6px;
            border: none;
            border-radius: var(--destiny-radius-sm);
            background: rgba(255, 255, 255, 0.08);
            color: var(--destiny-text-muted);
            cursor: pointer;
            font-size: 11px;
            font-weight: 500;
            transition: all 0.15s ease;
            text-align: center;
        }
        .d2tr-adv-btn:hover {
            background: rgba(255, 255, 255, 0.14);
            color: var(--destiny-text);
        }
        .d2tr-adv-btn.danger-text {
            color: var(--destiny-danger);
        }
        .d2tr-adv-btn.danger-text:hover {
            background: rgba(231, 76, 60, 0.15);
        }

        /* Toast */
        .d2tr-toast {
            position: fixed;
            bottom: 76px;
            right: 80px;
            background: var(--destiny-panel);
            color: var(--destiny-text);
            padding: 10px 16px;
            border-radius: var(--destiny-radius-sm);
            font-size: 13px;
            z-index: 10002;
            opacity: 0;
            transition: all 0.3s ease;
            pointer-events: none;
            box-shadow: var(--destiny-shadow);
            border: 1px solid var(--destiny-border);
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            display: flex;
            align-items: center;
            gap: 6px;
            max-width: 280px;
        }
        .d2tr-toast.show { opacity: 1; }
        .d2tr-toast.success { border-left: 3px solid var(--destiny-success); }
        .d2tr-toast.error { border-left: 3px solid var(--destiny-danger); }
    `);

    /* === Toast 提示 === */
    function showToast(message, success = true) {
        const toast = document.createElement('div');
        toast.className = `d2tr-toast ${success ? 'success' : 'error'}`;
        toast.textContent = message;
        document.body.appendChild(toast);
        requestAnimationFrame(() => toast.classList.add('show'));
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 2500);
    }

    /* === 创建悬浮按钮 === */
    const fab = document.createElement('button');
    fab.className = 'd2tr-fab' + (isPaused ? ' paused' : '');
    fab.textContent = 'D2';
    fab.title = '命运2术语替换';

    const statusDot = document.createElement('div');
    statusDot.className = 'd2tr-status-dot loading';
    fab.appendChild(statusDot);

    document.body.appendChild(fab);

    /* === 创建面板 === */
    const panel = document.createElement('div');
    panel.className = 'd2tr-panel';

    // 头部
    const header = document.createElement('div');
    header.className = 'd2tr-header';
    const headerTitle = document.createElement('span');
    headerTitle.className = 'd2tr-header-title';
    headerTitle.textContent = '命运2术语替换';
    const headerMeta = document.createElement('span');
    headerMeta.className = 'd2tr-header-meta';
    headerMeta.id = 'd2trTermCount';
    headerMeta.textContent = '加载中...';
    header.appendChild(headerTitle);
    header.appendChild(headerMeta);
    panel.appendChild(header);

    /* --- Section: 语言设置 --- */
    function createLangSection() {
        const section = document.createElement('div');
        section.className = 'd2tr-section open';

        const secHeader = createSectionHeader('语言设置');
        secHeader.addEventListener('click', () => section.classList.toggle('open'));
        section.appendChild(secHeader);

        const body = document.createElement('div');
        body.className = 'd2tr-section-body';

        // 源语言行
        const srcRow = document.createElement('div');
        srcRow.className = 'd2tr-lang-row';
        const srcLabel = document.createElement('label');
        srcLabel.textContent = '从';
        const srcSelect = document.createElement('select');
        srcSelect.id = 'd2trLangSource';
        for (const [code, name] of Object.entries(LANGUAGES)) {
            const opt = document.createElement('option');
            opt.value = code;
            opt.textContent = name;
            if (code === langSource) opt.selected = true;
            srcSelect.appendChild(opt);
        }
        srcRow.appendChild(srcLabel);
        srcRow.appendChild(srcSelect);
        body.appendChild(srcRow);

        // 目标语言行 + 交换按钮
        const tgtRow = document.createElement('div');
        tgtRow.className = 'd2tr-lang-row';
        const tgtLabel = document.createElement('label');
        tgtLabel.textContent = '到';
        const swapBtn = document.createElement('button');
        swapBtn.className = 'd2tr-swap-btn';
        swapBtn.textContent = '⇄';
        swapBtn.title = '交换源语言和目标语言';
        const tgtSelect = document.createElement('select');
        tgtSelect.id = 'd2trLangTarget';
        for (const [code, name] of Object.entries(LANGUAGES)) {
            const opt = document.createElement('option');
            opt.value = code;
            opt.textContent = name;
            if (code === langTarget) opt.selected = true;
            tgtSelect.appendChild(opt);
        }
        tgtRow.appendChild(tgtLabel);
        tgtRow.appendChild(swapBtn);
        tgtRow.appendChild(tgtSelect);
        body.appendChild(tgtRow);

        // 事件
        srcSelect.addEventListener('change', async () => {
            langSource = srcSelect.value;
            GM_setValue(LANG_SOURCE_KEY, langSource);
            await reloadTermMap();
            updateModeButtonsText();
            showToast(`源语言已切换为 ${LANGUAGES[langSource]}`);
        });
        tgtSelect.addEventListener('change', async () => {
            langTarget = tgtSelect.value;
            GM_setValue(LANG_TARGET_KEY, langTarget);
            await reloadTermMap();
            updateModeButtonsText();
            showToast(`目标语言已切换为 ${LANGUAGES[langTarget]}`);
        });
        swapBtn.addEventListener('click', async () => {
            const tmp = srcSelect.value;
            srcSelect.value = tgtSelect.value;
            tgtSelect.value = tmp;
            langSource = srcSelect.value;
            langTarget = tgtSelect.value;
            GM_setValue(LANG_SOURCE_KEY, langSource);
            GM_setValue(LANG_TARGET_KEY, langTarget);
            await reloadTermMap();
            updateModeButtonsText();
            showToast('已交换源语言和目标语言');
        });

        section.appendChild(body);
        return section;
    }

    /* --- Section: 替换模式 --- */
    function createModeSection() {
        const section = document.createElement('div');
        section.className = 'd2tr-section open';

        const secHeader = createSectionHeader('替换模式');
        secHeader.addEventListener('click', () => section.classList.toggle('open'));
        section.appendChild(secHeader);

        const body = document.createElement('div');
        body.className = 'd2tr-section-body';

        const modeRow = document.createElement('div');
        modeRow.className = 'd2tr-mode-row';
        const modes = [1, 2, 3].map(m => {
            const btn = document.createElement('button');
            btn.className = 'd2tr-mode-btn' + (m === currentMode ? ' active' : '');
            btn.dataset.mode = m;
            btn.addEventListener('click', () => {
                currentMode = m;
                modeRow.querySelectorAll('.d2tr-mode-btn').forEach(b => b.classList.toggle('active', parseInt(b.dataset.mode) === m));
            });
            modeRow.appendChild(btn);
            return btn;
        });
        body.appendChild(modeRow);

        // 操作按钮
        const actionRow = document.createElement('div');
        actionRow.className = 'd2tr-action-row';

        const btnApply = document.createElement('button');
        btnApply.className = 'd2tr-action-btn';
        btnApply.textContent = '应用规则';
        btnApply.addEventListener('click', applyAllRules);

        const btnUndo = document.createElement('button');
        btnUndo.className = 'd2tr-action-btn';
        btnUndo.id = 'd2trBtnUndo';
        btnUndo.textContent = '撤销';
        btnUndo.disabled = true;
        btnUndo.addEventListener('click', undoReplace);

        const btnClear = document.createElement('button');
        btnClear.className = 'd2tr-action-btn danger';
        btnClear.textContent = '更新数据';
        btnClear.addEventListener('click', clearCache);

        actionRow.appendChild(btnApply);
        actionRow.appendChild(btnUndo);
        actionRow.appendChild(btnClear);
        body.appendChild(actionRow);

        section.appendChild(body);

        // 暴露模式按钮引用供外部更新文本
        section._modeButtons = modes;
        return section;
    }

    /* --- Section: 自定义术语 --- */
    function createTermSection() {
        const section = document.createElement('div');
        section.className = 'd2tr-section';

        const secHeader = createSectionHeader('自定义术语');
        secHeader.addEventListener('click', () => section.classList.toggle('open'));
        section.appendChild(secHeader);

        const body = document.createElement('div');
        body.className = 'd2tr-section-body';

        // 按钮行
        const btnRow = document.createElement('div');
        btnRow.style.cssText = 'display:flex;gap:6px;margin-bottom:8px;';
        const btnAdd = document.createElement('button');
        btnAdd.className = 'd2tr-adv-btn';
        btnAdd.textContent = '添加';
        const btnManage = document.createElement('button');
        btnManage.className = 'd2tr-adv-btn';
        btnManage.textContent = '管理';
        const btnExport = document.createElement('button');
        btnExport.className = 'd2tr-adv-btn';
        btnExport.textContent = '导出';
        const btnImport = document.createElement('button');
        btnImport.className = 'd2tr-adv-btn';
        btnImport.textContent = '导入';
        btnRow.appendChild(btnAdd);
        btnRow.appendChild(btnManage);
        btnRow.appendChild(btnExport);
        btnRow.appendChild(btnImport);
        body.appendChild(btnRow);

        // 批量添加面板
        const batchPanel = document.createElement('div');
        batchPanel.style.display = 'none';
        const batchHint = document.createElement('p');
        batchHint.style.cssText = 'font-size:11px;color:var(--destiny-text-muted);margin:0 0 6px;line-height:1.4;';
        batchHint.appendChild(document.createTextNode('每行一条，使用 '));
        const eqCode = document.createElement('code');
        eqCode.style.cssText = 'background:rgba(0,212,255,0.1);padding:1px 4px;border-radius:3px;color:var(--destiny-tech);font-size:11px;';
        eqCode.textContent = '=';
        batchHint.appendChild(eqCode);
        batchHint.appendChild(document.createTextNode(' 或 '));
        const pipeCode = document.createElement('code');
        pipeCode.style.cssText = 'background:rgba(0,212,255,0.1);padding:1px 4px;border-radius:3px;color:var(--destiny-tech);font-size:11px;';
        pipeCode.textContent = '|';
        batchHint.appendChild(pipeCode);
        batchHint.appendChild(document.createTextNode(' 分隔'));
        batchPanel.appendChild(batchHint);
        const batchArea = document.createElement('textarea');
        batchArea.className = 'd2tr-batch-area';
        batchArea.placeholder = '在此粘贴术语映射...';
        batchPanel.appendChild(batchArea);
        const batchActions = document.createElement('div');
        batchActions.className = 'd2tr-batch-actions';
        const btnSave = document.createElement('button');
        btnSave.className = 'd2tr-btn-save';
        btnSave.textContent = '保存';
        const btnCancel = document.createElement('button');
        btnCancel.className = 'd2tr-btn-cancel';
        btnCancel.textContent = '取消';
        batchActions.appendChild(btnSave);
        batchActions.appendChild(btnCancel);
        batchPanel.appendChild(batchActions);
        body.appendChild(batchPanel);

        // 管理面板
        const managePanel = document.createElement('div');
        managePanel.style.display = 'none';
        const searchInput = document.createElement('input');
        searchInput.className = 'd2tr-term-search';
        searchInput.placeholder = '搜索术语...';
        managePanel.appendChild(searchInput);
        const termList = document.createElement('div');
        termList.className = 'd2tr-term-list';
        managePanel.appendChild(termList);
        const pagination = document.createElement('div');
        pagination.className = 'd2tr-pagination';
        managePanel.appendChild(pagination);
        const manageClose = document.createElement('div');
        manageClose.style.cssText = 'text-align:right;margin-top:8px;';
        const btnCloseManage = document.createElement('button');
        btnCloseManage.className = 'd2tr-btn-cancel';
        btnCloseManage.textContent = '关闭';
        manageClose.appendChild(btnCloseManage);
        managePanel.appendChild(manageClose);
        body.appendChild(managePanel);

        // 事件
        let batchVisible = false;
        let manageVisible = false;

        btnAdd.addEventListener('click', () => {
            batchVisible = !batchVisible;
            batchPanel.style.display = batchVisible ? 'block' : 'none';
            if (batchVisible) {
                manageVisible = false;
                managePanel.style.display = 'none';
                batchArea.focus();
            }
        });
        btnCancel.addEventListener('click', () => {
            batchVisible = false;
            batchPanel.style.display = 'none';
        });
        btnSave.addEventListener('click', () => {
            const raw = batchArea.value;
            if (!raw) { showToast('内容为空', false); return; }
            const lines = raw.split(/\n+/);
            let added = 0;
            for (const line of lines) {
                const trimmed = line.trim();
                if (!trimmed) continue;
                const match = trimmed.match(/^(.+?)[=|]+(.+)$/);
                if (match) {
                    const en = match[1].trim();
                    const cn = match[2].trim();
                    if (en && cn) {
                        userTerms[en] = cn;
                        addVariants(termMap, en, cn);
                        added++;
                    }
                }
            }
            if (added) {
                GM_setValue(USER_TERMS_KEY, userTerms);
                updateTermCount();
                showToast(`已添加 ${added} 条自定义术语`);
                batchArea.value = '';
                batchVisible = false;
                batchPanel.style.display = 'none';
            } else {
                showToast('未检测到有效输入', false);
            }
        });

        btnManage.addEventListener('click', () => {
            manageVisible = !manageVisible;
            managePanel.style.display = manageVisible ? 'block' : 'none';
            if (manageVisible) {
                batchVisible = false;
                batchPanel.style.display = 'none';
                searchInput.value = searchTerm = '';
                renderUserTermsList(termList, pagination, searchInput);
            }
        });
        btnCloseManage.addEventListener('click', () => {
            manageVisible = false;
            managePanel.style.display = 'none';
        });

        searchInput.addEventListener('input', () => {
            searchTerm = searchInput.value.trim().toLowerCase();
            currentPage = 1;
            renderUserTermsList(termList, pagination, searchInput);
        });

        btnExport.addEventListener('click', exportUserTerms);
        btnImport.addEventListener('click', importUserTerms);

        section.appendChild(body);
        section._termList = termList;
        section._pagination = pagination;
        section._searchInput = searchInput;
        return section;
    }


    /* === 组装面板 === */
    const langSection = createLangSection();
    const modeSection = createModeSection();
    const termSection = createTermSection();

    panel.appendChild(langSection);
    panel.appendChild(modeSection);
    panel.appendChild(termSection);
    document.body.appendChild(panel);

    const modeButtons = modeSection._modeButtons;
    const termListEl = termSection._termList;
    const paginationEl = termSection._pagination;
    const searchInputEl = termSection._searchInput;

    /* === 模式按钮文本更新 === */
    function updateModeButtonsText() {
        const srcName = LANGUAGES[langSource];
        const tgtName = LANGUAGES[langTarget];
        const shortSrc = srcName.substring(0, 2);
        const shortTgt = tgtName.substring(0, 2);
        modeButtons[0].textContent = shortTgt;
        modeButtons[0].title = `将${srcName}术语替换为纯${tgtName}`;
        modeButtons[1].textContent = `${shortSrc}|${shortTgt}`;
        modeButtons[1].title = `替换为 "${srcName} | ${tgtName}" 组合`;
        modeButtons[2].textContent = `${shortTgt}(${shortSrc})`;
        modeButtons[2].title = `替换为 "${tgtName}(${srcName})" 组合`;
    }
    updateModeButtonsText();

    /* === 面板开关联动 === */
    function openPanel() {
        panelOpen = true;
        panel.classList.remove('closing');
        panel.classList.add('open');
        GM_setValue(PANEL_OPEN_KEY, true);
    }

    function closePanel() {
        panelOpen = false;
        panel.classList.add('closing');
        setTimeout(() => {
            panel.classList.remove('open', 'closing');
        }, 200);
        GM_setValue(PANEL_OPEN_KEY, false);
    }

    GM_registerMenuCommand('打开/关闭术语面板', () => {
        if (panelOpen) closePanel();
        else openPanel();
    });

    fab.addEventListener('click', () => {
        if (panelOpen) closePanel();
        else openPanel();
    });

    // 点击外部关闭面板
    document.addEventListener('click', (e) => {
        if (panelOpen && !panel.contains(e.target) && !fab.contains(e.target)) {
            closePanel();
        }
    });

    /* === 快捷键 === */
    document.addEventListener('keydown', (e) => {
        if (e.ctrlKey && e.altKey && e.key.toLowerCase() === 'k') {
            e.preventDefault();
            if (panelOpen) closePanel();
            else openPanel();
        }
    });

    /* === 暂停/恢复 === */
    function setPaused(paused) {
        isPaused = paused;
        GM_setValue(PAUSED_KEY, paused);
        fab.classList.toggle('paused', paused);
        if (paused && panelOpen) closePanel();
    }

    GM_registerMenuCommand(isPaused ? '▶ 恢复术语替换' : '⏸ 暂停术语替换', () => {
        setPaused(!isPaused);
        showToast(isPaused ? '术语替换已暂停' : '术语替换已恢复');
    });

    /* === 术语计数更新 === */
    function updateTermCount() {
        const countEl = document.getElementById('d2trTermCount');
        if (countEl) {
            countEl.textContent = termMap.size > 0 ? `${termMap.size} 条术语` : '未加载';
        }
    }

    /* === 数据加载 === */
    function fetchTerms() {
        return new Promise((resolve, reject) => {
            GM_xmlhttpRequest({
                method: 'GET',
                url: ITEM_LIST_URL,
                timeout: 15000,
                onload: (res) => {
                    if (res.status >= 200 && res.status < 300) {
                        try {
                            const data = JSON.parse(res.responseText);
                            if (data && data.data) resolve(data);
                            else reject(new Error('获取到空数据'));
                        } catch (e) {
                            reject(new Error('数据解析失败'));
                        }
                    } else {
                        reject(new Error(`HTTP ${res.status}`));
                    }
                },
                onerror: (err) => reject(new Error(`网络错误: ${err}`)),
                ontimeout: () => reject(new Error('请求超时（15秒）'))
            });
        });
    }

    async function initTerminology() {
        const cachedData = GM_getValue('cachedTerms');
        const cacheTime = GM_getValue('cacheTime', 0);
        try {
            if (!cachedData || Date.now() - cacheTime > 86400000 * CACHE_DAYS) {
                const freshData = await fetchTerms();
                termMap = buildTermMapFromData(freshData, langSource, langTarget);
                GM_setValue('cachedTerms', freshData);
                GM_setValue('cacheTime', Date.now());
            } else {
                termMap = buildTermMapFromData(cachedData, langSource, langTarget);
            }
            userTerms = GM_getValue(USER_TERMS_KEY, {});
            if (userTerms && typeof userTerms === 'object') {
                for (const [source, target] of Object.entries(userTerms)) {
                    addVariants(termMap, source, target);
                }
            }
            dataStatus = 'ready';
            statusDot.className = 'd2tr-status-dot ready';
        } catch (error) {
            console.error('术语表初始化失败:', error);
            dataStatus = 'error';
            statusDot.className = 'd2tr-status-dot error';
            if (cachedData) {
                termMap = buildTermMapFromData(cachedData, langSource, langTarget);
                showToast('术语表加载失败，已使用缓存数据', false);
            } else {
                showToast('术语表加载失败且无缓存可用', false);
            }
        }
        updateTermCount();
    }

    async function reloadTermMap() {
        const cachedData = GM_getValue('cachedTerms');
        if (cachedData) {
            termMap = buildTermMapFromData(cachedData, langSource, langTarget);
            userTerms = GM_getValue(USER_TERMS_KEY, {});
            if (userTerms && typeof userTerms === 'object') {
                for (const [source, target] of Object.entries(userTerms)) {
                    addVariants(termMap, source, target);
                }
            }
            updateTermCount();
            processedNodes = new WeakSet();
        }
    }

    async function clearCache() {
        try {
            GM_deleteValue('cachedTerms');
            GM_deleteValue('cacheTime');
            const freshData = await fetchTerms();
            termMap = buildTermMapFromData(freshData, langSource, langTarget);
            GM_setValue('cachedTerms', freshData);
            GM_setValue('cacheTime', Date.now());
            dataStatus = 'ready';
            statusDot.className = 'd2tr-status-dot ready';
            updateTermCount();
            showToast(`缓存已清除，已加载 ${termMap.size} 条术语`);
        } catch (error) {
            console.error('缓存清除失败:', error);
            dataStatus = 'error';
            statusDot.className = 'd2tr-status-dot error';
            showToast(`缓存清除失败：${error.message}`, false);
            termMap.clear();
            updateTermCount();
        }
    }

    /* === 替换逻辑 === */
    function applyAllRules() {
        if (isPaused) { showToast('术语替换已暂停，请先恢复', false); return; }
        const termRules = Array.from(termMap).map(([en, cn]) => {
            switch (currentMode) {
                case 1: return [en, cn];
                case 2: return [en, `${en} | ${cn}`];
                case 3: return [en, `${cn}（${en}）`];
                default: return [en, cn];
            }
        });
        const count = performReplace(termRules);
        if (count > 0) {
            showToast(`已替换 ${count} 个术语`);
        } else {
            showToast('未找到可替换的术语');
        }
    }

    function performReplace(rules) {
        if (!rules.length) return 0;
        const regex = buildRegex(rules);
        const lowerMap = new Map(rules.map(([k, v]) => [k.toLowerCase(), v]));
        const snapshot = [];
        const SKIP_TAGS = new Set(['SCRIPT', 'STYLE', 'CODE', 'PRE', 'TEXTAREA', 'NOSCRIPT']);

        const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null, false);
        while (walker.nextNode()) {
            const node = walker.currentNode;
            if (processedNodes.has(node)) continue;
            if (SKIP_TAGS.has(node.parentNode && node.parentNode.nodeName)) continue;
            const original = node.nodeValue;
            const replaced = original.replace(regex, (m) => lowerMap.get(m.toLowerCase()) ?? m);
            if (replaced !== original) {
                snapshot.push({ node, text: original });
                node.nodeValue = replaced;
                processedNodes.add(node);
            }
        }

        if (snapshot.length) {
            replacementHistory.push(snapshot);
            if (replacementHistory.length > HISTORY_LIMIT) replacementHistory.shift();
            document.getElementById('d2trBtnUndo').disabled = false;
        }
        return snapshot.length;
    }

    function buildRegex(rules) {
        const sortedKeys = [...new Set(rules.map(([k]) => k))]
            .sort((a, b) => b.length - a.length)
            .map(k => k.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
        return new RegExp(`\\b(${sortedKeys.join('|')})\\b`, 'gi');
    }

    function undoReplace() {
        if (replacementHistory.length) {
            const last = replacementHistory.pop();
            last.forEach(({ node, text }) => {
                if (node.parentNode) {
                    node.nodeValue = text;
                    processedNodes.delete(node);
                }
            });
            document.getElementById('d2trBtnUndo').disabled = !replacementHistory.length;
            showToast('已撤销上次替换');
        }
    }

    /* === 自定义术语管理 === */
    function renderUserTermsList(listContainer, pageControls, searchEl) {
        const allEntries = Object.entries(userTerms);
        const filtered = allEntries.filter(([en, cn]) =>
            en.toLowerCase().includes(searchTerm) || cn.toLowerCase().includes(searchTerm)
        );
        const totalPages = Math.max(1, Math.ceil(filtered.length / itemsPerPage));
        if (currentPage > totalPages) currentPage = totalPages;
        const startIdx = (currentPage - 1) * itemsPerPage;
        const pageEntries = filtered.slice(startIdx, startIdx + itemsPerPage);

        clearElement(listContainer);
        if (!pageEntries.length) {
            const empty = document.createElement('div');
            empty.style.cssText = 'text-align:center;color:var(--destiny-text-muted);padding:16px;font-size:12px;';
            empty.textContent = '无匹配结果';
            listContainer.appendChild(empty);
        } else {
            for (const [en, cn] of pageEntries) {
                const row = document.createElement('div');
                row.className = 'd2tr-term-item';
                const textSpan = document.createElement('span');
                textSpan.className = 'd2tr-term-text';
                const sourceSpan = document.createElement('span');
                sourceSpan.style.color = 'var(--destiny-tech)';
                sourceSpan.textContent = en;
                const arrowSpan = document.createElement('span');
                arrowSpan.style.color = 'var(--destiny-text-muted)';
                arrowSpan.textContent = ' → ';
                const targetSpan = document.createElement('span');
                targetSpan.style.color = 'var(--destiny-accent)';
                targetSpan.textContent = cn;
                textSpan.appendChild(sourceSpan);
                textSpan.appendChild(arrowSpan);
                textSpan.appendChild(targetSpan);
                const delBtn = document.createElement('button');
                delBtn.className = 'd2tr-term-del';
                delBtn.textContent = '×';
                delBtn.addEventListener('click', () => {
                    deleteUserTerm(en);
                    renderUserTermsList(listContainer, pageControls, searchEl);
                });
                row.appendChild(textSpan);
                row.appendChild(delBtn);
                listContainer.appendChild(row);
            }
        }

        clearElement(pageControls);
        if (totalPages > 1) {
            const mkBtn = (txt, dis, fn) => {
                const b = document.createElement('button');
                b.textContent = txt;
                b.disabled = dis;
                b.addEventListener('click', fn);
                return b;
            };
            pageControls.appendChild(mkBtn('上一页', currentPage === 1, () => {
                if (currentPage > 1) { currentPage--; renderUserTermsList(listContainer, pageControls, searchEl); }
            }));
            const info = document.createElement('span');
            info.textContent = `${currentPage} / ${totalPages}`;
            pageControls.appendChild(info);
            pageControls.appendChild(mkBtn('下一页', currentPage === totalPages, () => {
                if (currentPage < totalPages) { currentPage++; renderUserTermsList(listContainer, pageControls, searchEl); }
            }));
        }
    }

    function deleteUserTerm(en) {
        if (!userTerms[en]) return;
        if (!confirm(`确定删除术语：${en} → ${userTerms[en]}？`)) return;
        delete userTerms[en];
        GM_setValue(USER_TERMS_KEY, userTerms);
        reloadTermMap();
        showToast(`已删除术语：${en}`);
    }

    function exportUserTerms() {
        const blob = new Blob([JSON.stringify(userTerms, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'destiny2_custom_terms.json';
        a.click();
        URL.revokeObjectURL(url);
        showToast('已导出自定义术语');
    }

    function importUserTerms() {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = 'application/json';
        input.onchange = () => {
            if (!input.files.length) return;
            const file = input.files[0];
            const reader = new FileReader();
            reader.onload = () => {
                try {
                    const data = JSON.parse(reader.result);
                    if (data && typeof data === 'object') {
                        Object.entries(data).forEach(([en, cn]) => {
                            userTerms[en] = cn;
                            addVariants(termMap, en, cn);
                        });
                        GM_setValue(USER_TERMS_KEY, userTerms);
                        updateTermCount();
                        showToast(`已导入 ${Object.keys(data).length} 条自定义术语`);
                    } else {
                        showToast('JSON 格式不正确', false);
                    }
                } catch (e) {
                    showToast('解析失败：' + e.message, false);
                }
            };
            reader.readAsText(file);
        };
        input.click();
    }

    /* === 初始化 === */
    initTerminology().then(() => {
        // 首次安装引导
        if (!GM_getValue(WELCOME_KEY)) {
            fab.classList.add('pulse');
            setTimeout(() => {
                fab.classList.remove('pulse');
            }, 6000);
            setTimeout(() => showToast('点击右下角按钮打开 Destiny 2 术语工具'), 500);
            GM_setValue(WELCOME_KEY, true);
        }

        // 恢复上次面板状态
        if (GM_getValue(PANEL_OPEN_KEY, false)) {
            openPanel();
        }
    });

})();
