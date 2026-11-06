"""Small synchronous CSV bundles over existing ledger projections."""
import csv
from datetime import timedelta, timezone
from decimal import Decimal
from io import BytesIO, StringIO
from zipfile import ZIP_DEFLATED, ZipFile

from backend.infrastructure import export_store, store
from backend.kernel.accounting import DomainError

SHANGHAI = timezone(timedelta(hours=8))
STATUS = {'pending': '待审批', 'posted': '已入账', 'reversed': '已冲销',
          'rejected': '已拒绝', 'in_transit': '待完成', 'completed': '已完成', 'cancelled': '已取消'}
KIND = {'public': '公账', 'private': '私账', 'external': '外部', 'internal': '内部'}


def timestamp(value):
    return value.astimezone(SHANGHAI).isoformat() if value else ''


def yuan(minor):
    return Decimal(minor).scaleb(-2)


def csv_bytes(headers, rows):
    output = StringIO(newline='')
    writer = csv.writer(output)
    writer.writerow(headers)
    count = 0
    for row in rows:
        # Treat user-authored text as text when opened in spreadsheet applications.
        writer.writerow(["'" + value if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@'))
                         else value for value in row])
        count += 1
    return output.getvalue().encode('utf-8-sig'), count


def bundle(db, user, mode, *, as_of=None, start=None, end=None):
    if not user.active:
        raise DomainError('请先登录', 401)
    if mode not in ('all', 'snapshot', 'changes'):
        raise DomainError('请选择导出类型')
    if (mode == 'all' and any(x is not None for x in (as_of, start, end))
            or mode == 'snapshot' and (start is not None or end is not None)
            or mode == 'changes' and (as_of is not None or start is None)):
        raise DomainError('时间参数与导出类型不匹配')
    with store.read_snapshot(db) as snapshot:
        generated = store.snapshot_timestamp(snapshot)
        cutoff = as_of if mode == 'snapshot' else end
        cutoff = cutoff or generated
        if cutoff > generated:
            raise DomainError('截止时间不能晚于当前时间')
        if start is not None and start >= cutoff:
            raise DomainError('起始时间必须早于截止时间')
        funds = {a.id: a for a in store.accounts(snapshot)}
        stocks = {a.id: a for a in store.stock_accounts(snapshot)}
        files = []
        if mode == 'snapshot':
            files.append(('资金余额.csv', csv_bytes(
                ['截止时间', '账户编号', '账户名称', '账户类型', '当前启用', '余额（元）'],
                ([timestamp(cutoff), a.code, a.name, KIND[a.kind], '是' if a.active else '否',
                  yuan(store.balance_delta(snapshot, a.id, as_of=cutoff))] for a in funds.values()))))
            files.append(('仓库库存.csv', csv_bytes(
                ['截止时间', '仓库编号', '仓库名称', '当前启用', 'SKU', '商品名称', '单位', '数量'],
                ([timestamp(cutoff), stocks[r['account_id']].code, r['account_name'],
                  '是' if stocks[r['account_id']].active else '否', r['sku_code'], r['sku_name'], r['unit'],
                  int(r['quantity'])] for r in export_store.inventory(snapshot, cutoff)))))
        else:
            def fund_rows():
                for item in export_store.fund_transfers(snapshot, start=start, end=cutoff):
                    src, dst = funds[item.source_account_id], funds[item.destination_account_id]
                    original = store.get_transfer(snapshot, item.reversal_of) if item.reversal_of else None
                    yield [item.code, timestamp(item.created_at), item.effective_date, timestamp(item.posted_at),
                           STATUS[item.status], src.code, src.name, KIND[src.kind], dst.code, dst.name, KIND[dst.kind],
                           yuan(item.amount_minor), original.code if original else '', item.description,
                           '；'.join(item.tags), item.counterparty or '']
            def stock_rows():
                for item, line, sku, move, confirmation in export_store.stock_lines(snapshot, start=start, end=cutoff):
                    src, dst = stocks[item.source_account_id], stocks[item.destination_account_id]
                    yield [item.code, timestamp(item.created_at), item.effective_date,
                           timestamp(move.created_at) if move else '', move.effective_date if move else '',
                           STATUS[item.status], src.code, src.name, KIND[src.kind], dst.code, dst.name, KIND[dst.kind],
                           sku.code, sku.name, sku.unit, line.quantity, confirmation.code if confirmation else '',
                           item.source_reference or '', item.description, '；'.join(item.tags)]
            files.append(('资金台账.csv', csv_bytes(
                ['资金单编号', '创建时间', '业务日期', '实际入账时间', '当前状态', '来源账户编号', '来源账户名称', '来源类型',
                 '去向账户编号', '去向账户名称', '去向类型', '金额（元）', '冲销原单编号', '用途', '标签', '交易对方'], fund_rows())))
            files.append(('货物台账.csv', csv_bytes(
                ['货物单编号', '创建时间', '业务日期', '实际入账时间', '完成业务日期', '当前状态', '来源账户编号', '来源账户名称',
                 '来源类型', '去向账户编号', '去向账户名称', '去向类型', 'SKU', '商品名称', '单位', '数量', '完成报告编号',
                 '采购参考号', '用途', '标签'], stock_rows())))
        scope = ('全部单据，包含待审批等未入账记录。' if mode == 'all' else
                 f'截至 {timestamp(cutoff)}，包含截止点的正式入账。' if mode == 'snapshot' else
                 f'实际入账时间 > {timestamp(start)} 且 <= {timestamp(cutoff)}。')
        note = '\n'.join([
            'FGAS 台账导出', f'生成时间：{timestamp(generated)}', scope,
            '时间为 Asia/Shanghai（UTC+08:00）。资金按 posted_at，货物按正式库存流水写入时间。',
            '现状(T) + (T,U] 已入账变化 = 现状(U)。创建时间和业务日期不用于这个组合。',
            '资金变化：来源减、去向加。原单及其冲销单均保留，已冲销原单也参与计算。',
            '货物每个单据的一个 SKU 一行；只有实际入账时间非空的记录影响库存。',
            '现状包含全部资金账户（含外部）及内部仓库；零余额、零库存和停用对象保留。',
            '名称、分类、启用状态、SKU 与单据状态为导出时当前资料；历史现状仅回溯金额和数量。',
            '新建目录对象可能以零余额/零库存出现在早于其创建时间的现状中。',
            '金额单位为元，余额=借方减贷方；私账为正表示应交回，为负表示社团应偿还。',
            'CSV 为 UTF-8 BOM；疑似表格公式的文本加单引号，避免打开时执行；标签用中文分号分隔。',
            '不包含附件、审批历史或结算匹配明细，不作为数据库恢复备份。',
            *[f'{name}：{count} 行（不含表头）' for name, (_, count) in files], '',
        ])
        output = BytesIO()
        with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
            for name, (data, _) in files:
                archive.writestr(name, data)
            archive.writestr('说明.txt', note.encode('utf-8-sig'))
        return output.getvalue(), f'fgas-{mode}-{generated.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")}.zip'
