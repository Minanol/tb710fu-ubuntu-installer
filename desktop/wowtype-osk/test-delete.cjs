const fs = require('fs'), vm = require('vm'), assert = require('assert');
const timers = new Map();let nextId = 0;
const GLib = {PRIORITY_DEFAULT: 0,
    timeout_add_once(_priority, delay, callback) {timers.set(++nextId, {delay, callback});return nextId;},
    source_remove(id) {timers.delete(id);}};
const Clutter = {KEY_BackSpace: 65288, InputContentPurpose: {PASSWORD: 8, PIN: 9}};
const Shell = {ActionMode: {LOCK_SCREEN: 4}};
const composition = {_compositionText: 'nihao'};
const nativeDeletes = [], raw = [], engine = [], commits = [];
const controller = {toggleDelete: enabled => nativeDeletes.push(enabled),
    keyvalPress: key => raw.push(['down', key]), keyvalRelease: key => raw.push(['up', key]),
    commit: async (text, modifiers) => commits.push({text, modifiers})};
const native = {toggleDelete: controller.toggleDelete, commit: controller.commit};
let handled = true;
const Main = {actionMode: 1, keyboard: {visible: true, keyboardActor: {_keyboardController: controller, _modifiers: new Set()}},
    extensionManager: {lookup: () => ({stateObj: composition})},
    inputMethod: {content_purpose: 0, currentFocus: {}, _context: {}, hasPreedit: () => false,
        handleVirtualKey: async key => {engine.push(key);return handled;}}};
const global = {display: {focus_window: {}}};
const context = {Extension: class {}, GLib, Clutter, Shell, Main, global, console};
vm.createContext(context);
vm.runInContext(fs.readFileSync(`${__dirname}/extension.js`, 'utf8')
    .replace(/^import .*;\n/gm, '')
    .replace('export default class WowTypeOsk', 'globalThis.WowTypeOsk = class WowTypeOsk'), context);
const ext = new context.WowTypeOsk();Object.assign(ext, {_disabled: false, _fcitxAvailable: true,
    _deleteQueue: Promise.resolve(), _deleteTimer: 0, _engineDeleteActive: false});ext._attach();
const flush = async () => {for (let i = 0; i < 10; i++) await Promise.resolve();};
const tick = async () => {const [id, timer] = timers.entries().next().value;timers.delete(id);timer.callback();await flush();};
const tap = async () => {controller.toggleDelete(true);controller.toggleDelete(false);await flush();};
(async () => {
    assert(ext._canDeletePreedit(), 'panel pinyin is composition even when native hasPreedit is false');
    await tap();assert.deepEqual(engine, [65288]);assert.equal(nativeDeletes.length, 0);
    assert.equal(raw.length, 0);assert.equal(timers.size, 0, 'short tap still deletes once after immediate release');
    controller.toggleDelete(true);controller.toggleDelete(false);controller.toggleDelete(true);controller.toggleDelete(false);
    await flush();assert.equal(engine.length, 3, 'rapid taps are serialized without dropping one');
    controller.toggleDelete(true);await flush();assert.equal([...timers.values()][0].delay, 300);
    await tick();assert.equal([...timers.values()][0].delay, 65);
    await tick();const beforeRelease = engine.length;controller.toggleDelete(false);await flush();
    assert.equal(timers.size, 0);assert.equal(engine.length, beforeRelease, 'release stops held deletion');
    controller.toggleDelete(true);await flush();handled = false;composition._compositionText = '';
    await tick();assert.deepEqual(raw, [['down', 65288], ['up', 65288]], 'held deletion continues to app text only when engine declines');
    controller.toggleDelete(false);await tap();assert.deepEqual(nativeDeletes, [true, false], 'ordinary app deletion stays native');
    handled = true;composition._compositionText = 'nihao';
    for (const purpose of [8, 9]) {Main.inputMethod.content_purpose = purpose;await tap();}
    Main.inputMethod.content_purpose = 0;Main.actionMode = 4;await tap();Main.actionMode = 1;
    Main.keyboard.keyboardActor._modifiers.add(123);await tap();Main.keyboard.keyboardActor._modifiers.clear();
    const beforeStale = engine.length;controller.toggleDelete(true);controller.toggleDelete(false);
    Main.inputMethod._context = {};await flush();assert.equal(engine.length, beforeStale, 'stale context cannot delete in another field');
    controller.toggleDelete(true);await flush();Main.keyboard.visible = false;await tick();
    assert(!ext._engineDeleteActive);assert.equal(timers.size, 0);Main.keyboard.visible = true;
    await tap();assert.equal(engine.length, beforeStale+2, 'delete recovers after keyboard reopens');
    const beforeFocus = engine.length;controller.toggleDelete(true);global.display.focus_window = {};await flush();
    assert.equal(engine.length, beforeFocus);assert(!ext._engineDeleteActive);
    await controller.commit('abc', new Set());assert.deepEqual(engine.slice(-3), [97, 98, 99]);
    Main.inputMethod.content_purpose = 8;await controller.commit('x', new Set());assert.equal(commits.at(-1).text, 'x');Main.inputMethod.content_purpose = 0;
    controller.toggleDelete(true);await flush();ext._disabled = true;ext._restore();
    assert.equal(timers.size, 0);assert.equal(controller.toggleDelete, native.toggleDelete);assert.equal(controller.commit, native.commit);
    console.log('Panel preedit backspace, short/rapid taps, held repeat, native fallback, sensitive/modifier guards, stale focus and restoration passed');
})().catch(error => {console.error(error);process.exitCode = 1;});
