/**
 * Product Page Accordion/Collapsible Sections
 * Handles expand/collapse for "Información del Producto", "Dimensiones", etc.
 *
 * Avo DOM structure (per repeater item):
 *   [role="listitem"]
 *     ├── .inner-box (decorative, aria-hidden)
 *     ├── .has-click-trigger  (clickable header)
 *     │     ├── inner-box (decorative)
 *     │     ├── [data-testid="richTextElement"] → h2 title
 *     │     ├── [data-semantic-classname="button"] → minus SVG (collapse icon)
 *     │     └── [data-semantic-classname="button"] → plus SVG (expand icon)
 *     ├── [data-testid="richTextElement"] (content text — sibling of trigger)
 *     └── hidden placeholder divs
 */
(function () {
    'use strict';

    // Handle both DOMContentLoaded and already-loaded states
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initAccordions);
    } else {
        // DOM already loaded (script is at end of body)
        initAccordions();
    }

    function initAccordions() {
        var triggers = document.querySelectorAll('.has-click-trigger');
        console.log('[Accordion] Found', triggers.length, 'trigger(s)');

        triggers.forEach(function (trigger, idx) {
            // Find the two button containers inside the trigger
            var buttons = trigger.querySelectorAll('[data-semantic-classname="button"]');
            console.log('[Accordion] Trigger', idx, '- buttons found:', buttons.length);

            if (buttons.length < 2) {
                console.warn('[Accordion] Trigger', idx, '- skipping, need 2 buttons but found', buttons.length);
                return;
            }

            var minusBtnContainer = buttons[0]; // First = minus (horizontal line SVG)
            var plusBtnContainer = buttons[1];   // Second = plus (cross SVG)

            // Get the title for logging
            var titleEl = trigger.querySelector('h2');
            var title = titleEl ? titleEl.textContent.trim() : '(unknown)';
            console.log('[Accordion] Setting up:', title);

            // Find content elements: siblings of the trigger within the listitem parent
            var listItem = trigger.closest('[role="listitem"]');
            if (!listItem) {
                console.warn('[Accordion] No listitem parent for trigger', idx);
                return;
            }

            var contentElements = [];
            var children = listItem.children;
            var pastTrigger = false;

            for (var i = 0; i < children.length; i++) {
                var child = children[i];

                if (child === trigger) {
                    pastTrigger = true;
                    continue;
                }

                if (!pastTrigger) continue;

                // Skip hidden placeholder divs
                var inlineVis = child.style.visibility;
                if (inlineVis === 'hidden') continue;

                // Content element: has data-testid="richTextElement" on itself or inside
                var isRichText = child.hasAttribute('data-testid') && child.getAttribute('data-testid') === 'richTextElement';
                var hasRichText = child.querySelector && child.querySelector('[data-testid="richTextElement"]');

                if (isRichText || hasRichText) {
                    contentElements.push(child);
                }
            }

            console.log('[Accordion] Content elements found:', contentElements.length);

            if (contentElements.length === 0) {
                console.warn('[Accordion] No content found for trigger', idx);
                return;
            }

            // Determine initial state from CSS:
            // - minus visible + plus hidden = expanded
            // - minus hidden + plus visible = collapsed
            var plusStyle = window.getComputedStyle(plusBtnContainer);
            var isExpanded = (plusStyle.display === 'none' || plusStyle.visibility === 'hidden');

            console.log('[Accordion]', title, '- initial state:', isExpanded ? 'EXPANDED' : 'COLLAPSED');

            // Set initial visual state
            applyState(minusBtnContainer, plusBtnContainer, contentElements, isExpanded);

            // Attach click handler
            trigger.style.cursor = 'pointer';
            trigger.addEventListener('click', function (e) {
                e.preventDefault();
                e.stopPropagation();
                isExpanded = !isExpanded;
                applyState(minusBtnContainer, plusBtnContainer, contentElements, isExpanded);
                console.log('[Accordion]', title, '- toggled to:', isExpanded ? 'EXPANDED' : 'COLLAPSED');
            });
        });
    }

    function applyState(minusBtn, plusBtn, contentEls, expanded) {
        if (expanded) {
            // Show minus, hide plus
            minusBtn.style.cssText = 'display: block !important; visibility: visible !important;';
            plusBtn.style.cssText = 'display: none !important; visibility: hidden !important;';

            // Show content with animation
            contentEls.forEach(function (el) {
                el.style.cssText = 'transition: max-height 0.3s ease, opacity 0.3s ease; max-height: 2000px; opacity: 1; overflow: visible;';
            });
        } else {
            // Hide minus, show plus
            minusBtn.style.cssText = 'display: none !important; visibility: hidden !important;';
            plusBtn.style.cssText = 'display: block !important; visibility: visible !important;';

            // Hide content with animation
            contentEls.forEach(function (el) {
                el.style.cssText = 'transition: max-height 0.3s ease, opacity 0.3s ease; max-height: 0; opacity: 0; overflow: hidden;';
            });
        }
    }
})();
