// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

import { updateActiveButtons } from "editor-toolbar";
import { EditingArea } from "./editingArea";
import { caretToEnd, nodeIsElement, getBlockElement } from "./helpers";
import { triggerChangeTimer } from "./changeTimer";

export function onInput(event: Event): void {
    // make sure IME changes get saved
    triggerChangeTimer(event.currentTarget as EditingArea);
    updateActiveButtons();
}

export function onKey(evt: KeyboardEvent): void {
    const currentField = evt.currentTarget as EditingArea;

    // esc clears focus, allowing dialog to close
    if (evt.code === "Escape") {
        currentField.blurEditable();
        return;
    }

    // prefer <br> instead of <div></div>
    if (
        evt.code === "Enter" &&
        !getBlockElement(currentField.shadowRoot!) !== evt.shiftKey
    ) {
        evt.preventDefault();
        document.execCommand("insertLineBreak");
    }

    // // fix Ctrl+right/left handling in RTL fields
    if (currentField.isRightToLeft()) {
        const selection = currentField.getSelection();
        const granularity = evt.ctrlKey ? "word" : "character";
        const alter = evt.shiftKey ? "extend" : "move";

        switch (evt.code) {
            case "ArrowRight":
                selection.modify(alter, "right", granularity);
                evt.preventDefault();
                return;
            case "ArrowLeft":
                selection.modify(alter, "left", granularity);
                evt.preventDefault();
                return;
        }
    }

    triggerChangeTimer(currentField);
}

globalThis.addEventListener("keydown", (evt: KeyboardEvent) => {
    if (evt.code === "Tab") {
        globalThis.addEventListener(
            "focusin",
            (evt: FocusEvent) => {
                const newFocusTarget = evt.target;
                if (newFocusTarget instanceof EditingArea) {
                    caretToEnd(newFocusTarget);
                    updateActiveButtons();
                }
            },
            { once: true }
        );
    }
});

export function onKeyUp(evt: KeyboardEvent): void {
    const currentField = evt.currentTarget as EditingArea;

    // Avoid div element on remove
    if (evt.code === "Enter" || evt.code === "Backspace") {
        const anchor = currentField.getSelection().anchorNode as Node;

        if (
            nodeIsElement(anchor) &&
            anchor.tagName === "DIV" &&
            !(anchor instanceof EditingArea) &&
            anchor.childElementCount === 1 &&
            anchor.children[0].tagName === "BR"
        ) {
            anchor.replaceWith(anchor.children[0]);
        }
    }
}
