# -*- coding: utf-8 -*-

from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, ValidationError


class test_money_order(TransactionCase):
    '''测试收付款'''
    def test_money_order_unlink(self):
        '''测试收付款单删除'''
        self.env.ref('money.get_40000').money_order_done()
        # 审核后不能删除
        with self.assertRaises(UserError):
            self.env.ref('money.get_40000').unlink()
        # 未审核，可以删除
        self.env.ref('money.pay_2000').unlink()

    def test_money_order_draft(self):
        ''' 测试收付款反审核  '''
        last_balance = self.env.ref('core.comm').balance
        jd_receivable = self.env.ref('core.jd').receivable
        lenovo_payable = self.env.ref('core.lenovo').payable
        # 先收款后付款。收款账户余额增加，业务伙伴应收款减少；
        # 付款账户余额减少，业务伙伴应付款减少
        self.env.ref('money.get_40000').money_order_done()
        self.assertEqual(
            self.env.ref('core.jd').receivable,
            jd_receivable - 40000)
        self.env.ref('money.pay_2000').money_order_done()
        self.assertEqual(
            self.env.ref('core.comm').balance,
            last_balance + 40000 - 2000)
        self.assertEqual(
            self.env.ref('core.lenovo').payable,
            lenovo_payable - 2000)
        # 余额不足不能反审核
        with self.assertRaises(UserError):
            self.env.ref('money.get_40000').money_order_draft()
        # 反审核付款'money.pay_2000'，账户余额增加，业务伙伴应付款增加
        self.env.ref('money.pay_2000').money_order_draft()
        self.assertEqual(
            self.env.ref('core.comm').balance,
            last_balance + 40000 - 2000 + 2000)
        self.assertEqual(
            self.env.ref('core.lenovo').payable,
            lenovo_payable - 2000 + 2000)

    def test_money_order_draft_voucher_done(self):
        ''' 测试收付款反审核 ：审核后的凭证先反审核再删除 '''
        self.env.ref('money.get_40000').money_order_done()
        self.env.ref('money.get_40000').money_order_draft()

    def test_money_order_onchange(self):
        '''测试收付款onchange'''
        # onchange_date  'get','pay'
        self.env.ref('money.get_40000').with_context({'type': 'get'}) \
            .onchange_date()
        self.env.ref('money.pay_2000').with_context({'type': 'pay'}) \
            .onchange_date()
        # onchange_partner_id 执行self.env.context.get('type') == 'get'
        self.env.ref('money.get_40000').with_context({'type': 'get'}) \
            .onchange_partner_id()
        # onchange_partner_id 执行self.env.context.get('type') == 'pay'
        self.env.ref('money.pay_2000').with_context({'type': 'pay'}) \
            .onchange_partner_id()
        # onchange_partner_id 执行partner_id为空，return
        self.partner_id = False
        self.env['money.order'].onchange_partner_id()
        # onchange_partner_id 存在 money_invoice 的情况
        self.env.ref('money.get_40000').money_order_done()
        self.env['money.invoice'].create({
            'partner_id': self.env.ref('core.jd').id, 'date': "2016-02-20",
            'name': 'invoice/2016001',
            'category_id': self.env.ref('money.core_category_sale').id,
            'amount': 200.0,
            'reconciled': 0,
            'to_reconcile': 200.0,
            'date_due': '2016-09-07'})
        self.env['money.order'].with_context({'type': 'get'}) \
            .create({
                'partner_id': self.env.ref('core.jd').id,
                'name': 'GET/20161017', 'date': "2016-02-20",
                'line_ids': [(0, 0, {
                    'bank_id': self.env.ref('core.comm').id,
                    'amount': 200.0})]
                }).onchange_partner_id()

    def test_money_order_done(self):
        ''' 测试收付款审核  '''
        # 余额不足不能付款
        with self.assertRaises(UserError):
            self.env.ref('money.pay_2000').money_order_done()
        # 收款
        self.env.ref('money.get_40000').money_order_done()
        # 执行money_order_draft 遍历source_ids的操作
        invoice = self.env['money.invoice'].create({
            'partner_id': self.env.ref('core.jd').id, 'date': "2016-02-20",
            'name': 'invoice/2016001',
            'category_id': self.env.ref('money.core_category_sale').id,
            'amount': 200.0,
            'reconciled': 0,
            'to_reconcile': 200.0,
            'date_due': '2016-09-07'})
        money = self.env['money.order'].with_context({'type': 'get'}) \
            .create({
                'partner_id': self.env.ref('core.jd').id,
                'name': 'GET/2016001', 'date': "2016-02-20",
                'note': 'zxy note',
                'line_ids': [(0, 0, {
                    'bank_id': self.env.ref('core.comm').id,
                    'amount': 200.0, 'note': 'money note'})],
                'source_ids': [(0, 0, {
                    'name': invoice.id,
                    'category_id': self.env.ref('money.core_category_sale').id,
                    'date': '2016-04-07',
                    'amount': 200.0,
                    'reconciled': 0,
                    'to_reconcile': 200.0,
                    'this_reconcile': 200.0,
                    'date_due': '2016-09-07'})],
                'type': 'get'})
        money.money_order_done()
        money.money_order_draft()
        # to_reconcile < this_concile, 执行'本次核销金额不能大于未核销金额'
        money.source_ids.to_reconcile = 100.0
        with self.assertRaises(UserError):
            money.money_order_done()
        self.partner_id = self.env.ref('core.jd')
        # advance_payment < 0, 执行'核销金额不能大于付款金额'
        self.env.ref('money.pay_2000').line_ids.amount = -10.0
        with self.assertRaises(UserError):
            self.env.ref('money.pay_2000').money_order_done()

        # 清空一级客户类别的科目，审核时报错
        self.env.ref('core.customer_category_1').account_id = False
        with self.assertRaises(UserError):
            self.env.ref('money.get_40000').money_order_done()
        # 清空本地供应商类别的科目，审核时报错
        self.env.ref('core.supplier_category_1').account_id = False
        with self.assertRaises(UserError):
            self.env.ref('money.pay_2000').money_order_done()

    def test_money_order_create_raise_exists_error(self):
        # 同一业务伙伴存在两个未审核的付款单，报错
        with self.assertRaises(UserError):
            self.env['money.order'].with_context({'type': 'get'}) \
            .create({
                    'partner_id': self.env.ref('core.jd').id,
                    'name': 'GET/201600111',
                    'date': "2016-02-20",
                    'type': 'get'
                    })

        with self.assertRaises(UserError):
            self.env.ref('money.pay_2000').partner_id = self.env.ref('core.jd').id

    def test_money_order_done_get_voucher(self):
        ''' 测试收付款审核时 单据行与当前用户公司的 currency 不一致的情况 '''
        # get
        self.env.ref('money.get_line_1').currency_id = self.env.ref('base.USD').id
        self.env.user.company_id.currency_id = self.env.ref('base.CNY').id
        self.env.ref('money.get_40000').money_order_done()
        # pay
        self.env.ref('money.pay_line_1').currency_id = self.env.ref('base.USD').id
        self.env.ref('money.pay_2000').money_order_done()

    def test_money_order_voucher(self):
        invoice = self.env['money.invoice'].create({
            'partner_id': self.env.ref('core.jd').id, 'date': "2016-02-20",
            'name': 'invoice/2016001',
            'category_id': self.env.ref('money.core_category_sale').id,
            'amount': 200.0,
            'reconciled': 0,
            'to_reconcile': 200.0,
            'date_due': '2016-09-07'})

        # 把业务伙伴未审核的收付款单审核
        self.env.ref('money.get_40000').money_order_done()
        self.env.ref('money.pay_2000').money_order_done()

        # get 存在结算单行
        money1 = self.env['money.order'].with_context({'type': 'get'}) \
            .create({
                'partner_id': self.env.ref('core.jd').id,
                'name': 'GET/20161017', 'date': "2016-02-20",
                'line_ids': [(0, 0, {
                    'bank_id': self.env.ref('core.comm').id,
                    'amount': 200.0})],
                'source_ids': [(0, 0, {
                    'name': invoice.id,
                    'category_id': self.env.ref('money.core_category_sale').id,
                    'date': '2016-02-20',
                    'amount': 210.0,
                    'reconciled': 0,
                    'to_reconcile': 210.0,
                    'this_reconcile': 210.0,
                    'date_due': '2016-09-07'})],
                'type': 'get'})
        money1.discount_account_id = self.env.ref('finance.small_business_chart5603001').id
        money1.discount_amount = 10
        money1.money_order_done()

        # pay
        invoice.partner_id = self.env.ref('core.lenovo').id
        money2 = self.env['money.order'].with_context({'type': 'pay'}) \
            .create({
                'partner_id': self.env.ref('core.lenovo').id,
                'name': 'PAY/2016001', 'date': "2016-02-20",
                'note': 'note',
                'line_ids': [(0, 0, {
                    'bank_id': self.env.ref('core.comm').id,
                    'amount': 200.0, 'note': 'money note'})],
                'source_ids': [(0, 0, {
                    'name': invoice.id,
                    'category_id': self.env.ref('money.core_category_purchase').id,
                    'date': '2016-02-20',
                    'amount': 210.0,
                    'reconciled': 0,
                    'to_reconcile': 210.0,
                    'this_reconcile': 210.0,
                    'date_due': '2016-09-07'})],
                'type': 'pay'})

        money2.discount_account_id = self.env.ref('finance.small_business_chart5603002').id
        money2.discount_amount = 10
        money2.money_order_done()

    def test_money_order_without_source_no_bank_account(self):
        '''测试 不带结算单明细行的收款单银行账户不存在 account_id 的情况'''
        self.env.ref('money.get_line_1').bank_id.account_id = False
        with self.assertRaises(UserError):
            self.env.ref('money.get_40000').money_order_done()
        self.env.ref('money.pay_line_1').bank_id.account_id = False
        with self.assertRaises(UserError):
            self.env.ref('money.pay_2000').money_order_done()

    def test_money_order_withsource_no_bank_account(self):
        '''测试 带结算单明细行的收款单银行账户不存在 account_id 的情况'''
        self.env.ref('money.get_40000').money_order_done()
        temp_bank = self.env['bank.account'].create({'name': 'temporary bank',
                                         'currency_id': self.env.ref('base.CNY').id,
                                         'account_id': False})

        invoice = self.env['money.invoice'].create({
            'partner_id': self.env.ref('core.jd').id, 'date': "2016-02-20",
            'name': 'invoice/201610171',
            'category_id': self.env.ref('money.core_category_sale').id,
            'amount': 200.0,
            'reconciled': 0,
            'to_reconcile': 200.0,
            'date_due': '2016-09-07'})
        get_money = self.env['money.order'].with_context({'type': 'get'}) \
            .create({'partner_id': self.env.ref('core.jd').id,
                    'name': 'GET/2016001', 'date': "2016-02-20",
                    'line_ids': [(0, 0, {
                        'bank_id': temp_bank.id,
                        'amount': 200.0})],
                     'source_ids': [(0, 0, {'name': invoice.id,
                        'category_id': self.env.ref('money.core_category_purchase').id,
                        'date': '2016-02-20', 'amount': 200.0,
                        'reconciled': 0, 'to_reconcile': 200.0,
                        'this_reconcile': 200.0, 'date_due': '2016-09-07'})],
                    'type': 'get'})

        # get 银行账户没设置科目 有结算单行
        with self.assertRaises(UserError):
            get_money.money_order_done()

        self.env.ref('money.pay_2000').money_order_done()
        invoice.partner_id = self.env.ref('core.lenovo').id
        pay_money = self.env['money.order'].with_context({'type': 'pay'}) \
            .create({'partner_id': self.env.ref('core.lenovo').id,
                    'name': 'PAY/2016001', 'date': "2016-02-20",
                    'line_ids': [(0, 0, {
                        'bank_id': temp_bank.id,
                        'amount': 200.0, 'note': 'money note'})],
                     'source_ids': [(0, 0, {'name': invoice.id,
                        'category_id': self.env.ref('money.core_category_purchase').id,
                        'date': '2016-02-20', 'amount': 200.0, 'reconciled': 0,
                        'to_reconcile': 200.0, 'this_reconcile': 200.0, 'date_due': '2016-09-07'})],
                    'type': 'pay'})

        # pay 银行账户没设置科目 有结算单行
        with self.assertRaises(UserError):
            pay_money.money_order_done()

    def test_compute_currency_id(self):
        '''测试 结算帐户与业务伙伴币别不一致 报错'''
        self.env.ref('money.get_40000').currency_id = self.env.ref('base.USD').id
        with self.assertRaises(ValidationError):
            self.env.ref('money.get_line_1').bank_id = self.env.ref('core.alipay').id


