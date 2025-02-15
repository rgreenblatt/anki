# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

from __future__ import annotations

import html
from typing import Any, Callable, List, Optional, Sequence, Tuple, Union

import aqt
import aqt.forms
from anki.cards import Card, CardId
from anki.collection import Collection, Config, OpChanges, SearchNode
from anki.consts import *
from anki.errors import NotFoundError
from anki.lang import without_unicode_isolation
from anki.notes import NoteId
from anki.stats import CardStats
from anki.tags import MARKED_TAG
from anki.utils import ids2str, isMac
from aqt import AnkiQt, gui_hooks
from aqt.browser.dialogs import (
    CardInfoDialog,
    ChangeModel,
    FindAndReplaceDialog,
    FindDupesDialog,
)
from aqt.browser.previewer import BrowserPreviewer as PreviewDialog
from aqt.browser.previewer import Previewer
from aqt.browser.sidebar import SidebarTreeView
from aqt.browser.table import Table
from aqt.editor import Editor
from aqt.exporting import ExportDialog
from aqt.main import ResetReason
from aqt.operations.card import set_card_deck, set_card_flag
from aqt.operations.collection import undo
from aqt.operations.note import remove_notes
from aqt.operations.scheduling import (
    forget_cards,
    reposition_new_cards_dialog,
    set_due_date_dialog,
    suspend_cards,
    unsuspend_cards,
)
from aqt.operations.tag import (
    add_tags_to_notes,
    clear_unused_tags,
    remove_tags_from_notes,
)
from aqt.qt import *
from aqt.switch import Switch
from aqt.utils import (
    HelpPage,
    KeyboardModifiersPressed,
    current_top_level_widget,
    disable_help_button,
    ensure_editor_saved,
    ensure_editor_saved_on_trigger,
    getTag,
    openHelp,
    qtMenuShortcutWorkaround,
    restore_combo_history,
    restore_combo_index_for_session,
    restoreGeom,
    restoreSplitter,
    restoreState,
    save_combo_history,
    save_combo_index_for_session,
    saveGeom,
    saveSplitter,
    saveState,
    shortcut,
    showInfo,
    showWarning,
    tooltip,
    tr,
)
from aqt.webview import AnkiWebView


