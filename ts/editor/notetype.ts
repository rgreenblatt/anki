// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
import type ButtonGroup from "editor-toolbar/ButtonGroup.svelte";
import type { ButtonGroupProps } from "editor-toolbar/ButtonGroup";
import type { DynamicSvelteComponent } from "sveltelib/dynamicComponent";

import { bridgeCommand } from "anki/bridgecommand";
import * as tr from "anki/i18n";
import { labelButton, buttonGroup } from "editor-toolbar/dynamicComponents";

export function getNotetypeGroup(): DynamicSvelteComponent<typeof ButtonGroup> &
    ButtonGroupProps {
    const fieldsButton = labelButton({
        onClick: () => bridgeCommand("fields"),
        disables: false,
        label: `${tr.editingFields()}...`,
        tooltip: tr.editingCustomizeFields(),
    });

    const cardsButton = labelButton({
        onClick: () => bridgeCommand("cards"),
        disables: false,
        label: `${tr.editingCards()}...`,
        tooltip: tr.editingCustomizeCardTemplatesCtrlandl(),
    });

    return buttonGroup({
        id: "notetype",
        buttons: [fieldsButton, cardsButton],
    });
}