class test_other_money_order(TransactionCase):
    '''测试其他收支单'''

    def test_other_money_order_unlink(self):
        '''测试其他收支单删除'''
        self.env.ref('money.other_get_60').other_money_done()
        # 审核状态不可删除
        with self.assertRaises(UserError):
            self.env.ref('money.other_get_60').unlink()
        # 未审核可以删除
        self.env.ref('money.other_pay_9000').unlink()

    def test_other_money_order_draft(self):
        ''' 测试其他收入支出反审核'''
        self.env.ref('money.get_40000').money_order_done()
        self.env.ref('money.other_pay_1000').other_money_done()
        self.env.ref('money.other_get_60').other_money_done()
        # 反审核
        self.env.ref('money.other_pay_1000').other_money_draft()
        # 反审核：收款退款余额不足，不能付款
        self.env.ref('money.other_get_60').line_ids.amount = 45000
        with self.assertRaises(UserError):
            self.env.ref('money.other_get_60').other_money_draft()

    def test_other_money_order(self):
        ''' 测试其他收入支出 '''
        self.env.ref('money.other_get_60').other_money_done()
        # 审核：余额不足，不能付款
        with self.assertRaises(UserError):
            self.env.ref('money.other_pay_9000').other_money_done()
        # 审核：转出账户收一笔款
        self.env.ref('money.get_40000').money_order_done()
        self.env.ref('money.other_pay_1000').other_money_done()
        # onchange_date  同时执行create时的type=other_get
        invoice = self.env['money.invoice'].create({
            'name': 'invoice', 'date': "2016-02-20",
            'partner_id': self.env.ref('core.jd').id,
            'category_id': self.env.ref('money.core_category_sale').id,
            'amount': 10.0,
            'reconciled': 0})
        other = self.env['other.money.order'] \
            .with_context({'type': 'other_get'}) \
            .create({
                'partner_id': self.env.ref('core.jd').id, 'date': "2016-02-20",
                'bank_id': self.env.ref('core.comm').id,
                'line_ids': [(0, 0, {
                    'category_id': self.env.ref('money.core_category_sale').id,
                    'amount': 10.0})]})
        other.onchange_date()

        other.other_money_done()
        other.other_money_draft()
        # onchange_date 执行type=other_pay
        invoice.partner_id = self.env.ref('core.lenovo').id,

        other = self.env['other.money.order'] \
            .with_context({'type': 'other_pay'}) \
            .create({
                'partner_id': self.env.ref('core.lenovo').id,
                'bank_id': self.env.ref('core.comm').id})
        other.onchange_date()

        # 测试其他收支单金额<0,执行if报错
        other = self.env['other.money.order'].create({
            'partner_id': self.env.ref('core.jd').id,
            'bank_id': self.env.ref('core.comm').id,
            'type': 'other_get'})
        self.env['other.money.order.line'].create({
            'other_money_id': other.id,
            'category_id': self.env.ref('money.core_category_sale').id,
            'amount': -10.0})
        with self.assertRaises(UserError):
            other.other_money_done()

        # other_get 没有设置科目 银行账户没设置科目
        other.line_ids[0].amount = 10
        other.line_ids[0].category_id.account_id = False
        with self.assertRaises(UserError):
            other.other_money_done()
        # other_pay 没有设置科目 银行账户没设置科目
        other = self.env['other.money.order'] \
            .with_context({'type': 'other_get'}) \
            .create({
                'partner_id': self.env.ref('core.jd').id, 'date': "2016-02-20",
                    'bank_id': self.env.ref('core.comm').id,
                    'line_ids': [(0, 0, {
                        'category_id': self.env.ref('money.core_category_sale').id,
                        'amount': 10.0})]})
        other.line_ids[0].category_id.account_id = False
        with self.assertRaises(UserError):
            other.other_money_done()
            
    def test_other_money_order_no_bank_account(self):
        ''' 其他收支单审核，bank 的 account 不存在 '''
        other_get = self.env.ref('money.other_get_60')
        other_get.bank_id.account_id = False
        with self.assertRaises(UserError):
            other_get.other_money_done()


