import { useEffect, useState, type ChangeEvent, type FormEvent } from 'react'
import { Archive, Check, Download, FileUp, Gauge, ListFilter, Tags } from 'lucide-react'
import { money, monthLabel, type InsightProviderErrorCode } from './workflow'
import { householdService, type EvaluationReport, type HouseholdCategory, type HouseholdExpense, type HouseholdInsight, type HouseholdService, type ImportRun } from './services/household'

const tabs = [
    { id: 'import', label: 'Importar', icon: FileUp },
    { id: 'review', label: 'Despesas', icon: ListFilter },
    { id: 'categories', label: 'Categorias', icon: Tags },
    { id: 'data', label: 'Dados', icon: Archive },
    { id: 'evaluation', label: 'Avaliação', icon: Gauge },
] as const

type Tab = typeof tabs[number]['id']
const currentMonth = () => new Date().toISOString().slice(0, 7)
const providerErrorMessages: Record<InsightProviderErrorCode, string> = {
    authentication: 'Não foi possível autenticar no GitHub Copilot.',
    rate_limit: 'O GitHub Copilot atingiu um limite de uso ou de créditos.',
    timeout: 'O GitHub Copilot demorou além do tempo limite; resumo determinístico exibido.',
    invalid_response: 'A resposta do GitHub Copilot não passou na validação; resumo determinístico exibido.',
    safety_rejection: 'A resposta do GitHub Copilot foi rejeitada pelas verificações de segurança da aplicação.',
    provider_error: 'Ocorreu uma falha no GitHub Copilot; resumo determinístico exibido.',
}

function saveDownload(blob: Blob, filename: string) {
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    link.click()
    URL.revokeObjectURL(url)
}

