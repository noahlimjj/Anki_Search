# -*- coding: utf-8 -*-
# Interface between Anki Review and this addon
import html
import urllib
# This files is part of anki-web-browser addon
# @author ricardo saturnino
# ------------------------------------------------
from typing import List, Optional, Iterable

from aqt import gui_hooks, mw
from aqt.qt import QAction
from aqt.reviewer import Reviewer

from .base_controller import BaseController
from .browser_context_menu import DataImportListener
from .config.main import config_service as cfg
from .core import Feedback
from .exception_handler import exceptionHandler
from .no_selection import NoSelectionResult


class ReviewController(BaseController, DataImportListener):
    """
        The mediator/adapter between Anki with its components and this addon specific API
    """

    browser = None
    _curSearch: List[str] = None
    _last_card_id: Optional[int] = None

    def __init__(self):
        super(ReviewController, self).__init__()

    def init_configurable_components(self):
        super().init_configurable_components()
        self.setup_bindings()

    def setup_bindings(self):
        # Remove context menu, use shift+click instead
        # gui_hooks.webview_will_show_context_menu.append(self.onReviewerHandle)
        
        gui_hooks.card_will_show.append(self.load_card)
        # Hook into Anki's bridge command system
        from aqt import mw
        self._old_link_handler = mw.reviewer._linkHandler
        mw.reviewer._linkHandler = self._wrap_link_handler(mw.reviewer._linkHandler)
        
        Reviewer._shortcutKeys = self.wrap_shortcutKeys(Reviewer._shortcutKeys)

        action = QAction("Anki-Web-Browser Config", mw)
        action.triggered.connect(ReviewController.open_config)
        mw.form.menuTools.addAction(action)
        self._result_handler.create_image_from_url = ReviewController._import_urlToLink

    @staticmethod
    def _import_urlToLink(url):
        return ""  # not supported yet

    @staticmethod
    def open_config():
        from .config.config_ctrl import ConfigController
        cc = ConfigController(mw)
        cc.open()

    def wrap_shortcutKeys(self, fn):
        ref = self

        def customShortcut(self):
            sList = fn(self)
            sList.append((cfg.getConfig().menuShortcut, lambda: ref.createReviewerMenu(mw.web, mw.web)))

            sList.append((cfg.getConfig().repeatShortcut, ref._repeat_provider_or_show_menu))
            return sList

        return customShortcut

    # --------------------------------------------------------------------------

    @exceptionHandler
    def _repeat_provider_or_show_menu(self):
        if not self._curSearch:
            return self.createReviewerMenu(mw.web, mw.web)

        webView = mw.web
        super()._repeat_provider_or_show_menu_for_view(webView)

    def handleProviderSelection(self, resultList: List[str]):
        Feedback.log('Handle provider selection')
        webview = mw.web
        query = self._getQueryValue(webview)
        self._curSearch = resultList
        if not query:
            return
        Feedback.log('Query: %s' % query)
        self.openInBrowser(query)

    @exceptionHandler
    def createReviewerMenu(self, webView, menu):
        """Handles context menu event on Reviewer"""

        self._providerSelection.showCustomMenu(menu, self.handleProviderSelection)

    def handleNoSelectionResult(self, result: NoSelectionResult):
        if not result or \
                result.resultType in (NoSelectionResult.NO_RESULT, NoSelectionResult.SELECTION_NEEDED):
            Feedback.showInfo('No value selected')
            return
        value = result.value
        if result.resultType == NoSelectionResult.USE_FIELD:
            value = self._currentNote.fields[result.value]
            value = self._filterQueryValue(value)
            Feedback.log('USE_FIELD {}: {}'.format(result.value, value))

        return self.openInBrowser(value)

    def getCurrentSearch(self) -> List[str]:
        return self._curSearch

    # ---------------------------------- Events listeners ---------------------------------

    def load_card(self, text: str, card, kind: str) -> str:
        Feedback.log('WebBrowser - CardShift')
        if not self.browser or cfg.getConfig().useSystemBrowser:
            # Inject JavaScript for ctrl+click handling even with system browser
            text += self._inject_shift_click_js()
            return text

        if self._last_card_id != card.id:
            self.browser.clearContext()
        if not cfg.getConfig().keepBrowserOpened:
            self.browser.close()

        self._currentNote = card.note()
        self.update_fields_from_note()
        self._last_card_id = card.id

        # Inject JavaScript for ctrl+click handling
        text += self._inject_shift_click_js()
        return text

    def onReviewerHandle(self, webView, menu):
        """
            Wrapper to the real context menu handler on the reviewer;
        """

        if mw.reviewer and mw.reviewer.card:
            self.createReviewerMenu(webView, menu)

    def handle_selection(self, field_index: int, value: any, isUrl=False):
        if isUrl:
            Feedback.showWarn("Importing media (URLs) is not supported in Review mode")
            return

        imported_content = self._result_handler.handle_selection(value, isUrl)
        if imported_content is None:
            return

        note = self._currentNote
        note.fields[field_index] += imported_content
        mw.col.update_note(note)
        mw.reviewer._redraw_current_card()
        Feedback.showInfo("Anki Web Browser: Note was edited during review. New content is imported.")

    def beforeOpenBrowser(self):
        self.browser.setFields(None)  # clear fields
        self.browser.setInfoList(['No action available on Reviewer mode'])
        self.browser.set_import_listener(self)

        self.update_fields_from_note()

    def update_fields_from_note(self):
        if not self._currentNote:
            return
        note = self._currentNote
        fieldList = note.note_type()["flds"]
        fieldsNames = {
            ind: val for ind, val in enumerate(map(lambda i: i["name"], fieldList))
        }
        self.browser.setFields(fieldsNames)

    def _inject_shift_click_js(self):
        """Inject JavaScript to handle Ctrl+Click events"""
        return '''
        <script>
        (function() {
            // Remove any existing event listeners
            document.removeEventListener('click', handleShiftClick, true);
            
            function handleShiftClick(event) {
                if (event.ctrlKey && event.button === 0) { // Left click with Ctrl
                    event.preventDefault();
                    event.stopPropagation();
                    
                    var selection = window.getSelection();
                    var selectedText = '';
                    
                    // If there's a selection, use it
                    if (selection && selection.toString()) {
                        selectedText = selection.toString().trim();
                    } else {
                        // If no selection, try to get word under cursor
                        var range = document.caretRangeFromPoint(event.clientX, event.clientY);
                        if (range) {
                            var textNode = range.startContainer;
                            if (textNode.nodeType === Node.TEXT_NODE) {
                                var text = textNode.textContent;
                                var offset = range.startOffset;
                                
                                // Find word boundaries
                                var start = offset;
                                var end = offset;
                                
                                // Find start of word
                                while (start > 0 && /\\w/.test(text[start - 1])) {
                                    start--;
                                }
                                
                                // Find end of word
                                while (end < text.length && /\\w/.test(text[end])) {
                                    end++;
                                }
                                
                                selectedText = text.substring(start, end).trim();
                            }
                        }
                    }
                    
                    if (selectedText) {
                        // Send message to Python
                        if (typeof pycmd !== 'undefined') {
                            pycmd('ankiWebBrowserShiftClick:' + selectedText);
                        }
                    }
                }
            }
            
            // Add event listener with capture=true to catch events early
            document.addEventListener('click', handleShiftClick, true);
        })();
        </script>
        '''

    def _wrap_link_handler(self, original_handler):
        """Wrap the original link handler to intercept our shift+click commands"""
        def wrapped_handler(url):
            if url.startswith('ankiWebBrowserShiftClick:'):
                selected_text = url.replace('ankiWebBrowserShiftClick:', '')
                if selected_text.strip():
                    Feedback.log(f'Ctrl+Click detected on text: {selected_text}')
                    # Simulate the old behavior but triggered by ctrl+click
                    self._handle_shift_click_selection(selected_text.strip())
                return
            # Call original handler for all other links
            return original_handler(url)
        return wrapped_handler

    def _handle_shift_click_selection(self, selected_text):
        """Handle the selected text from shift+click"""
        # Set the current search to default providers (automatically use Google Web)
        self._curSearch = ['Google Web']
        
        # Open in browser with the selected text
        self.openInBrowser(selected_text)

review_controller = ReviewController()