class test_other_money_order_line(TransactionCase):
    ''' 测试其他收支单明细 '''

    def setUp(self):
        '''准备数据'''
        super(test_other_money_order_line, self).setUp()
        self.get_order = self.env.ref('money.other_get_60').with_context({'type': 'other_get'})
        self.pay_order = self.env.ref('money.other_pay_1000').with_context({'type': 'other_pay'})

        self.service_1 = self.env.ref('core.service_1')

    def test_onchange_service(self):
        ''' 测试选择了服务的onchange '''
        # 其他收入单
        for line in self.get_order.line_ids:
            line.service = self.service_1   # 咨询服务
            line.onchange_service()
            self.assertTrue(line.category_id.id == self.service_1.get_categ_id.id)
            self.assertTrue(line.amount == 500)

        # 其他支出单
        for line in self.pay_order.line_ids:
            line.service = self.service_1   # 咨询服务
            line.onchange_service()
            self.assertTrue(line.category_id.id == self.service_1.pay_categ_id.id)
            self.assertTrue(line.amount == 500)

    def test_onchange_tax_amount(self):
        '''当订单行的金额、税率改变时，改变税额'''
        # 其他收入单
        for line in self.get_order.line_ids:
            line.service = self.service_1   # 咨询服务
            line.amount = 1000
            line.tax_rate = 17
            line.onchange_tax_amount()
            self.assertTrue(line.tax_amount == 170)


