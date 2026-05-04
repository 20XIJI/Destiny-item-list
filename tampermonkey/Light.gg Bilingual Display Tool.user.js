// ==UserScript==
// @name                Light.gg Bilingual Display Tool
// @version             6.0
// @description         命运2工具网站 light.gg 的增强脚本 - 支持三语言切换 (EN/简中/繁中)
// @author              Eliver
// @match               https://www.light.gg/*
// @grant               GM_setValue
// @grant               GM_getValue
// @grant               GM_addStyle
// @license             MIT
// @namespace https://greasyfork.org/users/1267935
// @downloadURL https://update.greasyfork.org/scripts/512095/Lightgg%20Bilingual%20Display%20Tool.user.js
// @updateURL https://update.greasyfork.org/scripts/512095/Lightgg%20Bilingual%20Display%20Tool.meta.js
// ==/UserScript==

(function () {
    'use strict';

    const CACHE_KEY = 'lightgg_term_map';
    const LAST_UPDATE_KEY = 'lightgg_last_update';
    const TOOLTIP_LANG_SETTING_KEY = 'lightgg_tooltip_lang_setting';
    const BILINGUAL_LANG_KEY = 'lightgg_bilingual_lang';
    const PAUSED_KEY = 'lgg_paused';
    const WELCOME_KEY = 'lgg_welcome_v6_panel';
    const PANEL_OPEN_KEY = 'lgg_panel_open';
    const TERM_MAP_URL = 'https://20xiji.github.io/Destiny-item-list/term-map.json';

    const LANGUAGES = {
        'en': 'English',
        'zh-chs': '简体中文',
        'zh-cht': '繁體中文'
    };

    let setTooltipLang = GM_getValue(TOOLTIP_LANG_SETTING_KEY, true);
    let bilingualLang = GM_getValue(BILINGUAL_LANG_KEY, 'zh-chs');
    let isPaused = GM_getValue(PAUSED_KEY, false);
    let panelOpen = false;
    let originalLang;
    let dataStatus = 'loading';

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

        @keyframes lgg-fadein {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        @keyframes lgg-fadeout {
            from { opacity: 1; transform: translateY(0); }
            to { opacity: 0; transform: translateY(10px); }
        }
        @keyframes lgg-pulse {
            0%, 100% { box-shadow: 0 4px 12px rgba(0,0,0,0.3), 0 0 0 0 rgba(240, 178, 50, 0.5); }
            50% { box-shadow: 0 4px 12px rgba(0,0,0,0.3), 0 0 0 10px rgba(240, 178, 50, 0); }
        }

        /* 悬浮按钮 */
        .lgg-fab {
            position: fixed;
            bottom: 20px;
            right: 20px;
            width: 48px;
            height: 48px;
            border-radius: 50%;
            border: none;
            background: linear-gradient(135deg, var(--destiny-accent), #e6a020);
            color: var(--destiny-bg);
            font-size: 18px;
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
        .lgg-fab:hover {
            transform: scale(1.1) rotate(90deg);
            box-shadow: 0 6px 20px rgba(240, 178, 50, 0.4);
        }
        .lgg-fab.paused {
            background: rgba(255, 255, 255, 0.15);
            color: var(--destiny-text-muted);
        }
        .lgg-fab.paused:hover {
            background: rgba(255, 255, 255, 0.25);
            transform: scale(1.1);
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        }
        .lgg-fab.pulse {
            animation: lgg-pulse 1.5s ease-in-out 4;
        }

        /* 状态指示灯 */
        .lgg-status-dot {
            position: absolute;
            top: -2px;
            right: -2px;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            border: 2px solid var(--destiny-panel);
            transition: background 0.3s ease;
        }
        .lgg-status-dot.loading { background: var(--destiny-accent); }
        .lgg-status-dot.ready { background: var(--destiny-success); }
        .lgg-status-dot.error { background: var(--destiny-danger); }

        /* 面板 */
        .lgg-panel {
            position: fixed;
            bottom: 76px;
            right: 20px;
            width: 280px;
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
        .lgg-panel.open {
            display: block;
            animation: lgg-fadein 0.25s ease-out;
        }
        .lgg-panel.closing {
            animation: lgg-fadeout 0.2s ease-in forwards;
        }

        /* 面板头部 */
        .lgg-header {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 14px 16px;
            border-bottom: 1px solid var(--destiny-border);
        }
        .lgg-header-icon {
            color: var(--destiny-accent);
            font-size: 16px;
        }
        .lgg-header-title {
            font-weight: 600;
            font-size: 14px;
            background: linear-gradient(135deg, var(--destiny-accent), var(--destiny-tech));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }

        /* 选项 */
        .lgg-option {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin: 12px 16px;
            padding: 10px 12px;
            background: rgba(0, 0, 0, 0.2);
            border-radius: var(--destiny-radius-sm);
            border: 1px solid var(--destiny-border);
        }
        .lgg-option-label {
            display: flex;
            flex-direction: column;
            gap: 3px;
            cursor: pointer;
            flex: 1;
        }
        .lgg-option-title {
            font-weight: 500;
            color: var(--destiny-text);
            font-size: 13px;
        }
        .lgg-option-desc {
            font-size: 11px;
            color: var(--destiny-text-muted);
        }

        /* 开关 */
        .lgg-switch {
            position: relative;
            width: 44px;
            height: 22px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 11px;
            cursor: pointer;
            transition: background 0.3s ease;
            flex-shrink: 0;
        }
        .lgg-switch.active {
            background: linear-gradient(135deg, var(--destiny-accent), #e6a020);
        }
        .lgg-switch-handle {
            position: absolute;
            top: 2px;
            left: 2px;
            width: 18px;
            height: 18px;
            background: white;
            border-radius: 50%;
            transition: left 0.3s ease;
            box-shadow: 0 1px 3px rgba(0,0,0,0.2);
        }
        .lgg-switch.active .lgg-switch-handle {
            left: 24px;
        }

        /* 语言选择 */
        .lgg-lang-select {
            background: rgba(0, 0, 0, 0.3);
            color: var(--destiny-text);
            border: 1px solid var(--destiny-border);
            border-radius: 6px;
            padding: 6px 10px;
            font-size: 12px;
            cursor: pointer;
            min-width: 100px;
            transition: border-color 0.2s ease;
        }
        .lgg-lang-select:focus {
            outline: none;
            border-color: var(--destiny-accent);
        }

        /* 更新按钮 */
        .lgg-update-btn {
            width: calc(100% - 32px);
            margin: 12px 16px;
            background: linear-gradient(135deg, var(--destiny-tech), #00b8d4);
            border: none;
            color: var(--destiny-bg);
            padding: 10px;
            border-radius: var(--destiny-radius-sm);
            cursor: pointer;
            font-size: 13px;
            font-weight: 600;
            transition: all 0.2s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 6px;
        }
        .lgg-update-btn:hover {
            transform: translateY(-1px);
            box-shadow: 0 3px 10px rgba(0, 212, 255, 0.3);
        }
        .lgg-update-btn:disabled {
            opacity: 0.7;
            cursor: not-allowed;
            transform: none;
            box-shadow: none;
        }

        /* 状态栏 */
        .lgg-status {
            display: flex;
            align-items: center;
            gap: 6px;
            margin: 0 16px 12px;
            padding: 8px 12px;
            background: rgba(76, 175, 80, 0.1);
            border-radius: var(--destiny-radius-sm);
            font-size: 11px;
            color: var(--destiny-success);
            border: 1px solid rgba(76, 175, 80, 0.2);
        }
        .lgg-status.error {
            background: rgba(231, 76, 60, 0.1);
            color: var(--destiny-danger);
            border-color: rgba(231, 76, 60, 0.2);
        }
        .lgg-status.warning {
            background: rgba(240, 178, 50, 0.1);
            color: var(--destiny-accent);
            border-color: rgba(240, 178, 50, 0.2);
        }

        /* 通知 */
        .lgg-notification {
            position: fixed;
            bottom: 76px;
            right: 80px;
            background: var(--destiny-panel);
            color: var(--destiny-text);
            padding: 10px 16px;
            border-radius: var(--destiny-radius-sm);
            font-size: 13px;
            font-weight: 500;
            box-shadow: var(--destiny-shadow);
            z-index: 10000;
            opacity: 0;
            transition: all 0.3s ease;
            pointer-events: none;
            max-width: 280px;
            word-wrap: break-word;
            border: 1px solid var(--destiny-border);
            backdrop-filter: blur(10px);
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        }
        .lgg-notification.show { opacity: 1; }
        .lgg-notification.success { border-left: 3px solid var(--destiny-success); }
        .lgg-notification.error { border-left: 3px solid var(--destiny-danger); }
        .lgg-notification.warning { border-left: 3px solid var(--destiny-accent); }
        .lgg-notification.info { border-left: 3px solid var(--destiny-tech); }
    `);

    /* === 性能优化 === */
    let cachedTermMap = null;
    let itemLookupMap = new Map();
    let processedElements = new WeakSet();
    let isDataReady = false;
    const ORIGINAL_TEXT_KEY = 'lggOriginalText';

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

    /* === 通知系统 === */
    function createNotification(message, type = 'info', duration = 2500) {
        const notification = document.createElement('div');
        notification.className = `lgg-notification ${type}`;
        notification.textContent = message;
        document.body.appendChild(notification);
        requestAnimationFrame(() => notification.classList.add('show'));
        setTimeout(() => {
            notification.classList.remove('show');
            setTimeout(() => notification.remove(), 300);
        }, duration);
    }

    /* === 数据处理 === */
    function buildLookupMap(termMapData) {
        itemLookupMap.clear();
        const buckets = termMapData.data || termMapData;
        for (const bucketName of Object.keys(buckets)) {
            const bucket = buckets[bucketName];
            for (const hashKey of Object.keys(bucket)) {
                const entry = bucket[hashKey];
                if (entry.en && entry[bilingualLang]) {
                    itemLookupMap.set(entry.en.toLowerCase(), entry[bilingualLang]);
                    itemLookupMap.set(entry[bilingualLang].toLowerCase(), entry.en);
                }
            }
        }
        console.log(`[Light.gg 双语工具] 构建查找映射表完成，包含 ${itemLookupMap.size} 个条目`);
    }

    function parseCachedTermMap(cached) {
        if (!cached) return { data: {} };
        try {
            return JSON.parse(cached);
        } catch (error) {
            console.warn('[Light.gg 双语工具] 缓存解析失败，已忽略缓存:', error);
            return { data: {} };
        }
    }

    function rebuildLookupMap() {
        const cached = GM_getValue(CACHE_KEY);
        if (cached) {
            const data = parseCachedTermMap(cached);
            buildLookupMap(data);
            processedElements = new WeakSet();
            optimizedTransformReviewItems();
        }
    }

    function getOriginalText(element) {
        if (element.dataset && element.dataset[ORIGINAL_TEXT_KEY]) {
            return element.dataset[ORIGINAL_TEXT_KEY];
        }
        return element.textContent.trim().split(' | ')[0].trim();
    }

    async function loadItemList() {
        const now = new Date().toDateString();
        const lastUpdate = GM_getValue(LAST_UPDATE_KEY, '');
        if (lastUpdate !== now) {
            try {
                const response = await fetch(TERM_MAP_URL);
                const data = await response.json();
                GM_setValue(CACHE_KEY, JSON.stringify(data));
                GM_setValue(LAST_UPDATE_KEY, now);
                cachedTermMap = data;
            } catch (error) {
                console.error('[Light.gg 双语工具] 更新失败:', error);
                const cached = GM_getValue(CACHE_KEY);
                cachedTermMap = parseCachedTermMap(cached);
                createNotification('数据更新失败，已使用缓存数据', 'warning');
            }
        } else {
            const cached = GM_getValue(CACHE_KEY);
            cachedTermMap = parseCachedTermMap(cached);
        }
        buildLookupMap(cachedTermMap);
        isDataReady = true;
        dataStatus = 'ready';
        statusDot.className = 'lgg-status-dot ready';
        console.log(`[Light.gg 双语工具] 数据加载完成，包含 ${itemLookupMap.size / 2} 个术语`);
        optimizedTransformReviewItems();
        return cachedTermMap;
    }

    /* === DOM 处理 === */
    function processElements(elements) {
        const newElements = Array.from(elements);
        if (newElements.length === 0) return;
        let processedCount = 0;
        newElements.forEach(element => {
            const originalText = getOriginalText(element);
            const translatedName = itemLookupMap.get(originalText.toLowerCase());
            if (translatedName) {
                const otherText = translatedName;
                if (otherText && otherText !== originalText) {
                    if (element.dataset) element.dataset[ORIGINAL_TEXT_KEY] = originalText;
                    element.textContent = `${originalText} | ${otherText}`;
                    if (!processedElements.has(element)) {
                        processedElements.add(element);
                        processedCount++;
                    }
                }
            } else if (element.dataset && element.dataset[ORIGINAL_TEXT_KEY]) {
                element.textContent = originalText;
                delete element.dataset[ORIGINAL_TEXT_KEY];
                processedElements.delete(element);
            }
        });
        if (processedCount > 0) {
            console.log(`[Light.gg 双语工具] 处理了 ${processedCount} 个新元素`);
        }
    }

    function optimizedTransformReviewItems() {
        if (isPaused) return;
        const elements = document.querySelectorAll('.item-name h2, .item-name a, .key-perk strong');
        if (isDataReady) {
            if (itemLookupMap.size > 0) processElements(elements);
            return;
        }
        if (typeof itemListPromise === 'undefined') return;
        itemListPromise.then(() => processElements(elements));
    }

    /* === XHR 拦截 === */
    const originalOpen = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function() {
        const url = arguments[1];
        if (/api\.light\.gg\/items\/\d*\/?/.test(url)) {
            this.addEventListener('load', throttle(optimizedTransformReviewItems, 200));
        }
        originalOpen.apply(this, arguments);
    };

    /* === MutationObserver === */
    const observer = new MutationObserver(throttle((mutations) => {
        if (isPaused) return;
        let shouldProcess = false;
        for (const mutation of mutations) {
            if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
                for (const node of mutation.addedNodes) {
                    if (node.nodeType === Node.ELEMENT_NODE) {
                        if (node.matches?.('.item-name, .key-perk') ||
                            node.querySelector?.('.item-name, .key-perk')) {
                            shouldProcess = true;
                            break;
                        }
                    }
                }
                if (shouldProcess) break;
            }
        }
        if (shouldProcess) optimizedTransformReviewItems();
    }, 200));

    observer.observe(document.body, { childList: true, subtree: true });

    /* === 创建悬浮按钮 === */
    const fab = document.createElement('button');
    fab.className = 'lgg-fab' + (isPaused ? ' paused' : '');
    fab.innerHTML = '⟐';
    fab.title = 'Light.gg 双语工具';

    const statusDot = document.createElement('div');
    statusDot.className = 'lgg-status-dot loading';
    fab.appendChild(statusDot);

    document.body.appendChild(fab);

    /* === 创建面板 === */
    const panel = document.createElement('div');
    panel.className = 'lgg-panel';

    // 头部
    const header = document.createElement('div');
    header.className = 'lgg-header';
    header.innerHTML = '<span class="lgg-header-icon">⟐</span><span class="lgg-header-title">Light.gg 双语工具</span>';
    panel.appendChild(header);

    // 中文 Perk 提示开关
    const tooltipOption = document.createElement('div');
    tooltipOption.className = 'lgg-option';
    const tooltipLabel = document.createElement('label');
    tooltipLabel.className = 'lgg-option-label';
    tooltipLabel.innerHTML = '<span class="lgg-option-title">中文 Perk 提示</span><span class="lgg-option-desc">将 Perk 提示框显示为中文</span>';
    const tooltipSwitch = document.createElement('div');
    tooltipSwitch.className = `lgg-switch ${setTooltipLang ? 'active' : ''}`;
    const tooltipHandle = document.createElement('div');
    tooltipHandle.className = 'lgg-switch-handle';
    tooltipSwitch.appendChild(tooltipHandle);
    tooltipOption.appendChild(tooltipLabel);
    tooltipOption.appendChild(tooltipSwitch);
    panel.appendChild(tooltipOption);

    tooltipSwitch.addEventListener('click', () => {
        setTooltipLang = !setTooltipLang;
        GM_setValue(TOOLTIP_LANG_SETTING_KEY, setTooltipLang);
        if (setTooltipLang) {
            if (typeof lggTooltip !== 'undefined') lggTooltip.lang = bilingualLang;
            tooltipSwitch.classList.add('active');
            createNotification(`已启用 ${LANGUAGES[bilingualLang]} Perk 提示`, 'success');
        } else {
            if (typeof lggTooltip !== 'undefined' && originalLang) lggTooltip.lang = originalLang;
            tooltipSwitch.classList.remove('active');
            createNotification('已关闭双语 Perk 提示', 'info');
        }
    });

    // 双语语言选择
    const langOption = document.createElement('div');
    langOption.className = 'lgg-option';
    const langLabel = document.createElement('label');
    langLabel.className = 'lgg-option-label';
    langLabel.innerHTML = '<span class="lgg-option-title">双语显示语言</span><span class="lgg-option-desc">选择物品名显示的第二种语言</span>';
    const langSelect = document.createElement('select');
    langSelect.className = 'lgg-lang-select';
    for (const [code, name] of Object.entries(LANGUAGES)) {
        if (code === 'en') continue;
        const option = document.createElement('option');
        option.value = code;
        option.textContent = name;
        if (code === bilingualLang) option.selected = true;
        langSelect.appendChild(option);
    }
    langSelect.addEventListener('change', () => {
        bilingualLang = langSelect.value;
        GM_setValue(BILINGUAL_LANG_KEY, bilingualLang);
        rebuildLookupMap();
        createNotification(`双语语言已切换为 ${LANGUAGES[bilingualLang]}`, 'success');
    });
    langOption.appendChild(langLabel);
    langOption.appendChild(langSelect);
    panel.appendChild(langOption);

    // 更新按钮
    const updateButton = document.createElement('button');
    updateButton.className = 'lgg-update-btn';
    updateButton.innerHTML = '更新数据';
    panel.appendChild(updateButton);

    // 状态栏
    const statusIndicator = document.createElement('div');
    statusIndicator.className = 'lgg-status';
    statusIndicator.textContent = '数据已加载';
    panel.appendChild(statusIndicator);

    // 数据加载
    let itemListPromise = loadItemList();

    // 更新按钮事件
    updateButton.addEventListener('click', async () => {
        updateButton.disabled = true;
        updateButton.textContent = '更新中...';
        statusIndicator.textContent = '正在更新数据...';
        statusIndicator.className = 'lgg-status warning';
        try {
            GM_setValue(CACHE_KEY, '');
            GM_setValue(LAST_UPDATE_KEY, '');
            cachedTermMap = null;
            isDataReady = false;
            itemListPromise = loadItemList();
            await itemListPromise;
            optimizedTransformReviewItems();
            createNotification('数据更新成功！', 'success');
            statusIndicator.textContent = '数据已更新';
            statusIndicator.className = 'lgg-status';
        } catch (error) {
            createNotification('更新失败：' + error.message, 'error');
            statusIndicator.textContent = '更新失败';
            statusIndicator.className = 'lgg-status error';
        } finally {
            updateButton.disabled = false;
            updateButton.textContent = '更新数据';
        }
    });

    document.body.appendChild(panel);

    /* === 面板开关 === */
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

    fab.addEventListener('click', () => {
        if (panelOpen) closePanel();
        else openPanel();
    });

    document.addEventListener('click', (e) => {
        if (panelOpen && !panel.contains(e.target) && !fab.contains(e.target)) {
            closePanel();
        }
    });

    /* === 快捷键 === */
    document.addEventListener('keydown', (e) => {
        if (e.ctrlKey && e.altKey && e.key.toLowerCase() === 'l') {
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

    GM_registerMenuCommand(isPaused ? '▶ 恢复双语显示' : '⏸ 暂停双语显示', () => {
        setPaused(!isPaused);
        createNotification(isPaused ? '双语显示已暂停' : '双语显示已恢复', 'info');
    });

    /* === 初始化 === */
    function initPageBehavior() {
        if (typeof lggTooltip !== 'undefined') {
            originalLang = lggTooltip.lang;
            if (setTooltipLang) lggTooltip.lang = bilingualLang;
        }

        // 首次安装引导
        if (!GM_getValue(WELCOME_KEY)) {
            fab.classList.add('pulse');
            setTimeout(() => fab.classList.remove('pulse'), 6000);
            setTimeout(() => createNotification('点击右下角按钮打开 Light.gg 双语工具', 'info', 3000), 500);
            GM_setValue(WELCOME_KEY, true);
        }

        // 恢复上次面板状态
        if (GM_getValue(PANEL_OPEN_KEY, false)) {
            openPanel();
        }

        const reviewTab = document.getElementById('review-tab');
        reviewTab?.click();
        optimizedTransformReviewItems();
    }

    if (document.readyState === 'loading') {
        window.addEventListener('load', initPageBehavior);
    } else {
        initPageBehavior();
    }

})();