class Browser(QMainWindow):
    mw: AnkiQt
    col: Collection
    editor: Optional[Editor]
    table: Table

    def __init__(
        self,
        mw: AnkiQt,
        card: Optional[Card] = None,
        search: Optional[Tuple[Union[str, SearchNode]]] = None,
    ) -> None:
        """
        card  : try to search for its note and select it
        search: set and perform search; caller must ensure validity
        """

        QMainWindow.__init__(self, None, Qt.Window)
        self.mw = mw
        self.col = self.mw.col
        self.lastFilter = ""
        self.focusTo: Optional[int] = None
        self._previewer: Optional[Previewer] = None
        self._closeEventHasCleanedUp = False
        self.form = aqt.forms.browser.Ui_Dialog()
        self.form.setupUi(self)
        self.setupSidebar()
        restoreGeom(self, "editor", 0)
        restoreState(self, "editor")
        restoreSplitter(self.form.splitter, "editor3")
        self.form.splitter.setChildrenCollapsible(False)
        self.card: Optional[Card] = None
        self.setup_table()
        self.setupMenus()
        self.setupHooks()
        self.setupEditor()
        self.onUndoState(self.mw.form.actionUndo.isEnabled())
        self.setupSearch(card, search)
        gui_hooks.browser_will_show(self)
        self.show()

    def on_operation_did_execute(
        self, changes: OpChanges, handler: Optional[object]
    ) -> None:
        focused = current_top_level_widget() == self
        self.table.op_executed(changes, handler, focused)
        self.sidebar.op_executed(changes, handler, focused)
        if changes.note or changes.notetype:
            if handler is not self.editor:
                # fixme: this will leave the splitter shown, but with no current
                # note being edited
                note = self.editor.note
                if note:
                    try:
                        note.load()
                    except NotFoundError:
                        self.editor.set_note(None)
                        return
                    self.editor.set_note(note)

            self._renderPreview()

    def on_focus_change(self, new: Optional[QWidget], old: Optional[QWidget]) -> None:
        if current_top_level_widget() == self:
            self.setUpdatesEnabled(True)
            self.table.redraw_cells()
            self.sidebar.refresh_if_needed()

    def setupMenus(self) -> None:
        # pylint: disable=unnecessary-lambda
        # actions
        f = self.form
        # edit
        qconnect(f.actionUndo.triggered, self.undo)
        qconnect(f.actionInvertSelection.triggered, self.table.invert_selection)
        qconnect(f.actionSelectNotes.triggered, self.selectNotes)
        if not isMac:
            f.actionClose.setVisible(False)
        qconnect(f.actionCreateFilteredDeck.triggered, self.createFilteredDeck)
        f.actionCreateFilteredDeck.setShortcuts(["Ctrl+G", "Ctrl+Alt+G"])
        # notes
        qconnect(f.actionAdd.triggered, self.mw.onAddCard)
        qconnect(f.actionAdd_Tags.triggered, lambda: self.add_tags_to_selected_notes())
        qconnect(
            f.actionRemove_Tags.triggered,
            lambda: self.remove_tags_from_selected_notes(),
        )
        qconnect(f.actionClear_Unused_Tags.triggered, self.clear_unused_tags)
        qconnect(f.actionToggle_Mark.triggered, self.toggle_mark_of_selected_notes)
        qconnect(f.actionChangeModel.triggered, self.onChangeModel)
        qconnect(f.actionFindDuplicates.triggered, self.onFindDupes)
        qconnect(f.actionFindReplace.triggered, self.onFindReplace)
        qconnect(f.actionManage_Note_Types.triggered, self.mw.onNoteTypes)
        qconnect(f.actionDelete.triggered, self.delete_selected_notes)
        # cards
        qconnect(f.actionChange_Deck.triggered, self.set_deck_of_selected_cards)
        qconnect(f.action_Info.triggered, self.showCardInfo)
        qconnect(f.actionReposition.triggered, self.reposition)
        qconnect(f.action_set_due_date.triggered, self.set_due_date)
        qconnect(f.action_forget.triggered, self.forget_cards)
        qconnect(f.actionToggle_Suspend.triggered, self.suspend_selected_cards)
        qconnect(f.actionRed_Flag.triggered, lambda: self.set_flag_of_selected_cards(1))
        qconnect(
            f.actionOrange_Flag.triggered, lambda: self.set_flag_of_selected_cards(2)
        )
        qconnect(
            f.actionGreen_Flag.triggered, lambda: self.set_flag_of_selected_cards(3)
        )
        qconnect(
            f.actionBlue_Flag.triggered, lambda: self.set_flag_of_selected_cards(4)
        )
        qconnect(f.actionExport.triggered, lambda: self._on_export_notes())
        # jumps
        qconnect(f.actionPreviousCard.triggered, self.onPreviousCard)
        qconnect(f.actionNextCard.triggered, self.onNextCard)
        qconnect(f.actionFirstCard.triggered, self.onFirstCard)
        qconnect(f.actionLastCard.triggered, self.onLastCard)
        qconnect(f.actionFind.triggered, self.onFind)
        qconnect(f.actionNote.triggered, self.onNote)
        qconnect(f.actionSidebar.triggered, self.focusSidebar)
        qconnect(f.actionCardList.triggered, self.onCardList)
        # help
        qconnect(f.actionGuide.triggered, self.onHelp)
        # keyboard shortcut for shift+home/end
        self.pgUpCut = QShortcut(QKeySequence("Shift+Home"), self)
        qconnect(self.pgUpCut.activated, self.onFirstCard)
        self.pgDownCut = QShortcut(QKeySequence("Shift+End"), self)
        qconnect(self.pgDownCut.activated, self.onLastCard)
        # add-on hook
        gui_hooks.browser_menus_did_init(self)
        self.mw.maybeHideAccelerators(self)

    def closeEvent(self, evt: QCloseEvent) -> None:
        if self._closeEventHasCleanedUp:
            evt.accept()
            return
        self.editor.call_after_note_saved(self._closeWindow)
        evt.ignore()

    def _closeWindow(self) -> None:
        self._cleanup_preview()
        self.editor.cleanup()
        self.table.cleanup()
        saveSplitter(self.form.splitter, "editor3")
        saveGeom(self, "editor")
        saveState(self, "editor")
        self.teardownHooks()
        self.mw.maybeReset()
        aqt.dialogs.markClosed("Browser")
        self._closeEventHasCleanedUp = True
        self.mw.deferred_delete_and_garbage_collect(self)
        self.close()

    @ensure_editor_saved
    def closeWithCallback(self, onsuccess: Callable) -> None:
        self._closeWindow()
        onsuccess()

    def keyPressEvent(self, evt: QKeyEvent) -> None:
        if evt.key() == Qt.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(evt)

    def reopen(
        self,
        _mw: AnkiQt,
        card: Optional[Card] = None,
        search: Optional[Tuple[Union[str, SearchNode]]] = None,
    ) -> None:
        if search is not None:
            self.search_for_terms(*search)
            self.form.searchEdit.setFocus()
        elif card:
            self.show_single_card(card)
            self.form.searchEdit.setFocus()

    # Searching
    ######################################################################

    def setupSearch(
        self,
        card: Optional[Card] = None,
        search: Optional[Tuple[Union[str, SearchNode]]] = None,
    ) -> None:
        qconnect(self.form.searchEdit.lineEdit().returnPressed, self.onSearchActivated)
        self.form.searchEdit.setCompleter(None)
        self.form.searchEdit.lineEdit().setPlaceholderText(
            tr.browsing_search_bar_hint()
        )
        self.form.searchEdit.addItems(self.mw.pm.profile["searchHistory"])
        if search is not None:
            self.search_for_terms(*search)
        elif card:
            self.show_single_card(card)
        else:
            self.search_for(
                self.col.build_search_string(SearchNode(deck="current")), ""
            )
        self.form.searchEdit.setFocus()

    # search triggered by user
    @ensure_editor_saved
    def onSearchActivated(self) -> None:
        text = self.current_search()
        try:
            normed = self.col.build_search_string(text)
        except Exception as err:
            showWarning(str(err))
        else:
            self.search_for(normed)
            self.update_history()

    def search_for(self, search: str, prompt: Optional[str] = None) -> None:
        """Keep track of search string so that we reuse identical search when
        refreshing, rather than whatever is currently in the search field.
        Optionally set the search bar to a different text than the actual search.
        """

        self._lastSearchTxt = search
        prompt = search if prompt == None else prompt
        self.form.searchEdit.lineEdit().setText(prompt)
        self.search()

    def current_search(self) -> str:
        return self.form.searchEdit.lineEdit().text()

    def search(self) -> None:
        """Search triggered programmatically. Caller must have saved note first."""

        try:
            self.table.search(self._lastSearchTxt)
        except Exception as err:
            showWarning(str(err))

    def update_history(self) -> None:
        sh = self.mw.pm.profile["searchHistory"]
        if self._lastSearchTxt in sh:
            sh.remove(self._lastSearchTxt)
        sh.insert(0, self._lastSearchTxt)
        sh = sh[:30]
        self.form.searchEdit.clear()
        self.form.searchEdit.addItems(sh)
        self.mw.pm.profile["searchHistory"] = sh

    def updateTitle(self) -> None:
        selected = self.table.len_selection()
        cur = self.table.len()
        tr_title = (
            tr.browsing_window_title_notes
            if self.table.is_notes_mode()
            else tr.browsing_window_title
        )
        self.setWindowTitle(
            without_unicode_isolation(tr_title(total=cur, selected=selected))
        )

    def search_for_terms(self, *search_terms: Union[str, SearchNode]) -> None:
        search = self.col.build_search_string(*search_terms)
        self.form.searchEdit.setEditText(search)
        self.onSearchActivated()

    def show_single_card(self, card: Card) -> None:
        if card.nid:

            def on_show_single_card() -> None:
                self.card = card
                search = self.col.build_search_string(SearchNode(nid=card.nid))
                search = gui_hooks.default_search(search, card)
                self.search_for(search, "")
                self.table.select_single_card(card.id)

            self.editor.call_after_note_saved(on_show_single_card)

    def onReset(self) -> None:
        self.sidebar.refresh()
        self.begin_reset()
        self.end_reset()

    # caller must have called editor.saveNow() before calling this or .reset()
    def begin_reset(self) -> None:
        self.editor.set_note(None, hide=False)
        self.mw.progress.start()
        self.table.begin_reset()

    def end_reset(self) -> None:
        self.table.end_reset()
        self.mw.progress.finish()

    # Table & Editor
    ######################################################################

    def setup_table(self) -> None:
        self.table = Table(self)
        self.table.set_view(self.form.tableView)
        switch = Switch(11, tr.browsing_card_initial(), tr.browsing_note_initial())
        switch.setChecked(self.table.is_notes_mode())
        switch.setToolTip(tr.browsing_toggle_showing_cards_notes())
        qconnect(self.form.action_toggle_mode.triggered, switch.toggle)
        qconnect(switch.toggled, self.on_table_state_changed)
        self.form.gridLayout.addWidget(switch, 0, 0)

    def setupEditor(self) -> None:
        def add_preview_button(editor: Editor) -> None:
            preview_shortcut = "Ctrl+Shift+P"  # TODO

            editor._links["preview"] = lambda _editor: self.onTogglePreview()
            editor.web.eval(
                f"""
$editorToolbar.addButton({{
    component: editorToolbar.LabelButton,
    label: `{tr.actions_preview()}`,
    tooltip: `{tr.browsing_preview_selected_card(val=shortcut(preview_shortcut))}`,
    onClick: () => bridgeCommand("preview"),
    disables: false,
}}, "notetype");
"""
            )

        def add_preview_shortcut(cuts: List[Tuple], editor: Editor) -> None:
            cuts.append(("Ctrl+Shift+P", self.onTogglePreview, True))

        gui_hooks.editor_did_init.append(add_preview_button)
        gui_hooks.editor_did_init_shortcuts.append(add_preview_shortcut)
        self.editor = aqt.editor.Editor(self.mw, self.form.fieldsArea, self)
        gui_hooks.editor_did_init_shortcuts.remove(add_preview_shortcut)
        gui_hooks.editor_did_init.remove(add_preview_button)

    @ensure_editor_saved
    def onRowChanged(
        self, _current: Optional[QItemSelection], _previous: Optional[QItemSelection]
    ) -> None:
        """Update current note and hide/show editor. """
        if self._closeEventHasCleanedUp:
            return

        self.updateTitle()
        # the current card is used for context actions
        self.card = self.table.get_current_card()
        # if there is only one selected card, use it in the editor
        # it might differ from the current card
        card = self.table.get_single_selected_card()
        self.singleCard = bool(card)
        self.form.splitter.widget(1).setVisible(self.singleCard)
        if self.singleCard:
            self.editor.set_note(card.note(), focusTo=self.focusTo)
            self.focusTo = None
            self.editor.card = card
        else:
            self.editor.set_note(None)
        self._renderPreview()
        self._update_context_actions()
        gui_hooks.browser_did_change_row(self)

    def _update_context_actions(self) -> None:
        self._update_flags_menu()
        self._update_toggle_mark_action()
        self._update_toggle_suspend_action()

    @ensure_editor_saved
    def on_table_state_changed(self, checked: bool) -> None:
        self.mw.progress.start()
        self.table.toggle_state(checked, self._lastSearchTxt)
        self.mw.progress.finish()

    # Sidebar
    ######################################################################

    def setupSidebar(self) -> None:
        dw = self.sidebarDockWidget = QDockWidget(tr.browsing_sidebar(), self)
        dw.setFeatures(QDockWidget.DockWidgetClosable)
        dw.setObjectName("Sidebar")
        dw.setAllowedAreas(Qt.LeftDockWidgetArea)

        self.sidebar = SidebarTreeView(self)
        self.sidebarTree = self.sidebar  # legacy alias
        dw.setWidget(self.sidebar)
        qconnect(
            self.form.actionSidebarFilter.triggered,
            self.focusSidebarSearchBar,
        )
        grid = QGridLayout()
        grid.addWidget(self.sidebar.searchBar, 0, 0)
        grid.addWidget(self.sidebar.toolbar, 0, 1)
        grid.addWidget(self.sidebar, 1, 0, 1, 2)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(0)
        w = QWidget()
        w.setLayout(grid)
        dw.setWidget(w)
        self.sidebarDockWidget.setFloating(False)

        self.sidebarDockWidget.setTitleBarWidget(QWidget())
        self.addDockWidget(Qt.LeftDockWidgetArea, dw)

        # schedule sidebar to refresh after browser window has loaded, so the
        # UI is more responsive
        self.mw.progress.timer(10, self.sidebar.refresh, False)

    def showSidebar(self) -> None:
        # workaround for PyQt focus bug
        self.editor.hideCompleters()
        self.sidebarDockWidget.setVisible(True)

    def focusSidebar(self) -> None:
        self.showSidebar()
        self.sidebar.setFocus()

    def focusSidebarSearchBar(self) -> None:
        self.showSidebar()
        self.sidebar.searchBar.setFocus()

    def toggle_sidebar(self) -> None:
        want_visible = not self.sidebarDockWidget.isVisible()
        self.sidebarDockWidget.setVisible(want_visible)
        if want_visible:
            self.sidebar.refresh()

    # legacy

    def setFilter(self, *terms: str) -> None:
        self.sidebar.update_search(*terms)

    # Info
    ######################################################################

    def showCardInfo(self) -> None:
        if not self.card:
            return

        info, cs = self._cardInfoData()
        reps = self._revlogData(cs)

        card_info_dialog = CardInfoDialog(self)
        l = QVBoxLayout()
        l.setContentsMargins(0, 0, 0, 0)
        w = AnkiWebView(title="browser card info")
        l.addWidget(w)
        w.stdHtml(info + "<p>" + reps, context=card_info_dialog)
        bb = QDialogButtonBox(QDialogButtonBox.Close)
        l.addWidget(bb)
        qconnect(bb.rejected, card_info_dialog.reject)
        card_info_dialog.setLayout(l)
        card_info_dialog.setWindowModality(Qt.WindowModal)
        card_info_dialog.resize(500, 400)
        restoreGeom(card_info_dialog, "revlog")
        card_info_dialog.show()

    def _cardInfoData(self) -> Tuple[str, CardStats]:
        cs = CardStats(self.col, self.card)
        rep = cs.report(include_revlog=True)
        return rep, cs

    # legacy - revlog used to be generated here, and some add-ons
    # wrapped this function

    def _revlogData(self, cs: CardStats) -> str:
        return ""

    # Menu helpers
    ######################################################################

    def selected_cards(self) -> Sequence[CardId]:
        return self.table.get_selected_card_ids()

    def selected_notes(self) -> Sequence[NoteId]:
        return self.table.get_selected_note_ids()

    def selectedNotesAsCards(self) -> Sequence[CardId]:
        return self.table.get_card_ids_from_selected_note_ids()

    def oneModelNotes(self) -> Sequence[NoteId]:
        sf = self.selected_notes()
        if not sf:
            return []
        mods = self.col.db.scalar(
            """
select count(distinct mid) from notes
where id in %s"""
            % ids2str(sf)
        )
        if mods > 1:
            showInfo(tr.browsing_please_select_cards_from_only_one())
            return []
        return sf

    def onHelp(self) -> None:
        openHelp(HelpPage.BROWSING)

    # legacy

    selectedCards = selected_cards
    selectedNotes = selected_notes

    # Misc menu options
    ######################################################################

    @ensure_editor_saved_on_trigger
    def onChangeModel(self) -> None:
        nids = self.oneModelNotes()
        if nids:
            ChangeModel(self, nids)

    def createFilteredDeck(self) -> None:
        search = self.current_search()
        if self.mw.col.schedVer() != 1 and KeyboardModifiersPressed().alt:
            aqt.dialogs.open("FilteredDeckConfigDialog", self.mw, search_2=search)
        else:
            aqt.dialogs.open("FilteredDeckConfigDialog", self.mw, search=search)

    # Preview
    ######################################################################

    def onTogglePreview(self) -> None:
        if self._previewer:
            self._previewer.close()
            self._on_preview_closed()
        else:
            self._previewer = PreviewDialog(self, self.mw, self._on_preview_closed)
            self._previewer.open()

    def _renderPreview(self) -> None:
        if self._previewer:
            if self.singleCard:
                self._previewer.render_card()
            else:
                self.onTogglePreview()

    def _cleanup_preview(self) -> None:
        if self._previewer:
            self._previewer.cancel_timer()
            self._previewer.close()

    def _on_preview_closed(self) -> None:
        if self.editor.web:
            self.editor.web.eval(
                "document.getElementById('previewButton').classList.remove('highlighted')"
            )
        self._previewer = None

    # Card deletion
    ######################################################################

    def delete_selected_notes(self) -> None:
        # ensure deletion is not accidentally triggered when the user is focused
        # in the editing screen or search bar
        focus = self.focusWidget()
        if focus != self.form.tableView:
            return

        # nothing selected?
        nids = self.table.get_selected_note_ids()
        if not nids:
            return

        # select the next card if there is one
        self.focusTo = self.editor.currentField
        self.table.to_next_row()

        remove_notes(parent=self, note_ids=nids).run_in_background()

    # legacy

    deleteNotes = delete_selected_notes

    # Deck change
    ######################################################################

    @ensure_editor_saved_on_trigger
    def set_deck_of_selected_cards(self) -> None:
        from aqt.studydeck import StudyDeck

        cids = self.table.get_selected_card_ids()
        if not cids:
            return

        did = self.mw.col.db.scalar("select did from cards where id = ?", cids[0])
        current = self.mw.col.decks.get(did)["name"]
        ret = StudyDeck(
            self.mw,
            current=current,
            accept=tr.browsing_move_cards(),
            title=tr.browsing_change_deck(),
            help=HelpPage.BROWSING,
            parent=self,
        )
        if not ret.name:
            return
        did = self.col.decks.id(ret.name)

        set_card_deck(parent=self, card_ids=cids, deck_id=did).run_in_background()

    # legacy

    setDeck = set_deck_of_selected_cards

    # Tags
    ######################################################################

    @ensure_editor_saved_on_trigger
    def add_tags_to_selected_notes(
        self,
        tags: Optional[str] = None,
    ) -> None:
        "Shows prompt if tags not provided."
        if not (tags := tags or self._prompt_for_tags(tr.browsing_enter_tags_to_add())):
            return
        add_tags_to_notes(
            parent=self, note_ids=self.selected_notes(), space_separated_tags=tags
        ).run_in_background(initiator=self)

    @ensure_editor_saved_on_trigger
    def remove_tags_from_selected_notes(self, tags: Optional[str] = None) -> None:
        "Shows prompt if tags not provided."
        if not (
            tags := tags or self._prompt_for_tags(tr.browsing_enter_tags_to_delete())
        ):
            return

        remove_tags_from_notes(
            parent=self, note_ids=self.selected_notes(), space_separated_tags=tags
        ).run_in_background(initiator=self)

    def _prompt_for_tags(self, prompt: str) -> Optional[str]:
        (tags, ok) = getTag(self, self.col, prompt)
        if not ok:
            return None
        else:
            return tags

    @ensure_editor_saved_on_trigger
    def clear_unused_tags(self) -> None:
        clear_unused_tags(parent=self).run_in_background()

    addTags = add_tags_to_selected_notes
    deleteTags = remove_tags_from_selected_notes
    clearUnusedTags = clear_unused_tags

    # Suspending
    ######################################################################

    def _update_toggle_suspend_action(self) -> None:
        is_suspended = bool(self.card and self.card.queue == QUEUE_TYPE_SUSPENDED)
        self.form.actionToggle_Suspend.setChecked(is_suspended)

    @ensure_editor_saved
    def suspend_selected_cards(self, checked: bool) -> None:
        cids = self.selected_cards()
        if checked:
            suspend_cards(parent=self, card_ids=cids).run_in_background()
        else:
            unsuspend_cards(parent=self.mw, card_ids=cids).run_in_background()

    # Exporting
    ######################################################################

    def _on_export_notes(self) -> None:
        cids = self.selectedNotesAsCards()
        if cids:
            ExportDialog(self.mw, cids=list(cids))

    # Flags & Marking
    ######################################################################

    @ensure_editor_saved
    def set_flag_of_selected_cards(self, flag: int) -> None:
        if not self.card:
            return

        # flag needs toggling off?
        if flag == self.card.user_flag():
            flag = 0

        set_card_flag(
            parent=self, card_ids=self.selected_cards(), flag=flag
        ).run_in_background()

    def _update_flags_menu(self) -> None:
        flag = self.card and self.card.user_flag()
        flag = flag or 0

        flagActions = [
            self.form.actionRed_Flag,
            self.form.actionOrange_Flag,
            self.form.actionGreen_Flag,
            self.form.actionBlue_Flag,
        ]

        for c, act in enumerate(flagActions):
            act.setChecked(flag == c + 1)

        qtMenuShortcutWorkaround(self.form.menuFlag)

    def toggle_mark_of_selected_notes(self, checked: bool) -> None:
        if checked:
            self.add_tags_to_selected_notes(tags=MARKED_TAG)
        else:
            self.remove_tags_from_selected_notes(tags=MARKED_TAG)

    def _update_toggle_mark_action(self) -> None:
        is_marked = bool(self.card and self.card.note().has_tag(MARKED_TAG))
        self.form.actionToggle_Mark.setChecked(is_marked)

    # Scheduling
    ######################################################################

    @ensure_editor_saved_on_trigger
    def reposition(self) -> None:
        if self.card and self.card.queue != QUEUE_TYPE_NEW:
            showInfo(tr.browsing_only_new_cards_can_be_repositioned(), parent=self)
            return

        reposition_new_cards_dialog(
            parent=self, card_ids=self.selected_cards()
        ).run_in_background()

    @ensure_editor_saved_on_trigger
    def set_due_date(self) -> None:
        set_due_date_dialog(
            parent=self,
            card_ids=self.selected_cards(),
            config_key=Config.String.SET_DUE_BROWSER,
        ).run_in_background()

    @ensure_editor_saved_on_trigger
    def forget_cards(self) -> None:
        forget_cards(
            parent=self,
            card_ids=self.selected_cards(),
        ).run_in_background()

    # Edit: selection
    ######################################################################

    @ensure_editor_saved_on_trigger
    def selectNotes(self) -> None:
        nids = self.selected_notes()
        # clear the selection so we don't waste energy preserving it
        self.table.clear_selection()
        search = self.col.build_search_string(
            SearchNode(nids=SearchNode.IdList(ids=nids))
        )
        self.search_for(search)
        self.table.select_all()

    # Hooks
    ######################################################################

    def setupHooks(self) -> None:
        gui_hooks.undo_state_did_change.append(self.onUndoState)
        # fixme: remove this once all items are using `operation_did_execute`
        gui_hooks.sidebar_should_refresh_notetypes.append(self.on_item_added)
        gui_hooks.backend_will_block.append(self.table.on_backend_will_block)
        gui_hooks.backend_did_block.append(self.table.on_backend_did_block)
        gui_hooks.operation_did_execute.append(self.on_operation_did_execute)
        gui_hooks.focus_did_change.append(self.on_focus_change)

    def teardownHooks(self) -> None:
        gui_hooks.undo_state_did_change.remove(self.onUndoState)
        gui_hooks.sidebar_should_refresh_notetypes.remove(self.on_item_added)
        gui_hooks.backend_will_block.remove(self.table.on_backend_will_block)
        gui_hooks.backend_did_block.remove(self.table.on_backend_will_block)
        gui_hooks.operation_did_execute.remove(self.on_operation_did_execute)
        gui_hooks.focus_did_change.remove(self.on_focus_change)

    def on_item_added(self, item: Any = None) -> None:
        self.sidebar.refresh()

    # Undo
    ######################################################################

    def undo(self) -> None:
        undo(parent=self)

    def onUndoState(self, on: bool) -> None:
        self.form.actionUndo.setEnabled(on)
        if on:
            self.form.actionUndo.setText(self.mw.form.actionUndo.text())

    # Edit: replacing
    ######################################################################

    @ensure_editor_saved_on_trigger
    def onFindReplace(self) -> None:
        nids = self.selected_notes()
        if not nids:
            return

        FindAndReplaceDialog(self, mw=self.mw, note_ids=nids)

    # Edit: finding dupes
    ######################################################################

    @ensure_editor_saved_on_trigger
    def onFindDupes(self) -> None:
        import anki.find

        d = QDialog(self)
        self.mw.garbage_collect_on_dialog_finish(d)
        frm = aqt.forms.finddupes.Ui_Dialog()
        frm.setupUi(d)
        restoreGeom(d, "findDupes")
        disable_help_button(d)
        searchHistory = restore_combo_history(frm.search, "findDupesFind")

        fields = sorted(
            anki.find.fieldNames(self.col, downcase=False), key=lambda x: x.lower()
        )
        frm.fields.addItems(fields)
        restore_combo_index_for_session(frm.fields, fields, "findDupesFields")
        self._dupesButton: Optional[QPushButton] = None

        # links
        frm.webView.set_title("find duplicates")
        web_context = FindDupesDialog(dialog=d, browser=self)
        frm.webView.set_bridge_command(self.dupeLinkClicked, web_context)
        frm.webView.stdHtml("", context=web_context)

        def onFin(code: Any) -> None:
            saveGeom(d, "findDupes")

        qconnect(d.finished, onFin)

        def onClick() -> None:
            search_text = save_combo_history(frm.search, searchHistory, "findDupesFind")
            save_combo_index_for_session(frm.fields, "findDupesFields")
            field = fields[frm.fields.currentIndex()]
            self.duplicatesReport(frm.webView, field, search_text, frm, web_context)

        search = frm.buttonBox.addButton(
            tr.actions_search(), QDialogButtonBox.ActionRole
        )
        qconnect(search.clicked, onClick)
        d.show()

    def duplicatesReport(
        self,
        web: AnkiWebView,
        fname: str,
        search: str,
        frm: aqt.forms.finddupes.Ui_Dialog,
        web_context: FindDupesDialog,
    ) -> None:
        self.mw.progress.start()
        try:
            res = self.mw.col.findDupes(fname, search)
        except Exception as e:
            self.mw.progress.finish()
            showWarning(str(e))
            return
        if not self._dupesButton:
            self._dupesButton = b = frm.buttonBox.addButton(
                tr.browsing_tag_duplicates(), QDialogButtonBox.ActionRole
            )
            qconnect(b.clicked, lambda: self._onTagDupes(res))
        t = ""
        groups = len(res)
        notes = sum(len(r[1]) for r in res)
        part1 = tr.browsing_group(count=groups)
        part2 = tr.browsing_note_count(count=notes)
        t += tr.browsing_found_as_across_bs(part=part1, whole=part2)
        t += "<p><ol>"
        for val, nids in res:
            t += (
                """<li><a href=# onclick="pycmd('%s');return false;">%s</a>: %s</a>"""
                % (
                    html.escape(
                        self.col.build_search_string(
                            SearchNode(nids=SearchNode.IdList(ids=nids))
                        )
                    ),
                    tr.browsing_note_count(count=len(nids)),
                    html.escape(val),
                )
            )
        t += "</ol>"
        web.stdHtml(t, context=web_context)
        self.mw.progress.finish()

    def _onTagDupes(self, res: List[Any]) -> None:
        if not res:
            return
        self.begin_reset()
        self.mw.checkpoint(tr.browsing_tag_duplicates())
        nids = set()
        for _, nidlist in res:
            nids.update(nidlist)
        self.col.tags.bulk_add(list(nids), tr.browsing_duplicate())
        self.mw.progress.finish()
        self.end_reset()
        self.mw.requireReset(reason=ResetReason.BrowserTagDupes, context=self)
        tooltip(tr.browsing_notes_tagged())

    def dupeLinkClicked(self, link: str) -> None:
        self.search_for(link)
        self.onNote()

    # Jumping
    ######################################################################

    def has_previous_card(self) -> bool:
        return self.table.has_previous()

    def has_next_card(self) -> bool:
        return self.table.has_next()

    def onPreviousCard(self) -> None:
        self.focusTo = self.editor.currentField
        self.editor.call_after_note_saved(self.table.to_previous_row)

    def onNextCard(self) -> None:
        self.focusTo = self.editor.currentField
        self.editor.call_after_note_saved(self.table.to_next_row)

    def onFirstCard(self) -> None:
        self.table.to_first_row()

    def onLastCard(self) -> None:
        self.table.to_last_row()

    def onFind(self) -> None:
        # workaround for PyQt focus bug
        self.editor.hideCompleters()

        self.form.searchEdit.setFocus()
        self.form.searchEdit.lineEdit().selectAll()

    def onNote(self) -> None:
        # workaround for PyQt focus bug
        self.editor.hideCompleters()

        self.editor.web.setFocus()
        self.editor.loadNote(focusTo=0)

    def onCardList(self) -> None:
        self.form.tableView.setFocus()
