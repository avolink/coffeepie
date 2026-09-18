// Coffee Pie — slide switches change state on drag, never on a plain click.
//
// A tap on a slide switch is far too easy to trigger by accident, and some of
// ours act immediately: "mantener encendida" in the machine context menu
// starts or shuts down a real VM. So pointer input has to travel sideways
// before anything changes — press and slide, the way a physical switch works.
//
// Keyboard activation is deliberately left alone. Both switch skins hide the
// checkbox with opacity (not display:none), so it still takes focus, and
// Space/Enter must keep working or the control becomes unusable without a
// mouse. Clicks produced by the keyboard carry detail === 0, which is how we
// tell them apart from pointer clicks.
//
// Covers both skins in the project:
//   • label.toggle > input           — machines.html (Básico/Avanzado, keep-on)
//   • label > input.tg-checkbox      — panel.html (notifications, 2FA)
// Bound by delegation, so switches added to the DOM later are covered too.
(function () {
    'use strict';

    var THRESHOLD = 12;   // px of horizontal travel that counts as a drag
    var active = null;

    function switchAt(node) {
        if (!node || !node.closest) return null;
        var label = node.closest('label');
        if (!label) return null;
        var input = label.querySelector('input[type="checkbox"]');
        if (!input) return null;
        var isSwitch = label.classList.contains('toggle') ||
                       input.classList.contains('tg-checkbox');
        return isSwitch ? { label: label, input: input } : null;
    }

    function setState(input, on) {
        if (input.checked === on) return;
        input.checked = on;
        input.dispatchEvent(new Event('change', { bubbles: true }));
    }

    // Two things, both pointer-only — neither changes how a switch looks:
    //   • touch-action: vertical scrolling still works, horizontal drags are ours.
    //   • ::after: the switches are small (48×26 in the panel, 26px of grab
    //     height), and now that they need a deliberate drag, that is a fiddly
    //     target. This overlays an invisible grab area centred on the switch,
    //     never smaller than 44×44 (WCAG 2.5.5 Target Size). It is a pseudo-
    //     element, so events still report the label as their target.
    var GRAB = '44px';
    function installStyle() {
        var css = document.createElement('style');
        css.textContent =
            'label.toggle,label:has(input.tg-checkbox){' +
                'touch-action:pan-y;position:relative;cursor:pointer;' +
                '-webkit-user-select:none;user-select:none;-webkit-user-drag:none;}' +
            'label.toggle::after,label:has(input.tg-checkbox)::after{' +
                'content:"";position:absolute;left:50%;top:50%;' +
                'transform:translate(-50%,-50%);' +
                'width:max(100%,' + GRAB + ');height:max(100%,' + GRAB + ');}';
        (document.head || document.documentElement).appendChild(css);
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', installStyle);
    } else {
        installStyle();
    }

    document.addEventListener('pointerdown', function (e) {
        if (e.button) return;                 // primary button / touch only
        var s = switchAt(e.target);
        if (!s || s.input.disabled) return;
        active = { input: s.input, startX: e.clientX };
    }, true);

    document.addEventListener('pointermove', function (e) {
        if (!active) return;
        var dx = e.clientX - active.startX;
        if (Math.abs(dx) < THRESHOLD) return;
        setState(active.input, dx > 0);       // drag right = on, left = off
    }, true);

    function endDrag() { active = null; }
    document.addEventListener('pointerup', endDrag, true);
    document.addEventListener('pointercancel', endDrag, true);

    // Sliding across the switch would otherwise start a text selection, and the
    // next slide drags that selection — which is what paints the "no drop"
    // cursor over the control. Both are suppressed for the duration of a switch
    // drag only, so selection everywhere else behaves normally.
    function blockWhileDragging(e) { if (active) e.preventDefault(); }
    document.addEventListener('selectstart', blockWhileDragging, true);
    document.addEventListener('dragstart', blockWhileDragging, true);

    // Pointer clicks never toggle: a completed drag has already applied the
    // state, and a click without one is exactly what we are guarding against.
    document.addEventListener('click', function (e) {
        if (!e.detail) return;                // keyboard-generated: allow
        if (!switchAt(e.target)) return;
        e.preventDefault();
        e.stopPropagation();
    }, true);
})();
