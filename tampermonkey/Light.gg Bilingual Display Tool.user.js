// ==UserScript==
// @name                Light.gg Bilingual Display Tool
// @version             4.0
// @description         命运2工具网站 light.gg 的增强脚本，将物品名显示为双语，并可选择性设置tooltip语言。
// @author              Eliver
// @match               https://www.light.gg/*
// @grant               GM_setValue
// @grant               GM_getValue
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
    const TERM_MAP_URL = 'https://20xiji.github.io/Destiny-item-list/term-map.json';

    let setTooltipLang = GM_getValue(TOOLTIP_LANG_SETTING_KEY, true);
    let originalLang;

    // 性能优化：缓存和查找映射
    let cachedTermMap = null;
    let itemLookupMap = new Map(); // en → zh-chs, zh-chs → en
    let processedElements = new WeakSet();
    let isDataReady = false;

    // 性能优化：节流函数替代防抖
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

    // 从 term-map.json 构建双向查找映射表
    function buildLookupMap(termMapData) {
        itemLookupMap.clear();
        const buckets = termMapData.data || termMapData;

        for (const bucketName of Object.keys(buckets)) {
            const bucket = buckets[bucketName];
            for (const hashKey of Object.keys(bucket)) {
                const entry = bucket[hashKey];
                if (entry.en && entry['zh-chs']) {
                    itemLookupMap.set(entry.en.toLowerCase(), entry['zh-chs']);
                    itemLookupMap.set(entry['zh-chs'].toLowerCase(), entry.en);
                }
            }
        }

        console.log(`构建查找映射表完成，包含 ${itemLookupMap.size} 个条目`);
    }

    // 创建通知系统
    function createNotification(message, type = 'info', duration = 3000) {
        const notification = document.createElement('div');
        notification.className = 'lightgg-notification';
        notification.textContent = message;

        const colors = {
            success: '#4CAF50',
            error: '#f44336',
            info: '#2196F3',
            warning: '#ff9800'
        };

        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: ${colors[type]};
            color: white;
            padding: 12px 20px;
            border-radius: 8px;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            font-size: 14px;
            font-weight: 500;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            z-index: 10000;
            transform: translateX(100%);
            transition: transform 0.3s ease;
            max-width: 300px;
            word-wrap: break-word;
        `;

        document.body.appendChild(notification);

        setTimeout(() => {
            notification.style.transform = 'translateX(0)';
        }, 10);

        setTimeout(() => {
            notification.style.transform = 'translateX(100%)';
            setTimeout(() => notification.remove(), 300);
        }, duration);
    }

    function createSettingsUI() {
        const container = document.createElement('div');
        container.className = 'lightgg-settings-container';
        container.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 9999;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        `;

        const toggleButton = document.createElement('button');
        toggleButton.className = 'lightgg-toggle-btn';
        toggleButton.innerHTML = '⚙️';
        toggleButton.title = 'Light.gg 双语工具设置';
        toggleButton.style.cssText = `
            width: 44px;
            height: 44px;
            border-radius: 50%;
            border: none;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            font-size: 18px;
            cursor: pointer;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            justify-content: center;
        `;

        const settingsPanel = document.createElement('div');
        settingsPanel.className = 'lightgg-settings-panel';
        settingsPanel.style.cssText = `
            position: absolute;
            top: 54px;
            right: 0;
            background: white;
            border-radius: 12px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.12);
            padding: 20px;
            min-width: 280px;
            transform: translateY(-10px);
            opacity: 0;
            visibility: hidden;
            transition: all 0.3s ease;
            border: 1px solid #e1e5e9;
        `;

        const title = document.createElement('h3');
        title.style.cssText = `
            margin: 0 0 16px 0;
            font-size: 16px;
            font-weight: 600;
            color: #1a1a1a;
            display: flex;
            align-items: center;
            gap: 8px;
        `;
        title.innerHTML = '🌐 Light.gg 双语工具';

        const langOption = document.createElement('div');
        langOption.style.cssText = `
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 16px;
            padding: 12px;
            background: #f8f9fa;
            border-radius: 8px;
        `;

        const langLabel = document.createElement('label');
        langLabel.style.cssText = `
            display: flex;
            flex-direction: column;
            gap: 4px;
            cursor: pointer;
            flex: 1;
        `;

        const langTitle = document.createElement('span');
        langTitle.textContent = '中文 Perk 提示';
        langTitle.style.cssText = `
            font-weight: 500;
            color: #1a1a1a;
            font-size: 14px;
        `;

        const langDesc = document.createElement('span');
        langDesc.textContent = '将Perk提示框显示为中文';
        langDesc.style.cssText = `
            font-size: 12px;
            color: #6c757d;
        `;

        const toggleSwitch = document.createElement('div');
        toggleSwitch.className = 'lightgg-switch';
        toggleSwitch.style.cssText = `
            position: relative;
            width: 48px;
            height: 24px;
            background: ${setTooltipLang ? '#007bff' : '#dee2e6'};
            border-radius: 12px;
            cursor: pointer;
            transition: background 0.3s ease;
        `;

        const switchHandle = document.createElement('div');
        switchHandle.style.cssText = `
            position: absolute;
            top: 2px;
            left: ${setTooltipLang ? '26px' : '2px'};
            width: 20px;
            height: 20px;
            background: white;
            border-radius: 50%;
            transition: left 0.3s ease;
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        `;

        toggleSwitch.appendChild(switchHandle);
        langLabel.appendChild(langTitle);
        langLabel.appendChild(langDesc);
        langOption.appendChild(langLabel);
        langOption.appendChild(toggleSwitch);

        const updateButton = document.createElement('button');
        updateButton.innerHTML = '🔄 更新数据';
        updateButton.style.cssText = `
            width: 100%;
            background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
            border: none;
            color: white;
            padding: 12px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 500;
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
        `;

        const statusIndicator = document.createElement('div');
        statusIndicator.style.cssText = `
            display: flex;
            align-items: center;
            gap: 8px;
            margin-top: 12px;
            padding: 8px 12px;
            background: #e8f5e8;
            border-radius: 6px;
            font-size: 12px;
            color: #155724;
        `;
        statusIndicator.innerHTML = '✅ 数据已加载';

        let isOpen = false;

        toggleButton.addEventListener('click', () => {
            isOpen = !isOpen;
            if (isOpen) {
                settingsPanel.style.opacity = '1';
                settingsPanel.style.visibility = 'visible';
                settingsPanel.style.transform = 'translateY(0)';
                toggleButton.style.transform = 'rotate(180deg)';
            } else {
                settingsPanel.style.opacity = '0';
                settingsPanel.style.visibility = 'hidden';
                settingsPanel.style.transform = 'translateY(-10px)';
                toggleButton.style.transform = 'rotate(0deg)';
            }
        });

        document.addEventListener('click', (e) => {
            if (!container.contains(e.target) && isOpen) {
                isOpen = false;
                settingsPanel.style.opacity = '0';
                settingsPanel.style.visibility = 'hidden';
                settingsPanel.style.transform = 'translateY(-10px)';
                toggleButton.style.transform = 'rotate(0deg)';
            }
        });

        toggleSwitch.addEventListener('click', () => {
            setTooltipLang = !setTooltipLang;
            GM_setValue(TOOLTIP_LANG_SETTING_KEY, setTooltipLang);

            if (setTooltipLang) {
                lggTooltip.lang = "zh-chs";
                toggleSwitch.style.background = '#007bff';
                switchHandle.style.left = '26px';
                createNotification('已启用中文 Perk 提示', 'success');
            } else {
                lggTooltip.lang = originalLang;
                toggleSwitch.style.background = '#dee2e6';
                switchHandle.style.left = '2px';
                createNotification('已关闭中文 Perk 提示', 'info');
            }
        });

        updateButton.addEventListener('click', async () => {
            updateButton.disabled = true;
            updateButton.innerHTML = '⏳ 更新中...';
            updateButton.style.opacity = '0.7';
            statusIndicator.innerHTML = '🔄 正在更新数据...';
            statusIndicator.style.background = '#fff3cd';
            statusIndicator.style.color = '#856404';

            try {
                GM_setValue(CACHE_KEY, '');
                GM_setValue(LAST_UPDATE_KEY, '');
                cachedTermMap = null;
                isDataReady = false;
                itemListPromise = loadItemList();
                await itemListPromise;
                optimizedTransformReviewItems();

                createNotification('数据更新成功！', 'success');
                statusIndicator.innerHTML = '✅ 数据已更新';
                statusIndicator.style.background = '#e8f5e8';
                statusIndicator.style.color = '#155724';
            } catch (error) {
                createNotification('更新失败：' + error.message, 'error');
                statusIndicator.innerHTML = '❌ 更新失败';
                statusIndicator.style.background = '#f8d7da';
                statusIndicator.style.color = '#721c24';
            } finally {
                updateButton.disabled = false;
                updateButton.innerHTML = '🔄 更新数据';
                updateButton.style.opacity = '1';
            }
        });

        settingsPanel.appendChild(title);
        settingsPanel.appendChild(langOption);
        settingsPanel.appendChild(updateButton);
        settingsPanel.appendChild(statusIndicator);

        container.appendChild(toggleButton);
        container.appendChild(settingsPanel);
        document.body.appendChild(container);

        toggleButton.addEventListener('mouseenter', () => {
            toggleButton.style.transform = 'scale(1.1)';
            toggleButton.style.boxShadow = '0 6px 20px rgba(0,0,0,0.25)';
        });

        toggleButton.addEventListener('mouseleave', () => {
            if (!isOpen) {
                toggleButton.style.transform = 'scale(1)';
                toggleButton.style.boxShadow = '0 4px 12px rgba(0,0,0,0.15)';
            }
        });

        updateButton.addEventListener('mouseenter', () => {
            if (!updateButton.disabled) {
                updateButton.style.transform = 'translateY(-1px)';
                updateButton.style.boxShadow = '0 4px 12px rgba(40, 167, 69, 0.3)';
            }
        });

        updateButton.addEventListener('mouseleave', () => {
            updateButton.style.transform = 'translateY(0)';
            updateButton.style.boxShadow = 'none';
        });
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
                console.error('更新失败:', error);
                const cached = GM_getValue(CACHE_KEY);
                cachedTermMap = cached ? JSON.parse(cached) : { data: {} };
                createNotification('数据更新失败，已使用缓存数据', 'warning');
            }
        } else {
            const cached = GM_getValue(CACHE_KEY);
            cachedTermMap = cached ? JSON.parse(cached) : { data: {} };
        }

        buildLookupMap(cachedTermMap);
        isDataReady = true;
        return cachedTermMap;
    }

    let itemListPromise = loadItemList();

    // 性能优化：只处理新元素，使用O(1)查找
    function processElements(elements, lang) {
        const newElements = Array.from(elements).filter(el => !processedElements.has(el));

        if (newElements.length === 0) return;

        newElements.forEach(element => {
            const originalText = element.textContent.trim();
            const translatedName = itemLookupMap.get(originalText.toLowerCase());

            if (translatedName) {
                const otherText = translatedName;
                if (otherText && otherText !== originalText) {
                    element.textContent = `${originalText} | ${otherText}`;
                    processedElements.add(element);
                }
            }
        });

        console.log(`处理了 ${newElements.length} 个新元素`);
    }

    function optimizedTransformReviewItems() {
        const elements = document.querySelectorAll('.item-name h2, .item-name a, .key-perk strong');
        const lang = window.location.pathname.includes('/zh-chs/') ? 'zh-chs' : 'en';

        if (isDataReady && itemLookupMap.size > 0) {
            processElements(elements, lang);
        } else {
            itemListPromise.then(() => {
                processElements(elements, lang);
            });
        }
    }

    // 性能优化：XHR拦截使用节流
    const originalOpen = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function() {
        const url = arguments[1];
        if (/api\.light\.gg\/items\/\d*\/?/.test(url)) {
            this.addEventListener('load', throttle(optimizedTransformReviewItems, 200));
        }
        originalOpen.apply(this, arguments);
    };

    // 性能优化：更智能的DOM观察者
    const observer = new MutationObserver(throttle((mutations) => {
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

        if (shouldProcess) {
            optimizedTransformReviewItems();
        }
    }, 200));

    observer.observe(document.body, { childList: true, subtree: true });

    // 初始化
    window.addEventListener('load', () => {
        createSettingsUI();
        originalLang = lggTooltip.lang;
        if (setTooltipLang) lggTooltip.lang = "zh-chs";

        if (window.location.pathname === '/' || window.location.pathname === '') {
            setTimeout(() => {
                createNotification('Light.gg 双语工具已启动 🚀', 'success', 2000);
            }, 1000);
        }

        const reviewTab = document.getElementById('review-tab');
        reviewTab?.click();
        optimizedTransformReviewItems();
    });
})();
