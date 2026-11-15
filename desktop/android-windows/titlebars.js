import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Meta from 'gi://Meta';
import Pango from 'gi://Pango';
import Shell from 'gi://Shell';
import St from 'gi://St';

export const TITLEBAR_HEIGHT = 52;
const BORDER = 1;
const DRAG_THRESHOLD = 8;

function rectCopy(rect) {
    return {x: rect.x, y: rect.y, width: rect.width, height: rect.height};
}

// Decorations are children of their own Meta.WindowActor, never Shell chrome.
// They therefore share that window's stacking, transforms and workspace motion.
export class AttachedTitlebars {
    constructor(isAndroidWindow) {
        this._isAndroidWindow = isAndroidWindow;
        this._windows = new Map();
        this._sources = new Set();
        this._stopped = false;
        this._settings = new Gio.Settings({schema_id: 'org.gnome.desktop.interface'});
        this._settingsId = this._settings.connect('changed', () => this.refresh(false));
        this._createdId = global.display.connect('window-created', () => this._later(() => this.refresh()));
        this._focusId = global.display.connect('notify::focus-window', () => this.refresh(false));
        this.refresh();
    }

    _later(callback) {
        let id = GLib.idle_add(GLib.PRIORITY_DEFAULT_IDLE, () => {
            this._sources.delete(id);
            if (!this._stopped)
                callback();
            return GLib.SOURCE_REMOVE;
        });
        this._sources.add(id);
        return id;
    }

    refresh(fit = true) {
        if (this._stopped)
            return;
        for (const actor of global.get_window_actors()) {
            const window = actor.meta_window;
            if (!window || window.get_window_type() !== Meta.WindowType.NORMAL ||
                !this._isAndroidWindow(window))
                continue;
            if (!this._windows.has(window))
                this._attach(window, actor);
            const state = this._windows.get(window);
            if (fit)
                this._fit(state);
            this._update(state);
        }
    }