class test_money_transfer_order(TransactionCase):
    '''测试其他资金转账单'''

    def test_money_transfer_order_unlink(self):
        '''测试资金转账单删除'''
        self.env.ref('money.get_40000').money_order_done()
        self.env.ref('money.transfer_300').money_transfer_done()
        # 已审核的转账单不能删除
        with self.assertRaises(UserError):
            self.env.ref('money.transfer_300').unlink()
        # 未审核的转账单可以删除
        self.env.ref('money.transfer_400').unlink()

    def test_money_transfer_order_draft(self):
        '''测试资金转账单反审核'''
        self.env.ref('money.get_40000').money_order_done()
        self.env.ref('money.transfer_300').money_transfer_done()
        # 反审核
        self.env.ref('money.transfer_300').money_transfer_draft()
        # 转入账户余额不足，不能反审核
        self.env.ref('core.alipay').balance = \
            self.env.ref('core.alipay').balance - 100
        with self.assertRaises(UserError):
            self.env.ref('money.transfer_400').money_transfer_draft()

    def test_money_transfer_order(self):
        ''' 测试转账单审核 '''
        comm_balance = self.env.ref('core.comm').balance
        money_transfer_300 = self.env.ref('money.transfer_300')
        with self.assertRaises(UserError):
            # 转出账户余额不足
            money_transfer_300.money_transfer_done()
        # 转出账户收一笔款
        self.env.ref('money.get_40000').money_order_done()
        # 审核
        money_transfer_300.money_transfer_done()
        self.assertEqual(
            self.env.ref('core.comm').balance,
            comm_balance + 40000 - 300)
        self.assertEqual(
            self.env.ref('core.alipay').balance,
            comm_balance + 300)
        # line_ids不存在，则审核报错
        transfer_order = self.env['money.transfer.order']
        transfer_no_line = transfer_order.create({'note': 'no line'})
        with self.assertRaises(UserError):
            transfer_no_line.money_transfer_done()
        # 转出转入账户相同，则审核报错
        money_transfer_300.line_ids.out_bank_id = \
            self.env.ref('core.alipay').id
        with self.assertRaises(UserError):
            money_transfer_300.money_transfer_done()
        # 转出金额<0，则审核报错
        money_transfer_300.line_ids.out_bank_id = self.env.ref('core.comm').id
        money_transfer_300.line_ids.amount = -10.0
        with self.assertRaises(UserError):
            money_transfer_300.money_transfer_done()
        # 转出金额=0，则审核报错
        money_transfer_300.line_ids.out_bank_id = self.env.ref('core.comm').id
        money_transfer_300.line_ids.amount = 0
        with self.assertRaises(UserError):
            money_transfer_300.money_transfer_done()

    def test_inCurrency_notEqual_company_curreny(self):
        '''测试 资金转账单 转入账户与公司币别不一致 '''
        self.env.ref('money.get_40000').money_order_done()
        self.env.ref('money.transfer_line_1').out_bank_id.account_id = self.env.ref('finance.account_cash').id
        self.env.ref('money.transfer_line_1').in_bank_id.account_id.currency_id = self.env.ref('base.USD').id
        self.env.ref('money.transfer_line_1').currency_amount = 233.75
        self.env.ref('money.transfer_300').money_transfer_done()

    def test_outCurrency_notEqual_company_curreny(self):
        '''测试 资金转账单 转出账户与公司币别不一致 '''
        # 转出账户余额不足
        self.env.ref('money.transfer_line_1').out_bank_id.account_id.currency_id = self.env.ref('base.USD').id
        self.env.ref('money.transfer_line_1').currency_amount = 233.75
        with self.assertRaises(UserError):
            self.env.ref('money.transfer_300').money_transfer_done()

        # 转入账户与公司币别一致 : in_currency_id == company_currency_id
        self.env.ref('money.get_40000').money_order_done()
        self.env.ref('money.transfer_line_1').in_bank_id.account_id = self.env.ref('finance.account_cash').id
        self.env.ref('money.transfer_300').money_transfer_done()

        # 系统不支持外币转外币
        self.env.ref('money.transfer_300').money_transfer_draft()
        self.env.ref('money.transfer_line_1').out_bank_id.account_id.currency_id = self.env.ref('base.USD').id
        self.env.ref('money.transfer_line_1').in_bank_id.account_id.currency_id = self.env.ref('base.USD').id
        with self.assertRaises(UserError):
            self.env.ref('money.transfer_300').money_transfer_done()


class test_partner(TransactionCase):

    def test_partner(self):
        ''' 客户、供应商对账单 和  银行帐'''
        self.env.ref('core.jd').partner_statements()
        self.env.ref('core.lenovo').partner_statements()
        self.env.ref('core.comm').bank_statements()

    def test_partner_set_init(self):
        '''测试客户期初'''
        customer = self.env.ref('core.jd')
        customer.receivable_init = 1234567
        self.assertEqual(customer.receivable, customer.receivable_init)
        # 测试  客户 如果有前期初值，删掉已前的单据   的 if 判断
        customer._set_receivable_init()

        vendor = self.env.ref('core.lenovo')
        vendor.payable_init = 23456789
        self.assertEqual(vendor.payable, vendor.payable_init)
        # 测试   供应商如果有前期初值，删掉已前的单据   的 if 判断
        vendor._set_payable_init()

    def test_bank_set_init(self):
        '''测试资金期初'''
        bank = self.env.ref('core.comm')
        balance = bank.balance
        bank.init_balance = 1111
        self.assertEqual(bank.balance, bank.init_balance + balance)
        # 测试   资金如果有前期初值，删掉已前的单据   的 if 判断
        bank._set_init_balance()
