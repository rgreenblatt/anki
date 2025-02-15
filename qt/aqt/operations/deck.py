# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

from __future__ import annotations

from typing import Optional, Sequence

from anki.collection import OpChanges, OpChangesWithCount, OpChangesWithId
from anki.decks import DeckCollapseScope, DeckId, UpdateDeckConfigs
from aqt import QWidget
from aqt.operations import CollectionOp
from aqt.utils import getOnlyText, tooltip, tr


def remove_decks(
    *,
    parent: QWidget,
    deck_ids: Sequence[DeckId],
) -> CollectionOp[OpChangesWithCount]:
    return CollectionOp(parent, lambda col: col.decks.remove(deck_ids)).success(
        lambda out: tooltip(tr.browsing_cards_deleted(count=out.count), parent=parent)
    )


def reparent_decks(
    *, parent: QWidget, deck_ids: Sequence[DeckId], new_parent: DeckId
) -> CollectionOp[OpChangesWithCount]:
    return CollectionOp(
        parent, lambda col: col.decks.reparent(deck_ids=deck_ids, new_parent=new_parent)
    ).success(
        lambda out: tooltip(
            tr.browsing_reparented_decks(count=out.count), parent=parent
        )
    )


def rename_deck(
    *,
    parent: QWidget,
    deck_id: DeckId,
    new_name: str,
) -> CollectionOp[OpChanges]:
    return CollectionOp(
        parent,
        lambda col: col.decks.rename(deck_id, new_name),
    )


def add_deck_dialog(
    *,
    parent: QWidget,
    default_text: str = "",
) -> Optional[CollectionOp[OpChangesWithId]]:
    if name := getOnlyText(
        tr.decks_new_deck_name(), default=default_text, parent=parent
    ).strip():
        return add_deck(parent=parent, name=name)
    else:
        return None


def add_deck(*, parent: QWidget, name: str) -> CollectionOp[OpChangesWithId]:
    return CollectionOp(parent, lambda col: col.decks.add_normal_deck_with_name(name))


def set_deck_collapsed(
    *,
    parent: QWidget,
    deck_id: DeckId,
    collapsed: bool,
    scope: DeckCollapseScope.V,
) -> CollectionOp[OpChanges]:
    return CollectionOp(
        parent,
        lambda col: col.decks.set_collapsed(
            deck_id=deck_id, collapsed=collapsed, scope=scope
        ),
    )


def set_current_deck(*, parent: QWidget, deck_id: DeckId) -> CollectionOp[OpChanges]:
    return CollectionOp(parent, lambda col: col.decks.set_current(deck_id))


def update_deck_configs(
    *, parent: QWidget, input: UpdateDeckConfigs
) -> CollectionOp[OpChanges]:
    return CollectionOp(parent, lambda col: col.decks.update_deck_configs(input))
