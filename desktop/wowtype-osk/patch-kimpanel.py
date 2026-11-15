"""Integrate upstream Kimpanel v92 candidates with GNOME 50's touch OSK."""
from pathlib import Path
import sys
root = Path(sys.argv[1])
p = root / 'extension.js'
source = p.read_text()
marker = '// TB710FU: native touch candidate row'
if marker not in source:
    original = source
    source = source.replace("import GObject from 'gi://GObject';", "import GObject from 'gi://GObject';\nimport Clutter from 'gi://Clutter';\nimport Shell from 'gi://Shell';", 1)
    source = source.replace('        this.watch_id = 0;\n        this.indicator', '''        this.watch_id = 0;
        this._oskVisibleId = Main.keyboard.connect('visibility-changed', () => this.updateInputPanel());
        this._oskPurposeId = Main.inputMethod.connect('notify::content-purpose', () => this.updateInputPanel());
        this.indicator''', 1)
    source = source.replace('        this._isDestroyed = true;\n        this.resetData();', '''        this._isDestroyed = true;
        Main.keyboard.disconnect(this._oskVisibleId);
        Main.inputMethod.disconnect(this._oskPurposeId);
        Main.keyboard.resetSuggestions();
        this.resetData();''', 1)
    old = '''        this.inputpanel.updatePosition();
    }
    emit(signal)'''
    new = '''        this.inputpanel.updatePosition();
        // TB710FU: native touch candidate row
        const purpose = Main.inputMethod.content_purpose;
        const sensitive = purpose === Clutter.InputContentPurpose.PASSWORD ||
            purpose === Clutter.InputContentPurpose.PIN ||
            Main.actionMode === Shell.ActionMode.LOCK_SCREEN;
        Main.keyboard.resetSuggestions();
        if (Main.keyboard.visible) {
            // GNOME's native buttons process TOUCH_BEGIN without stealing focus.
            this.inputpanel.hide();
            if (!sensitive && this.showLookupTable && this.table.length) {
                if (this._hasPrev)
                    Main.keyboard.addSuggestion('‹', () => this.emit('LookupTablePageUp'));
                this.table.forEach((text, index) => {
                    Main.keyboard.addSuggestion(text, () => {
                        if (this.showLookupTable && this.table[index] === text)
                            this.selectCandidate(index);
                    });
                });
                if (this._hasNext)
                    Main.keyboard.addSuggestion('›', () => this.emit('LookupTablePageDown'));
                Main.keyboard.setSuggestionsVisible(true);
            }
        } else if (sensitive) {
            this.inputpanel.hide();
        }
    }
    emit(signal)'''
    assert source.count(old) == 1, 'Unexpected upstream updateInputPanel'
    source = source.replace(old, new, 1)
    source = source.replace('        this.table = texts;\n        this.cursor', '        this.table = texts;\n        this._hasPrev = hasPrev;\n        this._hasNext = hasNext;\n        this.cursor', 1)
    assert '_oskVisibleId' in source and 'this._hasNext = hasNext;' in source
    backup = root / 'extension.js.before-tb-osk'
    if not backup.exists(): backup.write_text(original)
    p.write_text(source)

# Keep mouse selection working and add real touch for floating candidates too.
p = root / 'panel.js'
source = p.read_text()
if 'item._touchEventId' not in source:
    original = source
    needle = "                item._enterEventId = item.connect('enter-event', (widget) => {"
    replacement = '''                item._touchEventId = item.connect('touch-event', (widget, event) => {
                    if (event.type() === Clutter.EventType.TOUCH_BEGIN && !widget.ignore_focus) {
                        this._candidateClicked(widget);
                        return Clutter.EVENT_STOP;
                    }
                    return Clutter.EVENT_PROPAGATE;
                });
''' + needle
    assert source.count(needle) == 1
    source = source.replace(needle, replacement, 1).replace('                    item.disconnect(item._buttonReleaseId);', '                    item.disconnect(item._buttonReleaseId);\n                    item.disconnect(item._touchEventId);', 1)
    backup = root / 'panel.js.before-tb-osk'
    if not backup.exists(): backup.write_text(original)
    p.write_text(source)
print('Kimpanel touch candidate integration installed')
# Keep eight candidates plus page arrows within the tablet in either orientation.
p = root / 'extension.js'
source = p.read_text()
if '// TB710FU: fit candidate buttons' not in source:
    if "import Pango from 'gi://Pango';" not in source:
        source = source.replace("import GObject from 'gi://GObject';", "import GObject from 'gi://GObject';\nimport Pango from 'gi://Pango';", 1)
    needle = '                Main.keyboard.setSuggestionsVisible(true);'
    assert source.count(needle) == 1
    source = source.replace(needle, needle + '''
                // TB710FU: fit candidate buttons to the tablet width.
                const keyboard = Main.keyboard.keyboardActor;
                const buttons = keyboard._suggestions.get_children();
                const isPage = button => button.label === '‹' || button.label === '›';
                const pageButtons = buttons.filter(isPage).length;
                const overhead = 24 + buttons.length * 6 + Math.max(0, buttons.length - 1) * 12;
                const width = Math.min(160, Math.floor((keyboard.width - overhead - pageButtons * 72) /
                    Math.max(1, buttons.length - pageButtons)));
                for (const button of buttons) {
                    button.width = isPage(button) ? 72 : Math.max(68, width);
                    const label = button.get_child();
                    if (label?.clutter_text)
                        label.clutter_text.ellipsize = Pango.EllipsizeMode.END;
                }''', 1)
    p.write_text(source)

# Version 6: fit the shared row's actual grid width, including compact spacing.
p = root / 'extension.js'
source = p.read_text()
old = "                const overhead = 24 + buttons.length * 6 + Math.max(0, buttons.length - 1) * 12;"
new = "                keyboard._suggestions.set_style('spacing: 6px; padding: 6px 12px;');\n                const candidateAreaWidth = keyboard._suggestions.get_parent()?.width || keyboard.width;\n                const overhead = 24 + buttons.length * 4 + Math.max(0, buttons.length - 1) * 6;"
if old in source:
    source = source.replace(old, new, 1)
    source = source.replace('(keyboard.width - overhead - pageButtons * 72)', '(candidateAreaWidth - overhead - pageButtons * 44)', 1)
    source = source.replace('button.width = isPage(button) ? 72 : Math.max(68, width);', "button.set_style('min-width: 24px; padding: 6px 8px; margin: 0 2px;');\n                    button.width = isPage(button) ? 44 : Math.max(40, width);", 1)
    p.write_text(source)

# Version 17: hand the native row to one persistent five-slot renderer.
# Replace the whole older adapter, including its second width calculation.
p = root / 'extension.js'
source = p.read_text()
start = source.index('        // TB710FU: native touch candidate row')
end = source.index('\n    }\n    emit(signal)', start)
adapter = Path(__file__).with_name('kimpanel-stable-candidates.txt').read_text().rstrip()
p.write_text(source[:start] + adapter + source[end:])
