# -*- Mode: Python; coding: utf-8 -*-
# vi:si:et:sw=4:sts=4:ts=4

##
## Copyright (C) 2013 Async Open Source <http://www.async.com.br>
## All rights reserved
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 2 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with this program; if not, write to the Free Software
## Foundation, Inc., or visit: http://www.gnu.org/.
##
## Author(s): Stoq Team <stoq-devel@async.com.br>
##

import logging

import gtk

from stoqlib.api import api
from stoqlib.database.runtime import get_default_store
from stoqlib.domain.workorder import WorkOrder
from stoqlib.gui.base.dialogs import run_dialog
from stoqlib.gui.editors.workordereditor import WorkOrderEditor
from stoqlib.gui.editors.producteditor import ProductEditor
from stoqlib.gui.events import (StartApplicationEvent, StopApplicationEvent,
                                EditorCreateEvent, RunDialogEvent)
from stoqlib.gui.utils.keybindings import add_bindings, get_accels
from stoqlib.gui.wizards.salequotewizard import SaleQuoteWizard
from stoqlib.lib.translation import stoqlib_gettext

from optical.medicssearch import OpticalMedicSearch
from optical.opticalslave import ProductOpticSlave, WorkOrderOpticalSlave
from optical.opticalwizard import OpticalSaleQuoteWizard

_ = stoqlib_gettext
log = logging.getLogger(__name__)


class OpticalUI(object):
    def __init__(self):
        self._ui = None
        self.default_store = get_default_store()
        StartApplicationEvent.connect(self._on_StartApplicationEvent)
        StopApplicationEvent.connect(self._on_StopApplicationEvent)
        EditorCreateEvent.connect(self._on_EditorCreateEvent)
        RunDialogEvent.connect(self._on_RunDialogEvent)
        add_bindings([
            ('plugin.optical.pre_sale', ''),
            ('plugin.optical.search_medics', ''),
        ])

    #
    # Private
    #

    def _get_menu_ui_string(self):
        return """<ui>
            <menubar name="menubar">
                <placeholder name="ExtraMenubarPH">
                    <menu action="OpticalMenu">
                    %s
                    </menu>
                </placeholder>
            </menubar>
        </ui>"""

    def _add_sale_menus(self, uimanager):
        menu_items_str = '''<menuitem action="OpticalPreSale"/>
                            <menuitem action="OpticalMedicSearch"/>'''
        ui_string = self._get_menu_ui_string() % menu_items_str

        group = get_accels('plugin.optical')
        ag = gtk.ActionGroup('OpticalMenuActions')
        ag.add_actions([
            ('OpticalMenu', None, _(u'Optical')),
            ('OpticalPreSale', None, _(u'Optical pre sale'),
             group.get('pre_sale'), None,
             self._on_OpticalPreSale__activate),
            ('OpticalMedicSearch', None, _(u'Medics ...'),
             group.get('search_medics'), None,
             self._on_MedicsSearch__activate),
        ])

        uimanager.insert_action_group(ag, 0)
        self._ui = uimanager.add_ui_from_string(ui_string)

    def _remove_app_ui(self, uimanager):
        if not self._ui:
            return
        uimanager.remove_ui(self._ui)
        self._ui = None

    def _add_work_order_editor_slave(self, editor, model, store):
        from stoqlib.gui.utils.printing import print_report
        from optical.opticalreport import OpticalWorkOrderReceiptReport
        slave = WorkOrderOpticalSlave(store, model, show_finish_date=False,
                                      visual_mode=editor.visual_mode)
        editor.add_extra_tab('Ótico', slave)

        def _print_report(button):
            print_report(OpticalWorkOrderReceiptReport, [model])

        # Also add an print button
        if model.sale:
            print_button = editor.add_button(_('Print'), gtk.STOCK_PRINT)
            print_button.connect('clicked', _print_report)

    def _add_product_slave(self, editor, model, store):
        editor.add_extra_tab(ProductOpticSlave.title,
                             ProductOpticSlave(store, model))

    def _create_pre_sale(self):
        with api.trans() as store:
            run_dialog(OpticalSaleQuoteWizard, self._current_app, store)

    #
    # Events
    #

    def _on_StartApplicationEvent(self, appname, app):
        self._current_app = app
        if appname == 'sales':
            app.new_activate = self._create_pre_sale
            self._add_sale_menus(app.uimanager)

    def _on_StopApplicationEvent(self, appname, app):
        self._remove_app_ui(app.uimanager)

    def _on_EditorCreateEvent(self, editor, model, store, *args):
        # Use type() instead of isinstance so tab does not appear on subclasses
        # (unless thats the desired effect)
        editor_type = type(editor)
        if editor_type is ProductEditor:
            self._add_product_slave(editor, model, store)
        elif editor_type is WorkOrderEditor:
            self._add_work_order_editor_slave(editor, model, store)

    def _on_RunDialogEvent(self, dialog, parent, *args, **kwargs):
        # If we are editing a sale that already has some workorders, we need to
        # use our own wizard.
        if dialog is SaleQuoteWizard:
            def select_wizard(store, model=None):
                if not model:
                    return
                has_workorders = not WorkOrder.find_by_sale(store, model).is_empty()
                if has_workorders:
                    return OpticalSaleQuoteWizard

            return select_wizard(*args, **kwargs)

    #
    # Callbacks
    #

    def _on_OpticalPreSale__activate(self, action):
        self._create_pre_sale()

    def _on_MedicsSearch__activate(self, action):
        with api.trans() as store:
            run_dialog(OpticalMedicSearch, None, store, hide_footer=True)