export default function WorkspaceTools({ service = householdService, onDataDeleted, reviewRequest = 0 }: { service?: HouseholdService; onDataDeleted?: () => void; reviewRequest?: number }) {
    const [tab, setTab] = useState<Tab>('import')
    const [categories, setCategories] = useState<HouseholdCategory[]>([])
    const [expenses, setExpenses] = useState<HouseholdExpense[]>([])
    const [month, setMonth] = useState(currentMonth)
    const [reviewOnly, setReviewOnly] = useState(false)
    const [categoryFilter, setCategoryFilter] = useState('')
    const [confidenceFilter, setConfidenceFilter] = useState('')
    const [paymentFilter, setPaymentFilter] = useState('')
    const [sourceFilter, setSourceFilter] = useState('')
    const [offset, setOffset] = useState(0)
    const [totalCount, setTotalCount] = useState(0)
    const [pendingReviewCount, setPendingReviewCount] = useState(0)
    const [monthlyExpenseCount, setMonthlyExpenseCount] = useState(0)
    const [reviewStatusLoading, setReviewStatusLoading] = useState(false)
    const [selectedFile, setSelectedFile] = useState<File | null>(null)
    const [importRun, setImportRun] = useState<ImportRun | null>(null)
    const [evaluation, setEvaluation] = useState<EvaluationReport | null>(null)
    const [monthlyInsight, setMonthlyInsight] = useState<HouseholdInsight | null>(null)
    const [householdId, setHouseholdId] = useState('')
    const [categoryLabel, setCategoryLabel] = useState('')
    const [parentCategoryId, setParentCategoryId] = useState('')
    const [renameId, setRenameId] = useState('')
    const [renameLabel, setRenameLabel] = useState('')
    const [mergeSourceId, setMergeSourceId] = useState('')
    const [mergeTargetId, setMergeTargetId] = useState('')
    const [busy, setBusy] = useState(false)
    const [message, setMessage] = useState('')
    const [error, setError] = useState('')
    const activeLeaves = categories.filter(category => category.is_active && !categories.some(child => child.is_active && child.parent_category_id === category.id))
    const topLevelCategories = categories.filter(category => category.is_active && category.parent_category_id === null)
    const customLeaves = activeLeaves.filter(category => !category.is_standard)
    const categoryName = (id: string) => categories.find(category => category.id === id)?.label ?? id
    const selectedMergeSourceId = customLeaves.some(category => category.id === mergeSourceId) ? mergeSourceId : customLeaves[0]?.id ?? ''
    const selectedMergeTargetId = activeLeaves.some(category => category.id === mergeTargetId && category.id !== selectedMergeSourceId) ? mergeTargetId : activeLeaves.find(category => category.id !== selectedMergeSourceId)?.id ?? ''

    useEffect(() => {
        let active = true
        void Promise.all([service.listCategories(), service.getDemoHouseholdId()]).then(([loadedCategories, id]) => {
            if (!active) return
            setCategories(loadedCategories)
            setHouseholdId(id)
            const parent = loadedCategories.find(category => category.is_active && category.parent_category_id === null)
            if (parent) setParentCategoryId(parent.id)
            const custom = loadedCategories.find(category => category.is_active && !category.is_standard && category.parent_category_id !== null)
            if (custom) setRenameId(custom.id)
        }).catch(cause => { if (active) setError(cause instanceof Error ? cause.message : 'Não foi possível carregar o espaço.') })
        return () => { active = false }
    }, [service])

    useEffect(() => {
        if (reviewRequest === 0) return
        setTab('review')
        setReviewOnly(true)
        setCategoryFilter('')
        setConfidenceFilter('')
        setPaymentFilter('')
        setSourceFilter('')
        setOffset(0)
    }, [reviewRequest])

    async function refreshExpenses() {
        const [result, pending, monthly] = await Promise.all([
            service.listExpenses({
                month,
                categoryId: categoryFilter || undefined,
                confidenceMin: confidenceFilter ? Number(confidenceFilter) : undefined,
                paymentMethod: paymentFilter || undefined,
                source: sourceFilter || undefined,
                reviewRequired: reviewOnly ? true : undefined,
                offset,
            }),
            service.listExpenses({ month, reviewRequired: true, offset: 0 }),
            service.listExpenses({ month, offset: 0 }),
        ])
        setExpenses(result.expenses)
        setTotalCount(result.totalCount)
        setPendingReviewCount(pending.totalCount)
        setMonthlyExpenseCount(monthly.totalCount)
    }

    useEffect(() => {
        if (tab !== 'review') return
        let active = true
        setReviewStatusLoading(true)
        void Promise.all([
            service.listExpenses({
                month,
                categoryId: categoryFilter || undefined,
                confidenceMin: confidenceFilter ? Number(confidenceFilter) : undefined,
                paymentMethod: paymentFilter || undefined,
                source: sourceFilter || undefined,
                reviewRequired: reviewOnly ? true : undefined,
                offset,
            }),
            service.listExpenses({ month, reviewRequired: true, offset: 0 }),
            service.listExpenses({ month, offset: 0 }),
        ]).then(([result, pending, monthly]) => {
            if (active) {
                setExpenses(result.expenses)
                setTotalCount(result.totalCount)
                setPendingReviewCount(pending.totalCount)
                setMonthlyExpenseCount(monthly.totalCount)
            }
        }).catch(cause => { if (active) setError(cause instanceof Error ? cause.message : 'Não foi possível listar as despesas.') })
            .finally(() => { if (active) setReviewStatusLoading(false) })
        return () => { active = false }
    }, [categoryFilter, confidenceFilter, month, offset, paymentFilter, reviewOnly, service, sourceFilter, tab])

    async function perform(action: () => Promise<void>, success: string) {
        setBusy(true)
        setError('')
        setMessage('')
        try {
            await action()
            setMessage(success)
        } catch (cause) {
            setError(cause instanceof Error ? cause.message : 'Não foi possível concluir a operação.')
        } finally {
            setBusy(false)
        }
    }

    function chooseFile(event: ChangeEvent<HTMLInputElement>) {
        setSelectedFile(event.currentTarget.files?.[0] ?? null)
        setImportRun(null)
        setMessage('')
    }

    function importFile(event: FormEvent<HTMLFormElement>) {
        event.preventDefault()
        if (!selectedFile) return
        void perform(async () => {
            const result = await service.importCsv(selectedFile)
            setImportRun(result)
            await refreshExpenses()
        }, 'Importação concluída.')
    }

    function createCategory(event: FormEvent<HTMLFormElement>) {
        event.preventDefault()
        void perform(async () => {
            const category = await service.createCategory(categoryLabel.trim(), parentCategoryId)
            setCategories(await service.listCategories())
            setCategoryLabel('')
            setRenameId(category.id)
        }, 'Categoria criada.')
    }

    function renameCategory(event: FormEvent<HTMLFormElement>) {
        event.preventDefault()
        void perform(async () => {
            await service.renameCategory(renameId, renameLabel.trim())
            setCategories(await service.listCategories())
            setRenameLabel('')
        }, 'Categoria atualizada.')
    }

    function mergeCategories(event: FormEvent<HTMLFormElement>) {
        event.preventDefault()
        void perform(async () => {
            await service.mergeCategories(selectedMergeSourceId, selectedMergeTargetId)
            setCategories(await service.listCategories())
            await refreshExpenses()
        }, 'Categorias mescladas e despesas reatribuídas.')
    }

    function downloadCsv() {
        void perform(async () => saveDownload(await service.exportCsv(), 'home-financial-expenses.csv'), 'Arquivo CSV gerado.')
    }

    function downloadArchive() {
        void perform(async () => saveDownload(await service.exportArchive(), 'home-financial-archive.json'), 'Arquivo JSON gerado.')
    }

    function deleteData() {
        if (!window.confirm('Apagar todas as despesas e os dados derivados desta casa demonstrativa? Esta ação não pode ser desfeita.')) return
        void perform(async () => {
            await service.deleteDemoData(householdId)
            setExpenses([])
            setImportRun(null)
            setEvaluation(null)
            setCategories(await service.listCategories())
            onDataDeleted?.()
        }, 'Dados da casa demonstrativa apagados.')
    }

    function runEvaluation() {
        void perform(async () => setEvaluation(await service.evaluate()), 'Avaliação concluída.')
    }

    async function correctExpense(expense: HouseholdExpense, categoryId: string) {
        if (categoryId === expense.category_id) return
        await perform(async () => {
            setMonthlyInsight(null)
            await service.correctCategory(expense.id, categoryId)
            await refreshExpenses()
        }, 'Categoria da despesa corrigida.')
    }

    function generateInsights() {
        void perform(async () => {
            setMonthlyInsight(await service.generateInsights(month))
        }, 'Insights do mês gerados.')
    }

    return <section className="workspace-tools" aria-labelledby="tools-title">
        <div className="section-heading"><span className="section-number">04</span><h2 id="tools-title">Gestão da casa</h2><span className="muted-label">Operações locais</span></div>
        <div className="tool-tabs" role="tablist" aria-label="Operações da casa">
            {tabs.map(({ id, label, icon: Icon }) => <button type="button" role="tab" key={id} id={`tab-${id}`} aria-selected={tab === id} aria-controls={tab === id ? `panel-${id}` : undefined} onClick={() => { setTab(id); setError(''); setMessage('') }}><Icon size={16} />{label}</button>)}
        </div>
        <div className="tool-panel" role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
            {tab === 'import' && <div className="tool-content">
                <h3>Importar despesas CSV</h3>
                <form className="tool-form import-form" onSubmit={importFile}>
                    <label className="file-field">Arquivo CSV<input type="file" accept=".csv,text/csv" onChange={chooseFile} /></label>
                    <button className="action-button" type="submit" disabled={!selectedFile || busy}><FileUp size={16} />Importar arquivo</button>
                </form>
                {importRun && <div className="import-report" role="status"><strong>{importRun.imported_rows} importadas</strong><span>{importRun.rejected_rows} rejeitadas de {importRun.total_rows} linhas</span>{importRun.row_errors.length > 0 && <ul>{importRun.row_errors.map((rowError, index) => <li key={`${rowError.row}-${rowError.field}-${index}`}>Linha {rowError.row}, {rowError.field}: {rowError.message}{rowError.value ? ` (${rowError.value})` : ''}</li>)}</ul>}</div>}
            </div>}
            {tab === 'review' && <div className="tool-content">
                <h3>Revisar despesas</h3>
                <div className="review-filters">
                    <label>Mês<input type="month" value={month} onChange={event => { setMonth(event.target.value); setOffset(0); setMonthlyInsight(null) }} /></label>
                    <label>Categoria<select value={categoryFilter} onChange={event => { setCategoryFilter(event.target.value); setOffset(0) }}><option value="">Todas</option>{activeLeaves.map(category => <option key={category.id} value={category.id}>{category.label}</option>)}</select></label>
                    <label>Confiança mínima<select value={confidenceFilter} onChange={event => { setConfidenceFilter(event.target.value); setOffset(0) }}><option value="">Todas</option><option value="0.5">50%</option><option value="0.7">70%</option><option value="0.9">90%</option></select></label>
                    <label>Pagamento<select value={paymentFilter} onChange={event => { setPaymentFilter(event.target.value); setOffset(0) }}><option value="">Todos</option><option value="dinheiro">Dinheiro</option><option value="debito">Débito</option><option value="credito">Crédito</option></select></label>
                    <label>Origem<select value={sourceFilter} onChange={event => { setSourceFilter(event.target.value); setOffset(0) }}><option value="">Todas</option><option value="manual">Manual</option><option value="csv">CSV</option></select></label>
                    <label className="check-filter"><input type="checkbox" checked={reviewOnly} onChange={event => { setReviewOnly(event.target.checked); setOffset(0) }} />Pendentes de revisão</label>
                </div>
                {expenses.length === 0 ? <p className="tool-empty">Nenhuma despesa encontrada para {monthLabel(month)}.</p> : <div className="expense-table-wrap"><table className="expense-table"><thead><tr><th>Data e descrição</th><th>Valor</th><th>Categoria</th><th>Origem</th></tr></thead><tbody>{expenses.map(expense => <tr key={expense.id}><td><strong>{expense.description}</strong><span>{new Intl.DateTimeFormat('pt-BR', { timeZone: 'UTC' }).format(new Date(`${expense.date}T12:00:00Z`))}{expense.review_required ? ' · Revisar' : ''}{expense.user_override ? ' · Corrigida' : ''}</span></td><td>{money(expense.amount_cents)}</td><td><select aria-label={`Categoria de ${expense.description}`} value={expense.category_id} disabled={busy} onChange={event => void correctExpense(expense, event.target.value)}>{activeLeaves.map(category => <option key={category.id} value={category.id}>{category.label}</option>)}</select></td><td>{expense.source}</td></tr>)}</tbody></table></div>}
                <div className="expense-pagination"><span>{totalCount === 0 ? '0 despesas' : `${offset + 1}–${Math.min(offset + expenses.length, totalCount)} de ${totalCount}`}</span><button type="button" className="action-button" disabled={busy || offset === 0} onClick={() => setOffset(Math.max(0, offset - 100))}>Anterior</button><button type="button" className="action-button" disabled={busy || offset + expenses.length >= totalCount} onClick={() => setOffset(offset + 100)}>Próxima</button></div>
                <div className="review-insight-action">
                    <button type="button" className="action-button" disabled={busy || reviewStatusLoading || pendingReviewCount > 0 || monthlyExpenseCount === 0} onClick={generateInsights}><Gauge size={16} />Gerar insights do mês</button>
                    {pendingReviewCount > 0 && <p role="status">Revise {pendingReviewCount} {pendingReviewCount === 1 ? 'despesa pendente' : 'despesas pendentes'} antes de gerar insights.</p>}
                </div>
                {monthlyInsight && <div className="review-insight" role="status"><h4>{monthlyInsight.title}</h4><p>{monthlyInsight.text}</p>{monthlyInsight.sources.length > 0 && <span>Baseado em {monthlyInsight.sources.length} {monthlyInsight.sources.length === 1 ? 'despesa' : 'despesas'}.</span>}{monthlyInsight.providerErrorCode && <p>{providerErrorMessages[monthlyInsight.providerErrorCode]}</p>}</div>}
            </div>}
            {tab === 'categories' && <div className="tool-content category-tools">
                <h3>Taxonomia</h3>
                <form className="tool-form" onSubmit={createCategory}><label>Nova categoria<input value={categoryLabel} onChange={event => setCategoryLabel(event.target.value)} maxLength={80} required /></label><label>Grupo<select value={parentCategoryId} onChange={event => setParentCategoryId(event.target.value)}>{topLevelCategories.map(category => <option key={category.id} value={category.id}>{category.label}</option>)}</select></label><button className="action-button" type="submit" disabled={busy}><Tags size={16} />Criar folha</button></form>
                <form className="tool-form" onSubmit={renameCategory}><label>Categoria própria<select value={renameId} onChange={event => setRenameId(event.target.value)}>{customLeaves.map(category => <option key={category.id} value={category.id}>{category.label}</option>)}</select></label><label>Novo nome<input value={renameLabel} onChange={event => setRenameLabel(event.target.value)} maxLength={80} required /></label><button className="action-button" type="submit" disabled={busy || customLeaves.length === 0}><Check size={16} />Renomear</button></form>
                <form className="tool-form" onSubmit={mergeCategories}><label>Mesclar categoria<select value={selectedMergeSourceId} onChange={event => setMergeSourceId(event.target.value)}>{customLeaves.map(category => <option key={category.id} value={category.id}>{category.label}</option>)}</select></label><label>Destino ativo<select value={selectedMergeTargetId} onChange={event => setMergeTargetId(event.target.value)}>{activeLeaves.filter(category => category.id !== selectedMergeSourceId).map(category => <option key={category.id} value={category.id}>{category.label}</option>)}</select></label><button className="action-button" type="submit" disabled={busy || customLeaves.length === 0 || !selectedMergeTargetId}><Tags size={16} />Mesclar</button></form>
            </div>}
            {tab === 'data' && <div className="tool-content data-tools"><h3>Portabilidade e exclusão</h3><button className="action-button" type="button" onClick={downloadCsv} disabled={busy}><Download size={16} />Baixar despesas CSV</button><button className="action-button" type="button" onClick={downloadArchive} disabled={busy}><Archive size={16} />Baixar arquivo JSON</button><button className="action-button danger-button" type="button" onClick={deleteData} disabled={busy || !householdId}>Apagar dados da demonstração</button></div>}
            {tab === 'evaluation' && <div className="tool-content"><h3>Avaliação de categorias</h3><button className="action-button" type="button" onClick={runEvaluation} disabled={busy}><Gauge size={16} />Executar avaliação</button>{evaluation && <div className="evaluation-report" role="status"><strong>{evaluation.passed ? 'Aprovada' : 'Abaixo da meta'} · {Math.round(evaluation.accuracy * 100)}%</strong><span>{evaluation.correct_count} acertos de {evaluation.total_count} registros</span><span>{evaluation.confusion_details.length} combinações na matriz de confusão</span>{evaluation.confusion_details.length > 0 && <ul>{evaluation.confusion_details.map((entry, index) => <li key={`${entry.expected_category_id}-${entry.predicted_category_id}-${index}`}>{categoryName(entry.expected_category_id)} → {categoryName(entry.predicted_category_id)}: {entry.count}</li>)}</ul>}</div>}</div>}
        </div>
        {error && <p className="tool-message tool-error" role="alert">{error}</p>}
        {message && <p className="tool-message" role="status">{message}</p>}
    </section>
}