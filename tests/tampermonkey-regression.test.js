const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const repoRoot = path.resolve(__dirname, '..');

function readScript(relativePath) {
    return fs.readFileSync(path.join(repoRoot, relativePath), 'utf8');
}

function extractFunction(source, name) {
    const start = source.indexOf(`function ${name}(`);
    assert.notEqual(start, -1, `Missing function ${name}`);
    const braceStart = source.indexOf('{', start);
    let depth = 0;
    for (let i = braceStart; i < source.length; i++) {
        const char = source[i];
        if (char === '{') depth++;
        if (char === '}') depth--;
        if (depth === 0) return source.slice(start, i + 1);
    }
    throw new Error(`Could not extract function ${name}`);
}

function createTextNode(value) {
    return {
        nodeValue: value,
        parentNode: { nodeName: 'DIV' }
    };
}

function createTextDocument(nodes) {
    return {
        body: {},
        getElementById() {
            return { disabled: true };
        },
        createTreeWalker() {
            let index = -1;
            return {
                currentNode: null,
                nextNode() {
                    index++;
                    this.currentNode = nodes[index];
                    return index < nodes.length;
                }
            };
        }
    };
}

test('Destiny term replacement can be applied again after undo restores text', () => {
    const source = readScript('tampermonkey/Destiny2_Term_replace.user.js');
    const context = {
        document: createTextDocument([createTextNode('Equip Gjallarhorn now')]),
        NodeFilter: { SHOW_TEXT: 4 },
        Set,
        WeakSet,
        Map,
        RegExp,
        replacementHistory: [],
        HISTORY_LIMIT: 20,
        processedNodes: new WeakSet(),
        showToast() {}
    };

    vm.createContext(context);
    vm.runInContext(`
        ${extractFunction(source, 'performReplace')}
        ${extractFunction(source, 'buildRegex')}
        ${extractFunction(source, 'undoReplace')}
        this.firstCount = performReplace([['Gjallarhorn', '加拉尔号角']]);
        undoReplace();
        this.secondCount = performReplace([['Gjallarhorn', '加拉尔号角']]);
    `, context);

    assert.equal(context.firstCount, 1);
    assert.equal(context.secondCount, 1);
});

test('Destiny undo only makes restored nodes eligible for replacement', () => {
    const source = readScript('tampermonkey/Destiny2_Term_replace.user.js');
    const firstNode = createTextNode('Gjallarhorn');
    const secondNode = createTextNode('Gjallarhorn');
    const nodes = [firstNode];
    const context = {
        document: createTextDocument(nodes),
        NodeFilter: { SHOW_TEXT: 4 },
        Set,
        WeakSet,
        Map,
        RegExp,
        replacementHistory: [],
        HISTORY_LIMIT: 20,
        processedNodes: new WeakSet(),
        showToast() {}
    };

    vm.createContext(context);
    context.nodes = nodes;
    context.secondNode = secondNode;
    vm.runInContext(`
        ${extractFunction(source, 'performReplace')}
        ${extractFunction(source, 'buildRegex')}
        ${extractFunction(source, 'undoReplace')}
        performReplace([['Gjallarhorn', 'Gjallarhorn | 加拉尔号角']]);
        nodes.push(secondNode);
        performReplace([['Gjallarhorn', 'Gjallarhorn | 加拉尔号角']]);
        undoReplace();
        performReplace([['Gjallarhorn', 'Gjallarhorn | 加拉尔号角']]);
        this.firstText = nodes[0].nodeValue;
        this.secondText = nodes[1].nodeValue;
    `, context);

    assert.equal(context.firstText, 'Gjallarhorn | 加拉尔号角');
    assert.equal(context.secondText, 'Gjallarhorn | 加拉尔号角');
});

test('Destiny no-match scan does not block later matching rules', () => {
    const source = readScript('tampermonkey/Destiny2_Term_replace.user.js');
    const node = createTextNode('Equip Gjallarhorn now');
    const context = {
        document: createTextDocument([node]),
        NodeFilter: { SHOW_TEXT: 4 },
        Set,
        WeakSet,
        Map,
        RegExp,
        replacementHistory: [],
        HISTORY_LIMIT: 20,
        processedNodes: new WeakSet()
    };

    vm.createContext(context);
    vm.runInContext(`
        ${extractFunction(source, 'performReplace')}
        ${extractFunction(source, 'buildRegex')}
        this.noMatchCount = performReplace([['Thorn', '荆棘']]);
        this.matchCount = performReplace([['Gjallarhorn', '加拉尔号角']]);
        this.finalText = document.createTreeWalker().currentNode;
    `, context);

    assert.equal(context.noMatchCount, 0);
    assert.equal(context.matchCount, 1);
    assert.equal(node.nodeValue, 'Equip 加拉尔号角 now');
});

test('Destiny empty rules do not scan or replace text', () => {
    const source = readScript('tampermonkey/Destiny2_Term_replace.user.js');
    let scanned = false;
    const context = {
        document: {
            body: {},
            createTreeWalker() {
                scanned = true;
                return { nextNode() { return false; } };
            }
        },
        NodeFilter: { SHOW_TEXT: 4 },
        Set,
        WeakSet,
        Map,
        RegExp,
        replacementHistory: [],
        HISTORY_LIMIT: 20,
        processedNodes: new WeakSet()
    };

    vm.createContext(context);
    vm.runInContext(`
        ${extractFunction(source, 'performReplace')}
        ${extractFunction(source, 'buildRegex')}
        this.count = performReplace([]);
    `, context);

    assert.equal(context.count, 0);
    assert.equal(scanned, false);
});

