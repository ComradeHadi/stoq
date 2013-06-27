# -*- coding: utf-8 -*-
# vi:si:et:sw=4:sts=4:ts=4

##
## Copyright (C) 2013 Async Open Source <http://www.async.com.br>
## All rights reserved
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU Lesser General Public License as published by
## the Free Software Foundation; either version 2 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU Lesser General Public License
## along with this program; if not, write to the Free Software
## Foundation, Inc., or visit: http://www.gnu.org/.
##
## Author(s): Stoq Team <stoq-devel@async.com.br>
##

from stoqlib.reporting.report import HTMLReport
from stoqlib.lib.translation import stoqlib_gettext

_ = stoqlib_gettext


class OpticalWorkOrderReceiptReport(HTMLReport):
    title = _("Work order")
    template_filename = "optical/optical.html"
    complete_header = True

    def __init__(self, filename, workorders):
        self.workorders = workorders
        # The workorders are always from the same sale.
        self.sale = workorders[0].sale
        self.subtitle = _("Sale number: %s") % self.sale.identifier
        super(OpticalWorkOrderReceiptReport, self).__init__(filename)

    def get_optical_data(self, workorder):
        from optical.opticaldomain import OpticalWorkOrder
        store = self.sale.store
        return store.find(OpticalWorkOrder, work_order=workorder).one()
