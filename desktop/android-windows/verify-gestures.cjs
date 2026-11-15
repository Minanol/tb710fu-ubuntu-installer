const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const names = ['TOUCH_BEGIN', 'TOUCH_UPDATE', 'TOUCH_END', 'TOUCH_CANCEL',
    'BUTTON_PRESS', 'BUTTON_RELEASE', 'MOTION', 'LEAVE'];
const Clutter = {EventType: Object.fromEntries(names.map(n => [n, n])),
    EVENT_STOP: 1, EVENT_PROPAGATE: 0, ModifierType: {BUTTON1_MASK: 1}};
const code = fs.readFileSync(path.join(__dirname, 'titlebars.js'), 'utf8')
    .replace(/^import .*;\n/gm, '').replace(/^export /gm, '');
const context = {Clutter, GLib: {get_monotonic_time: () => 100000000},
    global: {get_current_time: () => 1}};
vm.createContext(context);
vm.runInContext(code + '\nglobalThis.Manager = AttachedTitlebars;', context);

function fixture() {
    const manager = Object.create(context.Manager.prototype);
    const moves = [], actions = [0, 0, 0];
    const buttons = actions.map((_, i) => ({
        get_transformed_position: () => [270 + i * 42, 50],
        get_transformed_size: () => [42, 42],
        add_style_pseudo_class() {}, remove_style_pseudo_class() {},
    }));
    const state = {lastPress: 0, maximized: false,
        header: {get_transformed_position: () => [100, 50],
            get_transformed_size: () => [300, 52]},
        buttonActions: new Map(buttons.map((b, i) => [b, () => actions[i]++])),
        window: {activate() {}, get_frame_rect: () => ({x: 100, y: 102, width: 300, height: 400}),
            move_frame: (_, x, y) => moves.push([x, y])}};
    manager._fit = () => {};
    manager._request = (_, rect) => moves.push([rect.x, rect.y]);
    manager.toggleMaximize = () => {};
    const event = (type, x, y, seq = 'a', button = 1, mask = 1) => ({
        type: () => Clutter.EventType[type], get_coords: () => [x, y],
        get_event_sequence: () => ({get_slot: () => seq === 'a' ? 0 : 1}), get_button: () => button, get_state: () => mask});
    const send = (type, x, y, ...rest) => manager._moveEvent(state, event(type, x, y, ...rest));
    return {manager, state, moves, actions, send};
}

for (const [begin, move, end] of [['TOUCH_BEGIN', 'TOUCH_UPDATE', 'TOUCH_END'],
    ['BUTTON_PRESS', 'MOTION', 'BUTTON_RELEASE']]) {
    for (let i = 0; i < 3; i++) {
        const x = 280 + i * 42;
        let f = fixture();
        f.send(begin, x, 70); f.send(end, x + 2, 70);
        assert.equal(f.actions[i], 1); assert.equal(f.moves.length, 0);
        f = fixture();
        f.send(begin, x, 70); f.send(move, x + 20, 80); f.send(end, x + 30, 90);
        assert.deepEqual(f.actions, [0, 0, 0]);
        assert.deepEqual(f.moves.at(-1), [130, 122]);
        assert.equal(f.manager._moving, null);
    }
}
let f = fixture();
f.send('TOUCH_BEGIN', 370, 70); f.send('TOUCH_CANCEL', 370, 70);
assert.deepEqual(f.actions, [0, 0, 0]); assert.equal(f.manager._moving, null);
f = fixture();
f.send('TOUCH_BEGIN', 150, 70); f.send('TOUCH_BEGIN', 370, 70, 'b');
f.send('TOUCH_END', 370, 70, 'b'); assert.equal(f.manager._moving.sequence, 0);
f.send('TOUCH_UPDATE', 180, 85); f.send('TOUCH_END', 180, 85);
assert.deepEqual(f.moves.at(-1), [130, 117]); assert.deepEqual(f.actions, [0, 0, 0]);
f = fixture(); f.state.maximized = true;
f.state.restore = {x: 100, y: 102, width: 200, height: 300};
f.send('TOUCH_BEGIN', 150, 70); f.send('TOUCH_END', 150, 70);
assert.equal(f.state.maximized, true); assert.equal(f.moves.length, 0);
f.send('TOUCH_BEGIN', 150, 70); f.send('TOUCH_UPDATE', 180, 90);
assert.equal(f.state.maximized, false); assert.ok(f.moves.length > 0);
f = fixture(); f.send('BUTTON_PRESS', 370, 70); f.send('LEAVE', 375, 70);
assert.ok(f.manager._moving); // Crossing a label inside the header is safe.
f.send('LEAVE', 500, 70); assert.equal(f.manager._moving, null);
assert.deepEqual(f.actions, [0, 0, 0]);
f = fixture();
assert.equal(f.send('BUTTON_PRESS', 370, 70, 'a', 3), Clutter.EVENT_PROPAGATE);
assert.equal(f.send('MOTION', 600, 600), Clutter.EVENT_PROPAGATE);
f.send('TOUCH_BEGIN', 370, 70); f.send('TOUCH_END', 400, 100);
assert.deepEqual(f.actions, [0, 0, 0]); assert.ok(f.moves.length > 0);
console.log('Passed with fresh boxed touch-sequence wrappers and slot zero: all button taps/drags, title drag, cancellation, extra touch, maximize restore, pointer leave and unrelated input');
