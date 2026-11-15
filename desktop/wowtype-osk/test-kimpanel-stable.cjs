const fs = require('fs'), vm = require('vm'), assert = require('assert');
const delegated = [], selected = [], pages = [], fallback = [];
let owner = {setCandidateTable: (...args) => delegated.push(args)}, hidden = 0;
const Main = {actionMode: 1, inputMethod: {content_purpose: 0},
    keyboard: {visible: true, resetSuggestions: () => fallback.push('reset'),
        addSuggestion: label => fallback.push(label), setSuggestionsVisible: () => fallback.push('show')},
    extensionManager: {lookup: () => owner ? {stateObj: owner} : null}};
const ctx = {Main, Clutter: {InputContentPurpose: {PASSWORD: 8, PIN: 9}}, Shell: {ActionMode: {LOCK_SCREEN: 4}}};
vm.createContext(ctx);
const update = vm.runInContext('(function(){'+fs.readFileSync(`${__dirname}/kimpanel-stable-candidates.txt`, 'utf8')+'})',ctx);
const panel = {table: ['你','你好','你们','你是','你要'], showLookupTable: true, _hasPrev: false, _hasNext: true,
    inputpanel: {hide() {hidden++;}}, selectCandidate: index => selected.push(index), emit: value => pages.push(value)};
update.call(panel);assert.equal(fallback.length,0);assert.equal(delegated.length,1);assert.equal(hidden,1);
delegated.at(-1)[3](1);assert.deepEqual(selected,[1]);delegated.at(-1)[4](1);assert.deepEqual(pages,['LookupTablePageDown']);
panel.table = ['新的候选'];delegated.at(-1)[3](1);assert.deepEqual(selected,[1], 'stale callback cannot select changed text');
Main.inputMethod.content_purpose=8;update.call(panel);assert.equal(delegated.at(-1)[0].length,0);
Main.inputMethod.content_purpose=0;Main.keyboard.visible=false;const before=hidden;update.call(panel);
assert.equal(delegated.at(-1)[0].length,0);assert.equal(hidden,before, 'physical-keyboard floating panel is not hidden');
Main.keyboard.visible=true;owner=null;update.call(panel);assert.deepEqual(fallback,['reset','新的候选','›','show']);
console.log('Single renderer delegation, safe touch callbacks, sensitive hiding, floating-panel preservation and native fallback passed');
