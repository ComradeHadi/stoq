# -*- coding: utf-8 -*-
# vi:si:et:sw=4:sts=4:ts=4

##
## Copyright (C) 2006-2007 Async Open Source <http://www.async.com.br>
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

from stoqlib.domain.costcenter import CostCenterEntry
from stoqlib.domain.test.domaintest import DomainTest


class TestCostCenter(DomainTest):
    def testAddTransaction(self):
        cost_center = self.create_cost_center()
        stock_trans = self.create_stock_transaction_history()
        stock_trans.quantity = -1

        entry = self.store.find(CostCenterEntry, stock_transaction=stock_trans)
        self.assertEquals(len(list(entry)), 0)

        cost_center.add_stock_transaction(stock_trans)

        entry = self.store.find(CostCenterEntry, stock_transaction=stock_trans)
        self.assertEquals(len(list(entry)), 1)
        self.assertEquals(entry[0].stock_transaction, stock_trans)

    def testAddLonelyPayment(self):
        cost_center = self.create_cost_center()
        payment = self.create_payment()

        entry = self.store.find(CostCenterEntry, payment=payment)
        self.assertEquals(len(list(entry)), 0)

        cost_center.add_lonely_payment(payment)

        entry = self.store.find(CostCenterEntry, payment=payment)
        self.assertEquals(len(list(entry)), 1)
        self.assertEquals(entry[0].payment, payment)