test('Destiny script does not use Trusted Types blocked HTML sinks', () => {
    const source = readScript('tampermonkey/Destiny2_Term_replace.user.js');

    assert.doesNotMatch(source, /\.innerHTML\s*=/);
    assert.doesNotMatch(source, /\.outerHTML\s*=/);
    assert.doesNotMatch(source, /\.insertAdjacentHTML\s*\(/);
});

function createLightElement(text) {
    return {
        textContent: text,
        dataset: {}
    };
}

test('Light.gg bilingual output refreshes existing elements when language changes', () => {
    const source = readScript('tampermonkey/Light.gg Bilingual Display Tool.user.js');
    const element = createLightElement('Gjallarhorn');
    const context = {
        Array,
        Map,
        WeakSet,
        console: { log() {} },
        itemLookupMap: new Map(),
        processedElements: new WeakSet(),
        bilingualLang: 'zh-chs',
        ORIGINAL_TEXT_KEY: 'lggOriginalText'
    };

    context.element = element;
    vm.createContext(context);
    vm.runInContext(`
        ${extractFunction(source, 'buildLookupMap')}
        ${extractFunction(source, 'getOriginalText')}
        ${extractFunction(source, 'processElements')}
        const data = { data: { items: { 1: { en: 'Gjallarhorn', 'zh-chs': '加拉尔号角', 'zh-cht': '加拉爾號角' } } } };
        buildLookupMap(data);
        processElements([element]);
        this.simplifiedText = element.textContent;
        bilingualLang = 'zh-cht';
        buildLookupMap(data);
        processedElements = new WeakSet();
        processElements([element]);
        this.traditionalText = element.textContent;
    `, context);

    assert.equal(context.simplifiedText, 'Gjallarhorn | 加拉尔号角');
    assert.equal(context.traditionalText, 'Gjallarhorn | 加拉爾號角');
});

test('Light.gg missing translation restores the original element text', () => {
    const source = readScript('tampermonkey/Light.gg Bilingual Display Tool.user.js');
    const element = createLightElement('Gjallarhorn');
    const context = {
        Array,
        Map,
        WeakSet,
        console: { log() {} },
        itemLookupMap: new Map(),
        processedElements: new WeakSet(),
        bilingualLang: 'zh-chs',
        ORIGINAL_TEXT_KEY: 'lggOriginalText'
    };

    context.element = element;
    vm.createContext(context);
    vm.runInContext(`
        ${extractFunction(source, 'buildLookupMap')}
        ${extractFunction(source, 'getOriginalText')}
        ${extractFunction(source, 'processElements')}
        const data = { data: { items: { 1: { en: 'Gjallarhorn', 'zh-chs': '加拉尔号角' } } } };
        buildLookupMap(data);
        processElements([element]);
        bilingualLang = 'zh-cht';
        buildLookupMap(data);
        processedElements = new WeakSet();
        processElements([element]);
        this.finalText = element.textContent;
    `, context);

    assert.equal(context.finalText, 'Gjallarhorn');
});

test('Light.gg transform waits safely when data promise is not assigned yet', async () => {
    const source = readScript('tampermonkey/Light.gg Bilingual Display Tool.user.js');
    const element = createLightElement('Gjallarhorn');
    let queried = false;
    const context = {
        Array,
        Map,
        Promise,
        WeakSet,
        console: { log() {} },
        document: {
            querySelectorAll() {
                queried = true;
                return [element];
            }
        },
        itemLookupMap: new Map([['gjallarhorn', '加拉尔号角']]),
        processedElements: new WeakSet(),
        isDataReady: false,
        isPaused: false,
        bilingualLang: 'zh-chs',
        ORIGINAL_TEXT_KEY: 'lggOriginalText'
    };

    vm.createContext(context);
    vm.runInContext(`
        ${extractFunction(source, 'getOriginalText')}
        ${extractFunction(source, 'processElements')}
        ${extractFunction(source, 'optimizedTransformReviewItems')}
        optimizedTransformReviewItems();
    `, context);

    await Promise.resolve();

    assert.equal(queried, true);
    assert.equal(element.textContent, 'Gjallarhorn');
});

test('Light.gg corrupted cache falls back to empty term data', () => {
    const source = readScript('tampermonkey/Light.gg Bilingual Display Tool.user.js');
    const context = {};

    vm.createContext(context);
    vm.runInContext(`
        ${extractFunction(source, 'parseCachedTermMap')}
        this.emptyFromMissing = parseCachedTermMap('');
        this.emptyFromBadJson = parseCachedTermMap('{bad json');
        this.parsedData = parseCachedTermMap('{"data":{"items":{}}}');
    `, context);

    assert.equal(JSON.stringify(context.emptyFromMissing), '{"data":{}}');
    assert.equal(JSON.stringify(context.emptyFromBadJson), '{"data":{}}');
    assert.equal(JSON.stringify(context.parsedData), '{"data":{"items":{}}}');
});
