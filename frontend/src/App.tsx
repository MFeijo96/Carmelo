import { useEffect, useReducer, useRef, useState, type FormEvent } from 'react'
import { ArrowRight, Check, ChevronRight, CircleAlert, Clock3, House, ListFilter, LoaderCircle, Play, ReceiptText, RefreshCw, RotateCcw, ShieldCheck } from 'lucide-react'
import { startRun, getRunStatus, getCategories, getHistory } from './services/runs'
import { categoryOptions as defaultCategoryOptions, initialState, money, monthLabel, payments, parseAmount, validateInput, workflowReducer, type CategoryOption, type ExpenseInput, type InsightProviderErrorCode, type RunResult, type RunService } from './workflow'
import WorkspaceTools from './WorkspaceTools'

const defaultService: RunService = { startRun, getRunStatus, getCategories, getHistory }
const paymentLabels = { ...payments, debito: 'Débito', credito: 'Crédito' }
const statusPresentation = {
    idle: { label: 'Execução: ociosa', color: '#606870' },
    running: { label: 'Execução: em andamento', color: '#1755a6' },
    done: { label: 'Execução: concluída', color: '#14614d' },
    error: { label: 'Execução: erro', color: '#b42318' },
} as const
const insightProviderPresentation = {
    used: 'Insights gerados com IA.',
    unavailable: 'Provedor indisponível; resumo determinístico exibido.',
    failed: 'Falha no provedor; resumo determinístico exibido.',
    not_configured: 'IA não configurada; resumo determinístico exibido.',
} as const
const insightProviderErrorPresentation: Record<InsightProviderErrorCode, string> = {
    authentication: 'Não foi possível autenticar no GitHub Copilot.',
    rate_limit: 'O GitHub Copilot atingiu um limite de uso ou de créditos.',
    timeout: 'O GitHub Copilot demorou além do tempo limite; resumo determinístico exibido.',
    invalid_response: 'A resposta do GitHub Copilot não passou na validação; resumo determinístico exibido.',
    safety_rejection: 'A resposta do GitHub Copilot foi rejeitada pelas verificações de segurança da aplicação.',
    provider_error: 'Ocorreu uma falha no GitHub Copilot; resumo determinístico exibido.',
}
const localDate = () => {
    const date = new Date()
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

function Results({ result, categoryLabel, onReview }: { result: RunResult; categoryLabel: (id: string) => string; onReview: () => void }) {
    return <>
        <div className="result-heading"><div><span className="eyebrow">Resumo do mês</span><h3>{monthLabel(result.month)}</h3></div><span className="tag"><Check size={13} /> {statusPresentation.done.label}</span></div>
        <div className="metrics">
            <div className="metric primary"><span>Total registrado</span><strong>{money(result.totalCents)}</strong></div>
            <div className="metric"><span>Despesas</span><strong>{result.count.toString().padStart(2, '0')}</strong></div>
            <div className="metric"><span>Recorrentes</span><strong>{money(result.recurringCents)}</strong></div>
        </div>
        <div className="breakdowns">
            <div><h4>Por categoria</h4>{result.categories.map(item => <div className="category-row" key={item.name}>
                <div className="flex justify-between gap-3"><span>{item.label || categoryLabel(item.name)}</span><strong>{money(item.cents)}</strong></div>
                <div className="bar-track"><div style={{ width: `${item.cents / result.totalCents * 100}%` }} /></div>
            </div>)}</div>
            <div><h4>Por pagamento</h4>{result.payments.map(item => <div className="payment-row" key={item.name}><span>{paymentLabels[item.name]}</span><strong>{money(item.cents)}</strong></div>)}</div>
        </div>
        <div className="record"><ReceiptText size={19} /><div><span className="eyebrow">Despesa registrada</span><strong>{result.input.description}</strong><span>{categoryLabel(result.input.category)} · {paymentLabels[result.input.payment]}{result.input.recurring ? ' · Recorrente' : ''}</span></div><strong>{money(result.input.amountCents)}</strong></div>
        <p className="insight">{result.insight?.text ?? `${result.count} ${result.count === 1 ? 'despesa registrada' : 'despesas registradas'} em ${monthLabel(result.month)}, totalizando ${money(result.totalCents)}.`}</p>
        {result.insightProviderErrorCode
            ? <p className="insight-sources" role="status">{insightProviderErrorPresentation[result.insightProviderErrorCode]}</p>
            : result.insightProviderStatus && <p className="insight-sources" role="status">{insightProviderPresentation[result.insightProviderStatus]}</p>}
        {result.insight?.sources.length ? <p className="insight-sources">Baseado em {result.insight.sources.length === 1 ? '1 despesa' : `${result.insight.sources.length} despesas`}, incluindo {result.insight.sources[0].categoryLabel}.</p> : null}
        {(result.pendingReviewCount ?? 0) > 0 && <div className="review-prompt" role="status"><p>{result.pendingReviewCount} {result.pendingReviewCount === 1 ? 'despesa precisa' : 'despesas precisam'} de revisão antes dos insights do mês.</p><button className="action-button" type="button" onClick={onReview}><ListFilter size={16} />Revisar despesas</button></div>}
        {result.pendingReviewCount === null && <div className="review-prompt" role="status"><p>Não foi possível confirmar as pendências. Os insights foram adiados.</p><button className="action-button" type="button" onClick={onReview}><ListFilter size={16} />Conferir despesas</button></div>}
        <p className="result-note">Totais calculados pelo backend local. Use dados fictícios; não constitui aconselhamento financeiro.</p>
    </>
}

export default function App({ service = defaultService }: { service?: RunService }) {
    const [state, dispatch] = useReducer(workflowReducer, initialState)
    const [categoryOptions, setCategoryOptions] = useState<CategoryOption[]>([...defaultCategoryOptions])
    const [formError, setFormError] = useState<string | null>(null)
    const [selectedId, setSelectedId] = useState<string | null>(null)
    const [lastUpdated, setLastUpdated] = useState(() => new Date())
    const [reviewRequest, setReviewRequest] = useState(0)
    const [historyLoading, setHistoryLoading] = useState(Boolean(service.getHistory))
    const [historyError, setHistoryError] = useState<string | null>(null)
    const [historyAttempt, setHistoryAttempt] = useState(0)
    const historyGeneration = useRef(0)
    const restoreSelection = useRef(true)
    const formRef = useRef<HTMLFormElement>(null)
    const resultHeadingRef = useRef<HTMLHeadingElement>(null)
    const lastInput = useRef<ExpenseInput | null>(null)
    const lastRequestId = useRef<string | null>(null)
    const locked = useRef(false)
    const running = state.phase === 'running'
    const selected = state.history.find(result => result.requestId === selectedId)
    const error = formError ?? state.error
    const displayStatus = error ? 'error' : state.phase
    const presentation = statusPresentation[displayStatus]
    const categoryLabel = (id: string) => categoryOptions.find(category => category.id === id)?.label ?? id

    useEffect(() => {
        if (!service.getCategories) return
        let active = true
        void service.getCategories().then(options => {
            if (active && options.length > 0) setCategoryOptions(options)
        }).catch(() => { })
        return () => { active = false }
    }, [service])

    useEffect(() => {
        if (!service.getHistory) return
        let active = true
        const generation = ++historyGeneration.current
        setHistoryLoading(true)
        setHistoryError(null)
        void service.getHistory().then(results => {
            if (!active || generation !== historyGeneration.current) return
            dispatch({ type: 'restored', results })
            if (restoreSelection.current && !lastRequestId.current && !locked.current) {
                setSelectedId(current => current ?? results[0]?.runId ?? null)
            }
        }).catch(() => {
            if (active && generation === historyGeneration.current) setHistoryError('Não foi possível carregar as despesas salvas.')
        }).finally(() => {
            if (active && generation === historyGeneration.current) setHistoryLoading(false)
        })
        return () => { active = false }
    }, [service, historyAttempt])

    useEffect(() => {
        if (state.phase !== 'running' || !state.runId || !lastInput.current) return
        const requestId = state.runId
        const input = { ...lastInput.current }
        let stopped = false
        let timer: ReturnType<typeof setTimeout> | undefined
        const fail = (cause: unknown) => {
            if (stopped) return
            setLastUpdated(new Date())
            locked.current = false
            dispatch({ type: 'failed', runId: requestId, message: cause instanceof Error ? cause.message : 'Não foi possível concluir. Tente novamente.' })
        }
        async function poll(runId: string) {
            try {
                const status = await service.getRunStatus(runId)
                if (stopped) return
                setLastUpdated(new Date())
                if (status.status === 'done') {
                    locked.current = false
                    dispatch({ type: 'completed', runId: requestId, result: status.result, input })
                    setSelectedId(requestId)
                    for (const field of ['description', 'amount']) (formRef.current?.elements.namedItem(field) as HTMLInputElement).value = ''
                } else {
                    timer = setTimeout(() => { void poll(runId) }, 400)
                }
            } catch (cause) { fail(cause) }
        }
        void service.startRun(input, requestId).then(({ runId }) => {
            if (stopped) return
            setLastUpdated(new Date())
            void poll(runId)
        }).catch(fail)
        return () => { stopped = true; clearTimeout(timer); locked.current = false }
    }, [state.phase, state.runId, service])

    useEffect(() => {
        if (selectedId) resultHeadingRef.current?.focus({ preventScroll: true })
    }, [selectedId])

    function run(input: ExpenseInput, requestId: string = crypto.randomUUID()) {
        if (locked.current) return
        restoreSelection.current = false
        locked.current = true
        lastInput.current = { ...input }
        lastRequestId.current = requestId
        setFormError(null)
        setSelectedId(null)
        setLastUpdated(new Date())
        dispatch({ type: 'started', runId: requestId })
    }

    function submit(event: FormEvent<HTMLFormElement>) {
        event.preventDefault()
        if (locked.current) return
        const data = new FormData(event.currentTarget)
        try {
            run(validateInput({
                date: String(data.get('date')), description: String(data.get('description')),
                amountCents: parseAmount(String(data.get('amount'))),
                category: String(data.get('category')),
                payment: String(data.get('payment')) as RunResult['input']['payment'],
                recurring: data.get('recurring') === 'on',
            }, categoryOptions.map(category => category.id)))
        } catch (cause) {
            setLastUpdated(new Date())
            setFormError(cause instanceof Error ? cause.message : 'Confira os campos.'); return
        }
    }

    function retry() {
        const input = lastInput.current
        const form = formRef.current
        if (!input || !form || locked.current) return
        for (const field of ['date', 'description', 'category', 'payment'] as const) {
            (form.elements.namedItem(field) as HTMLInputElement | HTMLSelectElement).value = input[field]
        }
        (form.elements.namedItem('amount') as HTMLInputElement).value = `${Math.floor(input.amountCents / 100)},${String(input.amountCents % 100).padStart(2, '0')}`
            ; (form.elements.namedItem('recurring') as HTMLInputElement).checked = input.recurring
        run(input, lastRequestId.current ?? crypto.randomUUID())
    }

    function reset() {
        if (locked.current) return
        restoreSelection.current = false
        formRef.current?.reset()
        lastInput.current = null
        lastRequestId.current = null
        setFormError(null)
        setSelectedId(null)
        setLastUpdated(new Date())
        dispatch({ type: 'reset' })
            ; (formRef.current?.elements.namedItem('description') as HTMLInputElement)?.focus()
    }

    return <div className="app-shell">
        <a className="skip-link" href="#main">Ir para o conteúdo</a>
        <header className="app-header"><div className="brand"><span className="brand-mark"><House size={23} strokeWidth={1.7} /></span><span>Home Financial</span></div><span className="workspace"><span className="status-dot" /> Casa demonstrativa</span></header>
        <main id="main">
            <div className="crew-status" role="status" aria-live="polite" data-state={displayStatus}>
                <span className="crew-state" style={{ color: presentation.color }}><span className="crew-indicator" aria-hidden="true" />{presentation.label}</span>
                <span className="last-updated">Atualizado em <time dateTime={lastUpdated.toISOString()} title={lastUpdated.toLocaleString('pt-BR')}>{new Intl.DateTimeFormat('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' }).format(lastUpdated)}</time></span>
            </div>
            <div className="page-title"><div><p className="eyebrow">Minha casa / Despesas</p><h1>Despesas da casa</h1></div><span className="local-badge"><ShieldCheck size={16} /> Ambiente local</span></div>
            <div className="demo-notice"><CircleAlert size={17} /><p>Modo demonstração. Use apenas dados fictícios. Os registros ficam no backend local enquanto ele estiver em execução.</p></div>
            <div className="workbench">
                <section className="input-section" aria-labelledby="inputs-title">
                    <div className="section-heading"><span className="section-number">01</span><h2 id="inputs-title">Nova despesa</h2></div>
                    <form ref={formRef} onSubmit={submit} aria-describedby={error ? 'form-error' : undefined}>
                        <fieldset disabled={running}>
                            <div className="field"><label htmlFor="date">Data</label><input id="date" name="date" type="date" defaultValue={localDate()} required /></div>
                            <div className="field"><label htmlFor="description">Descrição</label><input id="description" name="description" placeholder="Ex.: compras do mercado" maxLength={120} required /></div>
                            <div className="field"><label htmlFor="amount">Valor</label><div className="amount-input"><span>R$</span><input id="amount" name="amount" inputMode="decimal" placeholder="0,00" aria-describedby={error ? 'form-error' : undefined} required /></div></div>
                            <div className="field"><label htmlFor="category">Categoria</label><select id="category" name="category" defaultValue="category-mercado"><option value="">Automatica</option>{categoryOptions.map(category => <option key={category.id} value={category.id}>{category.label}</option>)}</select></div>
                            <div className="field"><label htmlFor="payment">Forma de pagamento</label><select id="payment" name="payment" defaultValue="debito">{Object.keys(payments).map(payment => <option key={payment} value={payment}>{paymentLabels[payment as keyof typeof payments]}</option>)}</select></div>
                            <label className="recurring"><input name="recurring" type="checkbox" /><span>Despesa recorrente</span></label>
                        </fieldset>
                        {error && <p id="form-error" className="error" role="alert">{statusPresentation.error.label}: {error}</p>}
                        <div className="run-controls">
                            {state.error && lastInput.current ? <button className="submit-button" type="button" onClick={retry}><RefreshCw size={18} />Tentar novamente<ArrowRight size={17} className="ml-auto" /></button> : <button className="submit-button" type="submit" disabled={running}>{running ? <LoaderCircle className="spin" size={18} /> : <Play size={18} />}{running ? statusPresentation.running.label : 'Executar'}<ArrowRight size={17} className="ml-auto" /></button>}
                            <button className="reset-button" type="button" onClick={reset} disabled={running} aria-label="Redefinir" title="Redefinir"><RotateCcw size={18} /></button>
                        </div>
                    </form>
                </section>
                <section className="results-section" aria-labelledby="results-title">
                    <div className="section-heading"><span className="section-number">02</span><h2 id="results-title" ref={resultHeadingRef} tabIndex={-1}>Resultados</h2><span className="muted-label">Backend local</span></div>
                    {selected ? <Results result={selected} categoryLabel={categoryLabel} onReview={() => setReviewRequest(value => value + 1)} /> : <div className="empty-result"><span className={`empty-icon ${running ? 'is-running' : ''}`}>{running ? <LoaderCircle className="spin" size={32} /> : <ReceiptText size={34} strokeWidth={1.3} />}</span><h3>{running ? statusPresentation.running.label : 'Nenhum resultado por aqui'}</h3><p>{running ? 'Aguardando o resultado da execução.' : 'Nenhuma despesa registrada nesta sessão.'}</p><div className="empty-ledger" aria-hidden="true"><span /><span /><span /></div></div>}
                </section>
            </div>
            {service === defaultService && <WorkspaceTools reviewRequest={reviewRequest} onDataDeleted={() => {
                historyGeneration.current += 1
                setHistoryLoading(false)
                setHistoryError(null)
                lastInput.current = null
                lastRequestId.current = null
                setSelectedId(null)
                dispatch({ type: 'cleared' })
            }} />}
            <section className="history-section" aria-labelledby="history-title">
                <div className="section-heading"><span className="section-number">03</span><h2 id="history-title">Histórico</h2><span className="muted-label">{state.history.length} {state.history.length === 1 ? 'execução' : 'execuções'}</span></div>
                {historyError && <div className="error" role="alert"><p>{historyError}</p><button className="action-button" type="button" disabled={running} onClick={() => setHistoryAttempt(value => value + 1)}><RefreshCw size={16} />Tentar carregar novamente</button></div>}
                {state.history.length === 0 ? <div className="history-empty"><Clock3 size={18} /><span>{historyLoading ? 'Carregando despesas salvas...' : historyError ? 'Histórico indisponível.' : 'Nenhuma despesa registrada.'}</span></div> : <ul className="history-list">{state.history.map(result => <li key={result.requestId}><button type="button" className={`history-row ${selectedId === result.requestId ? 'selected' : ''}`} disabled={running} aria-label={`Ver resultado: ${result.submittedInput.description}`} aria-pressed={selectedId === result.requestId} onClick={() => setSelectedId(result.requestId)}><span className="history-icon"><ReceiptText size={18} /></span><span className="history-description"><strong>{result.submittedInput.description}</strong><span>{monthLabel(result.submittedInput.date.slice(0, 7))}</span></span><span className="history-amount">{money(result.submittedInput.amountCents)}</span><span className="history-status"><Check size={13} /> {statusPresentation.done.label}</span><ChevronRight size={17} /></button></li>)}</ul>}
            </section>
            <footer><span>Home Financial</span><span>Dados fictícios · Sem conexão bancária</span></footer>
        </main>
    </div>
}