    _attach(window, actor) {
        const state = {window, actor, signals: [], maximized: false, restore: null,
            pending: false, fitting: false, request: '', requestTime: 0, lastPress: 0};
        state.outline = new St.Widget({style_class: 'tb-android-attached-frame', reactive: false});
        state.header = new St.BoxLayout({style_class: 'tb-android-titlebar', reactive: true});
        state.moveArea = new St.BoxLayout({style_class: 'tb-android-titlebar-drag',
            reactive: true, x_expand: true});
        let app = Shell.WindowTracker.get_default().get_window_app(window);
        state.label = new St.Label({text: app?.get_name() ?? window.get_title() ?? '安卓应用',
            x_expand: true, y_align: Clutter.ActorAlign.CENTER});
        state.label.clutter_text.ellipsize = Pango.EllipsizeMode.END;
        state.moveArea.add_child(state.label);
        state.header.add_child(state.moveArea);
        state.buttonActions = new Map();
        const addButton = (label, glyph, action, extra = '') => {
            const button = new St.Button({style_class: `tb-android-titlebar-button ${extra}`,
                accessible_name: label, can_focus: true, reactive: true,
                width: 42, height: 42, y_align: Clutter.ActorAlign.CENTER,
                label: glyph});
            const activate = () => {
                if (!this._windows.has(window) || window.is_fullscreen())
                    return;
                window.activate(global.get_current_time());
                action();
            };
            state.buttonActions.set(button, activate);
            button.connect('clicked', activate);
            state.header.add_child(button);
            return button;
        };
        state.minimize = addButton('最小化', '−', () => window.minimize());
        state.maximize = addButton('最大化', '□', () => this.toggleMaximize(window));
        state.close = addButton('关闭窗口', '×',
            () => window.delete(global.get_current_time()), 'tb-android-titlebar-close');
        // Keep the native surface container last, including in fullscreen,
        // so an invisible decoration does not disable direct scanout.
        actor.insert_child_at_index(state.outline, 0);
        actor.insert_child_at_index(state.header, 1);
        this._windows.set(window, state);
        const schedule = () => {
            if (state.pending || this._stopped)
                return;
            state.pending = true;
            this._later(() => {
                state.pending = false;
                if (this._windows.has(window))
                    this._update(state);
            });
        };
        for (const signal of ['position-changed', 'size-changed', 'notify::fullscreen',
            'notify::maximized-horizontally', 'notify::maximized-vertically',
            'notify::minimized', 'notify::title', 'notify::appears-focused'])
            state.signals.push([window, window.connect(signal, schedule)]);
        state.signals.push([window, window.connect('unmanaged', () => this._remove(window))]);
        state.signals.push([actor, actor.connect('notify::allocation', schedule)]);
        state.signals.push([actor, actor.connect('notify::mapped', schedule)]);
        state.signals.push([actor, actor.connect('destroy', () => this._remove(window, true))]);
        state.header.connect('captured-event', (_actor, event) => this._moveEvent(state, event));
        this._fit(state);
        this._update(state);
        let attempts = 0;
        let diagnostic = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 500, () => {
            if (!this._windows.has(window) || window.is_fullscreen()) {
                this._sources.delete(diagnostic);
                return GLib.SOURCE_REMOVE;
            }
            const rect = window.get_frame_rect();
            if ((!actor.is_mapped() || rect.width < 1 || rect.height < 1) && ++attempts < 60)
                return GLib.SOURCE_CONTINUE;
            this._sources.delete(diagnostic);
            const parentMatches = state.header.get_parent() === actor;
            const [hx, hy] = state.header.get_transformed_position();
            const [hw, hh] = state.header.get_transformed_size();
            const outside = hy + hh <= rect.y + 2;
            const sameWidth = Math.abs(hw - rect.width - BORDER * 2) < 3;
            log(`[tb-android-windows] external titlebar: window-owned=${parentMatches}, ` +
                `outside-content=${outside}, full-width=${sameWidth}, ` +
                `header=${Math.round(hx)},${Math.round(hy)},${Math.round(hw)},${Math.round(hh)}, ` +
                `content=${rect.x},${rect.y},${rect.width},${rect.height}`);
            return GLib.SOURCE_REMOVE;
        });
        this._sources.add(diagnostic);
    }

    _area(state) {
        return state.window.get_work_area_for_monitor(state.window.get_monitor());
    }

    _fullRect(state) {
        const area = this._area(state);
        return {x: area.x + BORDER, y: area.y + TITLEBAR_HEIGHT + BORDER,
            width: Math.max(1, area.width - BORDER * 2),
            height: Math.max(1, area.height - TITLEBAR_HEIGHT - BORDER * 2)};
    }

    _request(state, rect) {
        const signature = [rect.x, rect.y, rect.width, rect.height].map(Math.round).join(',');
        const now = GLib.get_monotonic_time() / 1000;
        if (state.request === signature && now - state.requestTime < 1000)
            return;
        state.request = signature;
        state.requestTime = now;
        state.window.move_resize_frame(true, Math.round(rect.x), Math.round(rect.y),
            Math.max(1, Math.round(rect.width)), Math.max(1, Math.round(rect.height)));
    }

    _fit(state) {
        const window = state.window;
        if (state.fitting || window.is_fullscreen() || window.minimized)
            return;
        state.fitting = true;
        try {
            const rect = window.get_frame_rect();
            if (rect.width < 1 || rect.height < 1)
                return;
            const area = this._fullRect(state);
            const width = Math.min(rect.width, area.width);
            const height = Math.min(rect.height, area.height);
            const target = state.maximized ? area : {
                x: Math.max(area.x, Math.min(rect.x, area.x + area.width - width)),
                y: Math.max(area.y, Math.min(rect.y, area.y + area.height - height)),
                width, height};
            if (Object.keys(target).some(key => Math.abs(target[key] - rect[key]) > 1))
                this._request(state, target);
        } finally {
            state.fitting = false;
        }
    }

    _update(state) {
        const window = state.window;
        const initial = window.get_frame_rect();
        const visible = !window.is_fullscreen() && state.actor.is_mapped() &&
            initial.width > 0 && initial.height > 0;
        state.header.visible = visible;
        state.outline.visible = visible;
        if (!visible)
            return;
        if (!state.firstFitted) {
            state.firstFitted = true;
            this._fit(state);
        }
        // Convert native maximize requests to a full outer frame, reserving
        // header space instead of covering the application's upper content.
        if (window.is_maximized()) {
            if (!state.maximized)
                state.restore = state.lastNormal ?? rectCopy(window.get_frame_rect());
            state.maximized = true;
            window.unmaximize();
            state.request = '';
            this._fit(state);
        }
        if (state.maximized)
            this._fit(state);
        const rect = window.get_frame_rect();
        const buffer = window.get_buffer_rect();
        // Mutter scales every WindowActor child by its geometry-scale matrix.
        // Cancel that static scale, while retaining the parent's animations.
        const transform = state.actor.get_child_transform();
        const rawX = transform.get_x_scale();
        const rawY = transform.get_y_scale();
        const sx = Number.isFinite(rawX) && rawX > 0 ? rawX : 1;
        const sy = Number.isFinite(rawY) && rawY > 0 ? rawY : 1;
        const x = (rect.x - buffer.x - BORDER) / sx;
        const y = (rect.y - buffer.y - TITLEBAR_HEIGHT) / sy;
        const width = rect.width + BORDER * 2;
        state.header.set_scale(1 / sx, 1 / sy);
        state.outline.set_scale(1 / sx, 1 / sy);
        state.header.set_position(x, y);
        if (Math.abs(state.header.width - width) > .5 || state.header.height !== TITLEBAR_HEIGHT)
            state.header.set_size(width, TITLEBAR_HEIGHT);
        state.outline.set_position(x, y - BORDER / sy);
        if (Math.abs(state.outline.width - width) > .5 ||
            Math.abs(state.outline.height - (rect.height + TITLEBAR_HEIGHT + BORDER * 2)) > .5)
            state.outline.set_size(width, rect.height + TITLEBAR_HEIGHT + BORDER * 2);
        state.maximize.label = state.maximized ? '❐' : '□';
        state.maximize.accessible_name = state.maximized ? '还原窗口' : '最大化';
        const dark = this._settings.get_string('color-scheme') === 'prefer-dark' ||
            this._settings.get_string('gtk-theme').endsWith('-dark');
        for (const actor of [state.header, state.outline]) {
            actor.set_style_class_name(actor === state.header ?
                `tb-android-titlebar${dark ? ' dark' : ''}` :
                `tb-android-attached-frame${dark ? ' dark' : ''}`);
            if (window.appears_focused)
                actor.add_style_pseudo_class('focus');
            else
                actor.remove_style_pseudo_class('focus');
        }
        if (!state.maximized)
            state.lastNormal = rectCopy(rect);
    }

    isMaximized(window) {
        return this._windows.get(window)?.maximized || window.is_maximized();
    }

    clearMaximize(window) {
        const state = this._windows.get(window);
        if (state)
            state.maximized = false;
    }

    toggleMaximize(window) {
        const state = this._windows.get(window);
        if (!state)
            return;
        if (state.maximized) {
            state.maximized = false;
            if (state.restore)
                this._request(state, state.restore);
        } else {
            state.restore = rectCopy(window.get_frame_rect());
            state.maximized = true;
            this._request(state, this._fullRect(state));
        }
        this._later(() => {
            if (this._windows.has(window)) {
                this._fit(state);
                this._update(state);
            }
        });
    }

    _buttonAt(state, x, y) {
        for (const button of state.buttonActions.keys()) {
            const [bx, by] = button.get_transformed_position();
            const [bw, bh] = button.get_transformed_size();
            if (x >= bx && x < bx + bw && y >= by && y < by + bh)
                return button;
        }
        return null;
    }

    _startDrag(drag) {
        const state = drag.state;
        const window = state.window;
        if (state.maximized) {
            const ratio = (drag.x - drag.rect.x) / Math.max(1, drag.rect.width);
            const rect = rectCopy(state.restore ?? drag.rect);
            rect.x = drag.x - Math.max(0, Math.min(1, ratio)) * rect.width;
            rect.y = drag.y + TITLEBAR_HEIGHT / 2;
            state.maximized = false;
            state.request = '';
            this._request(state, rect);
            drag.rect = rect;
        }
        drag.started = true;
        state.lastPress = 0;
        drag.button?.remove_style_pseudo_class('active');
    }

    _moveEvent(state, event) {
        const type = event.type();
        const touchBegin = type === Clutter.EventType.TOUCH_BEGIN;
        const mouseBegin = type === Clutter.EventType.BUTTON_PRESS;
        if (touchBegin || mouseBegin) {
            if (mouseBegin && event.get_button() !== 1)
                return Clutter.EVENT_PROPAGATE;
            // A second contact must not replace the gesture or click a button.
            if (this._moving)
                return Clutter.EVENT_STOP;
            const [x, y] = event.get_coords();
            const button = this._buttonAt(state, x, y);
            const now = GLib.get_monotonic_time() / 1000;
            state.window.activate(global.get_current_time());
            if (mouseBegin && !button && now - state.lastPress < 300) {
                state.lastPress = 0;
                this.toggleMaximize(state.window);
                return Clutter.EVENT_STOP;
            }
            state.lastPress = mouseBegin && !button ? now : 0;
            this._moving = {state, x, y, rect: rectCopy(state.window.get_frame_rect()),
                touch: touchBegin, sequence: touchBegin ? event.get_event_sequence().get_slot() : null,
                button, started: false};
            button?.add_style_pseudo_class('active');
            return Clutter.EVENT_STOP;
        }
        const drag = this._moving;
        if (!drag || drag.state !== state)
            return Clutter.EVENT_PROPAGATE;
        const touchEvent = [Clutter.EventType.TOUCH_UPDATE, Clutter.EventType.TOUCH_END,
            Clutter.EventType.TOUCH_CANCEL].includes(type);
        if (touchEvent && (!drag.touch || drag.sequence !== event.get_event_sequence().get_slot()))
            return Clutter.EVENT_STOP;
        if (drag.touch && !touchEvent)
            return Clutter.EVENT_PROPAGATE;
        const [hx, hy] = state.header.get_transformed_position();
        const [hw, hh] = state.header.get_transformed_size();
        const [ex, ey] = event.get_coords();
        const leftHeader = type === Clutter.EventType.LEAVE && !drag.touch &&
            (ex < hx || ex >= hx + hw || ey < hy || ey >= hy + hh);
        if (type === Clutter.EventType.TOUCH_CANCEL || leftHeader) {
            this._stopMove();
            if (drag.started)
                this._fit(state);
            return Clutter.EVENT_STOP;
        }
        const mouseEnd = type === Clutter.EventType.BUTTON_RELEASE && !drag.touch &&
            event.get_button() === 1;
        const touchEnd = type === Clutter.EventType.TOUCH_END && drag.touch;
        const mouseMove = type === Clutter.EventType.MOTION && !drag.touch;
        const touchMove = type === Clutter.EventType.TOUCH_UPDATE && drag.touch;
        if (!mouseEnd && !touchEnd && !mouseMove && !touchMove)
            return Clutter.EVENT_PROPAGATE;
        if (mouseMove && !(event.get_state() & Clutter.ModifierType.BUTTON1_MASK)) {
            this._stopMove();
            if (drag.started)
                this._fit(state);
            return Clutter.EVENT_STOP;
        }
        const [px, py] = event.get_coords();
        if (!drag.started && Math.hypot(px - drag.x, py - drag.y) >= DRAG_THRESHOLD)
            this._startDrag(drag);
        if (drag.started)
            state.window.move_frame(true, Math.round(drag.rect.x + px - drag.x),
                Math.round(drag.rect.y + py - drag.y));
        if (mouseEnd || touchEnd) {
            const action = !drag.started && drag.button &&
                this._buttonAt(state, px, py) === drag.button ?
                state.buttonActions.get(drag.button) : null;
            this._stopMove();
            if (drag.started)
                this._fit(state);
            action?.();
        }
        return Clutter.EVENT_STOP;
    }

    _stopMove() {
        // Only header events participate; no modal actor or global stage grab.
        this._moving?.button?.remove_style_pseudo_class('active');
        this._moving = null;
    }

    _remove(window, actorDestroyed = false) {
        const state = this._windows.get(window);
        if (!state)
            return;
        this._windows.delete(window);
        if (this._moving?.state === state)
            this._stopMove();
        for (const [object, id] of state.signals) {
            try { object.disconnect(id); } catch (_) { /* already destroyed */ }
        }
        if (!actorDestroyed) {
            state.header.destroy();
            state.outline.destroy();
        }
    }

    destroy() {
        this._stopped = true;
        this._stopMove();
        for (const id of this._sources)
            GLib.source_remove(id);
        this._sources.clear();
        global.display.disconnect(this._createdId);
        global.display.disconnect(this._focusId);
        this._settings.disconnect(this._settingsId);
        for (const window of [...this._windows.keys()])
            this._remove(window);
    }
}
